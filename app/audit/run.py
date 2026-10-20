"""Audit the money math: rebuild every position, recompute every copied trade and headline, reconcile with results/.

  cd app && uv run python -m audit.run                 # every results/<course>/<version>.json
  cd app && uv run python -m audit.run --only lpp/v1   # one file

For each results file:
  1. positions: the audit builds its own (audit.positions, from the events and contracts.md) and diffs them field
     by field with the course loaders' (backtest.<course>.build); every difference is a finding;
  2. the engine's full ledger (data/audit/<course>-<version>-ledger.jsonl, from `python -m backtest.run`) must be
     stamped with the sha256 of this exact results file, else it is stale and the file fails;
  3. trades: the audit's own positions go through the second calculator (audit.calc) at every delay; each trade
     (status, entry and exit time and price, P&L, and every fill) is checked against the ledger, and the trades
     the results file shows are checked directly: 1 cent at stored precision, times exact;
  4. headlines, per testable portfolio and delay (plus `same_sessions` and LPP's `as_taught_stitched`, rule
     11's ledger and sizing, rebuilt by the audit's own rule 11 ledger): end, return, just-holding end and
     return, trades, not_triggered, couldnt_copy, sized_down, won_pct, worst_drop_pct, word and the sealed block;
  5. by_year (when the file has it): every calendar year and all time, per portfolio and delay, recomputed by
     audit.years from the audit's own trades and the cached daily closes and dividends; `all` must also equal
     the headline's end, return and trades;
  6. strategy_profile (LPP's full-window file): every table, setup, rule (and its keep rule), losing pattern
     (and its selection) and worst day, recomputed by audit.strategy from the audit's own trades at 5 min;
  7. improvements (LPP's full-window file): every variant's change re-applied to the audit's own positions,
     re-priced by audit.calc, its dev and sealed numbers, SPY's total return and the keep decision
     (audit.improvements).
  Then results/strategy-lab.json (when present, on a full run): every run recomputed by audit.lab from the cached
  bars (contracts.md section strategy-lab), written to data/audit/diff-strategy-lab.json; and results/paper/
  (the forward paper test, CAP-18) recomputed by audit.paper from data/paper/daily/ and the 1-minute cache, written
  to data/audit/diff-paper.json.
Writes data/audit/diff-<course>-<version>.json (every compared trade and fill, every finding) and
proofs/audit.json (the pass record; `python -m audit.gate` reads it). Exits 0 only when everything reconciles.
No network: a bar missing from data/bars/ marks that trade no_bars; trades both sides call no_bars are listed
as `unverifiable`.
"""
import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import calc, improvements, lab, paper, strategy, years
from . import positions as P
from .paths import DATA, PROOFS, REPO, RESULTS

TRADE_TOL = 0.01      # 1 cent
HEAD_TOL = 1.0        # $1
RET_TOL = 0.01        # $1 on $10,000, in points
DROP_TOL = 0.1        # worst_drop_pct is stored to 0.1 pt
EXACT = ("trades", "word", "outcome", "vs", "not_triggered", "couldnt_copy", "sized_down", "won_pct")
MONEY = ("end", "hold_end")
POINTS = ("ret_pct", "hold_ret_pct")
HEAD_FIELDS = ("end", "ret_pct", "hold_end", "hold_ret_pct", "trades", "not_triggered", "couldnt_copy",
               "sized_down", "won_pct", "worst_drop_pct", "word", "outcome", "vs", "sealed")
SEALED_EXACT = ("trades", "word", "outcome", "vs")
MARKET = {"lpp": "us_equities", "ziptrader": "us_equities", "cryptowizard": "crypto"}
HOLD_BARS = {"SPY": "SPY", "BTC": "BTCUSDT"}

NOTES = {
    "sizing": "LPP sizing 'known' (rule 13e, no look-ahead, the headline: the first buy is $1,000, each add "
              "sized from the counts he had stated by then; a trim sells his stated share of his holding). "
              "'trade' (rule 6 as taught: all of a trade's buys together are $1,000, which reads later adds) is "
              "checked on the results file's `as_taught_stitched` block.",
    "ledger": "LPP positions follow contracts.md rule 13 (the headline since spec-audit story 18: overnight only "
              "on a hold said before 15:55 ET); rule 11's ledger (reads his next word) is rebuilt for "
              "`as_taught_stitched`.",
    "cash": "Rule 6's cash cap is applied per buy as it fills (2026-10-20), never reserving money for later adds.",
    "hold_close": "Just holding ends at the official daily close (what a holder gets: data/bars/daily); the last "
                  "1-minute bar's close is reported as an alternative (--hold-close minute).",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_ledger(path: Path) -> tuple[dict | None, dict | None]:
    """(stamp, {(pid, delay): row}); (None, None) when the file is missing; stamp None when unstamped."""
    if not path.exists():
        return None, None
    meta, out = None, {}
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        if "_meta" in r:
            meta = r["_meta"]
            continue
        out[(r["pid"], r["delay"])] = r
    return meta, out


def engine_row(r: dict) -> dict:
    """A ledger row as the trade fields results/ stores (entry = first entry fill, exit = last exit fill)."""
    if r["status"] != "priced":
        return {"status": r["status"]}
    fills = r.get("fills") or []
    entry = next((f for f in fills if f[3] == "entry"), None)
    exit_ = next((f for f in reversed(fills) if f[3] != "entry"), None)
    if entry is None or exit_ is None:
        return {"status": "priced:broken", "why": "ledger row has no entry fill" if entry is None
                else "ledger row has no exit fill"}
    return {"status": "priced", "entry_at": entry[0], "entry": round(entry[1], 4), "exit_at": exit_[0],
            "exit": round(exit_[1], 4), "pnl": round(r["pnl"], 2),
            "fills": [[f[0], round(f[1], 6), round(f[2], 8), f[3]] for f in fills]}


def stored_row(row: dict) -> dict:
    """A results/ trade row (one delay) in the same shape."""
    if "status" in row:
        return {"status": row["status"]}
    return {"status": "priced", "entry_at": calc.B.to_ts(row["entry_at"]), "entry": row["entry"],
            "exit_at": calc.B.to_ts(row["exit_at"]), "exit": row["exit"], "pnl": row["pnl"]}


def audit_row(t: calc.Trade) -> dict:
    if t.status != "priced":
        return {"status": t.status, **({"why": t.why} if t.why else {})}
    if t.entry is None or t.exit is None:
        return {"status": "priced:broken", "why": "audit trade has no entry or exit fill"}
    return {"status": "priced", "entry_at": t.entry.ts, "entry": round(t.entry.px, 4), "exit_at": t.exit.ts,
            "exit": round(t.exit.px, 4), "pnl": round(t.pnl, 2),
            "fills": [[f.ts, round(f.px, 6), round(f.qty, 8), f.kind] for f in t.fills]}


def compare_fills(where: str, pid: str, delay: int, theirs: list, ours: list, out: list) -> None:
    """Every fill (entries, adds, trims, targets, stops, default exits): same count, time, kind, price, shares."""
    a, b = sorted(theirs, key=lambda f: (f[0], f[3])), sorted(ours, key=lambda f: (f[0], f[3]))
    if len(a) != len(b):
        out.append({"kind": "fill", "against": where, "pid": pid, "delay": delay, "field": "count",
                    "theirs": len(a), "ours": len(b)})
        return
    for i, (x, y) in enumerate(zip(a, b)):
        bad = [f for f, ok in (("ts", int(x[0]) == int(y[0])), ("kind", x[3] == y[3]),
                               ("px", abs(x[1] - y[1]) <= 1e-4),
                               ("qty", abs(x[2] - y[2]) <= 1e-6 * max(1.0, abs(x[2])))) if not ok]
        if bad:
            out.append({"kind": "fill", "against": where, "pid": pid, "delay": delay, "field": "+".join(bad),
                        "fill": i, "theirs": x, "ours": y})


def compare_trade(where: str, pid: str, delay: int, theirs: dict, ours: dict, out: list) -> float:
    """Append mismatches; return the largest money difference seen."""
    worst = 0.0
    if theirs["status"] != ours["status"]:
        out.append({"kind": "trade", "against": where, "pid": pid, "delay": delay, "field": "status",
                    "theirs": theirs["status"], "ours": ours["status"],
                    **({"why": ours["why"]} if ours.get("why") else {}),
                    **({"theirs_why": theirs["why"]} if theirs.get("why") else {})})
        return worst
    if theirs["status"] != "priced":
        return worst
    for f in ("entry_at", "exit_at"):
        if theirs[f] != ours[f]:
            out.append({"kind": "trade", "against": where, "pid": pid, "delay": delay, "field": f,
                        "theirs": calc.B.iso(theirs[f]), "ours": calc.B.iso(ours[f])})
    for f in ("entry", "exit", "pnl"):
        diff = abs(theirs[f] - ours[f])
        worst = max(worst, diff)
        if diff > TRADE_TOL + 1e-9:
            out.append({"kind": "trade", "against": where, "pid": pid, "delay": delay, "field": f,
                        "theirs": theirs[f], "ours": ours[f], "diff": round(diff, 4)})
    if "fills" in theirs and "fills" in ours:
        compare_fills(where, pid, delay, theirs["fills"], ours["fills"], out)
    return worst


def compare_head(portfolio: str, delay: str, theirs: dict, ours: dict, out: list) -> float:
    worst = 0.0

    def miss(f, a, b, diff=None):
        out.append({"kind": "headline", "portfolio": portfolio, "delay": int(delay), "field": f, "theirs": a,
                    "ours": b, **({} if diff is None else {"diff": round(diff, 4)})})

    for f in HEAD_FIELDS:
        if f not in theirs or f not in ours:
            if f in theirs or f in ours:
                miss(f, theirs.get(f, "missing"), ours.get(f, "missing"))
            continue
        a, b = theirs[f], ours[f]
        if f == "sealed":
            for g in ("ret_pct", "hold_ret_pct") + SEALED_EXACT:
                x, y = (a or {}).get(g, "missing"), (b or {}).get(g, "missing")
                if g in SEALED_EXACT or None in (x, y) or "missing" in (x, y):
                    if x != y:
                        miss(f"sealed.{g}", x, y)
                elif abs(x - y) > RET_TOL + 1e-9:
                    miss(f"sealed.{g}", x, y, abs(x - y))
        elif f in EXACT:
            if a != b:
                miss(f, a, b)
        else:
            diff = abs(a - b)
            if f in MONEY:
                worst = max(worst, diff)
            tol = HEAD_TOL if f in MONEY else DROP_TOL if f == "worst_drop_pct" else RET_TOL
            if diff > tol + 1e-9:
                miss(f, a, b, diff)
    return worst


CASE_MONEY = ("end", "costs_usd", "borrow_usd")
CASE_POINTS = ("ret_pct", "hold_ret_pct")
CASE_EXACT = ("trades", "won_pct", "sized_down", "couldnt_copy", "word", "outcome", "vs")


def check_cost_cases(d: dict, mine: dict, same_mine: dict, hold_row: dict, sealed_from, name, market) -> list[dict]:
    """contracts.md section cost_cases: the flags of every ticker the priced trades short (from the cached
    lookups), then every portfolio x delay x case recomputed with calc's own cost code ($1, 0.01 pt, counts and
    words exact); a case row's `simple` must equal the file's headline row."""
    cc, out = d["cost_cases"], []

    def miss(where, field, theirs, ours, diff=None):
        out.append({"kind": "cost_cases", "portfolio": where, "field": field, "theirs": theirs, "ours": ours,
                    **({} if diff is None else {"diff": round(diff, 4)})})

    if cc.get("cases") != list(calc.CASES) or cc.get("default") != "realistic":
        miss("file", "cases", [cc.get("cases"), cc.get("default")], [list(calc.CASES), "realistic"])
    trades = [t for t in list(mine.values()) + list(same_mine.values()) if t.status == "priced"]
    shorted = sorted({t.ticker for t in trades if t.side == "short"})
    cached = calc.read_flags()
    flags = {t: "crypto" if market == "crypto" else cached.get(t, "unknown") for t in shorted}
    theirs_flags = (cc.get("borrow") or {}).get("flags")
    if theirs_flags != flags:
        diff = sorted(t for t in set(flags) | set(theirs_flags or {}) if (theirs_flags or {}).get(t) != flags.get(t))
        miss("file", "borrow.flags", {t: (theirs_flags or {}).get(t) for t in diff[:20]},
             {t: flags.get(t) for t in diff[:20]})
    for k, v in (("shorted_tickers", len(shorted)), ("hard", sum(x == "hard" for x in flags.values())),
                 ("unknown", sum(x == "unknown" for x in flags.values()))):
        if (cc.get("borrow") or {}).get(k) != v:
            miss("file", f"borrow.{k}", (cc.get("borrow") or {}).get(k), v)

    def row(ts, case, bench):
        tot = {}
        r = calc.portfolio(ts, hold_row, sealed_from, bench, name, case, flags, tot)
        return {**r, **tot}

    def cmp(where, dl, theirs, ours):
        for f in CASE_MONEY + CASE_POINTS + CASE_EXACT:
            a, b = theirs.get(f, "missing"), ours.get(f, "missing")
            if f in CASE_EXACT or "missing" in (a, b) or None in (a, b):
                if a != b:
                    miss(f"{where}@{dl}", f, a, b)
            elif abs(a - b) > (HEAD_TOL if f in CASE_MONEY else RET_TOL) + 1e-9:
                miss(f"{where}@{dl}", f, a, b, abs(a - b))
        for g in ("ret_pct", "hold_ret_pct") + SEALED_EXACT:
            x, y = (theirs.get("sealed") or {}).get(g, "missing"), (ours.get("sealed") or {}).get(g, "missing")
            if g in SEALED_EXACT or "missing" in (x, y) or None in (x, y):
                if x != y:
                    miss(f"{where}@{dl}", f"sealed.{g}", x, y)
            elif abs(x - y) > RET_TOL + 1e-9:
                miss(f"{where}@{dl}", f"sealed.{g}", x, y, abs(x - y))

    same = d.get("same_sessions")
    base = {}
    if same:
        got = (cc.get("same_sessions") or {}).get("by_delay") or {}
        for dl in map(str, d["delays_min"]):
            ts = [t for (pid, x), t in same_mine.items() if x == int(dl)]
            for case in calc.CASES:
                ours = base[(dl, case)] = row(ts, case, None)
                cmp(f"same_sessions:{case}", dl, (got.get(dl) or {}).get(case) or {}, ours)
    heads = {p["id"]: p["by_delay"] for p in d["portfolios"] if p.get("testable")}
    got_pf = {p["id"]: p["by_delay"] for p in cc.get("portfolios") or []}
    if sorted(got_pf) != sorted(heads):
        miss("file", "portfolios", sorted(got_pf), sorted(heads))
    for pf_id in heads:
        for dl in map(str, d["delays_min"]):
            ts = [t for (pid, x), t in mine.items() if x == int(dl) and (pf_id == "all" or t.portfolio == pf_id)]
            theirs_all = (got_pf.get(pf_id) or {}).get(dl) or {}
            for case in calc.CASES:
                if not same:
                    bench = "hold"
                elif pf_id == same.get("portfolio", "all"):
                    b = base[(dl, case)]
                    bench = (b["ret_pct"], b["sealed"]["ret_pct"])
                else:
                    bench = None
                cmp(f"{case}:{pf_id}", dl, theirs_all.get(case) or {}, row(ts, case, bench))
            simple, head = theirs_all.get("simple") or {}, heads[pf_id].get(dl) or {}
            for f in ("end", "ret_pct", "trades", "word", "outcome", "vs", "sized_down", "couldnt_copy"):
                if simple.get(f, "missing") != head.get(f, "missing"):
                    miss(f"simple:{pf_id}@{dl}", f"{f} vs headline", simple.get(f, "missing"), head.get(f, "missing"))
    return out


def lpp_sources(version: str) -> set[str]:
    return {e["source_id"] for e in P.rows(P.lpp_events_path(version))}


def audit_file(path: Path, ledger_dir: Path, sizing: str = calc.DEFAULT_SIZING,
               hold_close: str = calc.DEFAULT_HOLD_CLOSE) -> dict:
    d = json.loads(path.read_text())
    course, version = d["course"], d["version"]
    market = MARKET[course]
    symbol = HOLD_BARS.get(d["hold"]["symbol"], d["hold"]["symbol"])
    hold_row = calc.hold(market, symbol, d["window"], hold_close)
    sealed_from = d["window"].get("sealed_from")
    file_sha = sha256(path)
    mismatches: list[dict] = []
    compared: list[dict] = []
    unverifiable: list[str] = []
    position_reports: dict[str, dict] = {}
    loader_math: dict[str, dict] = {}
    worst, checked = 0.0, 0

    def own_positions(ver, only, label, ledger=P.HEADLINE):
        rep = P.compare(course, ver, only, ledger)
        position_reports[label] = {k: rep[k] for k in ("loader_positions", "audit_positions", "differences",
                                                       "positions_differing", "by_field")}
        for x in rep["details"]:
            mismatches.append({**x, "against": f"loader:{label}"})
        return P.build(course, ver, only, ledger)

    # rule 9's benchmark (CAP-7): just holding, named from the hold symbol; a proof-set file (same_sessions) is
    # compared only with v1 on the same sessions, from this audit's own recompute of that baseline
    same = d.get("same_sessions")
    name = same["version"] if same else calc.BENCH.get(d["hold"]["symbol"], d["hold"]["symbol"])
    want_cw = {"kind": "same_sessions" if same else "hold", "name": name}
    if d.get("compare_with") != want_cw:
        mismatches.append({"kind": "headline", "portfolio": "file", "field": "compare_with",
                           "theirs": d.get("compare_with", "missing"), "ours": want_cw})
    if same:
        for k in ("strategies", "ranges", "combos", "best_stop"):
            if k in d:
                mismatches.append({"kind": "headline", "portfolio": "file", "field": k,
                                   "theirs": "present", "ours": "absent in a proof-set file (rule 9)"})
    base_rows: dict[str, dict] = {}     # the audit's own same-sessions rows, by delay

    def bench_for(pf_id, dl, ledger_name):
        if not same:
            return "hold"
        if ledger_name or pf_id != same.get("portfolio", "all"):
            return None                 # the baseline itself, and a proof-set file's other portfolios
        b = base_rows[dl]
        return b["ret_pct"], b["sealed"]["ret_pct"]

    def run_set(positions, ledger_name, portfolios, mm=mismatches, cmp=compared, unv=unverifiable, main=True,
                sz=None):
        nonlocal worst, checked
        mine = {(p.pid, dl): calc.simulate(p, dl, sz or sizing) for p in positions for dl in d["delays_min"]}
        lpath = ledger_dir / f"{course}-{version}{ledger_name}-ledger.jsonl"
        meta, ledger = read_ledger(lpath)
        if ledger is None:
            mm.append({"kind": "missing", "field": "ledger", "theirs": str(lpath),
                       "ours": f"run: cd app && uv run python -m backtest.run --course {course} "
                               f"--version {version} --ledger-only"})
        elif not meta or meta.get("results_sha256") != file_sha:
            mm.append({"kind": "stale", "field": "ledger", "theirs": (meta or {}).get("results_sha256",
                       "unstamped"), "ours": file_sha, "ledger": str(lpath),
                       "fix": f"cd app && uv run python -m backtest.run --course {course} --version "
                              f"{version} --ledger-only"})
        if ledger is not None:
            for k in sorted(set(ledger) - set(mine)):
                mm.append({"kind": "trade", "against": "ledger", "pid": k[0], "delay": k[1],
                           "field": "presence", "theirs": "in engine ledger", "ours": "absent"})
            for (pid, dl), t in mine.items():
                if (pid, dl) not in ledger:
                    mm.append({"kind": "trade", "against": "ledger", "pid": pid, "delay": dl,
                               "field": "presence", "theirs": "absent", "ours": t.status})
                    continue
                theirs, ours = engine_row(ledger[(pid, dl)]), audit_row(t)
                n = len(mm)
                w = compare_trade("ledger", pid, dl, theirs, ours, mm)
                cmp.append({"against": "ledger" + ledger_name, "pid": pid, "delay": dl,
                            "ok": len(mm) == n, "theirs": theirs, "ours": ours})
                if theirs["status"] == ours["status"] == "no_bars":
                    unv.append(f"{pid}@{dl}{ledger_name}")
                if main:
                    worst = max(worst, w)
                    checked += 1
        for pf_id, rows in portfolios:
            for dl, theirs in rows.items():
                ts = [t for (pid, x), t in mine.items() if x == int(dl) and (pf_id == "all" or t.portfolio == pf_id)]
                ours = calc.portfolio(ts, hold_row, sealed_from, bench_for(pf_id, dl, ledger_name), name)
                if ledger_name == "-same_sessions" and main:
                    base_rows[dl] = ours
                w = compare_head(pf_id if ledger_name == "" else f"{ledger_name[1:]}:{pf_id}", dl, theirs, ours,
                                 mm)
                if main:
                    worst = max(worst, w)
        return mine

    def math_only(ver, only, ledger_name, portfolios, ledger=P.HEADLINE, sz=None):
        """The same reconciliation on the loaders' own positions: what is left is the math alone."""
        mm, cmp, unv = [], [], []
        run_set(P.loader_positions(course, ver, only, ledger), ledger_name, portfolios, mm, cmp, unv, main=False,
                sz=sz)
        loader_math[ledger_name or "main"] = {
            "trades_compared": len(cmp), "mismatches": len(mm),
            "by_class": dict(Counter(f"{m['kind']}:{m.get('against', m.get('portfolio', ''))}:{m['field']}"
                                     for m in mm)), "details": mm}

    same_mine = {}
    if same:   # first: its rows are the proof-set headline's benchmark
        srcs = P.lpp_proof_set() if same.get("proof_set") else lpp_sources(version)
        base = own_positions(same["version"], srcs, f"{same['version']}-same_sessions")
        ss = [(same.get("portfolio", "all"), same["by_delay"])]
        same_mine = run_set(base, "-same_sessions", ss)
        math_only(same["version"], srcs, "-same_sessions", ss)

    only = P.lpp_proof_set() if course == "lpp" and d["checks"].get("proof_set") else None
    positions = own_positions(version, only, version)
    pfs = [(p["id"], p["by_delay"]) for p in d["portfolios"] if p.get("testable")]
    mine = run_set(positions, "", pfs)
    math_only(version, only, "", pfs)

    # cost_cases (contracts.md rule 5 and section cost_cases, CAP-17): every testable portfolio and delay under the
    # three cost cases, from this audit's own trades and its own cost code; simple must equal the headline
    cc_note = "absent"
    if not d.get("cost_cases"):
        mismatches.append({"kind": "missing", "field": "cost_cases", "theirs": "absent",
                           "ours": "expected in every course file (contracts.md section cost_cases)"})
    else:
        try:
            found = check_cost_cases(d, mine, same_mine, hold_row, sealed_from, name, market)
        except calc.B.MissingBar as e:
            found = [{"kind": "missing", "field": "cost_cases", "theirs": "cost_cases", "ours": str(e)}]
        mismatches.extend(found)
        cc_note = {"cases": d["cost_cases"].get("cases"), "mismatches": len(found),
                   "shorted_tickers": len(d["cost_cases"].get("borrow", {}).get("flags") or {})}

    # by_year (contracts.md section by_year): every file but a proof-set one (rule 9) carries it, for every
    # testable portfolio and delay the file has; the expected list comes from the portfolios, not from by_year
    by_year_note = "absent"
    expected = [p["id"] for p in d["portfolios"] if p.get("testable")]
    if d.get("same_sessions"):
        if d.get("by_year"):
            mismatches.append({"kind": "by_year", "portfolio": "file", "field": "present",
                               "theirs": "by_year", "ours": "none in a proof-set file (rule 9)"})
    elif not d.get("by_year"):
        mismatches.append({"kind": "missing", "field": "by_year", "theirs": "absent", "ours": "expected"})
    else:
        try:
            hv = years.hold_values(market, symbol, d["window"])
            mismatches.extend(years.compare(d["by_year"], mine, expected, d["delays_min"], hv, name,
                                            HEAD_TOL, RET_TOL))
            by_year_note = {"periods": [p["id"] for p in years.periods(hv)], "hold_basis": hv["basis"],
                            "dividends": hv["dividends"]}
        except calc.B.MissingBar as e:
            mismatches.append({"kind": "missing", "field": "by_year", "theirs": "by_year", "ours": str(e)})
        heads = {p["id"]: p["by_delay"] for p in d["portfolios"] if p.get("testable")}
        for pid in expected:
            rows_by_delay = ((d["by_year"].get("portfolios") or {}).get(pid) or {}).get("by_delay") or {}
            for dl in map(str, d["delays_min"]):
                h, a = heads[pid].get(dl) or {}, (rows_by_delay.get(dl) or {}).get("all") or {}
                for f in ("end", "ret_pct", "trades", "outcome"):   # word and vs may differ: total-return holding
                    if f not in h or a.get(f, "missing") != h[f]:
                        mismatches.append({"kind": "by_year", "portfolio": f"{pid}@{dl}:all",
                                           "field": f"{f} vs headline", "theirs": a.get(f, "missing"),
                                           "ours": h.get(f, "missing")})

    # strategy_profile (contracts.md section strategy_profile, CAP-14): every number recomputed from this audit's
    # own trades; LPP's full-window file must carry it, a proof-set file must not (rule 9)
    sp_note = "absent"
    if d.get("strategy_profile"):
        if same:
            mismatches.append({"kind": "strategy_profile", "portfolio": "file", "field": "present",
                               "theirs": "strategy_profile", "ours": "none in a proof-set file (rule 9)"})
        else:
            head = next(p["by_delay"] for p in d["portfolios"] if p["id"] == d["strategy_profile"]["portfolio"])
            found = strategy.check(d["strategy_profile"], mine, head[str(d["strategy_profile"]["delay_min"])],
                                   version)
            mismatches.extend(found)
            sp_note = {"rules": len(d["strategy_profile"]["rules"]), "mismatches": len(found)}
    elif course == "lpp" and not same:
        mismatches.append({"kind": "missing", "field": "strategy_profile", "theirs": "absent",
                           "ours": "expected in LPP's full-window file (contracts.md section strategy_profile)"})

    # improvements (contracts.md section improvements, CAP-15): every variant re-applied to the audit's own
    # positions and re-priced; a proof-set file must not carry it (rule 9)
    imp_note = "absent"
    if d.get("improvements"):
        if same:
            mismatches.append({"kind": "improvements", "portfolio": "file", "field": "present",
                               "theirs": "improvements", "ours": "none in a proof-set file (rule 9)"})
        elif not d.get("strategy_profile"):
            mismatches.append({"kind": "improvements", "portfolio": "file", "field": "definitions",
                               "theirs": "improvements", "ours": "needs strategy_profile.definitions"})
        else:
            try:
                found = improvements.check(d["improvements"], mine, version, d["window"],
                                           d["strategy_profile"]["definitions"], market, symbol)
            except calc.B.MissingBar as e:
                found = [{"kind": "missing", "field": "improvements", "theirs": "improvements", "ours": str(e)}]
            mismatches.extend(found)
            imp_note = {"variants": len(d["improvements"].get("variants") or []),
                        "kept": sum(bool(v.get("kept")) for v in d["improvements"].get("variants") or []),
                        "mismatches": len(found)}

    # the trades the results file shows (a sample of up to 200): checked directly, not through the ledger
    for row in d.get("trades") or []:
        for dl, r in row["by_delay"].items():
            t = mine.get((row["trade_id"], int(dl)))
            if t is None:
                mismatches.append({"kind": "trade", "against": "results", "pid": row["trade_id"], "delay": int(dl),
                                   "field": "presence", "theirs": "in results", "ours": "absent"})
                continue
            theirs, ours = stored_row(r), audit_row(t)
            n = len(mismatches)
            worst = max(worst, compare_trade("results", row["trade_id"], int(dl), theirs, ours, mismatches))
            compared.append({"against": "results", "pid": row["trade_id"], "delay": int(dl),
                             "ok": len(mismatches) == n, "theirs": theirs, "ours": ours})
            checked += 1

    if d.get("as_taught_stitched"):
        # rule 11 with rule 6's whole-trade sizing: its own ledger and sizing, beside rule 13's headline
        tp = [(x["id"], x["by_delay"]) for x in d["as_taught_stitched"]["portfolios"]]
        alt = own_positions(version, only, f"{version}-as_taught_stitched", "as_taught")
        run_set(alt, "-as_taught_stitched", tp, sz="trade")
        math_only(version, only, "-as_taught_stitched", tp, "as_taught", "trade")
    elif course == "lpp":
        mismatches.append({"kind": "missing", "field": "as_taught_stitched", "theirs": "absent",
                           "ours": "expected in every LPP file (contracts.md rule 11)"})

    hold_note = {"symbol": symbol, "first_open": hold_row["px0"], "official_close": hold_row["official_close"],
                 "minute_close": hold_row["minute_close"], "used": hold_row["used"],
                 "sealed_first_open": hold_row["sealed_px0"]}
    return {"file": f"{course}/{version}", "results_sha256": file_sha, "sizing": sizing, "hold_close": hold_close,
            "pass": not mismatches, "trades_checked": checked, "mismatches": len(mismatches),
            "max_abs_diff": round(worst, 4), "hold": hold_note, "by_year": by_year_note,
            "strategy_profile": sp_note, "improvements": imp_note, "cost_cases": cc_note,
            "positions": position_reports,
            "unverifiable": sorted(unverifiable),
            "math_on_loader_positions": loader_math,
            "by_class": dict(Counter(f"{m['kind']}:{m.get('against', m.get('portfolio', ''))}:{m['field']}"
                                     for m in mismatches)),
            "details": mismatches, "compared": compared}


def results_git_sha(results_dir: Path) -> str | None:
    out = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(results_dir)], cwd=REPO,
                         capture_output=True, text=True).stdout.strip()
    return out or None


def write_proofs(path: Path, a, rdir: Path, ok: bool, summary: dict, reports: dict) -> None:
    """proofs/audit.json: the default reading at the top level; a run with other readings (--sizing,
    --hold-close) is kept under `alternatives`, so both answers sit side by side. `signoff` stays as Luis left it
    (null until he signs with `python -m audit.gate --sign`); the gate checks its hand-check hash."""
    default = a.sizing == calc.DEFAULT_SIZING and a.hold_close == calc.DEFAULT_HOLD_CLOSE
    run = {"generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "results_git_sha": results_git_sha(rdir), "pass": ok, "sizing": a.sizing, "hold_close": a.hold_close,
           "command": "cd app && uv run python -m audit.run"
                      + ("" if default else f" --sizing {a.sizing} --hold-close {a.hold_close}"),
           "files": summary}
    old = json.loads(path.read_text()) if path.exists() else {}
    if default:
        rec = {"schema": "audit/2", **run,
               "results_sha256": {k: r["results_sha256"] for k, r in reports.items()}
               | ({"strategy-lab": hashlib.sha256((rdir / "strategy-lab.json").read_bytes()).hexdigest()}
                  if "strategy-lab" in summary else {})
               | ({"paper/summary": hashlib.sha256((rdir / "paper" / "summary.json").read_bytes()).hexdigest()}
                  if "paper/summary" in summary else {}),
               "tolerance": {"trade": "1 cent (prices 4 dp, P&L 2 dp; times exact; every fill's time, kind, "
                                      "price and shares)",
                             "headline": "$1 (returns and sealed 0.01 pts; worst drop 0.1 pt; trades, counts, "
                                         "won_pct and word exact)"},
               "notes": NOTES,
               "positions": {k: r["positions"] for k, r in reports.items()},
               "unverifiable": {k: r["unverifiable"] for k, r in reports.items() if r["unverifiable"]},
               "signoff": old.get("signoff"),
               "findings": old.get("findings"),   # refreshed by python -m audit.findings (run it after this)
               "alternatives": {k: v for k, v in old.get("alternatives", {}).items()
                                if v.get("results_git_sha") == run["results_git_sha"]}}
    else:
        rec = old or {"schema": "audit/2", "signoff": None}
        rec.setdefault("alternatives", {})[f"sizing={a.sizing},hold_close={a.hold_close}"] = run
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(RESULTS))
    ap.add_argument("--ledger-dir", default=str(DATA / "audit"))
    ap.add_argument("--out-dir", default=str(DATA / "audit"))
    ap.add_argument("--proofs", default=str(PROOFS / "audit.json"), help="'' to skip writing it")
    ap.add_argument("--sizing", choices=calc.SIZINGS, default=calc.DEFAULT_SIZING,
                    help="LPP sizing: known = rule 13(e), no look-ahead (default, the headline); trade = rule 6 "
                         "as taught, all of a trade's buys together are $1,000; first = his first entry is "
                         "$1,000, adds at the same factor")
    ap.add_argument("--hold-close", choices=calc.HOLD_CLOSES, default=calc.DEFAULT_HOLD_CLOSE,
                    help="rule 7's last price: official = the session close (daily cache); minute = last 1-min bar")
    ap.add_argument("--only", action="append", help="course/version, e.g. lpp/v1 (repeatable)")
    a = ap.parse_args(argv)
    rdir, out_dir = Path(a.results_dir), Path(a.out_dir)
    files = sorted(p for p in rdir.glob("*/*.json") if p.parent.name != "paper"   # results/paper/: audit.paper
                   and (not a.only or f"{p.parent.name}/{p.stem}" in a.only))
    if not files:
        print("no results files found", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    summary, reports = {}, {}
    for p in files:
        rep = audit_file(p, Path(a.ledger_dir), a.sizing, a.hold_close)
        alt = "" if (a.sizing, a.hold_close) == (calc.DEFAULT_SIZING, calc.DEFAULT_HOLD_CLOSE) \
            else f"-{a.sizing}-{a.hold_close}"
        (out_dir / f"diff-{p.parent.name}-{p.stem}{alt}.json").write_text(json.dumps(rep, indent=1))
        reports[rep["file"]] = rep
        summary[rep["file"]] = {k: rep[k] for k in ("pass", "trades_checked", "mismatches", "max_abs_diff")} | \
            {"position_differences": sum(x["differences"] for x in rep["positions"].values()),
             "unverifiable": len(rep["unverifiable"]),
             "math_on_loader_positions": sum(x["mismatches"] for x in rep["math_on_loader_positions"].values())}
        print(f"{rep['file']:<16} {'PASS' if rep['pass'] else 'FAIL'}  trades checked {rep['trades_checked']:>5}  "
              f"mismatches {rep['mismatches']:>5}  max diff {rep['max_abs_diff']}  "
              f"unverifiable {len(rep['unverifiable'])}")
        for label, pr in rep["positions"].items():
            print(f"    positions {label}: loader {pr['loader_positions']}, audit {pr['audit_positions']}, "
                  f"{pr['positions_differing']} differ {pr['by_field']}")
        for cls, n in sorted(rep["by_class"].items(), key=lambda x: -x[1]):
            print(f"    {n:>5}  {cls}")
        for label, lm in rep["math_on_loader_positions"].items():
            print(f"    math alone (calc on the loaders' positions, {label}): {lm['trades_compared']} trades, "
                  f"{lm['mismatches']} mismatches {lm['by_class']}")
    lab_file = rdir / "strategy-lab.json"
    if lab_file.exists() and not a.only:
        # results/strategy-lab.json (contracts.md section strategy-lab, CAP-15): every run recomputed by audit.lab
        rep = lab.check(lab_file)
        (out_dir / "diff-strategy-lab.json").write_text(json.dumps(rep, indent=1))
        summary["strategy-lab"] = {k: rep[k] for k in ("pass", "runs_checked", "mismatches")} | \
            {"unverifiable": len(rep["unverifiable"])}
        print(f"{'strategy-lab':<16} {'PASS' if rep['pass'] else 'FAIL'}  runs checked {rep['runs_checked']:>5}  "
              f"mismatches {rep['mismatches']:>5}  unverifiable {len(rep['unverifiable'])}")
    paper_file = rdir / "paper" / "summary.json"
    if paper_file.exists() and not a.only:
        # results/paper/ (contracts.md section paper, CAP-18): the forward paper test recomputed by audit.paper
        rep = paper.check(rdir / "paper")
        (out_dir / "diff-paper.json").write_text(json.dumps(rep, indent=1))
        summary["paper/summary"] = {k: rep[k] for k in ("pass", "sessions_checked", "trades_checked", "mismatches")} \
            | {"unverifiable": len(rep["unverifiable"])}
        print(f"{'paper':<16} {'PASS' if rep['pass'] else 'FAIL'}  sessions checked {rep['sessions_checked']:>4}  "
              f"trades checked {rep['trades_checked']:>4}  mismatches {rep['mismatches']:>5}")
    ok = all(s["pass"] for s in summary.values())
    if a.proofs:
        write_proofs(Path(a.proofs), a, rdir, ok, summary, reports)
    print("PASS: every position, trade and headline reconciles" if ok else "FAIL: see data/audit/diff-*.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
