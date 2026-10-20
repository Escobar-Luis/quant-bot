"""CAP-2 grading: the sample is seeded and reproducible, and scoring counts what Luis answered (synthetic data)."""
import http.client
import json
import os
import threading

import pytest

from audit import grade as G


def _jsonl(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "data"
    lpp = []
    for s in range(6):
        v = f"vid{s}"
        for k in range(20):
            lpp.append({"event_id": f"lpp:{v}:{k:03d}", "source_id": f"yt:{v}", "course": "lpp",
                        "type": "trade" if k % 2 else "rule", "action": "open", "ticker": "NVDA",
                        "status": "ok" if k % 4 != 3 else "needs_review",
                        "fail": [] if k % 4 != 3 else (["open_never_closed"] if k % 8 == 3 else ["ticker_bad"]),
                        "t_s": 10.0 * k, "quote": f"word{k} next{k}", "session_date": "2024-08-15"})
        caps = {"events": [{"tStartMs": 10000 * k, "segs": [{"utf8": f"word{k} "}, {"utf8": f"next{k}",
                                                                                 "tOffsetMs": 500}]}
                           for k in range(14)] + [{"tStartMs": 0, "segs": [{"utf8": "[Music]"}]}]}
        d = root / "lpp" / "youtube" / v
        d.mkdir(parents=True)
        (d / f"{v}.en-orig.json3").write_text(json.dumps(caps))
    _jsonl(root / "lpp" / "events.jsonl", lpp)
    _jsonl(root / "cryptowizard" / "events.jsonl", [{"event_id": "cw:x:000", "source_id": "dc:1/x"}])
    cw = [{"event_id": f"cw:{i}:000", "source_id": f"dc:1/{i}", "type": "call", "status": "ok",
           "entry": 1.0, "pair": "BTCUSDT"} for i in range(40)]
    cw += [{"event_id": f"cw:{i}:001", "source_id": f"dc:1/{i}b", "type": "trade", "status": "ok",
            "links_to": f"cw:{i}:000"} for i in range(40)]
    cw += [{"event_id": "cw:nolink:000", "source_id": "dc:1/n", "type": "trade", "status": "ok", "links_to": None},
           {"event_id": "cw:noentry:000", "source_id": "dc:1/e", "type": "call", "status": "ok", "pair": "X"}]
    _jsonl(root / "cryptowizard" / "events.calls.jsonl", cw)
    (root / "cryptowizard" / "raw").mkdir(parents=True)
    (root / "cryptowizard" / "raw" / "p.json").write_text(json.dumps(
        {"posts": [{"message_id": str(i), "text": f"post {i}", "channel": "c"} for i in range(40)]}))
    _jsonl(root / "ziptrader" / "events.jsonl",
           [{"event_id": f"zt:9:{i:03d}", "source_id": "dc:1/9", "course": "ziptrader",
             "type": "rule" if i == 0 else "setup"} for i in range(7)])
    (root / "ziptrader" / "discord" / "img").mkdir(parents=True)
    (root / "ziptrader" / "discord" / "img" / "a b.png").write_bytes(b"\x89PNG")
    return root


@pytest.fixture
def drawn(data, tmp_path):
    G.write_sample(data, proofs=tmp_path / "proofs")
    return data


def test_sample_is_reproducible_and_sized(data):
    a, b = G.draw(data), G.draw(data)
    assert a == b
    assert len(a["courses"]["lpp"]["event_ids"]) == 30
    assert len(a["courses"]["cryptowizard"]["event_ids"]) == 30
    assert len(a["courses"]["ziptrader"]["event_ids"]) == 7          # every ZipTrader event
    assert a["courses"]["ziptrader"]["types"]["zt:9:000"] == "rule"   # labelled by type
    assert len(a["recall"]["sessions"]) == 3
    assert a["courses"]["lpp"]["file_sha256"] == G.sha256(data / "lpp" / "events.jsonl")
    assert G.draw(data, seed=1)["courses"]["lpp"]["event_ids"] != a["courses"]["lpp"]["event_ids"]


def test_sample_draws_only_what_the_backtest_prices(data):
    a = G.draw(data)
    lpp = {e["event_id"]: e for e in G.read_events(data, "lpp")}
    for i in a["courses"]["lpp"]["event_ids"]:
        e = lpp[i]
        assert e["type"] == "trade" and (e["status"] == "ok" or e["fail"] == ["open_never_closed"])
    assert a["courses"]["lpp"]["n_population"] == 6 * 8     # per session 10 trades, 2 fail a non-ledger check
    assert a["courses"]["cryptowizard"]["file"] == "cryptowizard/events.calls.jsonl"
    assert a["courses"]["cryptowizard"]["n_population"] == 80                  # no orphan trade, no entry-less call
    assert not {"cw:nolink:000", "cw:noentry:000"} & set(a["courses"]["cryptowizard"]["event_ids"])


def test_sample_ignores_file_order(data):
    a = G.draw(data)
    p = data / "cryptowizard" / "events.calls.jsonl"
    p.write_text("".join(reversed(p.read_text().splitlines(keepends=True))))
    b = G.draw(data)
    assert a["courses"]["cryptowizard"]["event_ids"] == b["courses"]["cryptowizard"]["event_ids"]
    assert a["courses"]["cryptowizard"]["file_sha256"] != b["courses"]["cryptowizard"]["file_sha256"]


def test_write_sample_keeps_stamp_and_commits_ids_only(data, tmp_path):
    p = G.write_sample(data, proofs=tmp_path / "proofs")
    first = json.loads(p.read_text())
    G.write_sample(data, proofs=tmp_path / "proofs")
    assert json.loads(p.read_text()) == first
    pub = (tmp_path / "proofs" / "grading-sample.json").read_text()
    assert json.loads(pub) == first and "word" not in pub and "post" not in pub


def _ids(sample, course):
    return sample["courses"][course]["event_ids"]


def test_score_precision_reasons_and_recall(drawn):
    s = G.load_sample(drawn)
    rids = G.recall_extracted(s, drawn)
    a = G.load_answers(drawn)
    lpp_ids = _ids(s, "lpp")
    for i in lpp_ids[:6]:
        G.apply(a, {"event_id": i, "verdict": "correct"}, s)
    G.apply(a, {"event_id": lpp_ids[6], "verdict": "wrong", "reason": "ticker"}, s)
    G.apply(a, {"event_id": lpp_ids[7], "verdict": "wrong", "reason": "price"}, s)
    G.apply(a, {"event_id": lpp_ids[8], "verdict": "skip"}, s)
    G.apply(a, {"event_id": "zt:9:000", "verdict": "wrong", "reason": "other"}, s)
    G.apply(a, {"event_id": "zt:9:001", "verdict": "correct"}, s)
    v0, v1, _ = s["recall"]["sessions"]
    G.apply(a, {"session": v0, "missed": [{"t": 30, "note": "x"}, {"t": 90}], "wrong": [rids[v0][0]],
                "done": True}, s, rids)
    G.apply(a, {"session": v1, "missed": [{"t": 1}]}, s, rids)            # not done: not counted
    G.save_answers(a, drawn)

    out = G.score(s, G.load_answers(drawn), drawn)
    c = out["courses"]["lpp"]
    assert (c["graded"], c["correct"], c["skipped"], c["precision"]) == (8, 6, 1, 0.75)
    assert c["wrong_by_reason"] == {"ticker": 1, "side": 0, "price": 1, "size": 0, "not_a_trade": 0, "other": 0}
    assert c["source_changed_since_sample"] is False
    z = out["courses"]["ziptrader"]
    assert z["precision"] == 0.5
    assert z["by_type"]["rule"] == {"sampled": 1, "graded": 1, "correct": 0, "precision": 0.0}
    assert z["by_type"]["setup"]["precision"] == 1.0
    r = out["lpp_recall"]
    n = len(rids[v0])
    assert (r["sessions_done"], r["found"], r["missed"]) == (1, n - 1, 2)
    assert r["recall"] == round((n - 1) / (n + 1), 4)
    blob = json.dumps(out)
    assert "word" not in blob and "post" not in blob and "lpp:" not in blob   # numbers only


def test_score_flags_changed_source(drawn):
    with open(drawn / "ziptrader" / "events.jsonl", "a") as f:
        f.write(json.dumps({"event_id": "zt:9:999", "source_id": "dc:1/9"}) + "\n")
    s = G.load_sample(drawn)
    assert G.stale(s, drawn) == ["ziptrader/events.jsonl"]
    assert G.score(s, G.load_answers(drawn), drawn)["courses"]["ziptrader"]["source_changed_since_sample"] is True


def test_apply_validates_everything(drawn):
    s = G.load_sample(drawn)
    rids = G.recall_extracted(s, drawn)
    a = {"events": {}, "recall": {}}
    i = _ids(s, "lpp")[0]
    v = s["recall"]["sessions"][0]
    bad = [{"event_id": i, "verdict": "maybe"},
           {"event_id": i, "verdict": "wrong", "reason": "vibes"},
           {"event_id": "lpp:not-sampled:000", "verdict": "correct"},
           {"event_id": 5, "verdict": "correct"},
           {"session": "not-a-session", "done": True},
           {"session": v, "missed": ["30"]},
           {"session": v, "missed": [{"t": "soon"}]},
           {"session": v, "missed": [{"t": 3, "note": 7}]},
           {"session": v, "wrong": "x"},
           {"session": v, "wrong": ["lpp:unknown:000"]},
           {"session": v, "done": "yes"},
           ["not", "an", "object"]]
    for m in bad:
        with pytest.raises(ValueError):
            G.apply(a, m, s, rids)
    assert a == {"events": {}, "recall": {}}
    G.apply(a, {"event_id": i, "verdict": "wrong", "reason": "side"}, s)
    G.apply(a, {"event_id": i, "verdict": None}, s)
    assert a["events"] == {}


def test_lpp_context_centres_on_the_quote(drawn):
    it = next(i for i in G.items(drawn) if i["course"] == "lpp")
    ctx = it["context"]
    assert ctx["quote_found"] and any(line["hit"] for line in ctx["lines"])
    assert all(abs(line["t"] - ctx["at"]) <= G.CONTEXT_S for line in ctx["lines"])
    assert "[Music]" not in json.dumps(ctx)


def test_recall_events_past_the_captions_land_in_the_last_chunk(drawn):
    for sess in G.recall_sessions(drawn):
        placed = [e["event_id"] for c in sess["chunks"] for e in c["events"]]
        assert sorted(placed) == sorted(G.recall_extracted(G.load_sample(drawn), drawn)[sess["session"]])
        assert sess["chunks"][-1]["end"] is None
        assert any(e["t"] >= 130 for e in sess["chunks"][-1]["events"])   # captions end at 130 s


def test_record_is_serialised(drawn):
    s = G.load_sample(drawn)
    ids = _ids(s, "cryptowizard")
    ts = [threading.Thread(target=G.record, args=({"event_id": i, "verdict": "correct"}, s, {}, drawn))
          for i in ids]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert set(G.load_answers(drawn)["events"]) == set(ids)
    assert not list(G.grade_dir(drawn).glob("*.tmp"))


@pytest.fixture
def server(drawn):
    srv = G.make_server(drawn, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    yield drawn, port
    srv.shutdown()
    srv.server_close()


def _req(port, path, body=None, host=None, origin="same", ctype="application/json"):
    host = host or f"127.0.0.1:{port}"
    h = {"Host": host}
    if body is not None:
        h["Content-Type"] = ctype
        if origin:
            h["Origin"] = f"http://{host}" if origin == "same" else origin
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.putrequest("POST" if body is not None else "GET", path, skip_host=True, skip_accept_encoding=True)
    for k, v in h.items():
        c.putheader(k, v)
    data = json.dumps(body).encode() if body is not None else b""
    c.putheader("Content-Length", str(len(data)))
    c.endheaders(data)
    r = c.getresponse()
    out = r.status, r.read()
    c.close()
    return out


def test_server_saves_each_click(server):
    data, port = server
    code, body = _req(port, "/api/items")
    items = json.loads(body)["items"]
    assert code == 200 and len(items) == 30 + 30 + 7
    eid = items[0]["event_id"]
    code, body = _req(port, "/api/answer", {"event_id": eid, "verdict": "correct"})
    assert code == 200 and json.loads(body)["ok"]
    assert G.load_answers(data)["events"][eid]["verdict"] == "correct"
    assert _req(port, "/api/answer", {"event_id": "nope", "verdict": "correct"})[0] == 400
    assert _req(port, "/api/answer", {"event_id": eid, "verdict": "skip"}, host=f"localhost:{port}")[0] == 200


def test_server_blocks_csrf_and_rebinding(server):
    data, port = server
    eid = G.load_sample(data)["courses"]["lpp"]["event_ids"][0]
    msg = {"event_id": eid, "verdict": "correct"}
    assert _req(port, "/api/items", host="evil.example:80")[0] == 403                 # DNS rebinding
    assert _req(port, "/", host=f"attacker.test:{port}")[0] == 403
    assert _req(port, "/api/answer", msg, origin="http://evil.example")[0] == 403      # cross-site
    assert _req(port, "/api/answer", msg, origin=None)[0] == 403                       # no Origin
    assert _req(port, "/api/answer", msg, ctype="text/plain")[0] == 403                # simple-request form post
    assert _req(port, "/api/answer", msg, ctype="application/x-www-form-urlencoded")[0] == 403
    assert G.load_answers(data)["events"] == {}


def test_server_images_decode_and_stay_inside(server):
    _, port = server
    assert _req(port, "/img/discord/img/a%20b.png") == (200, b"\x89PNG")
    assert _req(port, "/img/..%2F..%2Flpp%2Fevents.jsonl")[0] == 404
    assert _req(port, "/img/%2E%2E/lpp/youtube/vid0/vid0.en-orig.json3")[0] == 404


def test_server_refuses_a_stale_sample_and_reloads_a_new_one(server, tmp_path):
    data, port = server
    p = data / "ziptrader" / "events.jsonl"
    p.write_text(p.read_text() + json.dumps({"event_id": "zt:9:007", "source_id": "dc:1/9", "type": "setup"}) + "\n")
    os.utime(G.grade_dir(data) / "sample.json", ns=(1, 1))      # force a sample re-check
    code, body = _req(port, "/api/items")
    assert code == 409 and "changed since the sample" in json.loads(body)["error"]
    G.write_sample(data, proofs=tmp_path / "proofs")
    code, body = _req(port, "/api/items")
    assert code == 200 and len(json.loads(body)["items"]) == 30 + 30 + 8
