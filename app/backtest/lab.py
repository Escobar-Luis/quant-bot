"""Strategy lab: his profitable rules (S4, S5) run as code on prices after his window and on stocks he never traded.

Spec (pre-registered, committed before the first run): notes/research/strategy-as-code.md. Contract: contracts.md,
section `strategy-lab`. Writes results/strategy-lab.json and the full trade list to data/lab/ledger.json.
    cd app && uv run python -m backtest.lab [--fetch-cap 200]
No model: rules, prices and verdicts are code (AGENTS.md rule 3). Network: Alpaca only (daily bars, the asset list's
borrow flags, and 1-minute bars for trigger sessions, at most --fetch-cap new ticker-days per run).
"""
import argparse
import datetime as dt
import json
import os
import sys

import httpx
import numpy as np

from . import bars as B
from .common import BARS, DATA, RESULTS, git_sha, has_alpaca, public_json

SPEC = "notes/research/strategy-as-code.md"
PREREGISTERED_SHA = "eb6c3e8"   # the commit that fixed the spec, before any test-window price was read
FROM, TO, SLICE_FROM = dt.date(2025, 9, 15), dt.date(2026, 10, 16), dt.date(2026, 7, 1)
DAILY_FROM = dt.date(2025, 7, 15)   # 20+ sessions before FROM: the previous close and the 20-session volume
MONEY, PER_TRADE = 10_000.0, 1_000.0
ADV_THIN = 50e6
SEED, DRAWS = 21, 2000

UNIVERSES = [
    {"id": "his-hot", "which": "a", "label": "His hot small and mid caps",
     "tickers": ["AFRM", "AI", "CVNA", "DJT", "GME", "HIMS", "OPEN", "PLTR", "RDDT", "SMCI", "SOFI", "SOUN", "TEM"],
     "rule": "names in his record that the code's ticker groups call hot small and mid caps"},
    {"id": "his-crypto", "which": "a", "label": "His crypto stocks", "tickers": ["COIN", "HOOD", "MARA", "MSTR"],
     "rule": "names in his record that the code's ticker groups call crypto-linked"},
    {"id": "new-hot", "which": "b", "label": "Other hot stocks",
     "tickers": ["SOGP", "IPDN", "ORBS", "OPAD", "NEGG", "CWD", "WLDS", "ONDS", "BMNR", "AAOI", "RUN", "SEDG", "BLSH",
                 "UUUU", "SBET", "APLD", "CRCL", "SMR", "PL", "PGY"],
     "rule": "top 20 by average daily range, $100M+ a day traded, $5+, not his, as of 2025-09-12"},
    {"id": "new-crypto", "which": "b", "label": "Other crypto stocks",
     "tickers": ["HUT", "KEEL", "HIVE", "BTBT", "BTDR", "IREN", "CIFR", "GLXY", "WULF", "LUNR"],
     "rule": "top 10 by one-year correlation with IBIT (0.4+, beta 1+), $20M+ a day traded, not his, as of 2025-09-12"},
]
RULES = [
    {"id": "S4", "label": "Short the run-up", "entry_et": "09:45", "universes": ["his-hot", "new-hot"],
     "text": "Short a hot stock at 09:45 ET when it opened 5%+ above yesterday's close; stop 5% above entry; "
             "cover at 15:55 ET."},
    {"id": "S5", "label": "Short crypto stocks that open up", "entry_et": "09:35",
     "universes": ["his-crypto", "new-crypto"],
     "text": "Short a crypto-linked stock at 09:35 ET when it opened 5%+ above yesterday's close; stop 5% above "
             "entry; cover at 15:55 ET."},
    {"id": "C", "label": "Short at the open (control)", "entry_et": "09:30",
     "universes": ["his-hot", "his-crypto", "new-hot", "new-crypto"],
     "text": "Short every stock at every open, cover at the close (daily bars). No signal, no stop."},
]
VARIANTS = [
    {"id": "P", "gap_pct": 5, "stop_pct": 5, "exit_et": "15:55"},
    {"id": "no-stop", "gap_pct": 5, "stop_pct": None, "exit_et": "15:55"},
    {"id": "exit-11", "gap_pct": 5, "stop_pct": 5, "exit_et": "11:00"},
    {"id": "gap-10", "gap_pct": 10, "stop_pct": 5, "exit_et": "15:55"},
]
PICKER_VERSIONS = 3
COSTS = {"base": "5 bps per side, 20 bps under $10 (contracts rule 5)",
         "x2": "every per-side cost doubled",
         "small_cap": "per side 50 bps under $5, 30 bps under $10, else 5 bps; +10 bps when the 20-session average "
                      "dollar volume before the session is under $50M",
         "borrow_high": "hard-to-borrow names (Alpaca's flag today) pay one day of a 100%-a-year fee: 0.4% of "
                        "notional; easy-to-borrow intraday shorts pay none"}
BORROW_HIGH = 0.004


# ---- data --------------------------------------------------------------------------------------------------------

def _hdr() -> dict:
    return {"APCA-API-KEY-ID": os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY") or "",
            "APCA-API-SECRET-KEY": os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY") or ""}


def daily_path(sym: str, adj: str) -> "os.PathLike":
    return BARS / "lab_daily" / f"{sym}_{adj}_{DAILY_FROM}_{TO}.json"


def daily(sym: str, adj: str) -> dict[str, list]:
    """{ET date: [o, h, l, c, v]} from DAILY_FROM to TO; adj = raw | split | all. Cached; one request."""
    p = daily_path(sym, adj)
    if p.exists():
        return json.loads(p.read_text())
    out, token = {}, None
    while True:
        params = {"timeframe": "1Day", "start": DAILY_FROM.isoformat(), "end": B.to_iso(B.et_at(TO, 17, 0)),
                  "limit": 10000, "feed": "sip", "adjustment": adj}
        if token:
            params["page_token"] = token
        js = B._alpaca_get(f"{sym}/bars", params)
        for b in js.get("bars") or []:
            out[B.et_date(B.to_ts(b["t"])).isoformat()] = [b["o"], b["h"], b["l"], b["c"], b["v"]]
        token = js.get("next_page_token")
        if not token:
            break
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    return out


def borrow_flags(tickers: list[str]) -> dict[str, bool]:
    """{ticker: easy_to_borrow} from Alpaca's asset list (today's flag), cached in data/lab/assets.json."""
    p = DATA / "lab" / "assets.json"
    have = json.loads(p.read_text()) if p.exists() else {}
    for t in tickers:
        if t not in have:
            r = httpx.get(f"https://paper-api.alpaca.markets/v2/assets/{t}", headers=_hdr(), timeout=30)
            have[t] = bool(r.json().get("easy_to_borrow")) if r.status_code == 200 else False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(have, indent=1, sort_keys=True))
    return {t: have[t] for t in tickers}


def minute_path(sym: str, day: str):
    return BARS / "alpaca_1m" / sym / f"{day}.json"


# ---- signals and trades ------------------------------------------------------------------------------------------

def sessions(spy: dict) -> list[str]:
    return [d for d in sorted(spy) if FROM.isoformat() <= d <= TO.isoformat()]


def gap_sessions(split: dict, gap_pct: float) -> list[str]:
    """Sessions in the window whose open is gap_pct% or more above the previous session's close."""
    days, out = sorted(split), []
    for i in range(1, len(days)):
        d = days[i]
        # rounded: 12.915 / 12.30 is exactly +5% but 12.30 * 1.05 is 12.915000000000001 in floating point
        if FROM.isoformat() <= d <= TO.isoformat() and round(split[d][0] / split[days[i - 1]][3] - 1, 9) >= gap_pct / 100:
            out.append(d)
    return out


def adv_before(raw: dict, day: str) -> float:
    prev = [d for d in sorted(raw) if d < day][-20:]
    return sum(raw[d][3] * raw[d][4] for d in prev) / len(prev) if prev else 0.0


def hhmm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def short_trade(bars: dict, day: dt.date, entry_et: str, stop_pct, exit_et: str) -> dict | None:
    """A short opened at the first bar at or after entry_et; stop (from the entry bar on: high >= stop fills at
    max(open, stop)); else the first bar at or after exit_et's open; else the last bar's close. None: no bar."""
    ks = sorted(bars)
    t_in, t_out = B.et_at(day, *hhmm(entry_et)), B.et_at(day, *hhmm(exit_et))
    after = [k for k in ks if k >= t_in]
    if not after:
        return None
    k0 = after[0]
    entry = bars[k0][0]
    stop = entry * (1 + stop_pct / 100) if stop_pct is not None else None
    for k in after:
        if k >= t_out:
            return {"entry_ts": k0, "entry": entry, "exit_ts": k, "exit": bars[k][0], "kind": "time"}
        o, h = bars[k][0], bars[k][1]
        if stop is not None and h >= stop:
            return {"entry_ts": k0, "entry": entry, "exit_ts": k, "exit": max(o, stop), "kind": "stop"}
    k = ks[-1]
    return {"entry_ts": k0, "entry": entry, "exit_ts": k, "exit": bars[k][3], "kind": "last"}


def bps(model: str, px: float, adv: float) -> float:
    base = 20 if px < 10 else 5
    if model == "base":
        return base
    if model == "x2":
        return 2 * base
    return (50 if px < 5 else 30 if px < 10 else 5) + (10 if adv < ADV_THIN else 0)


def pnl(t: dict, notional: float, model: str) -> float:
    q = notional / t["entry"]
    return q * (t["entry"] - t["exit"]) - q * t["entry"] * bps(model, t["entry"], t["adv"]) / 1e4 \
        - q * t["exit"] * bps(model, t["exit"], t["adv"]) / 1e4


# ---- portfolio ---------------------------------------------------------------------------------------------------

def word(trades: int, ret: float, bench: float) -> tuple[str, str]:
    outcome = "No trades" if trades == 0 else "Made money" if ret > 0 else "Lost money" if ret < 0 else "Broke even"
    if trades < 30:
        return "Not enough trades", outcome
    if ret < 0:
        return "No", outcome
    gap = ret - bench
    return ("Yes" if gap >= 2 else "Barely" if gap > -2 else "No"), outcome


def book(trades: list[dict], cal: list[str], model: str = "base", borrow: bool = False) -> dict:
    """Run the account over the window: per-session sizing, then P&L under a cost model. Mutates nothing."""
    by_day: dict[str, list[dict]] = {}
    for t in trades:
        by_day.setdefault(t["day"], []).append(t)
    realized, eq, peak, mdd, sized_down, out = 0.0, [], MONEY, 0.0, 0, []
    for d in cal:
        ts = sorted(by_day.get(d, []), key=lambda t: (t["entry_ts"], t["ticker"]))
        if ts:
            account = min(MONEY, MONEY + realized)
            each = PER_TRADE if len(ts) * PER_TRADE <= account else max(account, 0) / len(ts)
            if each < PER_TRADE:
                sized_down += len(ts)
            day_pnl = 0.0
            for t in ts:
                p = pnl(t, each, model) - (each * BORROW_HIGH if borrow and t["htb"] else 0.0)
                out.append({**t, "notional": each, "pnl": p})
                day_pnl += p
            realized += day_pnl
        e = MONEY + realized
        peak = max(peak, e)
        mdd = min(mdd, e / peak - 1)
        eq.append(e)
    return {"trades": out, "pnl": realized, "mdd_pct": 100 * mdd, "sized_down": sized_down}


def streak(trades: list[dict]) -> int:
    best = cur = 0
    for t in sorted(trades, key=lambda t: (t["entry_ts"], t["ticker"])):
        cur = cur + 1 if t["pnl"] <= 0 else 0
        best = max(best, cur)
    return best


def spy_ret(spy_all: dict, start: str, end: str) -> float:
    """Total return from the close of the session before `start` to the close of `end` (adjustment=all)."""
    days = sorted(spy_all)
    before = [d for d in days if d < start][-1]
    last = [d for d in days if d <= end][-1]
    return 100 * (spy_all[last][3] / spy_all[before][3] - 1)


def spy_mdd(spy_all: dict, cal: list[str]) -> float:
    days = sorted(spy_all)
    p0 = spy_all[[d for d in days if d < cal[0]][-1]][3]
    peak, mdd = p0, 0.0
    for d in cal:
        c = spy_all[d][3]
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)
    return 100 * mdd


def r2(x: float) -> float:
    return round(x + 0.0, 2)


def vs_random(twin: list[tuple[str, str]], pool: list[tuple[str, str]], split: dict, raw: dict) -> dict | None:
    """Daily-bar twin (short open -> close, $1,000, base costs) vs DRAWS random draws of as many sessions."""
    if not twin:
        return None

    def one(t, d):
        o, c = split[t][d][0], split[t][d][3]
        ro, rc = raw[t][d][0], raw[t][d][3]
        q = PER_TRADE / o
        return q * (o - c) - PER_TRADE * bps("base", ro, 0) / 1e4 - q * c * bps("base", rc, 0) / 1e4

    vals = np.array([one(t, d) for t, d in pool])
    idx = {k: i for i, k in enumerate(pool)}
    tw = float(sum(vals[idx[k]] for k in twin))
    rng = np.random.default_rng(SEED)
    draws = np.array([vals[rng.choice(len(pool), size=len(twin), replace=False)].sum() for _ in range(DRAWS)])
    return {"twin_pnl_usd": r2(tw), "p2_5": r2(float(np.percentile(draws, 2.5))),
            "p97_5": r2(float(np.percentile(draws, 97.5))),
            "pct_rank": round(100 * float((draws < tw).mean()), 1), "draws": DRAWS}


# ---- the run -----------------------------------------------------------------------------------------------------

def needed_minutes(split: dict) -> list[tuple[str, str]]:
    need = set()
    for r in RULES:
        if r["id"] == "C":
            continue
        for u in r["universes"]:
            for t in next(x for x in UNIVERSES if x["id"] == u)["tickers"]:
                for d in gap_sessions(split[t], min(v["gap_pct"] for v in VARIANTS)):
                    need.add((t, d))
    return sorted(need)


def fetch_minutes(need: list[tuple[str, str]], cap: int) -> tuple[int, int]:
    """Fetch missing ticker-days, at most `cap` this run. Returns (fetched now, still missing)."""
    missing = [(t, d) for t, d in need if not minute_path(t, d).exists()]
    for t, d in missing[:cap]:
        try:
            B.stock_day(t, dt.date.fromisoformat(d))
        except B.NoBars as e:
            print(f"  {t} {d}: {e}", file=sys.stderr)
    still = sum(1 for t, d in need if not minute_path(t, d).exists())
    return min(cap, len(missing)), still


def load_minutes(t: str, d: str) -> dict:
    p = minute_path(t, d)
    return {int(k): v for k, v in json.loads(p.read_text()).items()} if p.exists() else {}


def build(fetch_cap: int) -> dict | None:
    tickers = sorted({t for u in UNIVERSES for t in u["tickers"]})
    split = {t: daily(t, "split") for t in tickers}
    raw = {t: daily(t, "raw") for t in tickers}
    spy_all = daily("SPY", "all")
    cal = sessions(spy_all)
    htb = {t: not ok for t, ok in borrow_flags(tickers).items()}
    need = needed_minutes(split)
    fetched, still = fetch_minutes(need, fetch_cap)
    print(f"minute ticker-days needed {len(need)}, fetched this run {fetched}, still missing {still}",
          file=sys.stderr)
    log = DATA / "lab" / "fetch_runs.json"
    runs_log = json.loads(log.read_text()) if log.exists() else []
    if fetched:
        runs_log.append({"at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "fetched": fetched})
        log.write_text(json.dumps(runs_log, indent=1))
    if still:
        print("run again to fetch the rest (cap per run)", file=sys.stderr)
        return None

    spy_full = spy_ret(spy_all, cal[0], cal[-1])
    spy_slice = spy_ret(spy_all, SLICE_FROM.isoformat(), cal[-1])
    slice_cal = [d for d in cal if d >= SLICE_FROM.isoformat()]
    runs, ledger = [], {}
    for rule in RULES:
        for uid in rule["universes"]:
            uni = next(x for x in UNIVERSES if x["id"] == uid)
            pool = [(t, d) for t in uni["tickers"] for d in cal
                    if d in split[t] and any(x < d for x in split[t])]
            for v in (VARIANTS if rule["id"] != "C" else [{"id": "control"}]):
                trades, twin, no_bars = [], [], 0
                if rule["id"] == "C":
                    for t, d in pool:
                        o, c = split[t][d][0], split[t][d][3]
                        f = raw[t][d][0] / o   # raw fills for the cost tier; ratios from split-adjusted bars
                        trades.append({"ticker": t, "day": d, "entry_ts": B.et_at(dt.date.fromisoformat(d), 9, 30),
                                       "entry": o * f, "exit": c * f, "kind": "close",
                                       "adv": adv_before(raw[t], d), "htb": htb[t]})
                else:
                    for t in uni["tickers"]:
                        for d in gap_sessions(split[t], v["gap_pct"]):
                            twin.append((t, d))
                            tr = short_trade(load_minutes(t, d), dt.date.fromisoformat(d), rule["entry_et"],
                                             v["stop_pct"], v["exit_et"])
                            if tr is None:
                                no_bars += 1
                                continue
                            trades.append({"ticker": t, "day": d, **tr, "adv": adv_before(raw[t], d), "htb": htb[t]})
                base = book(trades, cal)
                n = len(base["trades"])
                ret = 100 * base["pnl"] / MONEY
                w, outcome = word(n, ret, spy_full)
                x2, sc, bh = book(trades, cal, "x2"), book(trades, cal, "small_cap"), book(trades, cal, "base", True)
                sl = [t for t in base["trades"] if t["day"] >= SLICE_FROM.isoformat()]
                sl_ret = 100 * sum(t["pnl"] for t in sl) / MONEY
                days: dict[str, float] = {}
                for t in base["trades"]:
                    days[t["day"]] = days.get(t["day"], 0.0) + t["pnl"]
                worst = min(days.items(), key=lambda kv: (kv[1], kv[0])) if days else None
                won = sum(1 for t in base["trades"] if t["pnl"] > 0)
                runs.append({
                    "rule": rule["id"], "variant": v["id"], "universe": uid, "primary": v["id"] in ("P", "control"),
                    "trades": n, "won_pct": round(100 * won / n) if n else None, "pnl_usd": r2(base["pnl"]),
                    "end": r2(MONEY + base["pnl"]), "ret_pct": r2(ret), "max_drawdown_pct": r2(base["mdd_pct"]),
                    "longest_losing_streak": streak(base["trades"]),
                    "worst_day": {"day": worst[0], "pnl_usd": r2(worst[1])} if worst else None,
                    "spy_ret_pct": r2(spy_full), "vs_spy_pts": r2(ret - spy_full), "word": w, "outcome": outcome,
                    "sized_down": base["sized_down"], "skipped": {"no_bars": no_bars},
                    "costs": {k: {"ret_pct": r2(100 * b["pnl"] / MONEY),
                                  "word": word(n, 100 * b["pnl"] / MONEY, spy_full)[0]}
                              for k, b in (("x2", x2), ("small_cap", sc))},
                    "borrow": {"htb_trades": sum(1 for t in base["trades"] if t["htb"]),
                               "borrow_high_ret_pct": r2(100 * bh["pnl"] / MONEY)},
                    "vs_random": vs_random(twin, pool, split, raw) if rule["id"] != "C" else None,
                    "slice": {"trades": len(sl), "ret_pct": r2(sl_ret), "spy_ret_pct": r2(spy_slice),
                              "word": word(len(sl), sl_ret, spy_slice)[0]},
                })
                ledger[f"{rule['id']}|{v['id']}|{uid}"] = [
                    {k: (round(x, 6) if isinstance(x, float) else x) for k, x in t.items()} for t in base["trades"]]
                print(f"{rule['id']:<3}{v['id']:<8}{uid:<11} trades {n:>5}  ret {ret:7.2f}%  vs SPY {ret - spy_full:7.2f}"
                      f"  {w}", file=sys.stderr)
    verdict = {}
    for rule in RULES[:2]:
        prim = [r for r in runs if r["rule"] == rule["id"] and r["variant"] == "P"]
        ok = all(r["word"] == "Yes" for r in prim)
        verdict[rule["id"]] = {"held_up": ok, "why": "; ".join(
            f"{r['universe']}: {r['word']} ({r['ret_pct']:+.2f}% vs SPY {r['spy_ret_pct']:+.2f}%, {r['trades']} trades)"
            for r in prim)}
    (DATA / "lab").mkdir(parents=True, exist_ok=True)
    (DATA / "lab" / "ledger.json").write_text(json.dumps(ledger))
    return {
        "schema": "strategy-lab/1", "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(), "preregistered_sha": PREREGISTERED_SHA, "spec": SPEC,
        "window": {"from": cal[0], "to": cal[-1], "slice_from": slice_cal[0]},
        "money_start": MONEY, "per_trade_usd": PER_TRADE, "costs": COSTS,
        "variants_tried": len(runs) + PICKER_VERSIONS,
        "fetch": {"minute_ticker_days": len(need), "runs": len(runs_log), "cap_per_run": fetch_cap},
        "benchmark": {"symbol": "SPY", "basis": "total return, dividends reinvested (Alpaca daily, adjustment=all), "
                                                 "close of the session before the window to the last close",
                      "from_close": [d for d in sorted(spy_all) if d < cal[0]][-1], "to_close": cal[-1],
                      "ret_pct": r2(spy_full), "max_drawdown_pct": r2(spy_mdd(spy_all, cal)),
                      "slice": {"ret_pct": r2(spy_slice)}},
        "universes": UNIVERSES, "rules": RULES, "variants": VARIANTS, "runs": runs, "verdict": verdict,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-cap", type=int, default=200, help="new 1-minute ticker-days to fetch this run")
    ap.add_argument("--out", default=str(RESULTS / "strategy-lab.json"))
    a = ap.parse_args(argv)
    if not has_alpaca():
        print("no Alpaca keys in .env", file=sys.stderr)
        return 2
    res = build(a.fetch_cap)
    if res is None:
        return 3
    with open(a.out, "w") as f:
        f.write(public_json(res) + "\n")
    print(f"wrote {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
