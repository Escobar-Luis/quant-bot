"""Story 17: the code that decides on the hold-intent pass's proposals. No network, no course data.

Run: cd app && uv run pytest lpp/test_hold_intent.py -q
"""
import pytest

from audit import positions as audit_positions
from backtest import lpp as bt_lpp
from lpp import hold_intent as H
from lpp.transcript import Transcript

T0 = 1747143000  # 2025-05-13 13:30:00 UTC = 09:30 ET


def tr_of(text: str, step: float = 1.0, release=T0) -> Transcript:
    return Transcript("vid00000001", [(i * step, w) for i, w in enumerate(text.split())], release, 600, "test")


def pos(legs=(("open", 2.0), ("add", 8.0)), overnight=True):
    return {"pid": "lpp-2025-05-13-000", "first": "lpp:vid00000001:000", "source_id": "yt:vid00000001",
            "session_date": "2025-05-13", "ticker": "TSLA", "side": "short", "overnight": overnight,
            "legs": [{"event_id": f"lpp:vid00000001:{i:03d}", "action": a, "t_s": t, "qty": None, "ticker_said": "tesla"}
                     for i, (a, t) in enumerate(legs)]}


TEXT = "ok I am short tesla here adding more tesla now I am going to carry this short overnight for sure"


def test_hold_kept_on_the_latest_buy_before_the_statement():
    d = H.decide(pos(), {"intent": "hold", "horizon": "sessions:1", "quote": "carry this short overnight", "t": 14},
                 tr_of(TEXT), T0)
    assert d["intent"] == "hold" and d["horizon"] == "overnight" and d["fail"] is None
    assert d["event_id"] == "lpp:vid00000001:001" and d["t_s"] == 14.0


@pytest.mark.parametrize("h, want", [("sessions:1", "overnight"), ("sessions:3", "3 sessions"),
                                     ("sessions:?", "more than one session"), (None, "more than one session")])
def test_horizon_text_reads_the_same_in_the_engine_and_the_audit(h, want):
    """Rules 4/13: what this pass writes, both ledgers turn into the same number of sessions."""
    text = H.horizon_text(h)
    assert text == want
    n = {"overnight": 1, "3 sessions": 3, "more than one session": 5}[want]
    assert bt_lpp.horizon_sessions({"horizon": text}) == n
    assert audit_positions.horizon_sessions(text) == n


def test_close_today_is_a_day_trade_in_both_ledgers():
    d = H.decide(pos(), {"intent": "close_today", "quote": "going to carry this short", "t": 11}, tr_of(TEXT), T0)
    assert d["horizon"] == "today"
    assert bt_lpp.horizon_sessions({"horizon": "today"}) == 0 and audit_positions.horizon_sessions("today") is None


def test_quote_not_in_captions_is_thrown_out():
    d = H.decide(pos(), {"intent": "hold", "horizon": "sessions:2", "quote": "holding this for two days", "t": 14},
                 tr_of(TEXT), T0)
    assert d["intent"] == "none" and d["fail"] == "quote_not_in_source" and d["horizon"] is None


def test_statement_at_or_after_1555_et_never_counts():
    late = T0 + (6 * 3600 + 25 * 60) - 14   # the quote's word lands at 15:55:00 ET
    d = H.decide(pos(), {"intent": "hold", "horizon": "sessions:1", "quote": "carry this short overnight", "t": 14},
                 tr_of(TEXT, release=late), late)
    assert d["intent"] == "none" and d["fail"] == "after_1555_et"


def test_statement_after_his_close_is_not_about_this_position():
    p = pos(legs=(("open", 2.0), ("close", 6.0)))
    d = H.decide(p, {"intent": "hold", "horizon": "sessions:1", "quote": "carry this short overnight", "t": 14},
                 tr_of(TEXT, step=10.0), T0)
    assert d["fail"] == "outside_position"


def test_long_verified_quote_is_trimmed_to_12_words_about_holding():
    q = "tesla now I am going to carry this short overnight for sure"   # 12 words
    q15 = "adding more " + q + " ok"
    text = "ok I am short tesla here " + q15
    d = H.decide(pos(), {"intent": "hold", "horizon": "sessions:1", "quote": q15, "t": 8}, tr_of(text), T0)
    assert d["intent"] == "hold" and len(d["quote"].split()) == 12 and "overnight" in d["quote"]
    assert d["quote_trimmed"] is True


def test_none_and_ambiguous_write_nothing():
    for r in ({"intent": "none"}, {"intent": "ambiguous", "quote": "carry this short", "t": 12}):
        d = H.decide(pos(), r, tr_of(TEXT), T0)
        assert d["horizon"] is None and d["event_id"] is None
    assert H.decide(pos(), {"intent": "maybe"}, tr_of(TEXT), T0)["fail"] == "bad_reply"


def test_apply_writes_horizon_and_keeps_an_extractions_own():
    evs = [{"event_id": "a", "horizon": None}, {"event_id": "b", "horizon": "2 days"}]
    ds = [{"event_id": "a", "horizon": "overnight", "quote": "q", "t_s": 1.0},
          {"event_id": "b", "horizon": "overnight", "quote": "q", "t_s": 1.0}]
    assert H.apply(evs, ds) == 1
    assert evs[0]["horizon"] == "overnight" and evs[0]["horizon_source"] == "hold_intent_v1"
    assert evs[1]["horizon"] == "2 days" and "horizon_source" not in evs[1]


def test_windows_cover_buys_mentions_and_sign_off_only_while_open():
    words = " ".join(["filler"] * 2000 + ["tesla"] + ["filler"] * 500)
    tr = tr_of(words)
    p = pos(legs=(("open", 100.0),))
    w = H.windows(p, tr)
    assert w[0][0] == 40.0                              # 1 minute before the open
    assert any(a <= 2000 <= b for a, b in w)            # the later mention of the ticker
    assert w[-1][1] >= tr.words[-1][0]                  # never closed: the stream's last minutes
    assert all(a >= 40.0 for a, _ in w)
