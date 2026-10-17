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


def test_next_day_add_carries_into_a_swing(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, [ev(0, "A", "2024-08-15T13:40:00Z", "open", 100),
                                  ev(0, "B", "2024-08-16T13:40:00Z", "add", 50),
                                  ev(1, "B", "2024-08-16T14:00:00Z", "close")])
    (p,) = lpp.build("v1")["positions"]
    assert p.portfolio == "swing" and [lg.action for lg in p.legs] == ["open", "add", "close"]


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
