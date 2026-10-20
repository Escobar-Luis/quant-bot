"""by_year (contracts.md section by_year, spec-audit CAP-4): years are slices of the one all-time run."""
import datetime as dt

import pytest

from backtest import bars, engine, extras
from backtest.engine import Fill, Position, Result


def _res(pid, entry_day, exit_day, notional, pnl, market="us_equities"):
    p = Position(pid=pid, course="lpp", market=market, ticker="X", side="long", portfolio="day", legs=[],
                 default_exit="day_close")
    t0, t1 = bars.et_at(entry_day, 10, 0), bars.et_at(exit_day, 15, 0)
    r = Result(p, 5, "priced", fills=[Fill(t0, 100.0, notional / 100, "entry"), Fill(t1, 101.0, 1, "exit")])
    r.pnl, r.entry_notional = pnl, notional
    return r


DATES = ["2024-12-30", "2024-12-31", "2025-01-02", "2025-01-03"]
HOLD = {"dates": DATES, "price": [10000.0, 10100.0, 10200.0, 10404.0],
        "total": [10000.0, 10150.0, 10250.0, 10455.0], "meta": {"symbol": "SPY", "basis": "total_return"}}


def test_years_slice_the_all_time_run_and_trades_belong_to_their_exit_year():
    rs = [_res("a", dt.date(2024, 12, 30), dt.date(2024, 12, 31), 1000, 100.0),
          _res("b", dt.date(2024, 12, 31), dt.date(2025, 1, 2), 1000, -50.0),   # enters 2024, exits 2025
          _res("c", dt.date(2025, 1, 2), dt.date(2025, 1, 3), 1000, 30.0)]
    out = extras.by_year({"all": {5: rs}}, HOLD)
    assert [p["id"] for p in out["periods"]] == ["2024", "2025", "all"]
    assert out["periods"][1] == {"id": "2025", "from": "2025-01-02", "to": "2025-01-03"}
    row = out["portfolios"]["all"]["by_delay"]["5"]
    assert row["2024"]["trades"] == 1 and row["2025"]["trades"] == 2 and row["all"]["trades"] == 3
    assert row["2024"]["end"] == 10100.0 and row["2025"]["start"] == 10100.0 and row["2025"]["end"] == 10080.0
    assert row["2025"]["ret_pct"] == pytest.approx(round(-20 / 10100 * 100, 2))   # realized P&L / year-start money
    assert row["all"]["end"] == 10080.0 and row["all"]["ret_pct"] == 0.8
    # holding: one run, chained at the previous year's last close; total return beside price only
    assert row["2024"]["hold_ret_pct"] == 1.5 and row["2024"]["hold_price_ret_pct"] == 1.0
    assert row["2025"]["hold_start"] == 10150.0 and row["2025"]["hold_ret_pct"] == pytest.approx(3.0, abs=0.01)
    assert row["all"]["hold_ret_pct"] == 4.55 and row["all"]["hold_price_ret_pct"] == 4.04
    assert all(r["word"] == "Not enough trades" for r in row.values())


def test_all_equals_the_headline_cash_cap_included():
    # 12 trades of $1,000 open at once: the cash cap sizes some down; by_year uses the same copied sizes
    rs = [_res(str(i), dt.date(2024, 12, 30), dt.date(2025, 1, 2), 1000, 10.0 * (i + 1)) for i in range(12)]
    head, _ = engine.portfolio_stats(rs, DATES, {"end": 1, "ret_pct": 0, "sealed_ret_pct": 0}, "2025-01-03")
    row = extras.by_year({"all": {5: rs}}, HOLD)["portfolios"]["all"]["by_delay"]["5"]
    assert head["sized_down"] or head["couldnt_copy"]
    assert (row["all"]["end"], row["all"]["ret_pct"], row["all"]["trades"]) == \
        (head["end"], head["ret_pct"], head["trades"])
    assert row["2024"]["trades"] == 0 and row["2025"]["trades"] == head["trades"]


def test_dividends_are_reinvested_at_the_ex_date_close(monkeypatch):
    closes = {"2024-09-19": 100.0, "2024-09-20": 100.0, "2024-09-23": 110.0}
    monkeypatch.setattr(bars, "daily_closes", lambda *a: closes)
    monkeypatch.setattr(bars, "day_bars", lambda *a: {1: [100.0, 0, 0, 0, 0]})
    monkeypatch.setattr(bars, "dividends", lambda *a: {"2024-09-19": 5.0, "2024-09-20": 1.0})
    h = extras.hold_paths("us_equities", "SPY", {"start": "2024-09-19", "end": "2024-09-23"})
    assert h["meta"]["dividends"] == 1                      # the buy day's ex-date pays nothing
    assert h["price"] == [10000.0, 10000.0, 11000.0]
    assert h["total"] == pytest.approx([10000.0, 10100.0, 11110.0])
