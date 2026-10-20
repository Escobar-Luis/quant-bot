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
    assert r.fills[0].qty * r.fills[0].px == pytest.approx(250)    # 100 of his 400 shares -> a quarter of $1,000
    assert r.fills[1].qty == pytest.approx(3 * r.fills[0].qty)


def _r(entry_ts, exit_ts, notional, pnl):
    p = pos([Leg("a", entry_ts, "open")])
    r = engine.Result(p, 1, "priced", fills=[engine.Fill(entry_ts, 1, notional, "entry"),
                                             engine.Fill(exit_ts, 1, notional, "exit")], pnl=pnl,
                      entry_notional=notional)
    return r


def test_overlapping_trades_never_spend_more_than_the_cash():
    a = _r(0, 100, 8000, 80)          # uses $8k until t=100
    b = _r(10, 50, 4000, 40)          # only $2k left: sized down to half
    c = _r(20, 60, 1000, 10)          # $0 left: skipped
    d = _r(200, 300, 4000, 40)        # after a and b exit: full size
    kept, sized_down, skipped, peak = engine.fit_to_cash([a, b, c, d])
    assert [f for _, f in kept] == [1.0, 0.5, 1.0] and sized_down == 1 and skipped == 1 and peak == 10000


def test_day_trade_too_late_to_copy_that_session(fake):
    late = bars.et_at(DAY, 15, 30)
    nxt = DAY + dt.timedelta(days=1)
    fake[nxt] = {bars.et_at(nxt, 9, 30) + 60 * i: [100.0, 101.0, 99.0, 100.5, 1] for i in range(390)}
    r = engine.simulate(pos([Leg("a", late, "open", 1)]), 30)   # 16:00: market closed
    assert r.status == "too_late"


def test_full_trim_then_add_re_enters(fake):
    r = engine.simulate(pos([Leg("a", T0, "open", 100), Leg("b", T0 + 300, "trim", 100),
                             Leg("c", T0 + 600, "add", 50), Leg("d", T0 + 900, "close")]), 1)
    assert [f.kind for f in r.fills] == ["entry", "exit", "entry", "exit"]


def test_day_trade_legs_after_1555_leave_at_1555(fake):
    r = engine.simulate(pos([Leg("a", T0, "open", 1), Leg("b", bars.et_at(DAY, 15, 58), "close")]), 1)
    assert r.assumed_exit and r.last_exit.ts == bars.et_at(DAY, 15, 55)


def test_target_ladder_and_break_even(fake):
    book = fake[DAY]
    for i in range(390):
        book[T0 + 60 * i] = [100.0, 100.4, 99.6, 100.0, 1]
    book[T0 + 300] = [100.0, 102.2, 99.9, 102.0, 1]    # trades TP1 (101) and TP2 (102)
    book[T0 + 600] = [100.5, 100.6, 99.5, 100.0, 1]    # back through the entry: break-even stop
    p = pos([Leg("a", T0, "open", 10)], stop=95.0, targets=[101.0, 102.0, 110.0], target_fracs=[0.25, 0.3, 0.45],
            be_after_target=2)
    r = engine.simulate(p, 1)
    kinds = [(f.kind, round(f.qty, 2), f.px) for f in r.fills]
    assert kinds == [("entry", 10, 100.0), ("target", 2.5, 101.0), ("target", 3.0, 102.0), ("stop", 4.5, 100.0)]


def test_portfolio_stats_reports_money_in_use_not_account_value():
    rs = [_r(0, 100, 1000, 50), _r(200, 300, 1000, 50)]
    row, series = engine.portfolio_stats(rs, ["1970-01-01"], {"end": 1, "ret_pct": 0, "sealed_ret_pct": 0},
                                         "1970-01-01")
    assert row["peak_invested_usd"] == 1000 and row["end"] == 10100 and row["trades"] == 2


# ---- story audit-2b-engine-fixes: the engine follows contracts.md where the audit found it didn't --------------

def test_post_time_keeps_its_fraction_of_a_second(fake):
    posted = T0 + 10 * 60 + 0.4           # 09:40:00.4 + 1 min = 09:41:00.4 -> the 09:42 bar, never 09:41
    r = engine.simulate(pos([Leg("a", posted, "open", 1)]), 1)
    assert r.entry.ts == T0 + 12 * 60


def test_post_ts_is_not_truncated():
    assert bars.post_ts("2025-10-17T16:17:56.687Z") % 1 == pytest.approx(0.687)


def test_several_targets_without_shares_exit_at_the_first(fake):
    book = fake[DAY]
    for i in range(390):
        book[T0 + 60 * i] = [100.0, 100.4, 99.6, 100.0, 1]
    book[T0 + 300] = [100.0, 101.2, 99.9, 101.0, 1]
    r = engine.simulate(pos([Leg("a", T0, "open", 10)], stop=95.0, targets=[101.0, 102.0]), 1)
    assert [(f.kind, f.qty, f.px) for f in r.fills] == [("entry", 10, 100.0), ("target", 10, 101.0)]


def test_at_horizon_before_the_entry_is_too_late(fake):
    p = pos([Leg("a", T0 + 600, "open", 1)])
    p.portfolio, p.default_exit = "swing", f"at:{T0 + 300}"
    assert engine.simulate(p, 1).status == "too_late"


def test_cash_rule_has_no_minimum():
    a = _r(0, 100, 9950, 10)
    b = _r(10, 50, 1000, 20)          # $50 left: sized down to it, not skipped
    kept, sized_down, skipped, _ = engine.fit_to_cash([a, b])
    assert [round(f, 4) for _, f in kept] == [1.0, 0.05] and sized_down == 1 and skipped == 0


def next_day(fake):
    nxt = DAY + dt.timedelta(days=1)
    fake[nxt] = {T0 + 86400 + 60 * i: [100.0, 100.4, 99.6, 100.0, 1] for i in range(390)}


def crypto(legs, **kw):
    return Position(pid="c", course="cryptowizard", market="us_equities", ticker="X", side="long",
                    portfolio="crypto", legs=legs, default_exit="hours:24", **kw)


def test_crypto_default_exit_is_24_hours_and_later_posts_are_too_late(fake):
    nxt = DAY + dt.timedelta(days=1)
    t1 = T0 + 86400
    fake[nxt] = {t1 + 60 * i: [100.0, 101.0, 99.0, 100.5, 1] for i in range(390)}
    r = engine.simulate(crypto([Leg("a", T0, "open"), Leg("b", T0 + 30 * 3600, "close")]), 1)
    assert r.assumed_exit and r.last_exit.kind == "default" and r.last_exit.ts == T0 + 60 + 86400


def test_take_profit_post_sells_that_targets_share(fake):
    book = fake[DAY]
    for i in range(390):
        book[T0 + 60 * i] = [100.0, 100.4, 99.6, 100.0, 1]
    next_day(fake)
    p = crypto([Leg("a", T0, "open"), Leg("tp1", T0 + 600, "trim", tp_index=1)], stop=90.0,
               targets=[105.0, 110.0], target_fracs=[0.4, 0.6])
    r = engine.simulate(p, 1)
    assert [(f.kind, round(f.qty, 6)) for f in r.fills][:2] == [("entry", 10.0), ("exit", 4.0)]


def test_take_profit_post_after_own_order_filled_sells_nothing(fake):
    book = fake[DAY]
    for i in range(390):
        book[T0 + 60 * i] = [100.0, 100.4, 99.6, 100.0, 1]
    book[T0 + 300] = [100.0, 105.2, 99.9, 105.0, 1]          # the copier's own TP1 order fills here
    next_day(fake)
    p = crypto([Leg("a", T0, "open"), Leg("tp1", T0 + 600, "trim", tp_index=1)], stop=90.0,
               targets=[105.0, 110.0], target_fracs=[0.4, 0.6])
    r = engine.simulate(p, 1)
    assert [f.kind for f in r.fills] == ["entry", "target", "default"]


def test_a_bar_is_never_watched_twice(fake):
    """A break-even stop set by a later bar must not fill in an earlier bar (a post after the 24 h exit used to
    send the engine back over bars it had already watched)."""
    book = fake[DAY]
    for i in range(390):
        book[T0 + 60 * i] = [100.0, 100.4, 99.6, 100.0, 1]       # dips under the entry, stop at 90 never trades
    book[T0 + 600] = [100.2, 102.2, 100.1, 102.0, 1]          # TP1 and TP2: break-even stop moves to 100
    next_day(fake)
    p = crypto([Leg("a", T0, "open"), Leg("c", T0 + 30 * 3600, "close")], stop=90.0,
               targets=[101.0, 102.0, 110.0], target_fracs=[0.25, 0.3, 0.45], be_after_target=2)
    r = engine.simulate(p, 1)
    assert [f.kind for f in r.fills] == ["entry", "target", "target", "stop"]
    assert r.fills[-1].ts > T0 + 600
