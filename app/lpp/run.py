"""Batch driver: extract (cached), check, and write data/lpp/{sources,events,sessions}.jsonl.

  uv run python -m lpp.run                 # every session with captions, 6 calls in parallel
  uv run python -m lpp.run --ids A B C     # just these
  uv run python -m lpp.run --no-extract    # rebuild the JSONL from cached replies only
"""
import argparse
import datetime as dt
import json
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import checks, extract, transcript
from .common import DATA, OUT, RES, VERSION

CATS = extract.CATS


def links() -> dict:
    rows = [json.loads(line) for line in open(DATA / "discord" / "youtube_links.jsonl")]
    return {r["video_id"]: r for r in rows}


def airtime(raw: dict, tr) -> dict:
    """Share of the stream per category, computed in code from the model's [t, category] boundaries."""
    end = tr.words[-1][0] if tr.words else (tr.duration or 0)
    marks = sorted(([float(a[0]), a[1]] for a in raw.get("airtime") or []
                    if isinstance(a, (list, tuple)) and len(a) == 2 and isinstance(a[0], (int, float))), key=lambda a: a[0])
    secs = Counter()
    for i, (t, cat) in enumerate(marks):
        nxt = marks[i + 1][0] if i + 1 < len(marks) else end
        secs[cat if cat in CATS else "other"] += max(0.0, min(nxt, end) - t)
    total = sum(secs.values()) or 1
    return {k: round(100 * v / total, 1) for k, v in secs.most_common()}


def session_row(vid, link, tr, raw, events, trips) -> dict:
    by = Counter(e["type"] for e in events)
    return {
        "source_id": f"yt:{vid}", "video_id": vid,
        "session_date": events[0]["session_date"] if events else (checks.bars.session_date(tr.release_ts) if tr and tr.release_ts else None),
        "release_utc": dt.datetime.fromtimestamp(tr.release_ts, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if tr and tr.release_ts else None,
        "posted_at": link.get("posted_at"), "duration_s": tr.duration if tr else None,
        "time_source": tr.time_source if tr else None,
        "words": len(tr.words) if tr else 0,
        "model": raw.get("model"), "secs": raw.get("secs"), "usage": raw.get("usage"),
        "call_errors": raw.get("errors") or [],
        "events": dict(by), "trades": by.get("trade", 0), "calls": by.get("call", 0), "rules": by.get("rule", 0),
        "ok": sum(e["status"] == "ok" for e in events),
        "needs_review": sum(e["status"] == "needs_review" for e in events),
        "fail_kinds": dict(Counter(f for e in events for f in e["fail"])),
        "round_trips": sum(t["closed"] for t in trips), "open_at_end": sum(not t["closed"] for t in trips),
        "airtime": airtime(raw, tr) if tr else {},
        "status": "no_captions" if tr is None else ("extract_failed" if not raw.get("model") else
                                                     ("needs_review" if any(e["status"] == "needs_review" for e in events) else "ok")),
    }


_CARRY = None
_CARRY_LOCK = threading.Lock()


def carry_map() -> dict:
    """v2 ledger input: for each session, the (ticker, side) positions still open when it starts, carried from
    earlier sessions (a hold can span days; a session without trades keeps them), from the full-year v1 events
    (the only run that covers every session). Built once, under a lock, before any worker reads it."""
    global _CARRY
    with _CARRY_LOCK:
        if _CARRY is None:
            carry = {}
            p = DATA / "events.jsonl"
            if VERSION != "v1" and p.exists():
                by, dates = {}, {}
                for e in map(json.loads, open(p)):
                    by.setdefault(e["source_id"], []).append(e)
                    dates[e["source_id"]] = e["session_date"]
                held = {}
                for src in sorted(by, key=lambda s: dates[s] or ""):
                    carry[src.split(":", 1)[1]] = {k for k, v in held.items() if v}
                    for e in sorted((e for e in by[src] if e["type"] == "trade" and e["ticker"]), key=lambda e: e["t_s"] or 0):
                        k = (e["ticker"], e["side"] or "long")
                        held[k] = e["action"] in ("open", "add") or (held.get(k, False) and e["action"] == "trim")
            _CARRY = carry
    return _CARRY


def process(vid, link, do_extract=True):
    tr = transcript.load(vid)
    if tr is None:
        return vid, None, {}, [], []
    p = OUT / f"{vid}.json"
    if do_extract:
        raw = extract.cached(tr)
    else:
        raw = json.loads(p.read_text()) if p.exists() else {"events": [], "errors": [{"error": "not extracted"}]}
    carry = carry_map().get(vid, set())
    events = checks.build(tr, raw, f"yt:{vid}", carry)
    trips = checks.ledger([dict(e, fail=list(e["fail"]), checks=dict(e["checks"])) for e in events], carry)
    return vid, tr, raw, events, trips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-extract", action="store_true")
    a = ap.parse_args()
    L = links()
    ids = a.ids or sorted(L)
    results = {}
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(process, v, L.get(v, {}), not a.no_extract): v for v in ids}
        for n, f in enumerate(as_completed(futs), 1):
            vid, tr, raw, events, trips = f.result()
            results[vid] = (tr, raw, events, trips)
            print(f"[{n}/{len(ids)}] {vid} model={raw.get('model')} secs={raw.get('secs')} "
                  f"events={len(events)} review={sum(e['status'] == 'needs_review' for e in events)}", flush=True)
    write(L, results if not a.ids else None)


def write(L, results=None):
    """(Re)write the three JSONL files from every cached reply, so partial runs and reruns stay consistent."""
    if results is None:  # every session with a cached reply (v1: all 247), plus sessions without captions
        results = {}
        for vid in sorted(L):
            if VERSION != "v1" and not (OUT / f"{vid}.json").exists():
                continue
            _, tr, raw, events, trips = process(vid, L[vid], do_extract=False)
            results[vid] = (tr, raw, events, trips)
    RES.mkdir(parents=True, exist_ok=True)
    with open(RES / "sources.jsonl", "w") as fs, open(RES / "events.jsonl", "w") as fe, \
            open(RES / "sessions.jsonl", "w") as fss:
        for vid in sorted(results, key=lambda v: L.get(v, {}).get("posted_at") or ""):
            tr, raw, events, trips = results[vid]
            link = L.get(vid, {})
            fs.write(json.dumps({
                "source_id": f"yt:{vid}", "course": "lpp", "kind": "youtube", "server_id": link.get("server_id"),
                "channel": link.get("channel"), "channel_id": link.get("channel_id"), "message_id": link.get("message_id"),
                "url": link.get("url"), "posted_at": link.get("posted_at"), "author": "LPP host", "author_role": "staff",
                "title": tr.title if tr else None, "duration_s": tr.duration if tr else None,
                "release_utc": dt.datetime.fromtimestamp(tr.release_ts, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if tr and tr.release_ts else None,
                "captions": "auto" if tr else "missing"}) + "\n")
            for e in events:
                fe.write(json.dumps(e) + "\n")
            fss.write(json.dumps(session_row(vid, link, tr, raw, events, trips)) + "\n")


if __name__ == "__main__":
    main()
