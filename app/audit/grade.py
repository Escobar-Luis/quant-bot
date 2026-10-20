"""CAP-2: Luis grades a seeded sample of extracted events against their source (human precision and recall).

  cd app && uv run python -m audit.grade sample           # draw the sample -> data/audit/grade/sample.json
  cd app && uv run python -m audit.grade serve            # grade at http://127.0.0.1:8765 (Ctrl-C to stop)
  cd app && uv run python -m audit.grade score            # print precision / recall -> proofs/grading.json

Local only. Course text (captions, posts, transcribed screenshots) is read from data/ and shown on a page served
on 127.0.0.1 (Host and Origin checked); it is never written outside data/. proofs/ gets numbers and event ids only.

Population: what the backtest prices (results/<course>/v1.json), so precision speaks for the money numbers.
  LPP           data/lpp/events.jsonl: `trade` events with a ticker and action, status ok or failing only the
                ledger checks (contracts.md rule 11; the same test as backtest.lpp.usable).
  Crypto Wizard data/cryptowizard/events.calls.jsonl: ok `call`s with an entry and a symbol, and the ok `trade`
                updates linked to one (backtest.cryptowizard.build).
  ZipTrader     data/ziptrader/events.jsonl: every event (86), each labelled with its type.
Sample (seed 20261021, reproducible): 30 LPP, 30 Crypto Wizard, every ZipTrader event, plus 3 LPP sessions for
recall. sample.json keeps the event ids, their types and each source file's sha256; grading refuses to start if
a source file changed since the sample. proofs/grading-sample.json is the same record, ids only, for git.

Precision = correct / (correct + wrong), skips excluded. LPP recall, over the recall sessions marked done:
found / (found + missed), where found = the session's priced trade events not marked wrong there, and missed =
the trades Luis adds by hand.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path

from .paths import DATA, PROOFS

SEED = 20261021            # 20261020 drew from every event type; re-drawn from the priced population
SAMPLE_VERSION = 2
SIZES = {"lpp": 30, "cryptowizard": 30, "ziptrader": None}   # None = every event
RECALL_SESSIONS = 3
REASONS = ["ticker", "side", "price", "size", "not_a_trade", "other"]
CONTEXT_S = 30
CHUNK_S = 120
LEDGER_FAILS = {"open_never_closed", "close_without_open", "qty_exceeds_position"}   # contracts.md rule 11


class SampleStale(Exception):
    pass


def grade_dir(data: Path = DATA) -> Path:
    return data / "audit" / "grade"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_jsonl(p: Path) -> list[dict]:
    with open(p) as f:
        return [json.loads(line) for line in f if line.strip()]


def read_events(data: Path, course: str) -> list[dict]:
    return read_jsonl(data / course / "events.jsonl")


# ---------------------------------------------------------------- population (what the backtest prices)

def lpp_priced(e: dict) -> bool:
    return e.get("type") == "trade" and bool(e.get("ticker")) and bool(e.get("action")) and \
        (e.get("status") == "ok" or (bool(e.get("fail")) and set(e["fail"]) <= LEDGER_FAILS))


def _cw_symbol(e: dict) -> bool:
    return bool(e.get("pair") or e.get("ticker"))


def population(data: Path, course: str) -> tuple[Path, list[dict]]:
    """(source file, the events in it that the backtest prices)."""
    if course == "lpp":
        p = data / "lpp" / "events.jsonl"
        return p, [e for e in read_jsonl(p) if lpp_priced(e)]
    if course == "cryptowizard":
        p = data / "cryptowizard" / "events.calls.jsonl"
        evs = read_jsonl(p)
        calls = {e["event_id"] for e in evs if e.get("type") == "call" and e.get("status") == "ok"
                 and e.get("entry") and _cw_symbol(e)}
        return p, [e for e in evs if e["event_id"] in calls or
                   (e.get("type") == "trade" and e.get("status") == "ok" and e.get("links_to") in calls)]
    p = data / course / "events.jsonl"
    return p, read_jsonl(p)


# ---------------------------------------------------------------- captions (LPP)

def load_words(data: Path, video_id: str) -> list[tuple[float, str]]:
    """[(t_s, word)] from the session's json3 auto-captions, [Music]-style tags dropped."""
    d = data / "lpp" / "youtube" / video_id
    caps = sorted(d.glob("*.en-orig.json3")) or sorted(d.glob("*.en.json3"))
    if not caps:
        return []
    words = []
    for e in json.loads(caps[0].read_text()).get("events", []):
        if "segs" not in e or "tStartMs" not in e:
            continue
        for s in e["segs"]:
            for w in s.get("utf8", "").split():
                if not (w.startswith("[") and w.endswith("]")):
                    words.append(((e["tStartMs"] + s.get("tOffsetMs", 0)) / 1000, w))
    return words


def _norm(w: str) -> str:
    return "".join(ch for ch in w.lower() if ch.isalnum() or ch in ".$%")


def find_quote(words: list, quote: str | None, near: float | None) -> tuple[int, int] | None:
    """Index span [i, j) of `quote` in the words (closest to `near`), else None."""
    q = [w for w in (_norm(x) for x in (quote or "").split()) if w]
    flat = [_norm(w) for _, w in words]
    if not q:
        return None
    hits = [i for i in range(len(flat) - len(q) + 1) if flat[i:i + len(q)] == q]
    if not hits:
        return None
    i = min(hits, key=lambda h: abs(words[h][0] - near)) if near is not None else hits[0]
    return i, i + len(q)


def lines(words: list, lo: float, hi: float, span: tuple[int, int] | None = None, every_s: float = 5) -> list[dict]:
    """Caption lines [{t, text, hit}] for words in [lo, hi], one line per ~every_s seconds."""
    out, cur, t0, hit = [], [], None, False
    for k, (t, w) in enumerate(words):
        if t < lo or t > hi:
            continue
        if t0 is not None and t - t0 >= every_s and cur:
            out.append({"t": t0, "text": " ".join(cur), "hit": hit})
            cur, t0, hit = [], None, False
        t0 = t if t0 is None else t0
        cur.append(w)
        hit = hit or bool(span and span[0] <= k < span[1])
    if cur:
        out.append({"t": t0, "text": " ".join(cur), "hit": hit})
    return out


def _f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def vid(e: dict) -> str:
    return e["source_id"].split(":", 1)[1]


# ---------------------------------------------------------------- sample

def draw(data: Path = DATA, seed: int = SEED) -> dict:
    """The sample: event ids (and types) per course, sorted and seeded, plus the recall sessions."""
    out = {"seed": seed, "sample_version": SAMPLE_VERSION, "drawn_at": None, "courses": {}, "recall": {}}
    for course, n in SIZES.items():
        p, evs = population(data, course)
        types = {e["event_id"]: e.get("type") for e in evs}
        ids = sorted(types)
        pick = ids if n is None or n >= len(ids) else sorted(random.Random(f"{seed}:{course}").sample(ids, n))
        out["courses"][course] = {"file": str(p.relative_to(data)), "file_sha256": sha256(p),
                                  "n_population": len(ids), "event_ids": pick,
                                  "types": {i: types[i] for i in pick}}
    _, lpp = population(data, "lpp")
    pool = [v for v in sorted({vid(e) for e in lpp}) if load_words(data, v)]
    sessions = sorted(random.Random(f"{seed}:lpp-recall").sample(pool, min(RECALL_SESSIONS, len(pool))))
    out["recall"] = {"course": "lpp", "found": "priced trade events", "sessions": sessions}
    return out


def _core(s: dict) -> dict:
    return {k: s.get(k) for k in ("seed", "sample_version", "courses", "recall")}


def write_sample(data: Path = DATA, seed: int = SEED, proofs: Path = PROOFS) -> Path:
    s = draw(data, seed)
    s["drawn_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    p = grade_dir(data) / "sample.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(p.read_text()) if p.exists() else None
    if old and _core(old) == _core(s):
        s["drawn_at"] = old.get("drawn_at")      # unchanged: keep the original stamp
    p.write_text(json.dumps(s, indent=1))
    proofs.mkdir(parents=True, exist_ok=True)
    (proofs / "grading-sample.json").write_text(json.dumps(s, indent=1) + "\n")   # ids, types, hashes: no text
    return p


def load_sample(data: Path = DATA) -> dict:
    p = grade_dir(data) / "sample.json"
    if not p.exists():
        sys.exit("No sample yet: run `uv run python -m audit.grade sample` first.")
    return json.loads(p.read_text())


def stale(sample: dict, data: Path = DATA) -> list[str]:
    """Source files that changed since the sample was drawn."""
    return [c["file"] for c in sample["courses"].values()
            if not (data / c["file"]).exists() or sha256(data / c["file"]) != c["file_sha256"]]


def sample_ids(sample: dict) -> set[str]:
    return {i for c in sample["courses"].values() for i in c["event_ids"]}


# ---------------------------------------------------------------- answers

_LOCK = threading.Lock()


def load_answers(data: Path = DATA) -> dict:
    p = grade_dir(data) / "answers.json"
    a = json.loads(p.read_text()) if p.exists() else {}
    a.setdefault("events", {})
    a.setdefault("recall", {})
    return a


def save_answers(a: dict, data: Path = DATA) -> None:
    p = grade_dir(data) / "answers.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="answers.", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(a, f, indent=1)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def record(msg: dict, sample: dict, recall_ids: dict, data: Path = DATA) -> dict:
    """Load, apply one click, save: one at a time."""
    with _LOCK:
        a = apply(load_answers(data), msg, sample, recall_ids)
        save_answers(a, data)
        return a


def apply(a: dict, msg: dict, sample: dict, recall_ids: dict | None = None) -> dict:
    """One click from the page -> answers. Event: {event_id, verdict, reason?}; recall: {session, ...}.

    Only ids and sessions in the sample are accepted; recall_ids = {session: [its priced trade event ids]}."""
    if not isinstance(msg, dict):
        raise ValueError("message must be an object")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    if "event_id" in msg:
        eid = msg["event_id"]
        if not isinstance(eid, str) or eid not in sample_ids(sample):
            raise ValueError(f"event {eid!r} is not in the sample")
        v = msg.get("verdict")
        if v is None:
            a["events"].pop(eid, None)
            return a
        if v not in ("correct", "wrong", "skip"):
            raise ValueError(f"bad verdict {v!r}")
        r = msg.get("reason") if v == "wrong" else None
        if v == "wrong" and r not in REASONS:
            raise ValueError(f"bad reason {r!r}")
        a["events"][eid] = {"verdict": v, "reason": r, "at": now}
    elif "session" in msg:
        sid = msg["session"]
        if not isinstance(sid, str) or sid not in (sample.get("recall") or {}).get("sessions", []):
            raise ValueError(f"session {sid!r} is not a recall session")
        new = dict(a["recall"].get(sid) or {"missed": [], "wrong": [], "done": False})
        if "missed" in msg:
            m = msg["missed"]
            if not isinstance(m, list) or not all(isinstance(x, dict) for x in m):
                raise ValueError("missed must be a list of objects")
            out = []
            for x in m:
                t = x.get("t", 0)
                if isinstance(t, bool) or not isinstance(t, (int, float)) or t < 0:
                    raise ValueError(f"bad missed time {t!r}")
                note = x.get("note", "")
                if not isinstance(note, str):
                    raise ValueError("missed note must be text")
                out.append({"t": float(t), "note": note[:200]})
            new["missed"] = out
        if "wrong" in msg:
            w = msg["wrong"]
            known = set((recall_ids or {}).get(sid, []))
            if not isinstance(w, list) or not all(isinstance(x, str) and x in known for x in w):
                raise ValueError("wrong must list this session's extracted trade ids")
            new["wrong"] = sorted(set(w))
        if "done" in msg:
            if not isinstance(msg["done"], bool):
                raise ValueError("done must be true or false")
            new["done"] = msg["done"]
        new["at"] = now
        a["recall"][sid] = new
    else:
        raise ValueError("message needs event_id or session")
    return a


# ---------------------------------------------------------------- score

def score(sample: dict, answers: dict, data: Path | None = DATA) -> dict:
    """Numbers only: per course graded/correct/precision/wrong_by_reason (and by type), LPP recall, sample sha."""
    out = {"sample_sha256": hashlib.sha256(json.dumps(_core(sample), sort_keys=True).encode()).hexdigest(),
           "seed": sample["seed"], "sample_version": sample.get("sample_version"), "courses": {},
           "lpp_recall": None, "graded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    ev = answers.get("events", {})
    changed = set(stale(sample, data)) if data is not None else set()
    for course, c in sample["courses"].items():
        def count(ids):
            got = [ev[i] for i in ids if i in ev]
            ok = sum(1 for g in got if g["verdict"] == "correct")
            bad = sum(1 for g in got if g["verdict"] == "wrong")
            return got, ok, bad
        got, n_ok, n_bad = count(c["event_ids"])
        graded = n_ok + n_bad
        by_type = {}
        for t in sorted({x or "?" for x in c.get("types", {}).values()}):
            _, tok, tbad = count([i for i in c["event_ids"] if (c["types"].get(i) or "?") == t])
            by_type[t] = {"sampled": sum(1 for i in c["event_ids"] if (c["types"].get(i) or "?") == t),
                          "graded": tok + tbad, "correct": tok,
                          "precision": round(tok / (tok + tbad), 4) if tok + tbad else None}
        out["courses"][course] = {
            "population": c.get("n_population"), "sampled": len(c["event_ids"]), "graded": graded,
            "correct": n_ok, "skipped": sum(1 for g in got if g["verdict"] == "skip"),
            "precision": round(n_ok / graded, 4) if graded else None,
            "wrong_by_reason": {r: sum(1 for g in got if g["verdict"] == "wrong" and g.get("reason") == r)
                                for r in REASONS},
            "by_type": by_type,
            "source_changed_since_sample": (c["file"] in changed) if data is not None else None}
    rec = sample.get("recall") or {}
    if rec.get("sessions"):
        found = missed = done = 0
        extracted = recall_extracted(sample, data) if data is not None else {}
        for v in rec["sessions"]:
            s = answers.get("recall", {}).get(v)
            if not s or not s.get("done"):
                continue
            done += 1
            found += len([i for i in extracted.get(v, []) if i not in set(s.get("wrong", []))])
            missed += len(s.get("missed", []))
        out["lpp_recall"] = {"sessions": len(rec["sessions"]), "sessions_done": done, "found": found,
                             "missed": missed,
                             "recall": round(found / (found + missed), 4) if done and found + missed else None}
    return out


def recall_extracted(sample: dict, data: Path) -> dict:
    """{session: [its priced trade event ids]} for the recall sessions."""
    want = set((sample.get("recall") or {}).get("sessions", []))
    out: dict = {v: [] for v in sorted(want)}
    if want:
        for e in population(data, "lpp")[1]:
            if vid(e) in want:
                out[vid(e)].append(e["event_id"])
    return out


def write_score(data: Path = DATA, proofs: Path = PROOFS) -> dict:
    s = score(load_sample(data), load_answers(data), data)
    proofs.mkdir(parents=True, exist_ok=True)
    (proofs / "grading.json").write_text(json.dumps(s, indent=1) + "\n")
    return s


def print_score(s: dict) -> None:
    names = {"lpp": "LPP", "cryptowizard": "Crypto Wizard", "ziptrader": "ZipTrader"}
    for course, c in s["courses"].items():
        p = f"{c['precision']:.0%}" if c["precision"] is not None else "-"
        bad = ", ".join(f"{r} {n}" for r, n in c["wrong_by_reason"].items() if n) or "none"
        flag = "  (source changed since the sample)" if c["source_changed_since_sample"] else ""
        print(f"{names.get(course, course):14} precision {p:>5}  {c['correct']}/{c['graded']} graded "
              f"of {c['sampled']}, {c['skipped']} skipped; wrong: {bad}{flag}")
        if len(c["by_type"]) > 1:
            for t, b in c["by_type"].items():
                bp = f"{b['precision']:.0%}" if b["precision"] is not None else "-"
                print(f"{'':16}{t:8} {bp:>5}  {b['correct']}/{b['graded']} of {b['sampled']}")
    r = s.get("lpp_recall")
    if r:
        rr = f"{r['recall']:.0%}" if r["recall"] is not None else "-"
        print(f"{'LPP recall':14} {rr:>5}  found {r['found']}, missed {r['missed']} "
              f"({r['sessions_done']}/{r['sessions']} sessions done)")


# ---------------------------------------------------------------- what the page shows

SHOW = ["type", "status", "wall_utc", "ticker_said", "ticker", "side", "action", "instrument", "qty", "price",
        "entry", "stop", "targets", "level", "level_kind", "horizon", "links_to", "why", "rule", "watch", "quote"]


def _fields(e: dict) -> dict:
    return {k: e.get(k) for k in SHOW if e.get(k) not in (None, [], "")}


def _cw_posts(data: Path) -> dict:
    posts = {}
    for f in sorted((data / "cryptowizard" / "raw").glob("*.json")):
        for p in json.loads(f.read_text()).get("posts", []):
            posts[p["message_id"]] = p
    return posts


def _zt_transcripts(data: Path) -> dict:
    out = {}
    p = data / "ziptrader" / "discord" / "transcripts.jsonl"
    if p.exists():
        for t in read_jsonl(p):
            out[t["source_id"]] = t["path"]      # the last transcription of a post wins
    return out


def items(data: Path = DATA) -> list[dict]:
    """Every sampled event with its fields and source context, in sample order."""
    sample = load_sample(data)
    posts, zt_tx, words_cache = _cw_posts(data), _zt_transcripts(data), {}
    zp = data / "ziptrader" / "sources.jsonl"
    zt_src = {s["source_id"]: s for s in read_jsonl(zp)} if zp.exists() else {}
    out = []
    for course, c in sample["courses"].items():
        by_id = {e["event_id"]: e for e in read_jsonl(data / c["file"])}
        for i in c["event_ids"]:
            e = by_id.get(i)
            if e is None:
                out.append({"course": course, "event_id": i, "missing": True})
                continue
            it = {"course": course, "event_id": i, "fields": _fields(e)}
            if course == "lpp":
                v = vid(e)
                w = words_cache.setdefault(v, load_words(data, v))
                t = _f(e.get("t_s"))
                span = find_quote(w, e.get("quote"), t)
                at = w[span[0]][0] if span else t
                it["context"] = {"kind": "captions", "session": v, "at": at, "quote_found": bool(span),
                                 "lines": lines(w, (at or 0) - CONTEXT_S, (at or 0) + CONTEXT_S, span)
                                 if at is not None else []}
            elif course == "cryptowizard":
                p = posts.get(e["source_id"].split("/")[-1], {})
                it["context"] = {"kind": "post", "text": p.get("text", "(post not found in raw/)"),
                                 "channel": p.get("channel"), "posted_at": p.get("posted_at")}
            else:
                tx = zt_tx.get(e["source_id"])
                txt = (data / "ziptrader" / tx).read_text() if tx and (data / "ziptrader" / tx).exists() \
                    else "(no transcription found)"
                src = zt_src.get(e["source_id"], {})
                it["context"] = {"kind": "screenshot", "text": txt, "channel": src.get("channel"),
                                 "posted_at": src.get("posted_at"),
                                 "images": ["/img/" + urllib.parse.quote(x) for x in src.get("image_files", [])]}
            out.append(it)
    return out


def recall_sessions(data: Path = DATA) -> list[dict]:
    """Each recall session as caption chunks, with its priced trade events inside each chunk.

    Events (and missed marks) after the last caption chunk belong to the last chunk."""
    sample = load_sample(data)
    ext = recall_extracted(sample, data)
    by_id = {e["event_id"]: e for e in population(data, "lpp")[1]} if any(ext.values()) else {}
    out = []
    for v in (sample.get("recall") or {}).get("sessions", []):
        w = load_words(data, v)
        evs = sorted((by_id[i] for i in ext.get(v, [])), key=lambda e: _f(e.get("t_s")) or 0)
        end = w[-1][0] if w else 0
        starts = list(range(0, int(end) + 1, CHUNK_S))
        chunks = []
        for k, lo in enumerate(starts):
            last = k == len(starts) - 1
            hi = lo + CHUNK_S
            chunks.append({"t": lo, "end": None if last else hi,
                           "lines": lines(w, lo, hi - 0.001, every_s=10),
                           "events": [{"event_id": e["event_id"], "t": _f(e.get("t_s")), "fields": _fields(e)}
                                      for e in evs if lo <= (_f(e.get("t_s")) or 0) and
                                      (last or (_f(e.get("t_s")) or 0) < hi)]})
        date = next((e.get("session_date") for e in evs), None)
        out.append({"session": v, "date": date, "n_extracted": len(evs), "chunks": chunks})
    return out


# ---------------------------------------------------------------- server

def make_server(data: Path = DATA, host: str = "127.0.0.1", port: int = 8765):
    """Local grading server. Every request must name this server in Host (no DNS rebinding); a POST must be JSON
    from this page's own Origin (no cross-site form posts)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    page = (Path(__file__).parent / "grade.html").read_bytes()
    img_root = (data / "ziptrader").resolve()
    state: dict = {"key": None}
    sample_p = grade_dir(data) / "sample.json"

    def current() -> dict:
        """Sample-derived data, rebuilt when sample.json changes; refuses a stale sample."""
        st = sample_p.stat()
        key = (st.st_mtime_ns, st.st_size)
        if state["key"] != key:
            sample = load_sample(data)
            bad = stale(sample, data)
            if bad:
                raise SampleStale(f"{', '.join(bad)} changed since the sample was drawn: re-run "
                                  "`uv run python -m audit.grade sample` before grading.")
            state.update(key=key, sample=sample, recall_ids=recall_extracted(sample, data),
                         items=None, recall=None)
        return state

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _allowed(self) -> set[str]:
            p = self.server.server_address[1]
            return {f"127.0.0.1:{p}", f"localhost:{p}"}

        def _send(self, code: int, body: bytes, ctype: str = "application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, json.dumps(obj).encode())

        def _host_ok(self) -> bool:
            if self.headers.get("Host") not in self._allowed():
                self._send(403, b"forbidden host", "text/plain")
                return False
            return True

        def do_GET(self):
            if not self._host_ok():
                return
            path = self.path.split("?", 1)[0]
            if path == "/":
                return self._send(200, page, "text/html; charset=utf-8")
            if path.startswith("/img/"):
                rel = urllib.parse.unquote(path[len("/img/"):])
                p = (img_root / rel).resolve()
                if p.is_relative_to(img_root) and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") \
                        and p.is_file():
                    ext = p.suffix.lower().lstrip(".").replace("jpg", "jpeg")
                    return self._send(200, p.read_bytes(), "image/" + ext)
                return self._send(404, b"not found", "text/plain")
            try:
                st = current()
            except SampleStale as e:
                return self._json({"error": str(e)}, 409)
            if path == "/api/items":
                if st["items"] is None:
                    st["items"] = items(data)
                return self._json({"items": st["items"], "reasons": REASONS})
            if path == "/api/recall":
                if st["recall"] is None:
                    st["recall"] = recall_sessions(data)
                return self._json({"sessions": st["recall"]})
            if path == "/api/answers":
                return self._json(load_answers(data))
            if path == "/api/score":
                return self._json(score(st["sample"], load_answers(data), data))
            return self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if not self._host_ok():
                return
            if self.path != "/api/answer":
                return self._send(404, b"not found", "text/plain")
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            origin = self.headers.get("Origin") or ""
            if ctype != "application/json" or origin not in {f"http://{h}" for h in self._allowed()}:
                return self._send(403, b"forbidden: JSON from this page only", "text/plain")
            try:
                st = current()
                n = int(self.headers.get("Content-Length", 0))
                if n > 1_000_000:
                    raise ValueError("too large")
                msg = json.loads(self.rfile.read(n))
                a = record(msg, st["sample"], st["recall_ids"], data)
            except SampleStale as e:
                return self._json({"error": str(e)}, 409)
            except (ValueError, KeyError, TypeError) as e:
                return self._json({"error": str(e)}, 400)
            return self._json({"ok": True, "graded": len(a["events"])})

    return ThreadingHTTPServer((host, port), H)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="audit.grade", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="draw the seeded sample")
    s.add_argument("--seed", type=int, default=SEED)
    v = sub.add_parser("serve", help="grade on a local page")
    v.add_argument("--port", type=int, default=8765)
    sub.add_parser("score", help="precision and recall -> proofs/grading.json")
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        p = write_sample(DATA, a.seed)
        smp = json.loads(p.read_text())
        for course, c in smp["courses"].items():
            types = {}
            for t in c["types"].values():
                types[t] = types.get(t, 0) + 1
            print(f"{course:13} {len(c['event_ids']):3} of {c['n_population']} priced events "
                  f"({', '.join(f'{k} {n}' for k, n in sorted(types.items()))})  {c['file']} "
                  f"sha256 {c['file_sha256'][:12]}")
        print(f"lpp recall    {len(smp['recall']['sessions'])} sessions: {', '.join(smp['recall']['sessions'])}")
        print(f"-> {p}\n-> {PROOFS / 'grading-sample.json'} (ids only)")
    elif a.cmd == "serve":
        bad = stale(load_sample(DATA), DATA)
        if bad:
            sys.exit(f"Not grading: {', '.join(bad)} changed since the sample was drawn. "
                     "Re-run `uv run python -m audit.grade sample` first.")
        srv = make_server(DATA, port=a.port)
        print(f"Grading at http://127.0.0.1:{a.port}  (answers -> {grade_dir(DATA) / 'answers.json'}; Ctrl-C stops)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            srv.server_close()
    else:
        s = write_score()
        print_score(s)
        print(f"-> {PROOFS / 'grading.json'}")


if __name__ == "__main__":
    main()
