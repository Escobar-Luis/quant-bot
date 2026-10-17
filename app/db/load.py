"""Load every course's JSONL (and LPP captions) into SurrealDB. Safe to re-run.

    uv run python -m db.load            # schema + sources + events + caption segments
    uv run python -m db.load --embed    # also embed rule/why text with voyage-finance-2 (Nicrron)
    uv run python -m db.load --stats    # print counts and one call of each agent function

Embedded on disk by default (surrealkv:// under ~/dev/quant-bot/data/surreal). Set SURREALDB_URL
(wss://<instance>.surreal.cloud), SURREALDB_USER and SURREALDB_PASS in ~/dev/quant-bot/.env for Surreal Cloud.
Schema and design: app/db/schema.surql, notes/storage-surrealdb.md.
"""

import argparse
import json
import os
import pathlib
from datetime import datetime

from dotenv import load_dotenv
from surrealdb import RecordID, Surreal

ROOT = pathlib.Path.home() / "dev" / "quant-bot"
load_dotenv(ROOT / ".env")
DATA = pathlib.Path(os.environ.get("DATA_DIR", ROOT / "data"))
LOCAL_URL = f"surrealkv://{DATA / 'surreal' / 'daytrader'}"
EMBEDDED = ("mem://", "memory://", "surrealkv://", "file://")
SCHEMA = pathlib.Path(__file__).with_name("schema.surql")

COURSES = {
    "lpp": {"name": "Learn Plan Profit", "market": "us_equities"},
    "ziptrader": {"name": "ZipTrader", "market": "us_equities"},
    "cryptowizard": {"name": "Crypto Wizard", "market": "crypto"},
}
SOURCE_FIELDS = ("kind", "url", "server_id", "channel", "channel_id", "message_id", "author", "author_role",
                 "title", "duration_s", "captions")
EVENT_TEXT = ("type", "session_date", "market", "ticker_said", "side", "action", "instrument", "level_kind",
              "horizon", "why", "rule", "quote", "status", "model", "prompt_version")
EVENT_NUM = ("t_s", "qty", "price", "entry", "stop", "level")
SEGMENT_S = 30


def connect(url: str | None = None) -> Surreal:
    url = url or os.environ.get("SURREALDB_URL") or LOCAL_URL
    if url.startswith("surrealkv://"):
        pathlib.Path(url.removeprefix("surrealkv://")).parent.mkdir(parents=True, exist_ok=True)
    db = Surreal(url)
    if not url.startswith(EMBEDDED):
        db.signin({"username": os.environ["SURREALDB_USER"], "password": os.environ["SURREALDB_PASS"]})
    db.use(os.environ.get("SURREALDB_NAMESPACE", "daytrader"), os.environ.get("SURREALDB_DATABASE", "courses"))
    return db


def when(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def num(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rows(path: pathlib.Path):
    """JSONL rows; skips a half-written last line while an agent is still appending."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def load_sources(db: Surreal, course: str) -> int:
    stats = {r["source_id"]: r for r in rows(DATA / course / "sessions.jsonl")}
    n = 0
    for r in rows(DATA / course / "sources.jsonl"):
        doc = {k: r.get(k) for k in SOURCE_FIELDS if r.get(k) is not None}
        doc.update(course=RecordID("course", course), posted_at=when(r["posted_at"]))
        if r.get("release_utc"):
            doc["live_start"] = when(r["release_utc"])
        if s := stats.get(r["source_id"]):
            doc["stats"] = {k: v for k, v in s.items() if k not in ("source_id", "video_id", "posted_at", "release_utc")}
        db.query("UPSERT $id CONTENT $doc", {"id": RecordID("source", r["source_id"]), "doc": doc})
        n += 1
    return n


def load_events(db: Surreal, course: str) -> int:
    n = 0
    for r in rows(DATA / course / "events.jsonl"):
        doc = {k: r.get(k) for k in EVENT_TEXT if r.get(k) is not None}
        doc.update({k: num(r.get(k)) for k in EVENT_NUM if num(r.get(k)) is not None})
        doc.update(course=RecordID("course", course), source=RecordID("source", r["source_id"]),
                   targets=[t for t in map(num, r.get("targets") or []) if t is not None],
                   checks=r.get("checks") or {}, fail=r.get("fail") or [])
        if r.get("wall_utc"):
            doc["wall"] = when(r["wall_utc"])
        ticker = (r.get("ticker") or "").upper().strip() or None
        if ticker:
            doc["ticker"] = ticker
        eid = RecordID("event", r["event_id"])
        # MERGE keeps an embedding computed on an earlier run
        db.query("UPSERT $id MERGE $doc; DELETE mentions WHERE in = $id;", {"id": eid, "doc": doc})
        if ticker:
            db.query("UPSERT $t MERGE {market: $m}; RELATE $e->mentions->$t;",
                     {"t": RecordID("ticker", ticker), "m": r.get("market"), "e": eid})
        n += 1
    return n


def caption_words(path: pathlib.Path) -> list[tuple[float, str]]:
    """YouTube json3 captions -> (seconds, text) pieces; json3 drops the space between caption lines."""
    out = []
    for e in json.loads(path.read_text()).get("events", []):
        segs = e.get("segs")
        if not segs or "tStartMs" not in e:
            continue
        for i, s in enumerate(segs):
            t = s.get("utf8", "").replace("\n", " ") + (" " if i == len(segs) - 1 else "")
            if t.strip():
                out.append(((e["tStartMs"] + s.get("tOffsetMs", 0)) / 1000, t))
    return out


def load_segments(db: Surreal, course: str) -> int:
    n = 0
    for r in rows(DATA / course / "sources.jsonl"):
        if r.get("kind") != "youtube":
            continue
        vid = r["source_id"].split(":", 1)[1]
        cap = DATA / course / "youtube" / vid / f"{vid}.en-orig.json3"
        if not cap.exists():
            continue
        buckets: dict[int, list[str]] = {}
        for t, text in caption_words(cap):
            buckets.setdefault(int(t // SEGMENT_S) * SEGMENT_S, []).append(text)
        src = RecordID("source", r["source_id"])
        docs = [{"id": RecordID("segment", f"{r['source_id']}:{start:05d}"), "source": src, "start_s": start,
                 "end_s": start + SEGMENT_S, "text": " ".join("".join(parts).split())}
                for start, parts in sorted(buckets.items())]
        db.query("DELETE segment WHERE source = $s; INSERT INTO segment $docs;", {"s": src, "docs": docs})
        n += len(docs)
    return n


def embed_events(db: Surreal, batch: int = 96) -> int:
    from openai import OpenAI

    client = OpenAI(base_url=os.environ.get("NICRRON_BASE_URL") or "https://api.nicrron.ai/v1",
                    api_key=os.environ["NICRRON_API_KEY"])
    todo = db.query("SELECT id, rule, why FROM event WHERE embedding = NONE AND (rule != NONE OR why != NONE)")
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        texts = [(e.get("rule") or e.get("why"))[:2000] for e in chunk]
        vecs = client.embeddings.create(model="voyage/voyage-finance-2", input=texts).data
        for e, v in zip(chunk, vecs):
            db.query("UPDATE $id SET embedding = $v", {"id": e["id"], "v": v.embedding})
    return len(todo)


def stats(db: Surreal) -> None:
    for table in ("course", "source", "segment", "event", "ticker", "mentions"):
        print(f"{table:9}", db.query(f"RETURN count(SELECT id FROM {table})"))
    print("embedded ", db.query("RETURN count(SELECT id FROM event WHERE embedding != NONE)"))
    for course in COURSES:
        s = db.query("RETURN fn::course_summary($c)", {"c": course})
        if s and s.get("sources"):
            print(course, json.dumps(s, default=str)[:600])
    print("search   ", [r.get("rule") for r in db.query("RETURN fn::search_rules('stop loss', 3)")])
    print("ticker   ", db.query("RETURN fn::ticker_activity('TSLA')"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="override SURREALDB_URL")
    ap.add_argument("--embed", action="store_true")
    ap.add_argument("--stats", action="store_true", help="only print counts")
    ap.add_argument("--no-segments", action="store_true")
    a = ap.parse_args()
    db = connect(a.url)
    if not a.stats:
        db.query(SCHEMA.read_text())
        for course, meta in COURSES.items():
            db.query("UPSERT $id CONTENT $doc", {"id": RecordID("course", course), "doc": meta})
            s, e = load_sources(db, course), load_events(db, course)
            g = 0 if a.no_segments else load_segments(db, course)
            print(f"{course}: {s} sources, {e} events, {g} caption segments")
        if a.embed:
            print("embedded", embed_events(db), "events")
    stats(db)


if __name__ == "__main__":
    main()
