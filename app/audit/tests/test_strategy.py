"""audit.strategy recomputes strategy_profile from the audit's own trades and flags any altered number."""
import copy
import json

import pytest

from audit import calc, strategy
from audit import positions as P
from audit.paths import DATA, RESULTS


def test_adds_and_patterns_follow_the_contract():
    f = lambda px: calc.Fill(0, px, 1.0, "entry")  # noqa: E731
    assert strategy._adds(calc.Trade("a", "day", 5, "priced", fills=[f(100.0)], side="short")) == "none"
    assert strategy._adds(calc.Trade("a", "day", 5, "priced", fills=[f(100.0), f(101.0)], side="short")) == "to_loser"
    assert strategy._adds(calc.Trade("a", "day", 5, "priced", fills=[f(100.0), f(99.0)], side="long")) == "to_loser"
    assert strategy._adds(calc.Trade("a", "day", 5, "priced", fills=[f(100.0), f(101.0)], side="long")) == "to_winner"


@pytest.fixture(scope="module")
def lpp_v1():
    path = RESULTS / "lpp" / "v1.json"
    if not path.exists() or not (DATA / "lpp" / "events.jsonl").exists():
        pytest.skip("needs results/lpp/v1.json and the local data/ folder")
    d = json.loads(path.read_text())
    if not d.get("strategy_profile"):
        pytest.skip("no strategy_profile in results/lpp/v1.json")
    mine = {}
    for p in P.build("lpp", "v1"):
        try:
            mine[(p.pid, 5)] = calc.simulate(p, 5)
        except calc.B.MissingBar:
            pytest.skip("bars missing from data/bars/")
    head = next(p for p in d["portfolios"] if p["id"] == "all")["by_delay"]["5"]
    return d["strategy_profile"], mine, head


def test_the_committed_profile_reconciles(lpp_v1):
    sp, mine, head = lpp_v1
    assert strategy.check(sp, mine, head, "v1") == []


def test_an_altered_number_or_a_rule_that_should_be_dropped_fails(lpp_v1):
    sp, mine, head = lpp_v1
    bad = copy.deepcopy(sp)
    bad["rules"][0]["pnl_usd"] += 5
    bad["rules"][0]["won_pct"] += 1
    bad["losing_patterns"] = bad["losing_patterns"][::-1]
    bad["tables"][0]["rows"][0]["trades"] += 1
    found = strategy.check(bad, mine, head, "v1")
    fields = {(m["portfolio"].split(".")[0], m["field"]) for m in found}
    assert {("rules", "pnl_usd"), ("rules", "won_pct"), ("losing_patterns", "selection"),
            ("tables", "trades")} <= fields
    bad = copy.deepcopy(sp)
    bad["rules"].append({**bad["rules"][0], "id": "S99", "when": {}, "does": {"side": ["long"]}})
    assert any(m["field"] == "kept_if" for m in strategy.check(bad, mine, head, "v1"))
