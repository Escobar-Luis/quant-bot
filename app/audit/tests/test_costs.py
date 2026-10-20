"""The audit's own rule 5 cost cases (spec-audit CAP-17, story 29)."""
import datetime as dt

import pytest

from audit import bars as B
from audit import calc

DAY = dt.date(2024, 8, 15)
T0 = B.et_time(DAY, 9, 30)


@pytest.fixture
def thin(monkeypatch):
    monkeypatch.setattr(calc, "dollar_volume_20", lambda t, d: 80e6 if t == "BIG" else 1e6)


def short(ticker="THIN", days=0):
    t = calc.Trade("x", "day", 5, "priced", market="us_equities", side="short", ticker=ticker)
    t.fills = [calc.Fill(T0, 20.0, 50.0, "entry"), calc.Fill(T0 + days * 86400 + 600, 19.0, 50.0, "exit")]
    t.cost = sum(calc.cost_of("us_equities", f.px, f.qty) for f in t.fills)
    t.pnl = 50.0 - t.cost
    t.entry_notional = 1000.0
    return t


def test_side_rates(thin):
    assert calc.side_rate("simple", "us_equities", "BIG", 9.0, T0) == 20 / 1e4
    assert calc.side_rate("realistic", "us_equities", "BIG", 12.0, T0) == 5 / 1e4
    assert calc.side_rate("realistic", "us_equities", "THIN", 12.0, T0) == 15 / 1e4
    assert calc.side_rate("x2", "us_equities", "THIN", 4.0, T0) == 120 / 1e4
    assert calc.side_rate("realistic", "crypto", "BTCUSDT", 1.0, T0) == 25 / 1e4


def test_simple_is_the_trade_itself(thin):
    t = short()
    assert calc.under_case(t, "simple", {}) is t


def test_realistic_short_borrow_by_flag_and_days(thin):
    t = calc.under_case(short(days=3), "realistic", {"THIN": "hard"})
    assert t.borrow == pytest.approx(1000 * 0.30 * 3 / 360)
    assert t.pnl == pytest.approx(50.0 - (1000 + 950) * 15 / 1e4 - t.borrow)
    easy = calc.under_case(short(), "x2", {"THIN": "easy"})
    assert easy.borrow == pytest.approx(1000 * 0.01 / 360)


def test_portfolio_totals_match_the_trades(thin):
    tot = {}
    row = calc.portfolio([short()], {"end": 1, "ret_pct": 0.0, "sealed_ret_pct": 0.0}, None, "hold", "x",
                         "realistic", {}, tot)
    t = calc.under_case(short(), "realistic", {})
    assert row["end"] == round(10_000 + t.pnl, 2)
    assert tot["costs_usd"] == pytest.approx(t.cost) and tot["borrow_usd"] == pytest.approx(t.borrow)
