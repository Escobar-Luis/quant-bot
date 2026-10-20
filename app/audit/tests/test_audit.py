"""The audit fails loudly on a result it can't reproduce, and passes an untouched one."""
import json
import shutil

import pytest

from audit import calc, run
from audit.paths import DATA, RESULTS


def test_headline_tolerance_is_one_dollar():
    base = {"end": 9765.86, "ret_pct": -2.34, "hold_end": 11963.79, "hold_ret_pct": 19.64, "trades": 315,
            "word": "No"}
    out = []
    run.compare_head("all", "5", base, {**base, "end": 9766.5}, out)
    assert out == []
    run.compare_head("all", "5", base, {**base, "end": 9767.0, "trades": 314, "word": "Barely"}, out)
    assert {m["field"] for m in out} == {"end", "trades", "word"}


def test_trade_tolerance_is_one_cent():
    a = {"status": "priced", "entry_at": 100, "entry": 10.0, "exit_at": 200, "exit": 11.0, "pnl": 5.0}
    out = []
    run.compare_trade("ledger", "x", 5, a, {**a, "pnl": 5.01}, out)
    assert out == []
    run.compare_trade("ledger", "x", 5, a, {**a, "pnl": 5.02, "exit_at": 260}, out)
    assert {m["field"] for m in out} == {"pnl", "exit_at"}


def test_word_follows_rule_9():
    assert calc.word(29, 50.0, 0.0) == "Not enough trades"
    assert calc.word(30, 2.0, 0.0) == "Yes"
    assert calc.word(30, 1.99, 0.0) == "Barely"
    assert calc.word(30, -2.0, 0.0) == "No"


NEED = [DATA / "audit" / "ziptrader-v1-ledger.jsonl", DATA / "ziptrader" / "events.jsonl"]


def _diff(tmp_path) -> dict:
    return json.loads((tmp_path / "diff-ziptrader-v1.json").read_text())


@pytest.mark.skipif(not all(p.exists() for p in NEED), reason="needs local data/ (ziptrader events, ledger, bars)")
def test_altered_result_exits_non_zero(tmp_path):
    src = RESULTS / "ziptrader" / "v1.json"
    (tmp_path / "ziptrader").mkdir()
    dst = tmp_path / "ziptrader" / "v1.json"
    args = ["--results-dir", str(tmp_path), "--out-dir", str(tmp_path), "--proofs", "", "--only", "ziptrader/v1"]

    shutil.copy(src, dst)
    run.main(args)                                     # untouched: the math alone reconciles, the ledger is fresh
    clean = _diff(tmp_path)
    assert clean["math_on_loader_positions"]["main"]["mismatches"] == 0
    assert not any(m["kind"] == "stale" for m in clean["details"])

    d = json.loads(src.read_text())
    d["portfolios"][0]["by_delay"]["5"]["end"] += 5    # a headline $5 off
    dst.write_text(json.dumps(d))
    assert run.main(args) != 0
    rep = _diff(tmp_path)
    assert any(m["kind"] == "stale" for m in rep["details"])          # the ledger no longer matches the file
    assert any(m["field"] == "end" and m["delay"] == 5 for m in rep["math_on_loader_positions"]["main"]["details"])

    d = json.loads(src.read_text())
    d["trades"][0]["by_delay"]["5"]["exit"] += 0.05    # one trade's exit 5 cents off
    dst.write_text(json.dumps(d))
    assert run.main(args) != 0
    assert any(m["field"] == "exit" and m["delay"] == 5 and m["against"] == "results"
               for m in _diff(tmp_path)["details"])
