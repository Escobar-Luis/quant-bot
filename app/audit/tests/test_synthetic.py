"""calc.simulate on made-up bars against answers worked out by hand from contracts.md; then the engine on the same
positions, with every place it departs from the contract listed (a finding, not a fix)."""
import pytest

from audit import bars as AB
from audit import calc
from audit.tests import synthetic as S

CASES = S.cases()


@pytest.fixture
def use_bars(monkeypatch):
    def go(book):
        S.patch_bars(book, monkeypatch.setattr)
    return go


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_calc_matches_the_contract(case, use_bars):
    use_bars(case.bars)
    got = S.outcome_audit(calc.simulate(case.position, case.delay, case.sizing))
    assert got["status"] == case.expect["status"], case.why
    if got["status"] == "priced":
        assert got["entry"] == pytest.approx(case.expect["entry"]), case.why
        assert got["exit"] == pytest.approx(case.expect["exit"]), case.why
        assert got["pnl"] == pytest.approx(case.expect["pnl"], abs=1e-9), case.why


def test_calc_cash_rule_has_no_minimum():
    trades, want = S.cash_case()
    assert S.audit_cash(trades) == want


# Where backtest.engine departs from the contract on these cases. PR #55 found three ("two targets, no fractions",
# "at: exit before entry", "cash under $100"); story audit-2b-engine-fixes fixed them. A change in this list means
# the engine (or the contract) changed: update it on purpose, never to make the test pass.
KNOWN_ENGINE_DIVERGENCES: set[str] = set()


def test_engine_divergences_are_the_known_ones():
    got = {d["case"] for d in S.engine_divergences()}
    assert got == KNOWN_ENGINE_DIVERGENCES


def test_bars_are_restored_after_engine_run():
    real = AB.day_bars
    S.engine_divergences()
    assert AB.day_bars is real
