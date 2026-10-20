"""Audit the money math: recompute every copied trade and headline, and reconcile them with results/.

  cd app && uv run python -m audit.run                 # every results/<course>/<version>.json
  cd app && uv run python -m audit.run --only lpp/v1   # one file

For each results file, delay [1, 3, 5, 10, 15, 30, 60] and testable portfolio (plus `same_sessions`), the second
calculator (audit.calc, written from contracts.md) recomputes:
  - every trade (entry time and price, exit time and price, P&L), checked against the engine's full ledger
    (data/audit/<course>-<version>-ledger.jsonl, written by `python -m backtest.run`) and against the trades
    the results file itself shows: 1 cent at stored precision (prices 4 dp, P&L 2 dp), times exact;
  - each headline (end value, return, just-holding end and return, trade count, word): within $1.
Writes data/audit/diff-<course>-<version>.json (every mismatch) and proofs/audit.json (the pass record).
Exits 0 only when everything reconciles. No network: a bar missing from data/bars/ marks that trade no_bars.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from backtest.common import DATA, REPO, RESULTS

from . import calc

TRADE_TOL = 0.01      # 1 cent
HEAD_TOL = 1.0        # $1
RET_TOL = 0.01        # $1 on $10,000, in points
HEAD_FIELDS = ("end", "ret_pct", "hold_end", "hold_ret_pct", "trades", "word")


def loader(course: str):
    if course == "lpp":
        from backtest import lpp
        return lpp
    if course == "cryptowizard":
        from backtest import cryptowizard
        return cryptowizard
    if course == "ziptrader":
        from backtest import ziptrader
        return ziptrader
    raise SystemExit(f"unknown course {course}")


def unique_ids(positions) -> None:
    """The ids results/ uses: a second position with the same id gets -2, -3, ... (as backtest.run names them)."""
    seen = Counter()
    for p in positions:
        seen[p.pid] += 1
        if seen[p.pid] > 1:
            p.pid = f"{p.pid}-{seen[p.pid]}"


def positions_for(mod, d: dict, version: str, sessions: set | None = None) -> list:
    if sessions is not None:
        ps = mod.build(version, sessions)["positions"]
    elif d["course"] == "lpp" and d["checks"].get("proof_set"):
        ps = mod.build(version, mod.proof_set())["positions"]
    else:
        ps = mod.build(version)["positions"]
    unique_ids(ps)
    return ps


def read_ledger(path: Path) -> dict | None:
    if not path.exists():
        return None
    out = {}
    for line in open(path):
        r = json.loads(line)
        out[(r["pid"], r["delay"])] = r
    return out


def engine_row(r: dict) -> dict:
    """A ledger row as the trade fields results/ stores (entry = first entry fill, exit = last exit fill)."""
    if r["status"] != "priced":
        return {"status": r["status"]}
    entry = next(f for f in r["fills"] if f[3] == "entry")
    exit_ = next(f for f in reversed(r["fills"]) if f[3] != "entry")
    return {"status": "priced", "entry_at": entry[0], "entry": round(entry[1], 4), "exit_at": exit_[0],
            "exit": round(exit_[1], 4), "pnl": round(r["pnl"], 2)}


def stored_row(row: dict) -> dict:
    """A results/ trade row (one delay) in the same shape."""
    if "status" in row:
        return {"status": row["status"]}
    return {"status": "priced", "entry_at": calc.B.to_ts(row["entry_at"]), "entry": row["entry"],
            "exit_at": calc.B.to_ts(row["exit_at"]), "exit": row["exit"], "pnl": row["pnl"]}


def audit_row(t: calc.Trade) -> dict:
    if t.status != "priced":
        return {"status": t.status, **({"why": t.why} if t.why else {})}
    return {"status": "priced", "entry_at": t.entry.ts, "entry": round(t.entry.px, 4), "exit_at": t.exit.ts,
            "exit": round(t.exit.px, 4), "pnl": round(t.pnl, 2)}


def compare_trade(where: str, pid: str, delay: int, theirs: dict, ours: dict, out: list) -> float:
    """Append mismatches; return the largest money difference seen."""
    worst = 0.0
    if theirs["status"] != ours["status"]:
        out.append({"kind": "trade", "against": where, "pid": pid, "delay": delay, "field": "status",
                    "theirs": theirs["status"], "ours": ours["status"], **({"why": ours["why"]} if ours.get("why") else {})})
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
    return worst


def compare_head(portfolio: str, delay: str, theirs: dict, ours: dict, out: list) -> float:
    worst = 0.0
    for f in HEAD_FIELDS:
        a, b = theirs[f], ours[f]
        if f in ("trades", "word"):
            bad = a != b
        else:
            diff = abs(a - b)
            worst = max(worst, diff if f in ("end", "hold_end") else 0.0)
            bad = diff > (RET_TOL if f.endswith("ret_pct") else HEAD_TOL) + 1e-9
        if bad:
            out.append({"kind": "headline", "portfolio": portfolio, "delay": int(delay), "field": f,
                        "theirs": a, "ours": b, **({} if f in ("trades", "word") else {"diff": round(abs(a - b), 4)})})
    return worst


def audit_file(path: Path, ledger_dir: Path, sizing: str = calc.DEFAULT_SIZING,
               hold_close: str = calc.DEFAULT_HOLD_CLOSE) -> dict:
    d = json.loads(path.read_text())
    course, version = d["course"], d["version"]
    mod = loader(course)
    market = mod.MARKET
    symbol = getattr(mod, "HOLD_BARS", mod.HOLD["symbol"])
    hold_row = calc.hold(market, symbol, d["window"], hold_close)
    mismatches: list[dict] = []
    worst, checked = 0.0, 0

    def run_set(positions, ledger_name, portfolios):
        nonlocal worst, checked
        mine = {(p.pid, dl): calc.simulate(p, dl, sizing) for p in positions for dl in d["delays_min"]}
        ledger = read_ledger(ledger_dir / f"{course}-{version}{ledger_name}-ledger.jsonl")
        if ledger is None:
            mismatches.append({"kind": "missing", "field": "ledger",
                               "theirs": f"data/audit/{course}-{version}{ledger_name}-ledger.jsonl",
                               "ours": "run: cd app && uv run python -m backtest.run --course "
                                       f"{course} --version {version}"})
        else:
            for k in sorted(set(ledger) - set(mine)):
                mismatches.append({"kind": "trade", "against": "ledger", "pid": k[0], "delay": k[1],
                                   "field": "presence", "theirs": "in engine ledger", "ours": "absent"})
            for (pid, dl), t in mine.items():
                if (pid, dl) not in ledger:
                    mismatches.append({"kind": "trade", "against": "ledger", "pid": pid, "delay": dl,
                                       "field": "presence", "theirs": "absent", "ours": "priced by audit"})
                    continue
                worst = max(worst, compare_trade("ledger", pid, dl, engine_row(ledger[(pid, dl)]),
                                                 audit_row(t), mismatches))
                checked += 1
        for pf_id, rows in portfolios:
            for dl, theirs in rows.items():
                ts = [t for (pid, x), t in mine.items() if x == int(dl) and (pf_id == "all" or t.portfolio == pf_id)]
                worst = max(worst, compare_head(pf_id if ledger_name == "" else f"same_sessions:{pf_id}", dl,
                                                theirs, calc.portfolio(ts, hold_row), mismatches))
        return mine

    positions = positions_for(mod, d, version)
    pfs = [(p["id"], p["by_delay"]) for p in d["portfolios"] if p["testable"]]
    mine = run_set(positions, "", pfs)

    # the trades the results file shows (a sample of up to 200): checked directly, not through the ledger
    for row in d["trades"]:
        for dl, r in row["by_delay"].items():
            t = mine.get((row["trade_id"], int(dl)))
            if t is None:
                mismatches.append({"kind": "trade", "against": "results", "pid": row["trade_id"], "delay": int(dl),
                                   "field": "presence", "theirs": "in results", "ours": "absent"})
                continue
            worst = max(worst, compare_trade("results", row["trade_id"], int(dl), stored_row(r), audit_row(t),
                                             mismatches))
            checked += 1

    if d.get("same_sessions"):
        same = d["same_sessions"]
        srcs = mod.proof_set() if same.get("proof_set") else {e["source_id"] for e in mod.load(version)}
        base = positions_for(mod, d, same["version"], sessions=srcs)
        run_set(base, "-same_sessions", [(same.get("portfolio", "all"), same["by_delay"])])

    hold_note = {"symbol": symbol, "first_open": hold_row["px0"], "official_close": hold_row["official_close"],
                 "minute_close": hold_row["minute_close"], "used": hold_row["used"]}
    return {"file": f"{course}/{version}", "sizing": sizing, "hold_close": hold_close, "pass": not mismatches, "trades_checked": checked,
            "mismatches": len(mismatches), "max_abs_diff": round(worst, 4), "hold": hold_note,
            "by_class": dict(Counter(f"{m['kind']}:{m.get('against', m.get('portfolio', ''))}:{m['field']}"
                                     for m in mismatches)),
            "details": mismatches}


def results_git_sha(results_dir: Path) -> str | None:
    out = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(results_dir)], cwd=REPO,
                         capture_output=True, text=True).stdout.strip()
    return out or None


def write_proofs(path: Path, a, rdir: Path, ok: bool, summary: dict) -> None:
    """proofs/audit.json: the default reading at the top level; a run with other readings (--sizing,
    --hold-close) is kept under `alternatives`, so both answers sit side by side."""
    default = a.sizing == calc.DEFAULT_SIZING and a.hold_close == calc.DEFAULT_HOLD_CLOSE
    run = {"generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "results_git_sha": results_git_sha(rdir), "pass": ok, "sizing": a.sizing, "hold_close": a.hold_close,
           "command": "cd app && uv run python -m audit.run"
                      + ("" if default else f" --sizing {a.sizing} --hold-close {a.hold_close}"),
           "files": summary}
    old = json.loads(path.read_text()) if path.exists() else {}
    if default:
        rec = {"schema": "audit/1", **run,
               "tolerance": {"trade": "1 cent (prices 4 dp, P&L 2 dp; times exact)",
                             "headline": "$1 (returns 0.01 pts; trades and word exact)"},
               "alternatives": {k: v for k, v in old.get("alternatives", {}).items()
                                if v.get("results_git_sha") == run["results_git_sha"]}}
    else:
        rec = old or {"schema": "audit/1"}
        rec.setdefault("alternatives", {})[f"sizing={a.sizing},hold_close={a.hold_close}"] = run
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(RESULTS))
    ap.add_argument("--ledger-dir", default=str(DATA / "audit"))
    ap.add_argument("--out-dir", default=str(DATA / "audit"))
    ap.add_argument("--proofs", default=str(REPO / "proofs" / "audit.json"), help="'' to skip writing it")
    ap.add_argument("--sizing", choices=calc.SIZINGS, default=calc.DEFAULT_SIZING,
                    help="LPP rule 6 reading: first = first entry is $1,000 (contracts.md literally); "
                         "trade = all entries together are $1,000 (the engine's reading)")
    ap.add_argument("--hold-close", choices=calc.HOLD_CLOSES, default=calc.DEFAULT_HOLD_CLOSE,
                    help="rule 7's last price: official = the session close (daily cache); minute = last 1-min bar")
    ap.add_argument("--only", action="append", help="course/version, e.g. lpp/v1 (repeatable)")
    a = ap.parse_args(argv)
    rdir, out_dir = Path(a.results_dir), Path(a.out_dir)
    files = sorted(p for p in rdir.glob("*/*.json") if not a.only or f"{p.parent.name}/{p.stem}" in a.only)
    if not files:
        print("no results files found", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for p in files:
        rep = audit_file(p, Path(a.ledger_dir), a.sizing, a.hold_close)
        alt = "" if (a.sizing, a.hold_close) == (calc.DEFAULT_SIZING, calc.DEFAULT_HOLD_CLOSE) \
            else f"-{a.sizing}-{a.hold_close}"
        (out_dir / f"diff-{p.parent.name}-{p.stem}{alt}.json").write_text(json.dumps(rep, indent=1))
        summary[rep["file"]] = {k: rep[k] for k in ("pass", "trades_checked", "mismatches", "max_abs_diff")}
        print(f"{rep['file']:<16} {'PASS' if rep['pass'] else 'FAIL'}  trades checked {rep['trades_checked']:>5}  "
              f"mismatches {rep['mismatches']:>5}  max diff {rep['max_abs_diff']}")
        for cls, n in sorted(rep["by_class"].items(), key=lambda x: -x[1]):
            print(f"    {n:>5}  {cls}")
    ok = all(s["pass"] for s in summary.values())
    if a.proofs:
        write_proofs(Path(a.proofs), a, rdir, ok, summary)
    print("PASS: every trade and headline reconciles" if ok else "FAIL: see data/audit/diff-*.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
