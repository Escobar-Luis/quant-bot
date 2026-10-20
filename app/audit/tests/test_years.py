"""audit.years recomputes by_year from the contract and flags any change to the file's numbers."""
import pytest

from audit import calc, years

HV = {"days": ["2024-12-30", "2024-12-31", "2025-01-02", "2025-01-03"],
      "price": {"2024-12-30": 10000.0, "2024-12-31": 10100.0, "2025-01-02": 10200.0, "2025-01-03": 10404.0},
      "total": {"2024-12-30": 10000.0, "2024-12-31": 10150.0, "2025-01-02": 10250.0, "2025-01-03": 10455.0},
      "dividends": 0, "basis": "total_return"}


def _t(pid, entry_ts, exit_ts, pnl):
    t = calc.Trade(pid, "day", 5, "priced", fills=[calc.Fill(entry_ts, 100.0, 10, "entry"),
                                                   calc.Fill(exit_ts, 101.0, 10, "exit")])
    t.pnl, t.entry_notional = pnl, 1000.0
    return t


DEC30, DEC31, JAN2, JAN3 = 1735570800, 1735657200, 1735830000, 1735916400   # 10:00 ET each day


def test_years_chain_and_trades_go_to_their_exit_year():
    rows = years.by_year([_t("a", DEC30, DEC31, 100.0), _t("b", DEC31, JAN2, -50.0), _t("c", JAN2, JAN3, 30.0)], HV)
    assert rows["2024"]["end"] == 10100.0 and rows["2025"]["start"] == 10100.0 and rows["2025"]["trades"] == 2
    assert rows["all"]["end"] == 10080.0 and rows["all"]["trades"] == 3
    assert rows["2025"]["hold_start"] == 10150.0 and rows["all"]["hold_ret_pct"] == 4.55


def test_compare_flags_an_altered_year():
    mine = {("a", 5): _t("a", DEC30, DEC31, 100.0), ("c", 5): _t("c", JAN2, JAN3, 30.0)}
    rows = years.by_year(list(mine.values()), HV)
    key = {"hold": {"basis": "total_return", "dividends": 0}, "periods": years.periods(HV),
           "portfolios": {"all": {"by_delay": {"5": rows}}}}
    assert years.compare(key, mine, [5], HV, 1.0, 0.01) == []
    bad = {**rows, "2025": {**rows["2025"], "end": rows["2025"]["end"] + 2, "word": "Yes"}}
    key["portfolios"]["all"]["by_delay"]["5"] = bad
    assert {m["field"] for m in years.compare(key, mine, [5], HV, 1.0, 0.01)} == {"end", "word"}


@pytest.mark.parametrize("y", ["2024", "2025"])
def test_periods_cover_each_year_inside_the_window(y):
    assert any(p["id"] == y for p in years.periods(HV))
