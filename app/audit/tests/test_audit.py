"""The audit fails loudly on a result it can't reproduce, and passes an untouched one."""
import datetime as dt
import json
import shutil

import pytest

from audit import calc, run
from audit.paths import DATA, RESULTS


def test_headline_tolerance_is_one_dollar():
    base = {"end": 9765.86, "ret_pct": -2.34, "hold_end": 11963.79, "hold_ret_pct": 19.64, "trades": 315,
            "word": "No"}
    out = []
    run.compare_head("all", "5", base, {**base, "end": 9766.5}, out)
    assert out == []
    run.compare_head("all", "5", base, {**base, "end": 9767.0, "trades": 314, "word": "Barely"}, out)
    assert {m["field"] for m in out} == {"end", "trades", "word"}


def test_trade_tolerance_is_one_cent():
    a = {"status": "priced", "entry_at": 100, "entry": 10.0, "exit_at": 200, "exit": 11.0, "pnl": 5.0}
    out = []
    run.compare_trade("ledger", "x", 5, a, {**a, "pnl": 5.01}, out)
    assert out == []
    run.compare_trade("ledger", "x", 5, a, {**a, "pnl": 5.02, "exit_at": 260}, out)
    assert {m["field"] for m in out} == {"pnl", "exit_at"}


def test_word_follows_rule_9():
    assert calc.word(29, 50.0, 0.0) == "Not enough trades"
    assert calc.word(30, 2.0, 0.0) == "Yes"
    assert calc.word(30, 1.99, 0.0) == "Barely"
    assert calc.word(30, -2.0, 0.0) == "No"


NEED = [DATA / "audit" / "ziptrader-v1-ledger.jsonl", DATA / "ziptrader" / "events.jsonl"]


def _diff(tmp_path) -> dict:
    return json.loads((tmp_path / "diff-ziptrader-v1.json").read_text())


@pytest.mark.skipif(not all(p.exists() for p in NEED), reason="needs local data/ (ziptrader events, ledger, bars)")
def test_altered_result_exits_non_zero(tmp_path):
    src = RESULTS / "ziptrader" / "v1.json"
    (tmp_path / "ziptrader").mkdir()
    dst = tmp_path / "ziptrader" / "v1.json"
    args = ["--results-dir", str(tmp_path), "--out-dir", str(tmp_path), "--proofs", "", "--only", "ziptrader/v1"]

    shutil.copy(src, dst)
    run.main(args)                                     # untouched: the math alone reconciles, the ledger is fresh
    clean = _diff(tmp_path)
    assert clean["math_on_loader_positions"]["main"]["mismatches"] == 0
    assert not any(m["kind"] == "stale" for m in clean["details"])

    d = json.loads(src.read_text())
    d["portfolios"][0]["by_delay"]["5"]["end"] += 5    # a headline $5 off
    dst.write_text(json.dumps(d))
    assert run.main(args) != 0
    rep = _diff(tmp_path)
    assert any(m["kind"] == "stale" for m in rep["details"])          # the ledger no longer matches the file
    assert any(m["field"] == "end" and m["delay"] == 5 for m in rep["math_on_loader_positions"]["main"]["details"])

    d = json.loads(src.read_text())
    d["trades"][0]["by_delay"]["5"]["exit"] += 0.05    # one trade's exit 5 cents off
    dst.write_text(json.dumps(d))
    assert run.main(args) != 0
    assert any(m["field"] == "exit" and m["delay"] == 5 and m["against"] == "results"
               for m in _diff(tmp_path)["details"])


HORIZONS = ["more than one session", "3 days", "two weeks", "into the next session", "hold it overnight",
            "a few days", "0 days", "today", "into earnings Oct 21", None, "20 sessions", "next trading day",
            "several sessions", "1 week"]


def test_audit_and_engine_read_every_horizon_the_same():
    """Two independent readings of rule 4/12(a) (audit.positions.horizon_sessions, backtest.ziptrader)."""
    from audit.positions import horizon_sessions
    from backtest.ziptrader import default_exit
    for h in HORIZONS:
        n = horizon_sessions(h)
        assert default_exit(h) == (f"sessions:{n}" if n else "day_close"), h


def test_audit_horizon_reading_from_the_contract():
    from audit.positions import horizon_sessions
    assert horizon_sessions("more than one session") == 5        # rule 4: no count -> 5 sessions
    assert horizon_sessions("into the next session") == 1
    assert horizon_sessions("hold it overnight") == 1
    assert horizon_sessions("two weeks") == 10
    assert horizon_sessions("0 days") is None
    assert horizon_sessions("today") is None


# ---- CAP-12, no look-ahead (contracts.md rule 13), on the audit's own ledger and calculator --------------------

def _lpp_events(tmp_path, monkeypatch, evs):
    from audit import positions as P
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in evs))
    monkeypatch.setattr(P, "lpp_events_path", lambda version: path)
    monkeypatch.setattr(P, "lpp_release", lambda: {})
    monkeypatch.setattr(P, "lpp_session_key", lambda: {})
    return P


def _ev(src, i, wall, action, qty=None, **kw):
    return {"event_id": f"lpp:{src}:{i:03d}", "source_id": f"yt:{src}", "type": "trade", "t_s": 0.0,
            "wall_utc": wall, "session_date": wall[:10], "ticker": "NVDA", "side": "short", "action": action,
            "instrument": "stock", "qty": qty, "status": "ok", "fail": [], **kw}


def test_audit_ledger_ignores_what_he_says_later(tmp_path, monkeypatch):
    """Rule 13: Thursday's short is decided at 15:55 Thursday; Friday's add and close leave it unchanged, and
    rule 11 (as_taught), which reads Friday's words, would have carried it."""
    thu = [_ev("A", 0, "2024-08-15T13:40:00Z", "open", 100)]
    fri = [_ev("B", 0, "2024-08-16T13:40:00Z", "add", 50), _ev("B", 1, "2024-08-16T14:00:00Z", "close")]
    P = _lpp_events(tmp_path, monkeypatch, thu)
    (alone,) = P.lpp("v1")["positions"]
    P = _lpp_events(tmp_path, monkeypatch, thu + fri)
    first, second = P.lpp("v1")["positions"]
    assert (first.pid, first.portfolio, first.default_exit, [lg.event_id for lg in first.legs]) == \
        (alone.pid, "day", "day_close", ["lpp:A:000"])
    assert [lg.action for lg in second.legs] == ["add", "close"]
    (taught,) = P.lpp("v1", ledger="as_taught")["positions"]
    assert taught.portfolio == "swing" and len(taught.legs) == 3


def test_audit_ledger_horizon_said_in_time(tmp_path, monkeypatch):
    P = _lpp_events(tmp_path, monkeypatch, [_ev("A", 0, "2024-08-15T13:40:00Z", "open", 100, horizon="2 days"),
                                            _ev("B", 0, "2024-08-16T13:40:00Z", "trim", 50),
                                            _ev("C", 0, "2024-08-20T13:40:00Z", "close")])
    built = P.lpp("v1")
    (p,) = built["positions"]
    assert p.portfolio == "swing" and p.default_exit == f"at:{P.leaves_at(dt.date(2024, 8, 19), 0)}"
    assert [lg.action for lg in p.legs] == ["open", "trim"] and built["stats"]["exit_without_open"] == 1


def test_audit_first_buy_is_the_same_whatever_he_adds_later(monkeypatch):
    from audit.positions import Leg
    from audit.tests import synthetic as S
    S.patch_bars(S.book(S.DAY), monkeypatch.setattr)
    legs = [Leg("o", S.at(9, 30), "open", qty=100), Leg("c", S.at(10, 0), "close")]
    alone = calc.simulate(S.pos(legs, course="lpp"), 1)
    later = calc.simulate(S.pos([legs[0], Leg("a", S.at(9, 40), "add", qty=900), legs[1]], course="lpp"), 1)
    assert later.fills[0] == alone.fills[0] and alone.fills[0].qty * alone.fills[0].px == pytest.approx(1000)
    taught = calc.simulate(S.pos([legs[0], Leg("a", S.at(9, 40), "add", qty=900), legs[1]], course="lpp"), 1,
                           "trade")
    assert taught.fills[0].qty * taught.fills[0].px == pytest.approx(100)    # rule 6 as taught reads the add
