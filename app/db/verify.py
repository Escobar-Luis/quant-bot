"""Compare what's in SurrealDB with the JSONL files on disk. Exit code 1 on any mismatch.

    uv run python -m db.verify
"""

import json
import sys

from db.load import COURSES, DATA, SEGMENT_S, caption_words, connect, rows


def expected() -> dict[str, dict[str, int]]:
    out = {}
    for course in COURSES:
        sources = {r["source_id"]: r for r in rows(DATA / course / "sources.jsonl")}
        events = {r["event_id"] for r in rows(DATA / course / "events.jsonl")}
        segments = 0
        for sid, r in sources.items():
            if r.get("kind") == "youtube":
                vid = sid.split(":", 1)[1]
                cap = DATA / course / "youtube" / vid / f"{vid}.en-orig.json3"
                if cap.exists():
                    segments += len({int(t // SEGMENT_S) for t, _ in caption_words(cap)})
        out[course] = {"sources": len(sources), "events": len(events), "segments": segments}
    return out


def main() -> None:
    db = connect()
    want = expected()
    ok = True
    print(f"{'course':13}{'table':10}{'files':>8}{'db':>8}")
    for course, counts in want.items():
        c = f"course:{course}"
        got = {
            "sources": db.query(f"RETURN count(SELECT id FROM source WHERE course = {c})"),
            "events": db.query(f"RETURN count(SELECT id FROM event WHERE course = {c})"),
            "segments": db.query(f"RETURN count(SELECT id FROM segment WHERE source.course = {c})"),
        }
        for table, n in counts.items():
            mark = "" if got[table] == n else "  MISMATCH"
            ok &= got[table] == n
            print(f"{course:13}{table:10}{n:8}{got[table]:8}{mark}")
    rules = db.query("RETURN count(SELECT id FROM event WHERE type = 'rule' AND rule != NONE)")
    emb = db.query("RETURN count(SELECT id FROM event WHERE embedding != NONE)")
    print(f"rule embeddings {emb}/{rules}")
    print("summary lpp:", json.dumps(db.query("RETURN fn::course_summary('lpp')"), default=str)[:300])
    print("search 'stop loss':", [r.get("rule") for r in db.query("RETURN fn::search_rules('stop loss', 2)")])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
