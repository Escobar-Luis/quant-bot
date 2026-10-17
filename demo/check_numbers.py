"""Print every number the demo script says, straight from the committed files, so the talk never drifts.

    python3 demo/check_numbers.py                                      # results/ and proofs/ in this checkout
    python3 demo/check_numbers.py --ref origin/story/1-copy-trade-backtest   # read them from a git ref instead

Compare the output with the "Numbers on screen" table in demo/script.md before going on stage.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(path, ref=None):
    if ref:
        out = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{path}"], capture_output=True, text=True)
        return json.loads(out.stdout) if out.returncode == 0 else None
    p = ROOT / path
    return json.loads(p.read_text()) if p.exists() else None


def money(x):
    return f"${x:,.0f}"


def headline(r, delay, pid="all"):
    p = next(p for p in r["portfolios"] if p["id"] == pid)
    return p["by_delay"][str(delay)]


def main():
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    proofs_ref = sys.argv[sys.argv.index("--proofs-ref") + 1] if "--proofs-ref" in sys.argv else ref
    src = ref or "this checkout"

    lpp = load("results/lpp/v1.json", ref)
    if lpp:
        for d in (5, 1, 15):
            b = headline(lpp, d)
            print(f"LPP {d:>2} min: {money(b['end'])} vs just holding {money(b['hold_end'])}, {b['word']}, {b['trades']} trades")
        b = headline(lpp, 5, "day")
        print(f"LPP day trades 5 min: {money(b['end'])} ({b['ret_pct']:+.1f}%) vs {b['hold_ret_pct']:+.1f}%, {b['word']}")
        print(f"LPP sample: {lpp.get('sample')}, partial: {lpp.get('partial')}")
    else:
        print(f"LPP: no results/lpp/v1.json in {src}")

    cw = load("results/cryptowizard/v1.json", ref)
    if cw:
        b = headline(cw, 5)
        s = b.get("sealed") or {}
        print(f"Crypto Wizard 5 min: {money(b['end'])} vs {money(b['hold_end'])}, {b['word']}; "
              f"sealed {s.get('ret_pct')}% vs {s.get('hold_ret_pct')}% ({s.get('trades')} trades)")

    zt = load("results/ziptrader/v1.json", ref)
    if zt:
        b = headline(zt, 5)
        print(f"ZipTrader 5 min: {b['trades']} trade(s), {b['word']}")

    v2 = load("results/lpp/v2.json", ref)
    if v2 and v2.get("same_sessions"):
        same = v2["same_sessions"]
        a, b = same["by_delay"]["5"], headline(v2, 5)
        print(f"LPP same {same['sessions']} sessions, 5 min: v1 {money(a['end'])} {a['word']} | v2 {money(b['end'])} {b['word']}")

    pr = load("proofs/prism.json", proofs_ref)
    if pr:
        ev = pr.get("evaluator") or {}
        cm = ev.get("code_mirror") or {}
        print(f"Evaluator '{ev.get('name')}': PRISM v1 {ev.get('v1', {}).get('pass_pct')} -> v2 {ev.get('v2', {}).get('pass_pct')}; "
              f"code mirror {cm.get('v1_pass_pct')}% -> {cm.get('v2_pass_pct')}%")
        rc = pr.get("root_cause") or {}
        print(f"Root Cause: cluster {rc.get('cluster')!r}, failed runs {rc.get('failed_runs')}, ours: {rc.get('our_sentence')!r}, url {rc.get('url')}")
        kb = pr.get("knowledge_base") or {}
        print(f"Knowledge Base: run {kb.get('run_url')}, query {kb.get('query')!r}, hits {len(kb.get('hits') or [])}")
    else:
        print(f"Proofs: no proofs/prism.json in {proofs_ref or 'this checkout'}")


if __name__ == "__main__":
    main()
