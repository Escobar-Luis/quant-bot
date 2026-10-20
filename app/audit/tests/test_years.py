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
    rows = years.by_year(list(mine.values()), HV, "the S&P")
    key = {"hold": {"basis": "total_return", "dividends": 0}, "periods": years.periods(HV),
           "portfolios": {"all": {"by_delay": {"5": rows}}}}
    assert years.compare(key, mine, ["all"], [5], HV, "the S&P", 1.0, 0.01) == []
    bad = {**rows, "2025": {**rows["2025"], "end": rows["2025"]["end"] + 2, "word": "Yes"}}
    key["portfolios"]["all"]["by_delay"]["5"] = bad
    assert {m["field"] for m in years.compare(key, mine, ["all"], [5], HV, "the S&P", 1.0, 0.01)} == {"end", "word"}


def test_compare_records_a_missing_or_broken_key_instead_of_raising():
    mine = {("a", 5): _t("a", DEC30, DEC31, 100.0)}
    assert years.compare("oops", mine, ["all"], [5], HV, "the S&P", 1.0, 0.01)[0]["field"] == "by_year"
    key = {"hold": {"basis": "total_return", "dividends": 0}, "periods": years.periods(HV),
           "portfolios": {"all": {"by_delay": {"5": {"2024": {"end": "x"}}}}, "zzz": {}}}
    fields = {(m["portfolio"], m["field"]) for m in years.compare(key, mine, ["all", "day"], [5], HV, "the S&P",
                                                                 1.0, 0.01)}
    assert ("day", "by_delay") in fields and ("zzz", "portfolio") in fields
    assert ("all@5:2024", "end") in fields and ("all@5", "periods") in fields


def test_loss_is_never_yes():
    ts = [_t(str(i), JAN2, JAN3, -1.0) for i in range(30)]
    for t in ts:
        t.entry_notional = 100.0   # all 30 fit in the cash (rule 6 takes cash per buy, from its fill)
        t.fills = [calc.Fill(f.ts, f.px, 1, f.kind) for f in t.fills]
    row = years.by_year(ts, {**HV, "total": {**HV["total"], "2025-01-03": 5000.0}}, "the S&P")["2025"]
    assert row["word"] == "No" and row["outcome"] == "Lost money" and row["vs"] == "less than the S&P"


@pytest.mark.parametrize("y", ["2024", "2025"])
def test_periods_cover_each_year_inside_the_window(y):
    assert any(p["id"] == y for p in years.periods(HV))
