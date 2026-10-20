"""CAP-2: Luis grades a seeded sample of extracted events against their source (human precision and recall).

  cd app && uv run python -m audit.grade sample           # draw the sample -> data/audit/grade/sample.json
  cd app && uv run python -m audit.grade serve            # grade at http://127.0.0.1:8765 (Ctrl-C to stop)
  cd app && uv run python -m audit.grade score            # print precision / recall -> proofs/grading.json

Local only. Course text (captions, posts, transcribed screenshots) is read from data/ and shown on a page served
on 127.0.0.1; it is never written outside data/. proofs/grading.json holds numbers only.

Sample (seed 20261020, reproducible): 30 LPP v1 events, 30 Crypto Wizard events, every ZipTrader event, plus 3 LPP
sessions for recall. sample.json keeps the event ids and each events.jsonl sha256, so a changed extraction shows.

Precision = correct / (correct + wrong), skips excluded. LPP recall, over the recall sessions marked done:
found / (found + missed), where found = the session's extracted trade events not marked wrong there, and missed =
the trades Luis adds by hand.
"""
import argparse
import datetime as dt
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

from .paths import DATA, PROOFS

SEED = 20261020
SIZES = {"lpp": 30, "cryptowizard": 30, "ziptrader": None}   # None = every event
RECALL_SESSIONS = 3
RECALL_TYPES = {"trade"}
REASONS = ["ticker", "side", "price", "size", "not_a_trade", "other"]
CONTEXT_S = 30
CHUNK_S = 120


def grade_dir(data: Path = DATA) -> Path:
    return data / "audit" / "grade"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_events(data: Path, course: str) -> list[dict]:
    with open(data / course / "events.jsonl") as f:
        return [json.loads(line) for line in f if line.strip()]


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
    q = [_norm(w) for w in (quote or "").split()]
    q = [w for w in q if w]
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
    """The sample: event ids per course (sorted, seeded) and the recall sessions. Same inputs, same output."""
    out = {"seed": seed, "drawn_at": None, "courses": {}, "recall": {}}
    for course, n in SIZES.items():
        p = data / course / "events.jsonl"
        ids = sorted(e["event_id"] for e in read_events(data, course))
        pick = ids if n is None or n >= len(ids) else sorted(random.Random(f"{seed}:{course}").sample(ids, n))
        out["courses"][course] = {"events_sha256": sha256(p), "n_events": len(ids), "event_ids": pick}
    lpp = read_events(data, "lpp")
    has_trade = sorted({vid(e) for e in lpp if e.get("type") in RECALL_TYPES})
    pool = [v for v in has_trade if load_words(data, v)]
    sessions = sorted(random.Random(f"{seed}:lpp-recall").sample(pool, min(RECALL_SESSIONS, len(pool))))
    out["recall"] = {"course": "lpp", "types": sorted(RECALL_TYPES), "sessions": sessions,
                     "events_sha256": out["courses"]["lpp"]["events_sha256"]}
    return out


def write_sample(data: Path = DATA, seed: int = SEED) -> Path:
    s = draw(data, seed)
    s["drawn_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    p = grade_dir(data) / "sample.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(p.read_text()) if p.exists() else None
    if old and {k: old[k] for k in ("courses", "recall")} == {k: s[k] for k in ("courses", "recall")}:
        s["drawn_at"] = old.get("drawn_at")      # unchanged: keep the original stamp
    p.write_text(json.dumps(s, indent=1))
    return p


def load_sample(data: Path = DATA) -> dict:
    p = grade_dir(data) / "sample.json"
    if not p.exists():
        sys.exit("No sample yet: run `uv run python -m audit.grade sample` first.")
    return json.loads(p.read_text())


# ---------------------------------------------------------------- answers

def load_answers(data: Path = DATA) -> dict:
    p = grade_dir(data) / "answers.json"
    a = json.loads(p.read_text()) if p.exists() else {}
    a.setdefault("events", {})
    a.setdefault("recall", {})
    return a


def save_answers(a: dict, data: Path = DATA) -> None:
    p = grade_dir(data) / "answers.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(a, indent=1))
    tmp.replace(p)


def apply(a: dict, msg: dict) -> dict:
    """One click from the page -> answers. Event: {event_id, verdict, reason?}; recall: {session, ...}."""
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    if "event_id" in msg:
        v = msg.get("verdict")
        if v is None:
            a["events"].pop(msg["event_id"], None)
            return a
        if v not in ("correct", "wrong", "skip"):
            raise ValueError(f"bad verdict {v!r}")
        r = msg.get("reason") if v == "wrong" else None
        if v == "wrong" and r not in REASONS:
            raise ValueError(f"bad reason {r!r}")
        a["events"][msg["event_id"]] = {"verdict": v, "reason": r, "at": now}
    elif "session" in msg:
        s = a["recall"].setdefault(msg["session"], {"missed": [], "wrong": [], "done": False})
        if "missed" in msg:
            s["missed"] = [{"t": float(m.get("t", 0)), "note": str(m.get("note", ""))[:200]} for m in msg["missed"]]
        if "wrong" in msg:
            s["wrong"] = sorted(set(msg["wrong"]))
        if "done" in msg:
            s["done"] = bool(msg["done"])
        s["at"] = now
    else:
        raise ValueError("message needs event_id or session")
    return a


# ---------------------------------------------------------------- score

def score(sample: dict, answers: dict, data: Path | None = DATA) -> dict:
    """Numbers only: per course graded/correct/precision/wrong_by_reason, LPP recall, sample sha."""
    out = {"sample_sha256": hashlib.sha256(json.dumps({k: sample[k] for k in ("seed", "courses", "recall")},
                                                      sort_keys=True).encode()).hexdigest(),
           "seed": sample["seed"], "courses": {}, "lpp_recall": None,
           "graded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    ev = answers.get("events", {})
    for course, c in sample["courses"].items():
        got = [ev[i] for i in c["event_ids"] if i in ev]
        n_ok = sum(1 for g in got if g["verdict"] == "correct")
        n_bad = sum(1 for g in got if g["verdict"] == "wrong")
        graded = n_ok + n_bad
        changed = None
        if data is not None and (data / course / "events.jsonl").exists():
            changed = sha256(data / course / "events.jsonl") != c["events_sha256"]
        out["courses"][course] = {
            "sampled": len(c["event_ids"]), "graded": graded, "correct": n_ok,
            "skipped": sum(1 for g in got if g["verdict"] == "skip"),
            "precision": round(n_ok / graded, 4) if graded else None,
            "wrong_by_reason": {r: sum(1 for g in got if g["verdict"] == "wrong" and g.get("reason") == r)
                                for r in REASONS},
            "events_changed_since_sample": changed}
    rec = sample.get("recall") or {}
    if rec.get("sessions"):
        found = missed = done = 0
        extracted = _recall_extracted(rec, data) if data is not None else {}
        for v in rec["sessions"]:
            s = answers.get("recall", {}).get(v)
            if not s or not s.get("done"):
                continue
            done += 1
            ids = extracted.get(v, [])
            found += len([i for i in ids if i not in set(s.get("wrong", []))])
            missed += len(s.get("missed", []))
        out["lpp_recall"] = {"sessions": len(rec["sessions"]), "sessions_done": done, "found": found,
                             "missed": missed,
                             "recall": round(found / (found + missed), 4) if done and found + missed else None}
    return out


def _recall_extracted(rec: dict, data: Path) -> dict:
    want = set(rec["sessions"])
    types = set(rec.get("types", RECALL_TYPES))
    out: dict = {}
    for e in read_events(data, rec.get("course", "lpp")):
        if e.get("type") in types and vid(e) in want:
            out.setdefault(vid(e), []).append(e["event_id"])
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
        flag = "  (events.jsonl changed since the sample)" if c["events_changed_since_sample"] else ""
        print(f"{names.get(course, course):14} precision {p:>5}  {c['correct']}/{c['graded']} graded "
              f"of {c['sampled']}, {c['skipped']} skipped; wrong: {bad}{flag}")
    r = s.get("lpp_recall")
    if r:
        rr = f"{r['recall']:.0%}" if r["recall"] is not None else "-"
        print(f"{'LPP recall':14} {rr:>5}  found {r['found']}, missed {r['missed']} "
              f"({r['sessions_done']}/{r['sessions']} sessions done)")


# ---------------------------------------------------------------- what the page shows

SHOW = ["type", "status", "wall_utc", "ticker_said", "ticker", "side", "action", "instrument", "qty", "price",
        "entry", "stop", "targets", "level", "level_kind", "horizon", "why", "rule", "watch", "quote"]


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
        for line in p.read_text().splitlines():
            if line.strip():
                t = json.loads(line)
                out[t["source_id"]] = t["path"]      # the last transcription of a post wins
    return out


def items(data: Path = DATA) -> list[dict]:
    """Every sampled event with its fields and source context, in sample order."""
    sample = load_sample(data)
    posts, zt_tx, words_cache = _cw_posts(data), _zt_transcripts(data), {}
    zt_src = {}
    zp = data / "ziptrader" / "sources.jsonl"
    if zp.exists():
        zt_src = {json.loads(x)["source_id"]: json.loads(x) for x in zp.read_text().splitlines() if x.strip()}
    out = []
    for course, c in sample["courses"].items():
        by_id = {e["event_id"]: e for e in read_events(data, course)}
        for i in c["event_ids"]:
            e = by_id.get(i)
            if e is None:
                out.append({"course": course, "event_id": i, "missing": True})
                continue
            it = {"course": course, "event_id": i, "fields": {k: e.get(k) for k in SHOW if e.get(k) not in
                                                               (None, [], "")}}
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
                                 "images": [f"/img/{x}" for x in src.get("image_files", [])]}
            out.append(it)
    return out


def recall_sessions(data: Path = DATA) -> list[dict]:
    """Each recall session as caption chunks, with the extracted trade events inside each chunk."""
    rec = load_sample(data).get("recall") or {}
    ext = _recall_extracted(rec, data) if rec.get("sessions") else {}
    by_id = {e["event_id"]: e for e in read_events(data, "lpp")} if ext else {}
    out = []
    for v in rec.get("sessions", []):
        w = load_words(data, v)
        evs = sorted((by_id[i] for i in ext.get(v, [])), key=lambda e: _f(e.get("t_s")) or 0)
        end = w[-1][0] if w else 0
        chunks = []
        for lo in range(0, int(end) + 1, CHUNK_S):
            hi = lo + CHUNK_S
            chunks.append({"t": lo, "lines": lines(w, lo, hi - 0.001, every_s=10),
                           "events": [{"event_id": e["event_id"], "t": _f(e.get("t_s")),
                                       "fields": {k: e.get(k) for k in SHOW if e.get(k) not in (None, [], "")}}
                                      for e in evs if lo <= (_f(e.get("t_s")) or 0) < hi]})
        date = next((e.get("session_date") for e in evs), None)
        out.append({"session": v, "date": date, "n_extracted": len(evs), "chunks": chunks})
    return out


# ---------------------------------------------------------------- server

def make_server(data: Path = DATA, host: str = "127.0.0.1", port: int = 8765):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    page = (Path(__file__).parent / "grade.html").read_bytes()
    cache: dict = {}
    img_root = (data / "ziptrader").resolve()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, json.dumps(obj).encode())

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                return self._send(200, page, "text/html; charset=utf-8")
            if path == "/api/items":
                if "items" not in cache:
                    cache["items"] = items(data)
                return self._json({"items": cache["items"], "reasons": REASONS})
            if path == "/api/recall":
                if "recall" not in cache:
                    cache["recall"] = recall_sessions(data)
                return self._json({"sessions": cache["recall"]})
            if path == "/api/answers":
                return self._json(load_answers(data))
            if path == "/api/score":
                return self._json(score(load_sample(data), load_answers(data), data))
            if path.startswith("/img/"):
                p = (img_root / path[len("/img/"):]).resolve()
                if img_root in p.parents and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and p.exists():
                    return self._send(200, p.read_bytes(), "image/" + p.suffix.lower().lstrip(".").replace("jpg", "jpeg"))
            return self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/answer":
                return self._send(404, b"not found", "text/plain")
            try:
                msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                a = apply(load_answers(data), msg)
            except (ValueError, KeyError, TypeError) as e:
                return self._json({"error": str(e)}, 400)
            save_answers(a, data)
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
            print(f"{course:13} {len(c['event_ids']):3} of {c['n_events']} events  sha256 {c['events_sha256'][:12]}")
        print(f"lpp recall    {len(smp['recall']['sessions'])} sessions: {', '.join(smp['recall']['sessions'])}")
        print(f"-> {p}")
    elif a.cmd == "serve":
        load_sample(DATA)
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
