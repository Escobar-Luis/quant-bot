"""Write results/<course>/<version>.json (contracts.md) from the collectors' events and cached bars.

  cd app && uv run python -m backtest.run --course lpp --version v1
  cd app && uv run python -m backtest.run --course lpp --version v1 --limit 40   # first 40 positions only (partial)

Code only: no model call, nothing to trace. Prints counts, never key values.
"""
import argparse
import datetime as dt
import json
from collections import Counter

from . import bars, engine
from .common import (COSTS_BPS, DEFAULT_DELAY_MIN, DELAYS_MIN, MONEY_START, RESULTS, git_sha)

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
    raise SystemExit(f"unknown course {course}")


def hold_numbers(market: str, symbol: str, window: dict) -> tuple[dict, list[str], list[float]]:
    """$10k bought at the window's first trading minute, held to its last bar; plus its daily series."""
    start, end = dt.date.fromisoformat(window["start"]), dt.date.fromisoformat(window["end"])
    days = bars.sessions(start, end, market, symbol)
    first = bars.day_bars(market, symbol, days[0])
    px0 = first[min(first)][0]
    closes = [bars.last_close_on(market, symbol, d) for d in days]
    sealed = dt.date.fromisoformat(window["sealed_from"])
    sealed_day = next(d for d in days if d >= sealed)
    sb = bars.day_bars(market, symbol, sealed_day)
    sealed_px0 = sb[min(sb)][0]
    series = [round(MONEY_START * c / px0, 2) for c in closes]
    hold = {"end": series[-1], "ret_pct": round((closes[-1] / px0 - 1) * 100, 2),
            "sealed_ret_pct": round((closes[-1] / sealed_px0 - 1) * 100, 2)}
    return hold, [d.isoformat() for d in days], series


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
    a = ap.parse_args()

    mod = course_module(a.course)
    built = mod.build(a.version)
    positions = built["positions"][: a.limit] if a.limit else built["positions"]
    print(f"{a.course} {a.version}: {len(built['positions'])} positions, pricing {len(positions)}")

    hold, dates, hold_series = hold_numbers(mod.MARKET, mod.HOLD["symbol"], mod.WINDOW)
    by_pos: dict[str, dict[int, engine.Result]] = {}
    for i, p in enumerate(positions):
        by_pos[p.pid] = {d: engine.simulate(p, d) for d in DELAYS_MIN}
        if (i + 1) % 25 == 0:
            print(f"  priced {i + 1}/{len(positions)}")
    status = Counter(r.status for rs in by_pos.values() for r in rs.values())
    print("  results by status (all delays):", dict(status))

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
    priced = [rs for rs in by_pos.values() if rs[d5].status == "priced"]
    priced.sort(key=lambda rs: -abs(rs[d5].pnl))
    trades = [trade_row(rs) for rs in priced[:SAMPLE_TRADES]]

    st = built["stats"]
    assumed = Counter(p.portfolio for rs in by_pos.values() for d, r in rs.items()
                      if d == d5 and r.assumed_exit for p in [r.position])
    unknown = mod.unknown(st, assumed, len(positions), len(built["positions"]), status) \
        if hasattr(mod, "unknown") else []

    out = {
        "schema": "results/1", "course": a.course, "course_name": mod.NAME, "version": a.version,
        "source_agent_id": f"extract-{a.course}-{a.version}", "sample": False,
        "partial": len(positions) < len(built["positions"]),
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_sha": git_sha(),
        "window": mod.WINDOW, "money_start": int(MONEY_START), "course_fee_usd": None,
        "delays_min": DELAYS_MIN, "default_delay_min": DEFAULT_DELAY_MIN, "costs_bps_per_side": COSTS_BPS,
        "sizing": mod.SIZING, "hold": mod.HOLD, "headline_portfolio": "all",
        "portfolios": portfolios, "rules": built["rules"], "trades": trades,
        **({"days": built["days"]} if built["days"] else {}),
        "unknown": unknown, "checks": {**built["checks"], "positions": len(built["positions"]),
                                       "positions_priced": len(positions),
                                       "results_by_status": dict(status)},
    }
    path = RESULTS / a.course / f"{a.version}.json" if not a.out else a.out
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
