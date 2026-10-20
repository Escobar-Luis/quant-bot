"""Independent recompute of the forward paper test: results/paper/ledger.jsonl and summary.json (contracts.md,
section `paper`; rules in app/paper/rules-v1.json, frozen at tag paper-rules-v1). Written from the contract and the
rules file, never importing app/paper or app/backtest. Reads only cached files: data/paper/daily/<day>.json (the
daily bars each session used) and data/bars/alpaca_1m/ (1-minute bars). Never fetches: a missing file is a
MissingBar.

Checks: the rules file is the frozen one; every ledger session counts (opens after the freeze), the sessions are in
order with none missing between the first and the last (per SPY's daily bars); each session's triggers, trades
(entry and exit time, price, kind), skips, sizing, P&L under every cost model, equity and SPY factor; and every
summary number (days, SPY return, trades, won, stops, borrow counts, end, return, worst drop, vs SPY, word, the
versus-random twin). Tolerance: $0.01 on money, 0.01 pt on percents, 1e-6 on prices and factors; counts, times,
kinds and words exact. The random band itself is a seeded simulation and is listed as unverifiable.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path

from .bars import ET, MissingBar
from .paths import BARS, DATA, REPO, RESULTS

PAPER = RESULTS / "paper"
RULES_FILE = REPO / "app" / "paper" / "rules-v1.json"

# Transcribed from app/paper/rules-v1.json (frozen at paper-rules-v1, 2026-10-20T21:38:43Z). The audit computes from
# these and fails when the rules file or the summary declares anything different.
FROZEN = {
    "rules_sha256": "7eb5f5fc74310b58e856f5ab78cc255ffe2e0d34083a00e336447905ed9f0a94",
    "freeze_at": "2026-10-20T21:38:43Z",
    "rules": {
        "S4": {"tickers": ["AFRM", "AI", "CVNA", "DJT", "GME", "HIMS", "OPEN", "PLTR", "RDDT", "SMCI", "SOFI", "SOUN",
                           "TEM", "SOGP", "ORBS", "NEGG", "CWD", "WLDS", "ONDS", "BMNR", "AAOI", "RUN", "SEDG", "BLSH",
                           "UUUU", "SBET", "APLD", "CRCL", "SMR", "PL", "PGY", "SKYD", "QS"],
               "gap": 5, "entry": "09:45", "stop": 5, "exit": "15:55"},
        "S5": {"tickers": ["COIN", "HOOD", "MARA", "MSTR", "HUT", "KEEL", "HIVE", "BTBT", "BTDR", "IREN", "CIFR",
                           "GLXY", "WULF", "LUNR"],
               "gap": 5, "entry": "09:35", "stop": 5, "exit": "15:55"},
    },
    "start": 10_000.0, "per_trade": 1_000.0, "thin_adv": 50e6, "borrow": 0.004, "min_trades_random": 30,
}
MODELS = ("realistic", "x2", "base")


def _t(day: str, hm: str) -> int:
    h, m = (int(x) for x in hm.split(":"))
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), ET).timestamp())


def _cost_bps(model: str, px: float, adv: float) -> float:
    if model == "base":
        return 20.0 if px < 10 else 5.0
    b = (50.0 if px < 5 else 30.0 if px < 10 else 5.0) + (10.0 if adv < FROZEN["thin_adv"] else 0.0)
    return 2 * b if model == "x2" else b


def _fee(model: str, etb) -> float:
    if model == "base" or etb is True:
        return 0.0
    return FROZEN["borrow"] * (2 if model == "x2" else 1)


def _daily(day: str) -> dict:
    p = DATA / "paper" / "daily" / f"{day}.json"
    if not p.exists():
        raise MissingBar(f"paper daily bars for {day}: not cached")
    return json.loads(p.read_text())


def _minutes(sym: str, day: str) -> list[tuple[int, list]]:
    p = BARS / "alpaca_1m" / sym / f"{day}.json"
    if not p.exists():
        raise MissingBar(f"{sym} {day}: no cached 1-minute bars")
    return sorted((int(k), v) for k, v in json.loads(p.read_text()).items())


def _row(rows: list, day: str) -> int | None:
    for i, r in enumerate(rows):
        if r[0] == day:
            return i
    return None


def _trade(sym: str, day: str, spec: dict) -> dict | None:
    bars = _minutes(sym, day)
    t_in, t_out = _t(day, spec["entry"]), _t(day, spec["exit"])
    live = [(k, b) for k, b in bars if k >= t_in]
    if not live:
        return None
    k0, entry = live[0][0], live[0][1][0]
    stop = entry * (1 + spec["stop"] / 100)
    for k, b in live:
        if k >= t_out:
            return {"entry_ts": k0, "entry": entry, "exit_ts": k, "exit": b[0], "kind": "time"}
        if b[1] >= stop:
            return {"entry_ts": k0, "entry": entry, "exit_ts": k, "exit": max(b[0], stop), "kind": "stop"}
    return {"entry_ts": k0, "entry": entry, "exit_ts": bars[-1][0], "exit": bars[-1][1][3], "kind": "last"}


def check(paper_dir: Path = PAPER, rules_file: Path = RULES_FILE) -> dict:
    mism, unverifiable = [], []

    def cmp(where: str, field: str, ours, theirs, tol: float | None = None):
        same = (ours is None and theirs is None) if (ours is None or theirs is None) else \
            (abs(ours - theirs) <= tol if tol is not None else ours == theirs)
        if not same:
            mism.append({"where": where, "field": field, "audit": ours, "file": theirs})

    summary = json.loads((paper_dir / "summary.json").read_text())
    lp = paper_dir / "ledger.jsonl"
    ledger = [json.loads(x) for x in lp.read_text().splitlines() if x.strip()] if lp.exists() else []
    rules_sha = hashlib.sha256(rules_file.read_bytes()).hexdigest()
    cmp("rules", "sha256 (file vs frozen)", rules_sha, FROZEN["rules_sha256"])
    cmp("summary", "rules_sha256", FROZEN["rules_sha256"], summary.get("rules_sha256"))
    cmp("summary", "freeze.at", FROZEN["freeze_at"], (summary.get("freeze") or {}).get("at"))
    rf = json.loads(rules_file.read_text())
    for r in rf["rules"]:
        spec = FROZEN["rules"].get(r["id"])
        declared = {"tickers": [t for v in r["lists"].values() for t in v], "gap": r["gap_min_pct"],
                    "entry": r["entry_et"], "stop": r["stop_pct"], "exit": r["exit_et"]}
        cmp("rules", f"{r['id']} parameters", spec, declared)
    freeze_ts = dt.datetime.fromisoformat(FROZEN["freeze_at"].replace("Z", "+00:00")).timestamp()

    # sessions: counted, ordered, none missing
    days = [ln["day"] for ln in ledger]
    cmp("ledger", "sessions in order, no repeats", sorted(set(days)), days)
    for d in days:
        if _t(d, "09:30") <= freeze_ts:
            mism.append({"where": f"ledger {d}", "field": "counts", "audit": "before the freeze", "file": "counted"})
    if ledger:
        cal = sorted({r[0] for d in days for r in _daily(d)["spy_all"]})
        freeze_day = dt.datetime.fromtimestamp(freeze_ts, ET).date().isoformat()
        expect = [d for d in cal if d <= days[-1] and _t(d, "09:30") > freeze_ts]
        first_cal = [r[0] for r in _daily(days[0])["spy_all"]]
        if any(freeze_day < d < days[0] and _t(d, "09:30") > freeze_ts for d in first_cal):
            mism.append({"where": "ledger", "field": "first session", "audit": "a session was skipped before it",
                         "file": days[0]})
        cmp("ledger", "sessions from first to last", [d for d in expect if d >= days[0]], days)

    eq = {rid: {m: FROZEN["start"] for m in MODELS} for rid in FROZEN["rules"]}
    trades_all = {rid: [] for rid in FROZEN["rules"]}
    spy = 1.0
    checked = 0
    for ln in ledger:
        d, daily = ln["day"], _daily(ln["day"])
        s = daily["spy_all"]
        i = _row(s, d)
        f = s[i][4] / s[i - 1][4] if i else None
        cmp(f"{d}", "spy_factor", f, ln["spy_factor"], 1e-9)
        spy *= f or 1.0
        for rid, spec in FROZEN["rules"].items():
            out = ln["rules_out"][rid]
            ours, skipped = [], []
            for sym in spec["tickers"]:
                rows = daily["split"].get(sym, [])
                j = _row(rows, d)
                if not j:
                    continue
                if round(rows[j][1] / rows[j - 1][4] - 1, 9) < spec["gap"] / 100:
                    continue
                tr = _trade(sym, d, spec)
                if tr is None:
                    skipped.append(sym)
                    continue
                raw = [r for r in daily["raw"].get(sym, []) if r[0] < d][-20:]
                adv = sum(r[4] * r[5] for r in raw) / len(raw) if raw else 0.0
                ours.append({"ticker": sym, **tr, "adv": adv, "etb": daily["easy_to_borrow"].get(sym)})
            ours.sort(key=lambda x: (x["entry_ts"], x["ticker"]))
            theirs = out["trades"]
            cmp(f"{d} {rid}", "trades", [x["ticker"] for x in ours], [x["ticker"] for x in theirs])
            cmp(f"{d} {rid}", "skipped", sorted(skipped), sorted(x["ticker"] for x in out["skipped"]))
            for m in MODELS:
                acct = min(FROZEN["start"], eq[rid][m])
                n = len(ours)
                each = FROZEN["per_trade"] if n * FROZEN["per_trade"] <= acct else (max(acct, 0.0) / n if n else 0.0)
                cmp(f"{d} {rid}", f"notional {m}", each, out["notional"][m], 0.01)
                for a, b in zip(ours, theirs):
                    q = each / a["entry"]
                    p = q * (a["entry"] - a["exit"]) - q * a["entry"] * _cost_bps(m, a["entry"], a["adv"]) / 1e4 \
                        - q * a["exit"] * _cost_bps(m, a["exit"], a["adv"]) / 1e4 - each * _fee(m, a["etb"])
                    a.setdefault("pnl", {})[m] = p
                    cmp(f"{d} {rid} {a['ticker']}", f"pnl {m}", p, b["pnl"][m], 0.01)
                eq[rid][m] += sum(a["pnl"][m] for a in ours)
                cmp(f"{d} {rid}", f"equity {m}", eq[rid][m], out["equity"][m], 0.01)
            for a, b in zip(ours, theirs):
                checked += 1
                for k in ("entry_ts", "exit_ts", "kind"):
                    cmp(f"{d} {rid} {a['ticker']}", k, a[k], b[k])
                for k in ("entry", "exit"):
                    cmp(f"{d} {rid} {a['ticker']}", k, a[k], b[k], 1e-6)
                cmp(f"{d} {rid} {a['ticker']}", "easy_to_borrow", a["etb"], b["easy_to_borrow"])
            trades_all[rid] += ours

    # summary
    cmp("summary", "days", len(ledger), summary["days"])
    cmp("summary", "first_session", days[0] if days else summary.get("first_session"), summary.get("first_session"))
    cmp("summary", "last_session", days[-1] if days else None, summary.get("last_session"))
    spy_ret = 100 * (spy - 1)
    cmp("summary", "benchmark.ret_pct", round(spy_ret, 2), summary["benchmark"]["ret_pct"], 0.01)
    by_id = {r["id"]: r for r in summary["rules"]}
    for rid in FROZEN["rules"]:
        r, ts = by_id[rid], trades_all[rid]
        n = len(ts)
        cmp(rid, "trades", n, r["trades"])
        cmp(rid, "won_pct", round(100 * sum(1 for t in ts if t["pnl"]["realistic"] > 0) / n) if n else None,
            r["won_pct"])
        cmp(rid, "stops", sum(1 for t in ts if t["kind"] == "stop"), r["stops"])
        cmp(rid, "hard_to_borrow_trades", sum(1 for t in ts if t["etb"] is False), r["hard_to_borrow_trades"])
        cmp(rid, "unknown_borrow_trades", sum(1 for t in ts if t["etb"] is None), r["unknown_borrow_trades"])
        for m in MODELS:
            path, peak, mdd, e = [], FROZEN["start"], 0.0, FROZEN["start"]
            for ln in ledger:
                day_ts = [t for t in ts if dt.datetime.fromtimestamp(t["entry_ts"], ET).date().isoformat() == ln["day"]]
                e += sum(t["pnl"][m] for t in day_ts)
                peak = max(peak, e)
                mdd = min(mdd, e / peak - 1)
            c = r["costs"][m]
            cmp(rid, f"{m}.end", e, c["end"], 0.01)
            cmp(rid, f"{m}.ret_pct", 100 * (e / FROZEN["start"] - 1), c["ret_pct"], 0.01)
            cmp(rid, f"{m}.max_drawdown_pct", 100 * mdd, c["max_drawdown_pct"], 0.01)
            if m == "realistic":
                ret = round(100 * (e / FROZEN["start"] - 1), 2)
                cmp(rid, "vs_spy_pts", ret - round(spy_ret, 2), r["vs_spy_pts"], 0.011)
                w = "Not enough trades" if n < 30 else "No" if ret < 0 else \
                    "Yes" if ret - spy_ret >= 2 else "Barely" if ret - spy_ret > -2 else "No"
                cmp(rid, "word", w, r["word"])
        if n >= FROZEN["min_trades_random"]:
            twin = 0.0
            for ln in ledger:
                daily = _daily(ln["day"])
                for sym in FROZEN["rules"][rid]["tickers"]:
                    rows, raw = daily["split"].get(sym, []), daily["raw"].get(sym, [])
                    j, k = _row(rows, ln["day"]), _row(raw, ln["day"])
                    if not j or k is None or round(rows[j][1] / rows[j - 1][4] - 1, 9) < FROZEN["rules"][rid]["gap"] / 100:
                        continue
                    o, c = rows[j][1], rows[j][4]
                    q = FROZEN["per_trade"] / o
                    twin += q * (o - c) - FROZEN["per_trade"] * _cost_bps("base", raw[k][1], 0) / 1e4 \
                        - q * c * _cost_bps("base", raw[k][4], 0) / 1e4
            cmp(rid, "vs_random.twin_pnl_usd", twin, (r["vs_random"] or {}).get("twin_pnl_usd"), 0.01)
            unverifiable.append(f"{rid}: vs_random band and rank (seeded simulation)")
        else:
            cmp(rid, "vs_random (under 30 trades)", None, r["vs_random"])
    return {"pass": not mism, "sessions_checked": len(ledger), "trades_checked": checked,
            "mismatches": len(mism), "details": mism[:200], "unverifiable": unverifiable}
