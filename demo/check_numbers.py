"""Print every number the demo script says, straight from the files, so the talk never drifts.

    git -C ~/dev/quant-bot fetch -q origin
    python3 demo/check_numbers.py

Each file is read from the first place that has it: this checkout, origin/main, then the branch that writes it
(results/ from story/1-copy-trade-backtest, proofs/ from story/2-prism-proofs). Pin a place with
--ref <git ref> (results) and --proofs-ref <git ref> (proofs). Compare the output with the
"Numbers on screen" table in demo/script.md. Exit code 1 means a PRISM value is still pending or a file is sample data.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLACES = {
    "results": [None, "origin/main", "origin/story/1-copy-trade-backtest"],
    "proofs": [None, "origin/main", "origin/story/2-prism-proofs"],
}
problems = []


def read(path, ref):
    if ref is None:
        p = ROOT / path
        return json.loads(p.read_text()) if p.exists() else None
    out = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{path}"], capture_output=True, text=True)
    if out.returncode == 0:
        return json.loads(out.stdout)
    if "invalid object name" in out.stderr or "unknown revision" in out.stderr:
        sys.exit(f"git ref not found: {ref}")
    return None


def load(path, pinned=None):
    kind = path.split("/")[0]
    for ref in ([pinned] if pinned else PLACES[kind]):
        data = read(path, ref)
        if data is not None:
            return data, ref or "this checkout"
    return None, None


def money(x):
    return f"${x:,.0f}"


def by_delay(r, delay, pid="all"):
    return next(p for p in r["portfolios"] if p["id"] == pid)["by_delay"][str(delay)]


def flag(value, what):
    if value is None:
        problems.append(what)
        return "PENDING"
    return value


def course(name, ref):
    r, where = load(f"results/{name}/v1.json", ref)
    if r is None:
        problems.append(f"no results/{name}/v1.json")
        print(f"{name}: no results/{name}/v1.json anywhere")
        return None
    if r.get("sample") or r.get("partial"):
        problems.append(f"{name} is sample or partial data")
    print(f"\n{r['course_name']} (v1, from {where}{', SAMPLE' if r.get('sample') else ''}{', PARTIAL' if r.get('partial') else ''})")
    return r


def main():
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    pref = sys.argv[sys.argv.index("--proofs-ref") + 1] if "--proofs-ref" in sys.argv else None

    lpp = course("lpp", ref)
    if lpp:
        for d in (5, 1, 15):
            b = by_delay(lpp, d)
            print(f"  {d:>2} min: {money(b['end'])} vs just holding {money(b['hold_end'])}, {b['word']}, {b['trades']} trades")
        b = by_delay(lpp, 5, "day")
        print(f"  day trades 5 min: {money(b['end'])} ({b['ret_pct']:+.1f}%), {b['word']}")
        print(f"  first unknown: {lpp['unknown'][0]}")
        r3 = (lpp.get("ranges") or {}).get("3m")
        if r3:
            b = r3["by_delay"]["5"]
            print(f"  chip 3M (until {r3['until']}): {money(b['end'])} vs {money(b['hold_end'])}, {b['word']}")
        bs = ((lpp.get("best_stop") or {}).get("by_delay") or {}).get("5")
        if bs:
            print(f"  best day to stop: {bs['date']}, {money(bs['end'])} vs holding {money(bs['hold_end'])}")
        for st in lpp.get("strategies") or []:
            b = (st.get("by_delay") or {}).get("5")
            if st.get("id") == "short-overbought" and b:
                print(f"  {st['name']}: {b.get('trades')} trades, {b.get('ret_pct'):+.1f}%, {b.get('word')}")
        v2, _ = load("results/lpp/v2.json", ref)
        if v2:
            same = v2.get("same_sessions") or {}
            a, b = same.get("by_delay", {}).get("5"), by_delay(v2, 5)
            if a:
                print(f"  v1 vs v2 on the same {same.get('sessions')} sessions, 5 min: {money(a['end'])} {a['word']} | {money(b['end'])} {b['word']}")
            print(f"  NOTE: the app shows the highest version per course; if the LPP stamp says {money(b['end'])} "
                  f"({b['trades']} trades), it is showing v2 ({same.get('sessions')} sessions), not the full year.")

    cw = course("cryptowizard", ref)
    if cw:
        b = by_delay(cw, 5)
        s = b.get("sealed") or {}
        print(f"  5 min: {money(b['end'])} vs {money(b['hold_end'])}, {b['word']}; newest months {s.get('ret_pct')}% vs {s.get('hold_ret_pct')}% ({s.get('trades')} trades)")

    zt = course("ziptrader", ref)
    if zt:
        b = by_delay(zt, 5)
        print(f"  5 min: {b['trades']} trade(s), {b['word']}")

    pr, where = load("proofs/prism.json", pref)
    if not pr:
        problems.append("no proofs/prism.json")
        print("\nProofs: no proofs/prism.json anywhere")
    else:
        print(f"\nPRISM proofs (from {where}, updated {pr.get('updated_at')})")
        ev = pr.get("evaluator") or {}
        cm = ev.get("code_mirror") or {}
        print(f"  Evaluator '{ev.get('name')}': PRISM {flag((ev.get('v1') or {}).get('pass_pct'), 'evaluator v1 pass rate')} -> "
              f"{flag((ev.get('v2') or {}).get('pass_pct'), 'evaluator v2 pass rate')}; our code {cm.get('v1_pass_pct')}% -> {cm.get('v2_pass_pct')}%")
        fr = ev.get("failed_runs") or {}
        print(f"  Failed runs: v1 {fr.get('v1')} -> v2 {fr.get('v2')} of {fr.get('of')}")
        ms = ev.get("money_same_sessions") or {}
        if ms:
            print(f"  Money, same {ms.get('sessions')} sessions, {ms.get('delay_min')} min: v1 {money(ms['v1_end'])} vs v2 {money(ms['v2_end'])}")
        rc = pr.get("root_cause") or {}
        print(f"  Root Cause: {flag(rc.get('failed_runs'), 'root cause failed runs')} failed runs, tier {rc.get('tier')!r}, url {rc.get('url')}")
        print(f"  Cluster: {flag(rc.get('cluster'), 'root cause cluster')!r}")
        print(f"  Our sentence: {rc.get('our_sentence')!r}")
        kb = pr.get("knowledge_base") or {}
        hits = kb.get("hits") or []
        print(f"  Knowledge Base: run {flag(kb.get('run_url'), 'knowledge base run')}, query {kb.get('query')!r}, "
              f"{len(hits)} hits, cites {kb.get('cites')}")

    if problems:
        print("\nNot ready: " + "; ".join(problems))
        sys.exit(1)
    print("\nAll values present.")


if __name__ == "__main__":
    main()
