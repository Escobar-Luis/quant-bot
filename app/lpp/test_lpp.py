"""Unit tests for the code that decides (checks, ledger, v2 quote trimming, gold review parsing, PRISM payload).
No network and no course data: synthetic captions only.

Run: cd app && uv run --with pytest pytest lpp -q
"""
import json

import pytest

from lpp import checks, evaluate, gold, prism, run
from lpp.transcript import Transcript, norm

T0 = 1747143000  # 2025-05-13 13:30:00 UTC = 09:30 ET


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    day = {"2025-05-13": [318.0, 326.0, 316.0, 324.0, 1]}
    monkeypatch.setattr(checks.bars, "daily", lambda t: day if t in ("TSLA", "SPY", "HIMS") else None)
    monkeypatch.setattr(checks.bars, "day_bar", lambda t, d: day.get(d) if t in ("TSLA", "SPY", "HIMS") else None)
    monkeypatch.setattr(checks.bars, "minute", lambda t, d: None)


def tr_of(text: str, step: float = 1.0) -> Transcript:
    return Transcript("vid00000001", [(i * step, w) for i, w in enumerate(text.split())], T0, 600, "test")


def trade(eid, action, qty=None, ticker="TSLA", side="short"):
    return {"event_id": eid, "type": "trade", "ticker": ticker, "side": side, "action": action, "qty": qty,
            "instrument": "stock", "fail": [], "checks": {}, "status": "ok"}


# ---- numbers ----------------------------------------------------------------------------------------------
def test_said_decimal_drop_for_prices_only():
    assert checks._said(58.74, checks._nums_in(norm("500 shares short here 5874")))
    assert checks._said(320.5, checks._nums_in(norm("we're at 32050")))
    assert checks._said(9.6, checks._nums_in(norm("$9.60,")))
    assert not checks._said(58.74, {58.0, 74.0})
    assert not checks._said(5, {500.0}, shift=False)  # a share count is never a dropped decimal
    assert not evaluate.grounded({"qty": 5, "quote": "another 500 shares"})


# ---- ledger -----------------------------------------------------------------------------------------------
def test_ledger_v1_failures(monkeypatch):
    monkeypatch.setattr(checks, "VERSION", "v1")
    ev = [trade("a", "trim", 100), trade("b", "open", 50), trade("c", "add", 50), trade("d", "trim", 150),
          trade("e", "open", 10, ticker="HIMS"), trade("f", "add", 10, ticker="HIMS")]
    trips = checks.ledger(ev)
    by = {e["event_id"]: e for e in ev}
    assert by["a"]["fail"] == ["close_without_open"]
    assert by["d"]["fail"] == ["qty_exceeds_position"]
    assert by["e"]["fail"] == ["open_never_closed"] and by["f"]["fail"] == []  # kind on the first leg only
    assert by["f"]["checks"]["ledger_ok"] is False
    assert [t["closed"] for t in trips] == [True, False]


def test_ledger_v2_carry_and_open_at_end(monkeypatch):
    monkeypatch.setattr(checks, "VERSION", "v2")
    ev = [trade("a", "add", 500), trade("b", "trim", 800), trade("c", "close"), trade("d", "open", 10, ticker="HIMS")]
    trips = checks.ledger(ev, carry_in={("TSLA", "short")})
    assert all(not e["fail"] for e in ev)  # add to and trim past a carried position, open at stream end: all fine
    assert trips[0]["carried_in"] and trips[0]["closed"] and not trips[1]["closed"]


def test_carry_map_spans_days_without_trades(monkeypatch, tmp_path):
    rows = [{"source_id": "yt:d1", "session_date": "2025-05-01", "type": "trade", "ticker": "TSLA", "side": "short",
             "action": "open", "t_s": 10},
            {"source_id": "yt:d2", "session_date": "2025-05-02", "type": "rule", "ticker": None, "side": None,
             "action": None, "t_s": 10},
            {"source_id": "yt:d3", "session_date": "2025-05-05", "type": "trade", "ticker": "TSLA", "side": "short",
             "action": "close", "t_s": 10}]
    (tmp_path / "events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(run, "DATA", tmp_path)
    monkeypatch.setattr(run, "VERSION", "v2")
    monkeypatch.setattr(run, "_CARRY", None)
    m = run.carry_map()
    assert m["d1"] == set() and m["d3"] == {("TSLA", "short")}


# ---- build: quote trimming and required fields ------------------------------------------------------------
CAPS = ("ok guys so here is the thing I really like this setup and I'm going to short it now "
        "500 shares short here at 32050 nice let's see")
QUOTE = "I really like this setup and I'm going to short it now 500 shares short here at 32050"


def raw(**e):
    return {"model": "m", "events": [{"type": "trade", "t": 10, "ticker": "TSLA", "side": "short", "action": "open",
                                      "qty": 500, "price": 320.5, "quote": QUOTE, **e}]}


def test_v2_trims_long_quote_to_the_numbers(monkeypatch):
    monkeypatch.setattr(checks, "VERSION", "v2")
    (e,) = checks.build(tr_of(CAPS), raw(), "yt:vid00000001")
    assert len(e["quote"].split()) == 12 and "500" in e["quote"] and "32050" in e["quote"]
    assert e["checks"]["quote_trimmed"] and "quote_too_long" not in e["fail"]
    assert evaluate.grounded(e)


def test_v1_flags_long_quote(monkeypatch):
    monkeypatch.setattr(checks, "VERSION", "v1")
    (e,) = checks.build(tr_of(CAPS), raw(), "yt:vid00000001")
    assert "quote_too_long" in e["fail"] and e["status"] == "needs_review"


def test_side_and_level_required(monkeypatch):
    monkeypatch.setattr(checks, "VERSION", "v1")
    (t,) = checks.build(tr_of(CAPS), raw(side=None, quote="500 shares short here at 32050"), "yt:x")
    assert "trade_without_side" in t["fail"]
    c = {"model": "m", "events": [{"type": "call", "t": 10, "ticker": "TSLA", "level": None, "quote": "nice let's see"}]}
    (call,) = checks.build(tr_of(CAPS), c, "yt:x")
    assert {"call_without_level", "call_without_side"} <= set(call["fail"]) and call["targets"] == []


# ---- gold review ------------------------------------------------------------------------------------------
CHECKLIST = """# LPP gold
Video: https://youtu.be/vid00000001  ·  reviewed: yes  (change to `reviewed: yes` when done)
- [x] [0:10](https://youtu.be/vid00000001?t=10) TRADE TSLA short open 500 @ 320.5: "500 shares short here at 32050" `g00`
- [ ] [0:20](https://youtu.be/vid00000001?t=20) TRADE TSLA short close **(unsure)**: "nice let's see" `g01`
- [x] [0:30](https://youtu.be/vid00000001?t=30) CALL HIMS short target 56.8: "drop down to 5680" `m00` <!--{"t": 30}-->
- [x] 1:05 TRADE HIMS long open 100: "added by Luis"
- [x] 12:34 TRADE TICKER short open 100 @ 1.23: "quote" (write it like this; I'll add it)
"""


def test_review_reads_lines_as_written():
    assert gold.reviewed(CHECKLIST) and not gold.reviewed(CHECKLIST.replace("·  reviewed: yes", "·  reviewed: no"))
    out = gold._apply_review(CHECKLIST, [], None)
    assert [(e["type"], e["ticker"], e["t_s"]) for e in out] == [("trade", "TSLA", 10.0), ("call", "HIMS", 30.0),
                                                                  ("trade", "HIMS", 65.0)]
    assert out[0]["qty"] == 500 and out[0]["price"] == 320.5 and out[1]["level"] == 56.8
    assert gold._match(out, [{"type": "call", "ticker": "HIMS", "t_s": 40.0}], "call")  # no KeyError on extras


# ---- PRISM payload ----------------------------------------------------------------------------------------
def test_prism_payload_shape():
    sess = {"source_id": "yt:vid00000001", "session_date": "2025-05-13", "release_utc": "2025-05-13T13:30:00Z",
            "words": 10, "duration_s": 600, "model": "m", "secs": 1.0, "usage": {"in": 1, "out": 2}, "call_errors": [],
            "events": {"trade": 1}, "trades": 1, "calls": 0, "rules": 0, "ok": 0, "needs_review": 1, "round_trips": 0,
            "fail_kinds": {"x": 1}, "airtime": {}}
    ev = [{"event_id": f"lpp:vid00000001:{i:03d}", "type": "rule", "status": "needs_review" if i == 0 else "ok",
           "fail": ["x"] if i == 0 else [], "quote": "w " * 12, "checks": {}, "rule": "r" * 400} for i in range(200)]
    p = prism.payload("vid00000001", sess, ev, {"vid00000001"}, "abc")
    assert p["conversation_id"] == "lpp-vid00000001" and p["final_status"] == "error"
    assert p["metadata"]["proof_set"] is True
    assert [s.get("tool_name") or s["label"] for s in p["steps"]] == ["load_captions", "llm_extract", "check_events", "events"]
    final = json.loads(p["steps"][-1]["output_summary"])  # still valid JSON after dropping events to fit
    assert len(p["steps"][-1]["output_summary"]) <= 30000 and final["events_left_out"] > 0
    assert final["failures"][0]["check"] == ["x"]


def test_fetch_captions_ids_and_command(tmp_path):
    from lpp import fetch_captions as fc
    f = tmp_path / "urls.txt"
    f.write_text("# list\nhttps://www.youtube.com/watch?v=A4929OT4Jls\n\nhttps://youtu.be/A4929OT4Jls\n"
                 "https://www.youtube.com/live/Jds31wPEh1U?si=x\nnot a link\n")
    assert fc.video_ids(f) == ["A4929OT4Jls", "Jds31wPEh1U"]
    cmd = fc.ytdlp_cmd("A4929OT4Jls")
    assert "--skip-download" in cmd and "json3" in cmd and cmd[-1].endswith("A4929OT4Jls")
