"""Knowledge Base proof, part 1: derived course notes in kb/, uploaded to PRISM and assigned to the verdict agent.

  uv run python -m prism.kb build                               # kb/<course>-{strategy-cards,events-summary,untestable}.md
  uv run python -m prism.kb upload --agent daytrader-verdict-v1  # once per agent: a PRISM doc belongs to one agent
  uv run python -m prism.kb list --agent daytrader-verdict-v1

Only derived records go in: paraphrased rules (15 words max), locators, quotes of 12 words max. Cards come from
events that passed every code check (status ok); the rest is counted in -untestable.md.
"""
import argparse
import collections
import json
import re

from .common import COURSES, DATA, KB, PROOFS, clip, now, read_jsonl

THEMES = [  # first match wins, most specific first
    ("sizing", "Sizing", r"\b(size|sizing|shares|position|contracts?|half|quarter)\b"),
    ("stop", "Stops and risk", r"\b(stop|stops|risk|loss|losses|cut)\b"),
    ("exit", "Exits and trims", r"\b(exit|sell|trim|profits?|close|scale out|target|targets|take)\b"),
    ("entry", "Entries", r"\b(enter|entry|entries|buy|long|short|break|breaks|breakout|reclaim|add|wait for)\b"),
    ("avoid", "When not to trade", r"\b(don't|do not|avoid|never|skip|no)\b"),
]
CARDS_PER_THEME = 6
FAIL_MEANING = {
    "quote_too_long": "The model's quote ran over 12 words.",
    "open_never_closed": "He opened a trade and never said he closed it; the exit is assumed.",
    "close_without_open": "A close with no matching open earlier in the session.",
    "number_not_near_quote": "The number is in the transcript, but not near the quoted words.",
    "number_not_in_source": "A number the model reported is never said.",
    "qty_exceeds_position": "Sold more shares than the position held.",
    "price_off_day_range": "The price is outside that day's trading range.",
    "quote_not_in_source": "The quote isn't in the source.",
    "quote_missing": "No quote was given.",
    "ticker_unresolved": "The ticker couldn't be matched to a real symbol.",
    "ticker_unknown": "The ticker isn't a known symbol.",
}
OPTIONS = re.compile(r"\b(options?|calls? option|puts?|strike|expir\w*|0dte|contracts?)\b", re.I)
FUTURES = {"ES", "NQ", "YM", "RTY", "MES", "MNQ"}


def theme_of(rule: str) -> str:
    for key, _, rx in THEMES:
        if re.search(rx, rule, re.I):
            return key
    return "other"


def locator(e: dict, src: dict | None) -> str:
    sid = e["source_id"]
    if sid.startswith("yt:") and e.get("t_s") is not None:
        return f"{sid} t={int(e['t_s'])}s"
    return sid


def label(e: dict, src: dict | None) -> str:
    day = (e.get("session_date") or (e.get("wall_utc") or "")[:10]) or "?"
    if e["source_id"].startswith("yt:"):
        return f"live session {day}"
    return f"#{(src or {}).get('channel') or 'discord'} {day}"


def kinds(e: dict) -> list[str]:
    return e.get("fail") or e.get("review_reasons") or ["needs_review"]


def spread(rows: list[dict], n: int) -> list[dict]:
    """n rows spaced evenly over the window, so the cards cover the whole year, not one week."""
    rows = sorted(rows, key=lambda e: e.get("wall_utc") or "")
    if len(rows) <= n:
        return rows
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def cards(course: str, ev: list[dict], src: dict) -> tuple[str, list[dict]]:
    rules = [e for e in ev if e.get("type") == "rule" and e.get("status") == "ok" and e.get("rule")]
    by = collections.defaultdict(list)
    for e in rules:
        by[theme_of(e["rule"])].append(e)
    name = COURSES[course]
    out = [f"# {name}: strategy cards", "",
           f"Rules {name} teaches, paraphrased from {len(rules)} rules that passed every code check. "
           "Each card cites its source by locator; quotes are 12 words or fewer. Cite a card by its id.", ""]
    index = []
    for key, title, _ in THEMES + [("other", "Other rules", "")]:
        rows = spread(by.get(key, []), CARDS_PER_THEME)
        if not rows:
            continue
        out += [f"## {title} ({len(by[key])} rules)", ""]
        for i, e in enumerate(rows, 1):
            cid = f"{course.upper()}-{key.upper()}-{i}"
            s = src.get(e["source_id"])
            out += [f"### {cid}", f"Rule: {clip(e['rule'], 15)}", f"Quote: \"{clip(e.get('quote'))}\"",
                    f"Source: {locator(e, s)} ({label(e, s)})", ""]
            index.append({"id": cid, "theme": key, "rule": clip(e["rule"], 15), "locator": locator(e, s)})
    return "\n".join(out), index


def summary(course: str, ev: list[dict], src: dict) -> str:
    name = COURSES[course]
    dates = sorted(d for d in ((e.get("wall_utc") or "")[:10] for e in ev) if d)
    types = collections.Counter(e.get("type") for e in ev)
    status = collections.Counter(e.get("status") for e in ev)
    out = [f"# {name}: events summary", "",
           f"Window: {dates[0] if dates else '?'} to {dates[-1] if dates else '?'}. "
           f"{len({e['source_id'] for e in ev})} sources, {len(ev)} events "
           f"({', '.join(f'{v} {k}s' for k, v in types.most_common())}). "
           f"{status.get('ok', 0)} passed every code check; {status.get('needs_review', 0)} need review.", "",
           "## Per month", "", "| Month | Trades | Calls | Setups | Rules | Need review |", "|---|---|---|---|---|---|"]
    months = collections.defaultdict(collections.Counter)
    for e in ev:
        m = (e.get("wall_utc") or "")[:7] or "?"
        months[m][e.get("type")] += 1
        months[m]["review"] += e.get("status") == "needs_review"
    for m in sorted(months):
        c = months[m]
        out.append(f"| {m} | {c['trade']} | {c['call']} | {c['setup']} | {c['rule']} | {c['review']} |")
    ok = [e for e in ev if e.get("status") == "ok" and e.get("ticker")]
    tick = collections.Counter(e["ticker"] for e in ok)
    sides = collections.Counter(e.get("side") for e in ok if e.get("side"))
    levels = sum(1 for e in ok if e.get("entry") or e.get("stop") or e.get("targets"))
    out += ["", "## What gets traded", "",
            f"- Top tickers (checked events): {', '.join(f'{t} {n}' for t, n in tick.most_common(12)) or 'none'}.",
            f"- Sides: {', '.join(f'{k} {v}' for k, v in sides.most_common()) or 'not stated'}.",
            f"- Events with an entry, stop or target level: {levels}."]
    sessions = read_jsonl(DATA / course / "sessions.jsonl")
    if sessions:
        done = [s for s in sessions if s.get("status") not in ("no_captions", "extract_failed")]
        rt = sum(s.get("round_trips") or 0 for s in done)
        open_end = sum(s.get("open_at_end") or 0 for s in done)
        trading = [s["airtime"]["trading"] for s in done if (s.get("airtime") or {}).get("trading") is not None]
        out += [f"- Live sessions read: {len(done)} of {len(sessions)}; round trips (open and close both said): {rt}; "
                f"positions still open at the end of a session: {open_end}.",
                f"- Share of airtime spent on trading: {round(sum(trading) / len(trading), 1) if trading else '?'}% on average."]
    out += ["", "How a trade is tested: entry at the first 1-minute bar at post time + delay; exit at the course's own "
            "close + delay, else stop or target, else the stated horizon, else 15:55 ET (day), 5 sessions (swing), "
            "24 h (crypto). Costs per side: 5 bps, 20 bps under $10, 25 bps crypto. Code decides, not the model.", ""]
    return "\n".join(out)


def untestable(course: str, ev: list[dict], src: dict) -> str:
    name = COURSES[course]
    review = [e for e in ev if e.get("status") == "needs_review"]
    by = collections.defaultdict(list)
    for e in review:
        for k in kinds(e):
            by[k].append(e)
    out = [f"# {name}: what we can't test, and why", "",
           f"{len(review)} of {len(ev)} events failed a code check and are left out of the money result. "
           "Each kind, with one example:", "", "| Check failed | Events | Means | Example |", "|---|---|---|---|"]
    for k, rows in sorted(by.items(), key=lambda kv: -len(kv[1])):
        ex = spread(rows, 1)[0]
        s = src.get(ex["source_id"])
        out.append(f"| {k} | {len(rows)} | {FAIL_MEANING.get(k, 'Flagged by a code check.')} | "
                   f"\"{clip(ex.get('quote'))}\" ({locator(ex, s)}) |")
    opts = [e for e in ev if e.get("type") in ("trade", "call") and OPTIONS.search(f"{e.get('quote')} {e.get('why')}")]
    fut = [e for e in ev if (e.get("ticker") or "") in FUTURES]
    out += ["", "## Not priced at all", "",
            f"- Options mentioned in {len(opts)} trades or calls: counted, not priced (no free options price history).",
            f"- Futures ({', '.join(sorted(FUTURES))}): {len(fut)} events; no free 2024-25 futures minute bars."]
    sessions = read_jsonl(DATA / course / "sessions.jsonl")
    if sessions:
        nc = sum(s.get("status") == "no_captions" for s in sessions)
        xf = sum(s.get("status") == "extract_failed" for s in sessions)
        out.append(f"- Sessions with no captions: {nc}; sessions the extractor failed on: {xf}.")
    out += ["- Exits he never announced are assumed (15:55 ET for day trades) and listed as assumed in the results.", ""]
    return "\n".join(out)


def build() -> dict:
    KB.mkdir(exist_ok=True)
    made = {}
    for course in COURSES:
        ev = read_jsonl(DATA / course / "events.jsonl")
        if not ev:
            print(f"{course}: no events yet, skipped")
            continue
        src = {s["source_id"]: s for s in read_jsonl(DATA / course / "sources.jsonl")}
        text, index = cards(course, ev, src)
        files = {f"{course}-strategy-cards.md": text, f"{course}-events-summary.md": summary(course, ev, src),
                 f"{course}-untestable.md": untestable(course, ev, src)}
        for fn, body in files.items():
            (KB / fn).write_text(body)
        (KB / f"{course}-cards.json").write_text(json.dumps(index, indent=1))
        made[course] = list(files)
        print(f"{course}: {len(ev)} events -> {', '.join(files)} ({len(index)} cards)")
    return made


def upload(agent: str, courses: list[str]) -> None:
    from .common import client
    pt = client()
    have = {d.get("name") for d in pt.kb_list_documents(agent_id=agent)}
    log_path = PROOFS / "parts" / "kb_uploads.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    for course in courses:
        for kind in ("strategy-cards", "events-summary", "untestable"):
            fn = f"{course}-{kind}.md"
            if not (KB / fn).exists():
                continue
            if fn in have:
                print(f"{fn}: already assigned to {agent}, skipped")
                continue
            body = (KB / fn).read_text()
            if agent != "daytrader-verdict-v1":  # PRISM dedupes identical files to one doc (one agent): make a copy
                body = body.replace("\n", f"\n\n_Copy assigned to {agent}._\n", 1)
            r = pt.kb_upload(fn, body, agent_id=agent, content_type="text/markdown",
                             description=f"{COURSES[course]} {kind.replace('-', ' ')} (derived notes, story 2)")
            print(f"{fn}: {'uploaded, ' + str(r.get('chunk_count')) + ' chunks' if r else 'FAILED'}")
            if r and r.get("agent_id", agent) != agent:
                print(f"{fn}: PRISM returned a doc assigned to {r.get('agent_id')}, not {agent}")
            elif r:
                log.append({"agent_id": agent, "doc": fn, "id": r.get("id"), "chunks": r.get("chunk_count"), "at": now()})
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=1))
    pt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "upload", "list"])
    ap.add_argument("--agent", default="daytrader-verdict-v1")
    ap.add_argument("--course", nargs="*", default=list(COURSES))
    a = ap.parse_args()
    if a.cmd == "build":
        build()
    elif a.cmd == "upload":
        upload(a.agent, a.course)
    else:
        from .common import client
        pt = client()
        for d in pt.kb_list_documents(agent_id=a.agent):
            print(d.get("name"), d.get("id"), d.get("chunk_count"), d.get("agent_id"))
        pt.close()


if __name__ == "__main__":
    main()
