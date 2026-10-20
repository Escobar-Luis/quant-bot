"""Independent recompute of results/strategy-lab.json (contracts.md, section strategy-lab; the pre-registered spec
notes/research/strategy-as-code.md). Written from the contract and the spec, never importing app/backtest. Reads only
cached files: data/bars/lab_daily/ (daily bars) and data/bars/alpaca_1m/ (1-minute bars), data/lab/assets.json
(borrow flags). Never fetches: a missing file is a MissingBar.

Checks every run's trades, P&L, return, win rate, max drawdown, longest losing streak, worst day, word, the two
stress cost models, the borrow charge and the post-cutoff slice, plus SPY's total return and the verdict.
Tolerance: $0.01 on money, 0.01 pt on percents (0.1 pt on win rate, rounded), counts and words exact.
The versus-random band is a seeded simulation and is not recomputed (listed as unverifiable).
"""
import datetime as dt
import json
from pathlib import Path

from .bars import ET, MissingBar
from .paths import BARS, DATA, RESULTS

LAB = RESULTS / "strategy-lab.json"

# Transcribed from the spec (notes/research/strategy-as-code.md: pre-registered at eb6c3e8, sections 2-6; the
# corrected list `new-hot-raw` from section 8, the PR #71 deviation). The audit computes from these, never from
# what the results file says, and fails when the file declares anything different.
SPEC = {
    "window": {"from": "2025-09-15", "to": "2026-10-16", "slice_from": "2026-07-01"}, "daily_from": "2025-07-15",
    "universes": {
        "his-hot": ["AFRM", "AI", "CVNA", "DJT", "GME", "HIMS", "OPEN", "PLTR", "RDDT", "SMCI", "SOFI", "SOUN", "TEM"],
        "his-crypto": ["COIN", "HOOD", "MARA", "MSTR"],
        "new-hot": ["SOGP", "IPDN", "ORBS", "OPAD", "NEGG", "CWD", "WLDS", "ONDS", "BMNR", "AAOI", "RUN", "SEDG",
                    "BLSH", "UUUU", "SBET", "APLD", "CRCL", "SMR", "PL", "PGY"],
        "new-crypto": ["HUT", "KEEL", "HIVE", "BTBT", "BTDR", "IREN", "CIFR", "GLXY", "WULF", "LUNR"],
        "new-hot-raw": ["SOGP", "ORBS", "NEGG", "CWD", "WLDS", "ONDS", "BMNR", "AAOI", "RUN", "SEDG", "BLSH", "UUUU",
                        "SBET", "APLD", "CRCL", "SMR", "PL", "PGY", "SKYD", "QS"]},
    "rules": {"S4": {"entry_et": "09:45", "universes": ["his-hot", "new-hot", "new-hot-raw"]},
              "S5": {"entry_et": "09:35", "universes": ["his-crypto", "new-crypto"]},
              "C": {"entry_et": "09:30", "universes": ["his-hot", "his-crypto", "new-hot", "new-crypto", "new-hot-raw"]}},
    "variants": {"P": {"gap_pct": 5, "stop_pct": 5, "exit_et": "15:55"},
                 "no-stop": {"gap_pct": 5, "stop_pct": None, "exit_et": "15:55"},
                 "exit-11": {"gap_pct": 5, "stop_pct": 5, "exit_et": "11:00"},
                 "gap-10": {"gap_pct": 10, "stop_pct": 5, "exit_et": "15:55"}},
    "preregistered_sha": "eb6c3e8",
}


def _daily(sym: str, adj: str, d0: str, d1: str) -> dict:
    p = BARS / "lab_daily" / f"{sym}_{adj}_{d0}_{d1}.json"
    if not p.exists():
        raise MissingBar(f"{sym} {adj} daily {d0}..{d1}: not cached")
    return json.loads(p.read_text())


def _minutes(sym: str, day: str) -> list[tuple[int, list]]:
    p = BARS / "alpaca_1m" / sym / f"{day}.json"
    if not p.exists():
        raise MissingBar(f"{sym} {day}: no cached 1-minute bars")
    return sorted((int(k), v) for k, v in json.loads(p.read_text()).items())


def _et(day: str, hm: str) -> int:
    h, m = (int(x) for x in hm.split(":"))
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), ET).timestamp())


def _side_cost(model: str, px: float, adv: float) -> float:
    """Per-side cost as a fraction of the fill's value (spec sections 5 and 5b; contracts rule 5's cases:
    realistic = small_cap, x2_realistic = it doubled)."""
    if model in ("small_cap", "x2_realistic"):
        b = 50 if px < 5 else (30 if px < 10 else 5)
        if adv < 50e6:
            b += 10
        return (2 * b if model == "x2_realistic" else b) / 1e4
    b = 5 if px >= 10 else 20
    return (2 * b if model == "x2" else b) / 1e4


# contracts rule 5 (story 29): one day of borrow fee per lab trade (all intraday shorts), annual rate by flag
RATE = {True: 0.005, False: 0.30, None: 0.30}
CASE_MODEL = {"simple": "base", "realistic": "small_cap", "x2": "x2_realistic"}


def _outcome(n: int, ret: float) -> str:
    return "No trades" if n == 0 else "Made money" if ret > 0 else "Lost money" if ret < 0 else "Broke even"


def _word(n: int, ret: float, bench: float) -> str:
    if n < 30:
        return "Not enough trades"
    if ret < 0 or ret - bench <= -2:
        return "No"
    return "Yes" if ret - bench >= 2 else "Barely"


def _adv20(raw: dict, day: str) -> float:
    prior = sorted(k for k in raw if k < day)[-20:]
    if not prior:
        return 0.0
    return sum(raw[k][3] * raw[k][4] for k in prior) / len(prior)


def _gap_days(split: dict, pct: float, d0: str, d1: str) -> list[str]:
    keys = sorted(split)
    # the lab's tolerance (spec section 8 item 4): the gap rounded to 9 decimals
    return [b for a, b in zip(keys, keys[1:]) if d0 <= b <= d1 and round(split[b][0] / split[a][3] - 1, 9) >= pct / 100]


def _fill_short(rows: list, day: str, entry_hm: str, stop_pct, exit_hm: str):
    t_in, t_out = _et(day, entry_hm), _et(day, exit_hm)
    live = [(k, v) for k, v in rows if k >= t_in]
    if not live:
        return None
    k0, v0 = live[0]
    px_in = v0[0]
    lvl = None if stop_pct is None else px_in * (1 + stop_pct / 100)
    for k, (o, h, *_rest) in live:
        if k >= t_out:
            return k0, px_in, o
        if lvl is not None and h >= lvl:
            return k0, px_in, (o if o > lvl else lvl)
    return k0, px_in, rows[-1][1][3]


def recompute(d: dict) -> dict:
    """{(rule, variant, universe): numbers} and SPY's, from the cached bars and the spec's parameters."""
    w = SPEC["window"]
    d0, d1 = SPEC["daily_from"], w["to"]
    spy = _daily("SPY", "all", d0, d1)
    cal = [k for k in sorted(spy) if w["from"] <= k <= w["to"]]

    def spy_from(start: str) -> float:
        before = max(k for k in spy if k < start)
        return 100 * (spy[cal[-1]][3] / spy[before][3] - 1)

    spy_ret, spy_slice = spy_from(w["from"]), spy_from(w["slice_from"])
    flags = json.loads((DATA / "lab" / "assets.json").read_text())   # true / false / null (unknown: not hard)
    unis = SPEC["universes"]
    entry_at = {k: r["entry_et"] for k, r in SPEC["rules"].items()}
    out = {}
    for run in d["runs"]:
        rid, vid, uid = run["rule"], run["variant"], run["universe"]
        fills = []   # (day, entry_ts, ticker, px_in, px_out, adv, hard_to_borrow)
        for t in unis[uid]:
            split, raw = _daily(t, "split", d0, d1), _daily(t, "raw", d0, d1)
            if rid == "C":
                keys = sorted(split)
                for a, b in zip(keys, keys[1:]):
                    if w["from"] <= b <= w["to"]:
                        k = raw[b][0] / split[b][0]
                        fills.append((b, _et(b, "09:30"), t, split[b][0] * k, split[b][3] * k, _adv20(raw, b),
                                      flags.get(t) is False, flags.get(t)))
                continue
            v = SPEC["variants"][vid]
            for day in _gap_days(split, v["gap_pct"], w["from"], w["to"]):
                f = _fill_short(_minutes(t, day), day, entry_at[rid], v["stop_pct"], v["exit_et"])
                if f:
                    fills.append((day, f[0], t, f[1], f[2], _adv20(raw, day), flags.get(t) is False, flags.get(t)))
        res = {}
        for model in ("base", "x2", "small_cap", "borrow", "case:simple", "case:realistic", "case:x2"):
            case = model[5:] if model.startswith("case:") else None
            cash_pnl, eq_peak, worst_dd, rows, lent = 0.0, 10_000.0, 0.0, [], 0.0
            for day in cal:
                todays = sorted((f for f in fills if f[0] == day), key=lambda f: (f[1], f[2]))
                if todays:
                    room = min(10_000.0, 10_000.0 + cash_pnl)
                    size = 1_000.0 if 1_000.0 * len(todays) <= room else max(room, 0.0) / len(todays)
                    for f in todays:
                        sh = size / f[3]
                        cm = "base" if model == "borrow" else CASE_MODEL[case] if case else model
                        p = sh * (f[3] - f[4]) - sh * f[3] * _side_cost(cm, f[3], f[5]) \
                            - sh * f[4] * _side_cost(cm, f[4], f[5])
                        if model == "borrow" and f[6]:
                            p -= size * 0.004
                        if case and case != "simple":
                            fee = size * RATE[f[7]] * (2 if case == "x2" else 1) / 360
                            p -= fee
                            lent += fee
                        rows.append((f[0], f[1], f[2], p))
                        cash_pnl += p
                eq = 10_000.0 + cash_pnl
                eq_peak = max(eq_peak, eq)
                worst_dd = min(worst_dd, eq / eq_peak - 1)
            res[model] = (cash_pnl, worst_dd, rows, lent)
        pnl, dd, rows, _ = res["base"]
        n = len(rows)
        ret = pnl / 100
        lose = run_len = 0
        for r in sorted(rows, key=lambda r: (r[1], r[2])):
            run_len = run_len + 1 if r[3] <= 0 else 0
            lose = max(lose, run_len)
        per_day = {}
        for r in rows:
            per_day[r[0]] = per_day.get(r[0], 0.0) + r[3]
        worst = min(per_day.items(), key=lambda kv: (kv[1], kv[0])) if per_day else None
        sl = [r for r in rows if r[0] >= w["slice_from"]]
        sl_ret = sum(r[3] for r in sl) / 100
        out[(rid, vid, uid)] = {
            "trades": n, "won_pct": round(100 * sum(r[3] > 0 for r in rows) / n) if n else None,
            "pnl_usd": pnl, "ret_pct": ret, "max_drawdown_pct": 100 * dd, "longest_losing_streak": lose,
            "worst_day": worst, "word": _word(n, ret, spy_ret),
            "x2": res["x2"][0] / 100, "small_cap": res["small_cap"][0] / 100, "borrow_high": res["borrow"][0] / 100,
            "htb_trades": sum(1 for f in fills if f[6]),
            "cases": {c: {"pnl_usd": res[f"case:{c}"][0], "ret_pct": res[f"case:{c}"][0] / 100,
                          "word": _word(len(res[f"case:{c}"][2]), res[f"case:{c}"][0] / 100, spy_ret),
                          "outcome": _outcome(len(res[f"case:{c}"][2]), res[f"case:{c}"][0] / 100),
                          "borrow_usd": res[f"case:{c}"][3]} for c in CASE_MODEL},
            "slice_trades": len(sl), "slice_ret": sl_ret, "slice_word": _word(len(sl), sl_ret, spy_slice)}
    return {"spy": spy_ret, "spy_slice": spy_slice, "runs": out}


def check(path: Path = LAB) -> dict:
    d = json.loads(path.read_text())
    mine = recompute(d)
    bad = []

    def cmp(where, field, theirs, ours, tol):
        same = theirs == ours if tol is None else (theirs is not None and ours is not None
                                                    and abs(theirs - ours) <= tol + 1e-9)
        if not same:
            bad.append({"kind": "strategy_lab", "where": where, "field": field, "theirs": theirs,
                        "ours": ours if not isinstance(ours, float) else round(ours, 4)})

    cmp("declared", "window", {k: d["window"][k] for k in ("from", "to", "slice_from")}, SPEC["window"], None)
    cmp("declared", "preregistered_sha", d["preregistered_sha"], SPEC["preregistered_sha"], None)
    cmp("declared", "universes", {u["id"]: u["tickers"] for u in d["universes"]}, SPEC["universes"], None)
    cmp("declared", "rules", {r["id"]: {"entry_et": r["entry_et"], "universes": r["universes"]} for r in d["rules"]},
        SPEC["rules"], None)
    cmp("declared", "variants", {v["id"]: {k: v[k] for k in ("gap_pct", "stop_pct", "exit_et")} for v in d["variants"]},
        SPEC["variants"], None)
    expected = sorted((r, v, u) for r, x in SPEC["rules"].items() for u in x["universes"]
                      for v in (["control"] if r == "C" else list(SPEC["variants"])))
    cmp("declared", "runs", sorted((r["rule"], r["variant"], r["universe"]) for r in d["runs"]), expected, None)
    cmp("benchmark", "ret_pct", d["benchmark"]["ret_pct"], mine["spy"], 0.01)
    cmp("benchmark", "slice.ret_pct", d["benchmark"]["slice"]["ret_pct"], mine["spy_slice"], 0.01)
    for r in d["runs"]:
        k = (r["rule"], r["variant"], r["universe"])
        m, where = mine["runs"][k], "|".join(k)
        cmp(where, "trades", r["trades"], m["trades"], None)
        cmp(where, "won_pct", r["won_pct"], m["won_pct"], None)
        cmp(where, "pnl_usd", r["pnl_usd"], m["pnl_usd"], 0.01)
        cmp(where, "ret_pct", r["ret_pct"], m["ret_pct"], 0.01)
        cmp(where, "max_drawdown_pct", r["max_drawdown_pct"], m["max_drawdown_pct"], 0.01)
        cmp(where, "longest_losing_streak", r["longest_losing_streak"], m["longest_losing_streak"], None)
        if m["worst_day"]:
            cmp(where, "worst_day.day", (r["worst_day"] or {}).get("day"), m["worst_day"][0], None)
            cmp(where, "worst_day.pnl_usd", (r["worst_day"] or {}).get("pnl_usd"), m["worst_day"][1], 0.01)
        cmp(where, "word", r["word"], m["word"], None)
        cmp(where, "costs.x2.ret_pct", r["costs"]["x2"]["ret_pct"], m["x2"], 0.01)
        cmp(where, "costs.small_cap.ret_pct", r["costs"]["small_cap"]["ret_pct"], m["small_cap"], 0.01)
        cmp(where, "borrow.borrow_high_ret_pct", r["borrow"]["borrow_high_ret_pct"], m["borrow_high"], 0.01)
        cmp(where, "borrow.htb_trades", r["borrow"]["htb_trades"], m["htb_trades"], None)
        cmp(where, "slice.trades", r["slice"]["trades"], m["slice_trades"], None)
        cmp(where, "slice.ret_pct", r["slice"]["ret_pct"], m["slice_ret"], 0.01)
        cmp(where, "slice.word", r["slice"]["word"], m["slice_word"], None)
        for c, mc in m["cases"].items():   # contracts rule 5's three cost cases (story 29)
            rc = (r.get("cost_cases") or {}).get(c) or {}
            for f, tol in (("pnl_usd", 0.01), ("ret_pct", 0.01), ("borrow_usd", 0.01), ("word", None),
                           ("outcome", None)):
                cmp(where, f"cost_cases.{c}.{f}", rc.get(f), mc[f], tol)
    for rule, v in d["verdict"].items():
        prim = [mine["runs"][k] for k in mine["runs"] if k[0] == rule and k[1] == "P" and k[2] != "new-hot-raw"]
        cmp(f"verdict|{rule}", "held_up", v["held_up"], bool(prim) and all(p["word"] == "Yes" for p in prim), None)
    fix = [mine["runs"][k] for k in mine["runs"] if k[0] == "S4" and k[1] == "P" and k[2] in ("his-hot", "new-hot-raw")]
    cmp("verdict|S4", "corrected_list.held_up", d["verdict"]["S4"].get("corrected_list", {}).get("held_up"),
        bool(fix) and all(p["word"] == "Yes" for p in fix), None)
    return {"file": "strategy-lab", "pass": not bad, "runs_checked": len(d["runs"]), "mismatches": len(bad),
            "unverifiable": ["vs_random (seeded simulation, not recomputed)"], "details": bad}


if __name__ == "__main__":
    rep = check()
    print(json.dumps({k: v for k, v in rep.items() if k != "details"}, indent=1))
    for b in rep["details"][:30]:
        print(b)
