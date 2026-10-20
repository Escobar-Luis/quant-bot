"""CAP-2 grading: the sample is seeded and reproducible, and scoring counts what Luis answered (synthetic data)."""
import json
import threading
import urllib.request

import pytest

from audit import grade as G


def _jsonl(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def data(tmp_path):
    lpp = []
    for s in range(6):
        v = f"vid{s}"
        for k in range(20):
            lpp.append({"event_id": f"lpp:{v}:{k:03d}", "source_id": f"yt:{v}", "course": "lpp",
                        "type": "trade" if k % 2 else "rule", "t_s": 10.0 * k, "quote": f"word{k} next{k}",
                        "session_date": "2024-08-15", "ticker": "NVDA"})
        caps = {"events": [{"tStartMs": 10000 * k, "segs": [{"utf8": f"word{k} "}, {"utf8": f"next{k}",
                                                                                 "tOffsetMs": 500}]}
                           for k in range(20)] + [{"tStartMs": 0, "segs": [{"utf8": "[Music]"}]}]}
        d = tmp_path / "lpp" / "youtube" / v
        d.mkdir(parents=True)
        (d / f"{v}.en-orig.json3").write_text(json.dumps(caps))
    _jsonl(tmp_path / "lpp" / "events.jsonl", lpp)
    _jsonl(tmp_path / "cryptowizard" / "events.jsonl",
           [{"event_id": f"cw:{i}:000", "source_id": f"dc:1/{i}", "course": "cryptowizard", "type": "call"}
            for i in range(50)])
    (tmp_path / "cryptowizard" / "raw").mkdir(parents=True)
    (tmp_path / "cryptowizard" / "raw" / "p.json").write_text(json.dumps(
        {"posts": [{"message_id": str(i), "text": f"post {i}", "channel": "c"} for i in range(50)]}))
    _jsonl(tmp_path / "ziptrader" / "events.jsonl",
           [{"event_id": f"zt:9:{i:03d}", "source_id": "dc:1/9", "course": "ziptrader", "type": "setup"}
            for i in range(7)])
    return tmp_path


def test_sample_is_reproducible_and_sized(data):
    a, b = G.draw(data), G.draw(data)
    assert a == b
    assert len(a["courses"]["lpp"]["event_ids"]) == 30
    assert len(a["courses"]["cryptowizard"]["event_ids"]) == 30
    assert len(a["courses"]["ziptrader"]["event_ids"]) == 7          # every ZipTrader event
    assert len(a["recall"]["sessions"]) == 3
    assert a["courses"]["lpp"]["events_sha256"] == G.sha256(data / "lpp" / "events.jsonl")
    assert G.draw(data, seed=1)["courses"]["lpp"]["event_ids"] != a["courses"]["lpp"]["event_ids"]


def test_sample_ignores_file_order(data):
    a = G.draw(data)
    p = data / "cryptowizard" / "events.jsonl"
    p.write_text("".join(reversed(p.read_text().splitlines(keepends=True))))
    b = G.draw(data)
    assert a["courses"]["cryptowizard"]["event_ids"] == b["courses"]["cryptowizard"]["event_ids"]
    assert a["courses"]["cryptowizard"]["events_sha256"] != b["courses"]["cryptowizard"]["events_sha256"]


def test_write_sample_keeps_stamp_when_unchanged(data):
    p = G.write_sample(data)
    first = json.loads(p.read_text())
    G.write_sample(data)
    assert json.loads(p.read_text()) == first


def test_score_precision_reasons_and_recall(data):
    G.write_sample(data)
    s = G.load_sample(data)
    a = G.load_answers(data)
    lpp_ids = s["courses"]["lpp"]["event_ids"]
    for i in lpp_ids[:6]:
        G.apply(a, {"event_id": i, "verdict": "correct"})
    G.apply(a, {"event_id": lpp_ids[6], "verdict": "wrong", "reason": "ticker"})
    G.apply(a, {"event_id": lpp_ids[7], "verdict": "wrong", "reason": "price"})
    G.apply(a, {"event_id": lpp_ids[8], "verdict": "skip"})
    G.apply(a, {"event_id": "not-in-sample", "verdict": "correct"})      # ignored by score
    v0, v1, v2 = s["recall"]["sessions"]
    G.apply(a, {"session": v0, "missed": [{"t": 30, "note": "x"}, {"t": 90}],
                "wrong": [f"lpp:{v0}:001"], "done": True})
    G.apply(a, {"session": v1, "missed": [{"t": 1}]})                     # not done: not counted
    G.save_answers(a, data)

    out = G.score(s, G.load_answers(data), data)
    c = out["courses"]["lpp"]
    assert (c["graded"], c["correct"], c["skipped"], c["precision"]) == (8, 6, 1, 0.75)
    assert c["wrong_by_reason"] == {"ticker": 1, "side": 0, "price": 1, "size": 0, "not_a_trade": 0, "other": 0}
    assert c["events_changed_since_sample"] is False
    assert out["courses"]["ziptrader"]["precision"] is None
    r = out["lpp_recall"]
    assert (r["sessions_done"], r["found"], r["missed"]) == (1, 9, 2)    # 10 trades in the session, 1 marked wrong
    assert r["recall"] == round(9 / 11, 4)
    assert "text" not in json.dumps(out) and "word" not in json.dumps(out)   # numbers only


def test_score_flags_changed_events(data):
    G.write_sample(data)
    with open(data / "ziptrader" / "events.jsonl", "a") as f:
        f.write(json.dumps({"event_id": "zt:9:999", "source_id": "dc:1/9"}) + "\n")
    out = G.score(G.load_sample(data), G.load_answers(data), data)
    assert out["courses"]["ziptrader"]["events_changed_since_sample"] is True


def test_apply_rejects_bad_answers():
    a = {"events": {}, "recall": {}}
    with pytest.raises(ValueError):
        G.apply(a, {"event_id": "x", "verdict": "maybe"})
    with pytest.raises(ValueError):
        G.apply(a, {"event_id": "x", "verdict": "wrong", "reason": "vibes"})
    G.apply(a, {"event_id": "x", "verdict": "wrong", "reason": "side"})
    G.apply(a, {"event_id": "x", "verdict": None})
    assert a["events"] == {}


def test_lpp_context_centres_on_the_quote(data):
    G.write_sample(data)
    it = next(i for i in G.items(data) if i["course"] == "lpp")
    ctx = it["context"]
    assert ctx["quote_found"] and any(line["hit"] for line in ctx["lines"])
    assert all(abs(line["t"] - ctx["at"]) <= G.CONTEXT_S for line in ctx["lines"])
    assert "[Music]" not in json.dumps(ctx)


def test_server_saves_each_click(data):
    G.write_sample(data)
    srv = G.make_server(data, port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        items = json.loads(urllib.request.urlopen(base + "/api/items").read())["items"]
        assert len(items) == 30 + 30 + 7
        req = urllib.request.Request(base + "/api/answer", method="POST",
                                     data=json.dumps({"event_id": items[0]["event_id"], "verdict": "correct"}).encode())
        assert json.loads(urllib.request.urlopen(req).read())["ok"]
        assert G.load_answers(data)["events"][items[0]["event_id"]]["verdict"] == "correct"
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/img/../../lpp/events.jsonl")
    finally:
        srv.shutdown()
        srv.server_close()
