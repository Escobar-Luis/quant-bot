"""audit.improvements recomputes the improvements key from the audit's own positions and flags altered numbers."""
import copy
import json

import pytest

from audit import calc, improvements
from audit import positions as P
from audit.paths import DATA, RESULTS


@pytest.fixture(scope="module")
def lpp_v1():
    path = RESULTS / "lpp" / "v1.json"
    if not path.exists() or not (DATA / "lpp" / "events.jsonl").exists():
        pytest.skip("needs results/lpp/v1.json and the local data/ folder")
    d = json.loads(path.read_text())
    if not d.get("improvements"):
        pytest.skip("no improvements in results/lpp/v1.json")
    mine = {}
    for p in P.build("lpp", "v1"):
        try:
            mine[(p.pid, 5)] = calc.simulate(p, 5)
        except calc.B.MissingBar:
            pytest.skip("bars missing from data/bars/")
    return d, mine


def run(d, mine, imp=None):
    return improvements.check(imp or d["improvements"], mine, "v1", d["window"],
                              d["strategy_profile"]["definitions"])


def test_the_committed_improvements_reconcile(lpp_v1):
    d, mine = lpp_v1
    assert run(d, mine) == []


def test_as_is_equals_the_headline(lpp_v1):
    d, _ = lpp_v1
    imp, head = d["improvements"], next(p for p in d["portfolios"] if p["id"] == "all")["by_delay"]["5"]
    assert imp["as_is"]["dev"]["trades"] + imp["as_is"]["sealed"]["trades"] == head["trades"]
    assert imp["as_is"]["sealed"]["ret_pct"] == head["sealed"]["ret_pct"]
    assert abs(imp["as_is"]["dev"]["ret_pct"] + imp["as_is"]["sealed"]["ret_pct"] - head["ret_pct"]) <= 0.02


def test_an_altered_number_or_keep_flag_is_flagged(lpp_v1):
    d, mine = lpp_v1
    imp = copy.deepcopy(d["improvements"])
    v = imp["variants"][0]
    v["sealed"]["ret_pct"] += 0.5
    v["kept"] = not v["kept"]
    fields = {m["field"] for m in run(d, mine, imp)}
    assert {"ret_pct", "kept"} <= fields


def test_a_look_ahead_condition_is_flagged(lpp_v1):
    d, mine = lpp_v1
    imp = copy.deepcopy(d["improvements"])
    imp["variants"][0]["when"] = {"adds": ["to_loser"]}
    assert any("known only after entry" in m["field"] for m in run(d, mine, imp))
