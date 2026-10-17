"""Every committed results file keeps the contracts.md shape the web app and PRISM lane read."""
import json

import pytest

from backtest import engine
from backtest.common import DELAYS_MIN, RESULTS

FILES = sorted(p for p in RESULTS.glob("*/*.json"))


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_results_file_matches_contract(path):
    d = json.loads(path.read_text())
    assert d["schema"] == "results/1" and d["course"] == path.parent.name and d["version"] == path.stem
    assert d["delays_min"] == DELAYS_MIN and str(d["default_delay_min"]) in {str(x) for x in DELAYS_MIN}
    assert d["window"]["start"] <= d["window"]["sealed_from"] <= d["window"]["end"]
    assert isinstance(d["sample"], bool) and isinstance(d["unknown"], list) and d["unknown"]
    assert {"symbol", "label", "what"} <= set(d["hold"])
    testable = {p["id"] for p in d["portfolios"] if p["testable"]}
    assert d["headline_portfolio"] == "all" and "all" in testable
    need = {"end", "ret_pct", "hold_end", "hold_ret_pct", "trades", "not_triggered", "couldnt_copy", "won_pct",
            "worst_drop_pct", "word", "sealed"}
    words = {"Yes", "Barely", "No", "Not enough trades"}
    for p in d["portfolios"]:
        if not p["testable"]:
            assert "count" in p and p["why"]
            continue
        assert set(p["by_delay"]) == {str(x) for x in DELAYS_MIN}
        assert len(p["series"]["dates"]) == len(p["series"]["hold"])
        for k, row in p["by_delay"].items():
            assert need <= set(row) and {"ret_pct", "hold_ret_pct"} <= set(row["sealed"])
            assert row["word"] in words
            assert row["word"] == engine.word(row["trades"], row["ret_pct"], row["hold_ret_pct"])
            assert len(p["series"]["by_delay"][k]) == len(p["series"]["dates"])
            assert row["end"] == pytest.approx(p["series"]["by_delay"][k][-1], abs=0.05)
    for item in d["rules"] + d["trades"]:
        if item.get("quote"):
            assert len(item["quote"].rstrip("…").split()) <= 12
    for r in d["rules"]:
        assert len(r["text"].split()) <= 15
    assert len(d["trades"]) <= 200


def test_results_exist():
    assert {f"{p.parent.name}/{p.stem}" for p in FILES} >= {"lpp/v1", "cryptowizard/v1", "ziptrader/v1"}
