"""Summary numbers for notes/sources/lpp.md, from data/lpp/{sessions,events}.jsonl. Prints markdown.

  uv run python -m lpp.stats
"""
import json
import statistics as st
from collections import Counter

from .common import DATA, RES


def main():
    S = [json.loads(line) for line in open(RES / "sessions.jsonl")]
    E = [json.loads(line) for line in open(RES / "events.jsonl")]
    done = [s for s in S if s["status"] in ("ok", "needs_review")]
    print(f"Sessions: {len(S)} linked; {len(done)} extracted; "
          f"{Counter(s['status'] for s in S)}")
    print(f"Dates: {min(s['session_date'] for s in done)} to {max(s['session_date'] for s in done)}; "
          f"median length {st.median(s['duration_s'] or 0 for s in done) / 60:.0f} min, "
          f"{sum(s['words'] for s in done):,} caption words")
    secs = [s["secs"] for s in done if s["secs"]]
    usage = [s["usage"] or {} for s in done]
    tin, tout = sum(u.get("in") or 0 for u in usage), sum(u.get("out") or 0 for u in usage)
    print(f"Model: {Counter(s['model'] for s in done)}; median call {st.median(secs):.0f} s; "
          f"tokens in {tin:,} out {tout:,}; est. cost ${tin * 2e-6 * 1.05 + tout * 10e-6 * 1.05:.2f} (list + 5%)")
    retried = [s for s in done if s["call_errors"]]
    print(f"Calls that needed a retry or fallback: {len(retried)} "
          f"{Counter(e['error'][:60] for s in retried for e in s['call_errors'])}")
    print()
    by = Counter(e["type"] for e in E)
    st_ = Counter((e["type"], e["status"]) for e in E)
    print("| Type | Events | ok | needs_review | per session (median) |")
    print("|---|---|---|---|---|")
    for t in ("trade", "call", "rule"):
        per = [s["events"].get(t, 0) for s in done]
        print(f"| {t} | {by[t]} | {st_[(t, 'ok')]} | {st_[(t, 'needs_review')]} | {st.median(per):g} |")
    print(f"| all | {len(E)} | {sum(e['status'] == 'ok' for e in E)} | {sum(e['status'] == 'needs_review' for e in E)} | |")
    print()
    print(f"Sessions with 0 trades: {sum(s['trades'] == 0 for s in done)}; round trips closed on air: "
          f"{sum(s['round_trips'] for s in done)}; positions still open at stream end: {sum(s['open_at_end'] for s in done)}")
    print(f"Sessions with every event ok: {sum(s['status'] == 'ok' for s in done)}; with 1+ needs_review: "
          f"{sum(s['status'] == 'needs_review' for s in done)}")
    print()
    print("Failure kinds (events):")
    fk = Counter(f for e in E for f in e["fail"])
    print("| Check failed | Events | Sessions |")
    print("|---|---|---|")
    for k, n in fk.most_common():
        print(f"| {k} | {n} | {sum(1 for s in done if k in s['fail_kinds'])} |")
    print()
    print("Airtime share, % of stream (model labels stretches; code sums them):")
    cats = Counter()
    for s in done:
        for k, v in s["airtime"].items():
            cats[k] += v
    print("| Category | Mean % | Median % |")
    print("|---|---|---|")
    for k, _ in cats.most_common():
        vals = [s["airtime"].get(k, 0) for s in done if s["airtime"]]
        print(f"| {k} | {st.mean(vals):.1f} | {st.median(vals):.1f} |")
    print()
    carried([json.loads(line) for line in open(DATA / "sessions.jsonl")],
            [json.loads(line) for line in open(DATA / "events.jsonl")])  # needs every session: always the v1 run
    print()
    tick = Counter(e["ticker"] for e in E if e["type"] == "trade" and e["ticker"])
    print("Most traded tickers:", ", ".join(f"{t} {n}" for t, n in tick.most_common(12)))
    side = Counter(e["side"] for e in E if e["type"] == "trade" and e["action"] == "open")
    print("Opens by side:", dict(side))
    month = Counter(e["session_date"][:7] for e in E if e["type"] == "trade")
    print("Trades by month:", dict(sorted(month.items())))


def carried(S, E):
    """How many ledger failures are positions carried overnight: a close_without_open whose (ticker, side) was
    still open at the end of the previous session, or an open_never_closed that the next session closes."""
    order = [s["source_id"] for s in sorted(S, key=lambda s: s["session_date"] or "") if s["session_date"]]
    by = {}
    for e in E:
        by.setdefault(e["source_id"], []).append(e)
    open_end = {}
    for src in order:
        evs = [e for e in by.get(src, []) if e["type"] == "trade" and e["ticker"]]
        held = {}
        for e in sorted(evs, key=lambda e: e["t_s"] or 0):
            k = (e["ticker"], e["side"] or "long")
            held[k] = e["action"] in ("open", "add") or (held.get(k, False) and e["action"] == "trim")
        open_end[src] = {k for k, v in held.items() if v}
    orphan = [(i, e) for i, src in enumerate(order) for e in by.get(src, []) if "close_without_open" in e["fail"]]
    expl = sum(1 for i, e in orphan if i > 0 and (e["ticker"], e["side"] or "long") in open_end[order[i - 1]])
    never = [(i, e) for i, src in enumerate(order) for e in by.get(src, []) if "open_never_closed" in e["fail"]]
    later = 0
    for i, e in never:
        if i + 1 < len(order):
            k = (e["ticker"], e["side"] or "long")
            later += any(x["type"] == "trade" and (x["ticker"], x["side"] or "long") == k and x["action"] in ("trim", "close")
                         for x in by.get(order[i + 1], []))
    print(f"Carried overnight: {expl} of {len(orphan)} close_without_open match a position open at the previous "
          f"session's end; {later} of {len(never)} open_never_closed are trimmed or closed in the next session.")


if __name__ == "__main__":
    main()
