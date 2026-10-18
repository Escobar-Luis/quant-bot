"""Load every course's JSONL (and LPP captions) into SurrealDB. Safe to re-run.

    uv run python -m db.load            # schema + sources + events + caption segments
    uv run python -m db.load --embed    # also embed rule text with voyage-finance-2 (Nicrron)
    uv run python -m db.load --stats    # print counts and one call of each agent function

Embedded on disk by default (surrealkv:// under ~/dev/quant-bot/data/surreal). Set SURREALDB_URL
(wss://<instance>.surreal.cloud), SURREALDB_USER and SURREALDB_PASS in ~/dev/quant-bot/.env for Surreal Cloud.
Schema and design: app/db/schema.surql, notes/storage-surrealdb.md.
"""

import argparse
import json
import os
import pathlib
import re
from datetime import datetime

from dotenv import load_dotenv
from surrealdb import RecordID, Surreal

ROOT = pathlib.Path.home() / "dev" / "quant-bot"
load_dotenv(ROOT / ".env")
DATA = pathlib.Path(os.environ.get("DATA_DIR", ROOT / "data"))
LOCAL_URL = f"surrealkv://{DATA / 'surreal' / 'daytrader'}"
EMBEDDED = ("mem://", "memory://", "surrealkv://", "file://")
SCHEMA = pathlib.Path(__file__).with_name("schema.surql")
INDEXES = pathlib.Path(__file__).with_name("indexes.surql")
BATCH = 250  # rows per query: few round trips to a Cloud instance, well under its 4 MiB RPC cap

COURSES = {
    "lpp": {"name": "Learn Plan Profit", "market": "us_equities"},
    "ziptrader": {"name": "ZipTrader", "market": "us_equities"},
    "cryptowizard": {"name": "Crypto Wizard", "market": "crypto"},
}
SOURCE_FIELDS = ("kind", "url", "server_id", "channel", "channel_id", "message_id", "author", "author_role",
                 "title", "duration_s", "captions")
EVENT_TEXT = ("type", "session_date", "market", "ticker_said", "side", "action", "instrument", "level_kind",
              "level_ref", "watch", "horizon", "why", "rule", "quote", "status", "model", "prompt_version")
EVENT_NUM = ("t_s", "qty", "price", "entry", "stop", "level")
EVENT_OWN = {*EVENT_TEXT, *EVENT_NUM, "event_id", "source_id", "course", "targets", "checks", "fail", "wall_utc", "ticker"}
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


def dialect(db: Surreal, sql: str) -> str:
    """schema.surql is written for SurrealDB 2.x; Surreal Cloud data tools need 3.1+, which renamed a few words."""
    major = int(re.search(r"(\d+)\.", str(db.version())).group(1))
    if major < 3:
        return sql
    sql = re.sub(r"FLEXIBLE TYPE ([^\s;]+)", r"TYPE \1 FLEXIBLE", sql)
    return sql.replace("SEARCH ANALYZER", "FULLTEXT ANALYZER").replace("type::thing(", "type::record(")


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


def batches(items: list, size: int = BATCH):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def session_keys(course: str) -> dict[str, str]:
    """video id -> public session key (lpp:<YYYY-MM-DD>), from the gitignored data/<course>/session_keys.json."""
    path = DATA / course / "session_keys.json"
    if not path.exists():
        return {}
    return {v["video_id"]: key for key, v in json.loads(path.read_text()).items()}


def load_sources(db: Surreal, course: str) -> int:
    stats = {r["source_id"]: r for r in rows(DATA / course / "sessions.jsonl")}
    keys = session_keys(course)
    docs = []
    for r in rows(DATA / course / "sources.jsonl"):
        doc = {k: r.get(k) for k in SOURCE_FIELDS if r.get(k) is not None}
        doc.update(course=RecordID("course", course), posted_at=when(r["posted_at"]))
        if r.get("release_utc"):
            doc["live_start"] = when(r["release_utc"])
        if key := keys.get(r["source_id"].split(":", 1)[1]):
            doc["session_key"] = key
        if s := stats.get(r["source_id"]):
            doc["stats"] = {k: v for k, v in s.items() if k not in ("source_id", "video_id", "posted_at", "release_utc")}
        docs.append({"id": RecordID("source", r["source_id"]), "doc": doc})
    for b in batches(docs):
        db.query("FOR $r IN $rows { UPSERT $r.id CONTENT $r.doc; };", {"rows": b})
    return len(docs)


def load_events(db: Surreal, course: str) -> int:
    docs, edges, tickers = [], [], {}
    for r in rows(DATA / course / "events.jsonl"):
        doc = {k: r.get(k) for k in EVENT_TEXT if r.get(k) is not None}
        doc.update({k: num(r.get(k)) for k in EVENT_NUM if num(r.get(k)) is not None})
        doc.update(course=RecordID("course", course), source=RecordID("source", r["source_id"]),
                   targets=[t for t in map(num, r.get("targets") or []) if t is not None],
                   checks=r.get("checks") or {}, fail=r.get("fail") or [])
        if r.get("wall_utc"):
            doc["wall"] = when(r["wall_utc"])
        if extra := {k: v for k, v in r.items() if k not in EVENT_OWN and v not in (None, [], {})}:
            doc["extra"] = extra  # nothing a collector writes is dropped
        eid = RecordID("event", r["event_id"])
        if ticker := (r.get("ticker") or "").upper().strip() or None:
            doc["ticker"] = ticker
            tickers[ticker] = r.get("market")
            edges.append({"in": eid, "out": RecordID("ticker", ticker)})
        docs.append({"id": eid, "doc": doc})
    tick = [{"id": RecordID("ticker", t), "market": m} for t, m in tickers.items()]
    for b in batches(tick):
        db.query("FOR $t IN $rows { UPSERT $t.id MERGE {market: $t.market}; };", {"rows": b})
    for b in batches(docs):
        # MERGE keeps an embedding computed on an earlier run; edges are rebuilt
        db.query("FOR $r IN $rows { UPSERT $r.id MERGE $r.doc; }; DELETE mentions WHERE in IN $ids;",
                 {"rows": b, "ids": [d["id"] for d in b]})
    for b in batches(edges):
        db.query("INSERT RELATION INTO mentions $rows;", {"rows": b})
    return len(docs)


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
        for b in batches(docs):
            # fixed ids + upsert: re-runs never scan the table to delete a session's old rows
            db.query("INSERT INTO segment $docs ON DUPLICATE KEY UPDATE text = $input.text, end_s = $input.end_s;",
                     {"docs": b})
        n += len(docs)
    return n


def embed_events(db: Surreal, batch: int = 96) -> int:
    from openai import OpenAI

    client = OpenAI(base_url=os.environ.get("NICRRON_BASE_URL") or "https://api.nicrron.ai/v1",
                    api_key=os.environ["NICRRON_API_KEY"])
    # rules only: what fn::similar_rules searches; keeps the free instance small (~8 KB per vector)
    todo = db.query("SELECT id, rule FROM event WHERE type = 'rule' AND rule != NONE AND embedding = NONE")
    for chunk in batches(todo, batch):
        vecs = client.embeddings.create(model="voyage/voyage-finance-2", input=[e["rule"][:2000] for e in chunk]).data
        db.query("FOR $u IN $rows { UPDATE $u.id SET embedding = $u.v; };",
                 {"rows": [{"id": e["id"], "v": v.embedding} for e, v in zip(chunk, vecs)]})
    return len(todo)


def stats(db: Surreal) -> None:
    for table in ("course", "source", "segment", "event", "ticker", "mentions"):
        print(f"{table:9}", db.query(f"RETURN count(SELECT id FROM {table})"))
    print("embedded ", db.query("RETURN count(SELECT id FROM event WHERE embedding != NONE)"))
    try:
        for course in COURSES:
            s = db.query("RETURN fn::course_summary($c)", {"c": course})
            if s and s.get("sources"):
                print(course, json.dumps(s, default=str)[:600])
        print("search   ", [r.get("rule") for r in db.query("RETURN fn::search_rules('stop loss', 3)")])
        print("ticker   ", db.query("RETURN fn::ticker_activity('TSLA')"))
    except Exception as e:  # an empty database has no schema or functions yet
        print("functions unavailable:", str(e)[:120])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="override SURREALDB_URL")
    ap.add_argument("--embed", action="store_true", help="embed rule text with voyage-finance-2 (Nicrron)")
    ap.add_argument("--stats", action="store_true", help="only print counts")
    ap.add_argument("--no-segments", action="store_true")
    a = ap.parse_args()
    db = connect(a.url)
    if not a.stats:
        db.query(dialect(db, SCHEMA.read_text()))
        for course, meta in COURSES.items():
            db.query("UPSERT $id CONTENT $doc", {"id": RecordID("course", course), "doc": meta})
            s, e = load_sources(db, course), load_events(db, course)
            g = 0 if a.no_segments else load_segments(db, course)
            print(f"{course}: {s} sources, {e} events, {g} caption segments")
        db.query(dialect(db, INDEXES.read_text()))  # rule full-text and vector indexes, built once at the end
        if a.embed:
            print("embedded", embed_events(db), "rules")
    stats(db)


if __name__ == "__main__":
    main()
