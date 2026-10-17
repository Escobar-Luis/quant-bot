"""Engine rules on made-up bars: cd app && uv run --with pytest pytest backtest/tests -q"""
import datetime as dt

import pytest

from backtest import bars, engine
from backtest.engine import Leg, Position

DAY = dt.date(2024, 8, 15)
T0 = bars.et_at(DAY, 9, 30)


@pytest.fixture
def fake(monkeypatch):
    """One session of 1-minute bars; minute i opens at 100 + i (close = open + 0.5, range +-1)."""
    book = {}

    def day_bars(market, symbol, day):
        return book.get(day, {})

    monkeypatch.setattr(bars, "day_bars", day_bars)
    book[DAY] = {T0 + 60 * i: [100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000] for i in range(390)}
    return book


def pos(legs, side="long", **kw):
    return Position(pid="t", course="lpp", market="us_equities", ticker="X", side=side, portfolio="day",
                    legs=legs, default_exit="day_close", **kw)


def test_entry_is_open_of_first_bar_at_or_after_post_plus_delay(fake):
    posted = T0 + 11 * 60 + 12            # 09:41:12
    r = engine.simulate(pos([Leg("a", posted, "open", 10), Leg("b", posted + 600, "close")]), 5)
    assert r.status == "priced"
    assert r.entry.ts == T0 + 17 * 60     # 09:46:12 rounds up to the 09:47 bar
    assert r.entry.px == 117.0
    assert r.last_exit.ts == T0 + 27 * 60 and r.last_exit.px == 127.0


def test_short_pnl_and_costs(fake):
    posted = T0 + 60
    r = engine.simulate(pos([Leg("a", posted, "open", 10), Leg("b", posted + 600, "close")], side="short"), 1)
    entry, exit_ = 102.0, 112.0
    cost = (entry * 10 + exit_ * 10) * 5 / 1e4
    assert r.pnl == pytest.approx((entry - exit_) * 10 - cost)


def test_under_ten_dollars_costs_twenty_bps():
    assert engine.cost_bps("us_equities", 9.99) == 20
    assert engine.cost_bps("us_equities", 10) == 5
    assert engine.cost_bps("crypto", 50_000) == 25


def test_no_size_buys_one_thousand_dollars(fake):
    r = engine.simulate(pos([Leg("a", T0, "open"), Leg("b", T0 + 600, "close")]), 1)
    assert r.entry.qty * r.entry.px == pytest.approx(1000)


def test_stop_and_target_in_one_bar_is_the_stop(fake):
    p = pos([Leg("a", T0, "open", 1)], stop=95.0, targets=[200.0])
    fake[DAY][T0 + 5 * 60] = [101.0, 201.0, 94.0, 100.0, 1]   # trades both levels
    r = engine.simulate(p, 1)
    assert r.last_exit.kind == "stop" and r.last_exit.px == 95.0 and r.last_exit.ts == T0 + 300


def test_unclosed_day_trade_exits_at_1555_assumed(fake):
    r = engine.simulate(pos([Leg("a", T0, "open", 1)]), 1)
    assert r.assumed_exit and r.last_exit.ts == bars.et_at(DAY, 15, 55)


def test_trim_without_size_sells_half(fake):
    r = engine.simulate(pos([Leg("a", T0, "open", 100), Leg("b", T0 + 300, "trim"), Leg("c", T0 + 600, "close")]), 1)
    assert [f.qty for f in r.fills] == [100, 50, 50]


def test_stated_trim_is_a_share_of_his_position(fake):
    r = engine.simulate(pos([Leg("a", T0, "open"), Leg("a2", T0, "add", 400), Leg("b", T0 + 300, "trim", 100),
                             Leg("c", T0 + 600, "close")]), 1)
    held = r.fills[0].qty + r.fills[1].qty
    assert r.fills[2].qty == pytest.approx(held * 100 / 400)


def test_trigger_never_trades_is_not_triggered(fake):
    r = engine.simulate(pos([Leg("a", T0, "open", 1)], trigger=50.0), 1)
    assert r.status == "not_triggered"


def test_word_rule():
    assert engine.word(29, 50, 0) == "Not enough trades"
    assert engine.word(30, 12, 10) == "Yes"
    assert engine.word(30, 11.9, 10) == "Barely"
    assert engine.word(30, 8.1, 10) == "Barely"
    assert engine.word(30, 8, 10) == "No"


def test_scaled_sizing_keeps_his_ratios(fake):
    p = pos([Leg("a", T0, "open", 100), Leg("b", T0 + 300, "add", 300), Leg("c", T0 + 600, "close")], scale=True)
    r = engine.simulate(p, 1)
    assert r.fills[0].qty * r.fills[0].px == pytest.approx(1000)
    assert r.fills[1].qty == pytest.approx(3 * r.fills[0].qty)
