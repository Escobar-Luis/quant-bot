"""Write results/<course>/<version>.json (contracts.md) from the collectors' events and cached bars.

  cd app && uv run python -m backtest.run --course lpp --version v1
  cd app && uv run python -m backtest.run --course lpp --version v1 --limit 40   # first 40 positions only (partial)

Code only: no model call, nothing to trace. Prints counts, never key values.
"""
import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path

from . import bars, engine, extras
from .common import (COSTS_BPS, DATA, DEFAULT_DELAY_MIN, DELAYS_MIN, MONEY_START, RESULTS, git_sha)

LABELS = {"all": "Everything he traded", "day": "Day trades", "swing": "Swing trades", "crypto": "Crypto setups",
          "options": "Options"}
SAMPLE_TRADES = 200


def course_module(course: str):
    if course == "lpp":
        from . import lpp
        return lpp
    if course == "cryptowizard":
        from . import cryptowizard
        return cryptowizard
    if course == "ziptrader":
        from . import ziptrader
        return ziptrader
    raise SystemExit(f"unknown course {course}")


def hold_numbers(market: str, symbol: str, window: dict) -> tuple[dict, list[str], list[float]]:
    """$10k bought at the open of the window's first trading minute, held to its last close; plus its daily series."""
    start, end = dt.date.fromisoformat(window["start"]), dt.date.fromisoformat(window["end"])
    closes = bars.daily_closes(market, symbol, start, end)
    dates = list(closes)

    def first_open(day: str) -> float:
        b = bars.day_bars(market, symbol, dt.date.fromisoformat(day))
        return b[min(b)][0]

    px0 = first_open(dates[0])
    sealed_px0 = first_open(next(d for d in dates if d >= window["sealed_from"]))
    last = closes[dates[-1]]
    series = [round(MONEY_START * c / px0, 2) for c in closes.values()]
    hold = {"end": series[-1], "ret_pct": round((last / px0 - 1) * 100, 2),
            "sealed_ret_pct": round((last / sealed_px0 - 1) * 100, 2)}
    return hold, dates, series


def prefetch(positions, workers: int = 6):
    """Fetch every stock session a position can touch (first leg to last leg + 7 days), in parallel."""
    from concurrent.futures import ThreadPoolExecutor
    need = set()
    for p in positions:
        if p.market != "us_equities":
            continue
        t0, t1 = min(lg.posted_ts for lg in p.legs), max(lg.posted_ts for lg in p.legs)
        day, last = bars.et_date(t0), bars.et_date(t1) + dt.timedelta(days=9 if p.portfolio == "swing" else 2)
        while day <= last:
            if day.weekday() < 5:
                need.add((p.ticker, day))
            day += dt.timedelta(days=1)
    todo = [k for k in need if not (bars.BARS / "alpaca_1m" / k[0] / f"{k[1].isoformat()}.json").exists()]
    print(f"  prefetch: {len(need)} ticker-sessions, {len(todo)} to download")

    def get(k):
        try:
            bars.stock_day(*k)
        except bars.NoBars as e:
            return str(e)

    with ThreadPoolExecutor(workers) as ex:
        errs = [e for e in ex.map(get, todo) if e]
    if errs:
        print(f"  prefetch errors: {len(errs)}, e.g. {errs[0]}")


def trade_row(results: dict[int, engine.Result]) -> dict:
    p = next(iter(results.values())).position
    first = min(p.legs, key=lambda lg: lg.posted_ts)
    row = {"trade_id": p.pid, "portfolio": p.portfolio, "ticker": p.ticker, "side": p.side,
           "posted_at": bars.to_iso(first.posted_ts), "quote": p.quote, "cite": p.cite, "by_delay": {}}
    for d, r in results.items():
        if r.status != "priced":
            row["by_delay"][str(d)] = {"status": r.status}
            continue
        row["by_delay"][str(d)] = {
            "entry_at": bars.to_iso(r.entry.ts), "entry": round(r.entry.px, 4),
            "exit_at": bars.to_iso(r.last_exit.ts), "exit": round(r.last_exit.px, 4),
            "ret_pct": round(r.ret_pct, 2), "pnl": round(r.pnl, 2), "legs": len(r.fills),
            "exit_kind": r.last_exit.kind, "assumed_exit": r.assumed_exit}
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--version", default="v1")
    ap.add_argument("--limit", type=int, default=None, help="price only the first N positions (partial file)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--all-sessions", action="store_true",
                    help="lpp v2+: every session extracted so far (default: the 30-session proof set)")
    ap.add_argument("--literal", action="store_true",
                    help="copy his raw share counts (default: scaled so each trade starts at $1,000)")
    a = ap.parse_args()
    a.scale = not a.literal

    mod = course_module(a.course)
    only = mod.proof_set() if a.course == "lpp" and a.version != "v1" and not a.all_sessions else None
    built = mod.build(a.version, only) if only else mod.build(a.version)
    positions = built["positions"][: a.limit] if a.limit else built["positions"]
    print(f"{a.course} {a.version}: {len(built['positions'])} positions, pricing {len(positions)}")
    seen = Counter()
    for p in built["positions"]:   # a post with two setups must not collapse into one id
        seen[p.pid] += 1
        if seen[p.pid] > 1:
            p.pid = f"{p.pid}-{seen[p.pid]}"

    for p in positions:
        p.scale = a.scale
    prefetch(positions)
    hold, dates, hold_series = hold_numbers(mod.MARKET, getattr(mod, "HOLD_BARS", mod.HOLD["symbol"]), mod.WINDOW)
    by_pos: dict[str, dict[int, engine.Result]] = {}
    for i, p in enumerate(positions):
        by_pos[p.pid] = {d: engine.simulate(p, d) for d in DELAYS_MIN}
        if (i + 1) % 25 == 0:
            print(f"  priced {i + 1}/{len(positions)}")
    status = Counter(r.status for rs in by_pos.values() for r in rs.values())
    print("  results by status (all delays):", dict(status))
    for why, n in Counter(r.why for rs in by_pos.values() for r in rs.values() if r.why).most_common(5):
        print(f"  skipped {n}x: {why}")

    kinds = ["day", "swing"] if mod.MARKET == "us_equities" else ["crypto"]
    portfolios = []
    for pid in ["all"] + kinds:
        rows, series = {}, {}
        for d in DELAYS_MIN:
            rs = [by_pos[p.pid][d] for p in positions if pid == "all" or p.portfolio == pid]
            rows[str(d)], series[str(d)] = engine.portfolio_stats(rs, dates, hold, mod.WINDOW["sealed_from"])
        portfolios.append({"id": pid, "label": LABELS[pid], "testable": True, "by_delay": rows,
                           "series": {"dates": dates, "hold": hold_series, "by_delay": series}})
    if built["options_count"] or mod.MARKET == "us_equities":
        portfolios.append({"id": "options", "label": LABELS["options"], "testable": False,
                           "count": built["options_count"], "why": "No free options price history"})

    d5 = DEFAULT_DELAY_MIN
    same = None
    if a.course == "lpp" and a.version != "v1" and not a.limit:   # the fix vs the failure in money: v1 priced on this version's sessions
        srcs = only or {e["source_id"] for e in mod.load(a.version)}
        base = mod.build("v1", srcs)["positions"]   # v1's events from exactly these sessions, same ledger rules
        for p in base:
            p.scale = a.scale
        prefetch(base)
        rows = {}
        for d in DELAYS_MIN:
            rs = [engine.simulate(p, d) for p in base]
            rows[str(d)] = engine.portfolio_stats(rs, dates, hold, mod.WINDOW["sealed_from"])[0]
        same = {"version": "v1", "sessions": len(srcs), "proof_set": bool(only), "portfolio": "all", "by_delay": rows,
                "note": f"v1's trades from the same {len(srcs)} sessions, priced the same way"}
        print(f"  v1 on the same {len(srcs)} sessions @5m: end {rows[str(d5)]['end']:,.0f}  trades {rows[str(d5)]['trades']}")
    priced = [rs for rs in by_pos.values() if rs[d5].status == "priced"]
    priced.sort(key=lambda rs: -abs(rs[d5].pnl))
    trades = [trade_row(rs) for rs in priced[:SAMPLE_TRADES]]

    st = built["stats"]
    assumed = Counter(p.portfolio for rs in by_pos.values() for d, r in rs.items()
                      if d == d5 and r.assumed_exit for p in [r.position])
    unknown = mod.unknown(st, assumed, len(positions), len(built["positions"]), status) \
        if hasattr(mod, "unknown") else []
    unknown.append("Worst drop counts closed trades only, not open ones.")
    if not a.scale:
        unknown = [u for u in unknown if "scaled" not in u]
    head = portfolios[0]["by_delay"][str(d5)]
    if head["sized_down"] or head["couldnt_copy"]:
        unknown.insert(0, f"At {d5} min, {head['sized_down']} trades were sized down and {head['couldnt_copy']} "
                          "not copied: no cash left, or too late in the day.")
    if same:
        what = f"the {len(only)}-session proof set PRISM scores" if only else f"{same['sessions']} sessions"
        unknown.insert(0, f"{a.version} covers {what} only; compare it with v1 on the same sessions "
                          "(same_sessions), not with the full year.")

    out = {
        "schema": "results/1", "course": a.course, "course_name": mod.NAME, "version": a.version,
        "source_agent_id": f"extract-{a.course}-{a.version}", "sample": False,
        "partial": len(positions) < len(built["positions"]),
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_sha": git_sha(),
        "window": mod.WINDOW, "money_start": int(MONEY_START), "course_fee_usd": None,
        "delays_min": DELAYS_MIN, "default_delay_min": DEFAULT_DELAY_MIN, "costs_bps_per_side": COSTS_BPS,
        "sizing": getattr(mod, "SIZING_SCALED", mod.SIZING) if a.scale else mod.SIZING, "hold": mod.HOLD, "headline_portfolio": "all",
        "portfolios": portfolios, **({"same_sessions": same} if same else {}),
        "rules": built["rules"], "trades": trades,
        **({"days": built["days"]} if built["days"] else {}),
        "unknown": unknown, "checks": {**built["checks"], "positions": len(built["positions"]),
                                       "positions_priced": len(positions),
                                       "results_by_status": dict(status)},
    }
    results_all = {d: [by_pos[p.pid][d] for p in positions] for d in DELAYS_MIN}
    strat = extras.strategies(mod, a.version, positions, by_pos, dates, hold, mod.WINDOW)
    rng = extras.ranges(results_all, dates, hold_series, mod.WINDOW)
    mix = extras.combos(mod, positions, by_pos, dates, hold, hold_series, mod.WINDOW)
    out.update({k: v for k, v in (("strategies", strat), ("ranges", rng), ("combos", mix)) if v})
    out["best_stop"] = extras.best_stop(portfolios[0], hold_series)
    sp = DATA / "improver" / f"{a.course}-{a.version}.json"   # written by backtest.improver (traced to PRISM)
    if sp.exists():
        out["suggestion"] = json.loads(sp.read_text())
        if out["suggestion"].get("trajectory_id") and not out["suggestion"].get("prism_url"):
            from .improver import PRISM_RUN
            out["suggestion"]["prism_url"] = PRISM_RUN.format(out["suggestion"]["trajectory_id"])
            sp.write_text(json.dumps(out["suggestion"], indent=1))
    print(f"  strategies {len(strat)}, ranges {list(rng)}, best stop @5m {out['best_stop']['by_delay']['5']}")
    for c in mix:
        print(f"  best mix {c['ids']}: dev {c['dev']['ret_pct']}% vs hold {c['dev']['hold_ret_pct']}%, "
              f"sealed {c['sealed']['ret_pct']}% vs {c['sealed']['hold_ret_pct']}% ({c['sealed']['trades']} trades) {c['word']}")
    path = Path(a.out) if a.out else RESULTS / a.course / f"{a.version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    al = portfolios[0]["by_delay"]
    for d in DELAYS_MIN:
        r = al[str(d)]
        print(f"  all @{d:>2}m: end {r['end']:>10,.0f}  ret {r['ret_pct']:>7.2f}%  hold {r['hold_ret_pct']:>6.2f}%  "
              f"trades {r['trades']:>4}  won {r['won_pct']}%  {r['word']}")
    print("wrote", path)


if __name__ == "__main__":
    main()
