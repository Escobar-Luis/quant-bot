"""Mutation test: break one engine constant, rerun the engine on a small fixture, and the audit must fail.

The fixture is the synthetic cases where the engine agrees with the contract. The engine's ledger is written by
backtest.run.write_ledger (into a temp dir) and read back by the audit, as in a real run.
"""
import json
from types import SimpleNamespace

import pytest

from audit import calc, run
from audit.tests import synthetic as S
from audit.tests.test_synthetic import KNOWN_ENGINE_DIVERGENCES
from backtest import engine
from backtest import run as brun

DELAYS = [1, 5]
FIXTURE = [c for c in S.cases() if c.name not in KNOWN_ENGINE_DIVERGENCES]


def reconcile(tmp_path, monkeypatch) -> list[dict]:
    """Engine -> stamped ledger on disk -> audit reconciliation; returns the audit's mismatches."""
    monkeypatch.setattr(brun, "DATA", tmp_path)
    results = tmp_path / "v1.json"
    results.write_text(json.dumps({"fixture": True}))
    mismatches = []
    for i, c in enumerate(FIXTURE):
        undo = S.patch_bars(c.bars)
        try:
            p = S.to_engine(c.position, c.sizing)
            p.pid = f"case-{i}"
            rows = [engine.simulate(p, d) for d in DELAYS]
            a = SimpleNamespace(limit=None, course="syn", version=f"v{i}", ledger_only=False)
            brun.write_ledger(a, "", rows, results, "test-run")
            meta, ledger = run.read_ledger(tmp_path / "audit" / f"syn-v{i}-ledger.jsonl")
            assert meta["results_sha256"] == run.sha256(results)
            for d in DELAYS:
                ours = calc.simulate(c.position, d, c.sizing)
                ours.pid = p.pid
                run.compare_trade("ledger", p.pid, d, run.engine_row(ledger[(p.pid, d)]), run.audit_row(ours),
                                  mismatches)
        finally:
            for mod, name, fn in undo:
                setattr(mod, name, fn)
    return mismatches


def test_unmutated_engine_reconciles(tmp_path, monkeypatch):
    assert reconcile(tmp_path, monkeypatch) == []


def test_cost_bps_off_fails(tmp_path, monkeypatch):
    monkeypatch.setitem(engine.COSTS_BPS, "stocks", 6)
    bad = reconcile(tmp_path, monkeypatch)
    assert any(m["field"] == "pnl" for m in bad)


def test_under_ten_tier_off_fails(tmp_path, monkeypatch):
    monkeypatch.setitem(engine.COSTS_BPS, "stocks_under_10", 5)
    bad = reconcile(tmp_path, monkeypatch)
    assert {m["pid"] for m in bad if m["field"] == "pnl"}


def test_delay_off_by_one_minute_fails(tmp_path, monkeypatch):
    real = engine._simulate

    def late(p, d):                                    # prices every leg one minute late, labelled as asked
        r = real(p, d + 1)
        r.delay_min = d
        return r

    monkeypatch.setattr(engine, "_simulate", late)
    bad = reconcile(tmp_path, monkeypatch)
    assert any(m["field"] in ("entry_at", "status") for m in bad)


def test_stale_ledger_fails(tmp_path):
    """A ledger stamped for another results file (e.g. before a --limit run rewrote results/) fails the file."""
    led = tmp_path / "x-v1-ledger.jsonl"
    led.write_text(json.dumps({"_meta": {"results_sha256": "0" * 64}}) + "\n")
    meta, rows = run.read_ledger(led)
    assert meta["results_sha256"] != run.sha256(led) and rows == {}


@pytest.mark.parametrize("fills", [[], [[1, 100.0, 1.0, "entry"]], [[1, 100.0, 1.0, "exit"]]])
def test_broken_ledger_row_is_a_mismatch_not_a_crash(fills):
    theirs = run.engine_row({"status": "priced", "fills": fills, "pnl": 0.0})
    out = []
    run.compare_trade("ledger", "x", 5, theirs, {"status": "priced"}, out)
    assert out and out[0]["field"] == "status"


def test_missing_headline_field_is_a_mismatch_not_a_crash():
    out = []
    run.compare_head("all", "5", {"end": 1.0}, {"end": 1.0, "won_pct": 50, "sealed": {"ret_pct": 0.0}}, out)
    assert {m["field"] for m in out} == {"won_pct", "sealed"}
