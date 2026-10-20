"""Rule 5's cost cases and rule 12(m)'s gap stops (spec-audit CAP-17, story 29): cd app && uv run pytest backtest/tests -q"""
import datetime as dt

import pytest

from backtest import bars, costs, engine
from backtest.engine import Leg, Position

DAY = dt.date(2024, 8, 15)
T0 = bars.et_at(DAY, 9, 30)


@pytest.fixture
def fake(monkeypatch):
    book = {}
    monkeypatch.setattr(bars, "day_bars", lambda market, symbol, day: book.get(day, {}))
    book[DAY] = {T0 + 60 * i: [100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000] for i in range(390)}
    monkeypatch.setattr(costs, "adv_before", lambda t, d: 80e6 if t == "BIG" else 1e6)
    return book


def pos(legs, side="long", ticker="BIG", **kw):
    return Position(pid="t", course="lpp", market="us_equities", ticker=ticker, side=side, portfolio="day",
                    legs=legs, default_exit="day_close", **kw)


def test_side_cost_tiers():
    assert costs.side_bps("simple", "us_equities", 9.99) == 20 and costs.side_bps("simple", "us_equities", 10) == 5
    assert costs.side_bps("realistic", "us_equities", 12, 60e6) == 5
    assert costs.side_bps("realistic", "us_equities", 12, 10e6) == 15
    assert costs.side_bps("realistic", "us_equities", 7, 60e6) == 30
    assert costs.side_bps("realistic", "us_equities", 4.99, 0) == 60
    assert costs.side_bps("x2", "us_equities", 4.99, 0) == 120
    assert costs.side_bps("realistic", "crypto", 50_000) == 25 and costs.side_bps("x2", "crypto", 1) == 50


def test_borrow_rates_and_days():
    assert costs.borrow_pct("simple", "hard") == 0
    assert costs.borrow_pct("realistic", "unknown") == costs.borrow_pct("realistic", "hard") == 30
    assert costs.borrow_pct("x2", "easy") == 1.0
    assert costs.days_held(DAY, DAY) == 1 and costs.days_held(DAY, DAY + dt.timedelta(days=3)) == 3
    assert costs.borrow_usd("realistic", "hard", 1000, 1) == pytest.approx(1000 * 0.30 / 360)
    assert costs.flag_word("us_equities", None) == "unknown" and costs.flag_word("crypto", True) == "crypto"


def test_simple_reprice_is_the_result_itself(fake):
    r = engine.simulate(pos([Leg("a", T0, "open", 10), Leg("b", T0 + 600, "close")], side="short"), 1)
    assert engine.reprice(r, costs.SIMPLE) is r


def test_realistic_short_pays_spread_and_one_day_of_borrow(fake):
    r = engine.simulate(pos([Leg("a", T0, "open", 10), Leg("b", T0 + 600, "close")], side="short", ticker="THIN"), 1)
    m = costs.Model("realistic", {"THIN": "hard"})
    x = engine.reprice(r, m)
    gross = r.pnl + r.cost
    spread = sum(f.px * f.qty for f in r.fills) * 15 / 1e4          # $10+ but thin: 5 + 10 bps
    borrow = r.entry.px * r.entry.qty * 0.30 / 360                   # intraday: one day
    assert x.borrow == pytest.approx(borrow)
    assert x.pnl == pytest.approx(gross - spread - borrow)
    x2 = engine.reprice(r, costs.Model("x2", {"THIN": "hard"}))
    assert x2.pnl == pytest.approx(gross - 2 * spread - 2 * borrow)


def test_long_pays_no_borrow(fake):
    r = engine.simulate(pos([Leg("a", T0, "open", 10), Leg("b", T0 + 600, "close")]), 1)
    assert engine.reprice(r, costs.Model("realistic", {"BIG": "hard"})).borrow == 0


def test_fit_to_cash_matches_reprice_and_totals(fake):
    r = engine.simulate(pos([Leg("a", T0, "open"), Leg("b", T0 + 600, "close")], side="short", ticker="THIN"), 1)
    m = costs.Model("realistic", {"THIN": "unknown"})
    x = engine.reprice(r, m)
    tot = {}
    kept, *_ = engine.fit_to_cash([x], m, tot)
    assert kept[0][1] == pytest.approx(x.pnl)
    assert tot["costs_usd"] == pytest.approx(x.cost) and tot["borrow_usd"] == pytest.approx(x.borrow)


def test_simple_case_row_equals_the_headline(fake):
    rs = [engine.simulate(pos([Leg("a", T0 + 60 * i, "open"), Leg("b", T0 + 60 * i + 600, "close")],
                              side="short"), 1) for i in range(3)]
    hold = {"end": 1, "ret_pct": 0, "sealed_ret_pct": 0}
    a = engine.portfolio_stats(rs, ["2024-08-15"], hold, "2024-08-15")[0]
    tot = {}
    b = engine.portfolio_stats(rs, ["2024-08-15"], hold, "2024-08-15", model=costs.SIMPLE, totals=tot)[0]
    assert a == b and tot["borrow_usd"] == 0
    c = engine.portfolio_stats(rs, ["2024-08-15"], hold, "2024-08-15", model=costs.Model("x2", {"BIG": "easy"}))[0]
    assert c["end"] < a["end"]


def test_stop_crossed_by_a_gap_fills_at_the_open(fake):
    """Rule 12(m): a short's stop at 105 with a bar opening at 110 fills at 110, not 105."""
    p = pos([Leg("a", T0, "open", 1)], side="short", stop=105.0)
    fake[DAY] = {T0 + 60: [100.0, 100.5, 99.5, 100.0, 1], T0 + 120: [110.0, 111.0, 109.0, 110.0, 1],
                 bars.et_at(DAY, 15, 55): [90.0, 90.0, 90.0, 90.0, 1]}
    r = engine.simulate(p, 1)
    assert r.last_exit.kind == "stop" and r.last_exit.px == 110.0


def test_stop_inside_the_bar_fills_at_its_level(fake):
    p = pos([Leg("a", T0, "open", 1)], side="short", stop=105.0)
    fake[DAY] = {T0 + 60: [100.0, 100.5, 99.5, 100.0, 1], T0 + 120: [101.0, 106.0, 100.0, 104.0, 1],
                 bars.et_at(DAY, 15, 55): [90.0, 90.0, 90.0, 90.0, 1]}
    assert engine.simulate(p, 1).last_exit.px == 105.0
