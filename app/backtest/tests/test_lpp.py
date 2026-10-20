"""LPP ledger on a handful of made-up events: cd app && uv run --with pytest pytest backtest/tests -q"""
import json

from backtest import lpp


def ev(i, src, wall, action, qty=None, side="short", ticker="NVDA", status="ok", fail=()):
    return {"event_id": f"lpp:{src}:{i:03d}", "source_id": f"yt:{src}", "type": "trade", "t_s": 60.0 * i,
            "wall_utc": wall, "session_date": wall[:10], "ticker": ticker, "side": side, "action": action,
            "instrument": "stock", "qty": qty, "quote": "shorting it here", "status": status, "fail": list(fail)}


def write(tmp_path, monkeypatch, evs):
    p = tmp_path / "events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in evs))
    monkeypatch.setattr(lpp, "events_path", lambda version: p)


def test_proof_set_keeps_only_those_sessions(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, [ev(0, "A", "2024-08-15T13:40:00Z", "open", 100),
                                  ev(1, "A", "2024-08-15T14:00:00Z", "close"),
                                  ev(0, "B", "2024-08-16T13:40:00Z", "open", 100)])
    b = lpp.build("v2", {"yt:A"})
    assert [p.cite["source_id"] for p in b["positions"]] == ["lpp:2024-08-15"] and b["checks"]["sessions"] == 1


def test_as_taught_next_day_add_carries_into_a_swing(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, [ev(0, "A", "2024-08-15T13:40:00Z", "open", 100),
                                  ev(0, "B", "2024-08-16T13:40:00Z", "add", 50),
                                  ev(1, "B", "2024-08-16T14:00:00Z", "close")])
    (p,) = lpp.build("v1", ledger="as_taught")["positions"]
    assert p.portfolio == "swing" and [lg.action for lg in p.legs] == ["open", "add", "close"] and p.as_taught


def test_later_word_does_not_change_an_earlier_decision(tmp_path, monkeypatch):
    """CAP-12: his next-day add would have carried Thursday's short overnight (rule 11). Under rule 13 Thursday's
    position is decided at 15:55 Thursday from what he had said: it is the same with or without Friday's words."""
    thursday = [ev(0, "A", "2024-08-15T13:40:00Z", "open", 100)]
    friday = [ev(0, "B", "2024-08-16T13:40:00Z", "add", 50), ev(1, "B", "2024-08-16T14:00:00Z", "close")]
    write(tmp_path, monkeypatch, thursday)
    (alone,) = lpp.build("v1")["positions"]
    write(tmp_path, monkeypatch, thursday + friday)
    first, second = lpp.build("v1")["positions"]
    assert (first.pid, first.portfolio, first.default_exit, [lg.event_id for lg in first.legs]) == \
        (alone.pid, "day", "day_close", ["lpp:A:000"])
    assert second.portfolio == "day" and [lg.action for lg in second.legs] == ["add", "close"]


def test_next_day_exit_with_nothing_open_is_skipped(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, [ev(0, "A", "2024-08-15T13:40:00Z", "open", 100),
                                  ev(0, "B", "2024-08-16T13:40:00Z", "close")])
    b = lpp.build("v1")
    assert len(b["positions"]) == 1 and b["stats"]["close_without_open"] == 1


def test_horizon_said_in_time_keeps_it_overnight(tmp_path, monkeypatch):
    """Rule 13(b): a horizon on one of its legs, said before 15:55, holds it to that horizon's last session."""
    write(tmp_path, monkeypatch, [{**ev(0, "A", "2024-08-15T13:40:00Z", "open", 100), "horizon": "2 days"},
                                  ev(0, "B", "2024-08-16T13:40:00Z", "add", 50),
                                  ev(0, "C", "2024-08-20T13:40:00Z", "trim", 50)])   # Tuesday: past 2 sessions
    b = lpp.build("v1")
    (p,) = b["positions"]
    end = lpp.bars.et_at(lpp.dt.date(2024, 8, 19), 15, 55)                          # Thursday + 2 weekdays
    assert p.portfolio == "swing" and p.default_exit == f"at:{end}" and [lg.action for lg in p.legs] == ["open", "add"]
    assert b["stats"]["close_without_open"] == 1


def test_horizon_said_after_the_close_is_too_late(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, [ev(0, "A", "2024-08-15T13:40:00Z", "open", 100),
                                  {**ev(1, "A", "2024-08-15T20:30:00Z", "add", 50), "horizon": "2 days"}])
    first, second = lpp.build("v1")["positions"]                                    # 16:30 ET: it already left
    assert first.portfolio == "day" and len(first.legs) == len(second.legs) == 1   # the add starts afresh,
    assert second.portfolio == "swing"                                               # held for its own horizon


def test_side_less_exit_joins_his_one_open_position(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, [ev(0, "A", "2024-08-15T13:40:00Z", "open", 100),
                                  ev(1, "A", "2024-08-15T14:00:00Z", "close", side=None)])
    (p,) = lpp.build("v1")["positions"]
    assert p.portfolio == "day" and [lg.action for lg in p.legs] == ["open", "close"]


def test_needs_review_without_ledger_fail_is_left_out(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, [ev(0, "A", "2024-08-15T13:40:00Z", "open", 100, status="needs_review"),
                                  ev(1, "A", "2024-08-15T13:50:00Z", "open", 100, ticker="TSLA",
                                     status="needs_review", fail=["open_never_closed"])])
    assert [p.ticker for p in lpp.build("v1")["positions"]] == ["TSLA"]


def test_public_files_get_session_keys_not_video_ids(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, [ev(0, "A4929OT4Jls", "2024-08-15T13:40:00Z", "open", 100),
                                  ev(1, "A4929OT4Jls", "2024-08-15T14:00:00Z", "close")])
    monkeypatch.setattr(lpp, "_session_keys", lambda: {"A4929OT4Jls": "lpp:2024-08-15"})
    (p,) = lpp.build("v1")["positions"]
    assert p.cite["source_id"] == "lpp:2024-08-15" and p.pid == "lpp-2024-08-15-000"
