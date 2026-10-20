"""backtest.howsure: the luck tests, the shuffles, walk-forward and the proven rule (spec-audit CAP-16)."""
import math

import numpy as np
import pytest

from backtest import howsure as H


def test_deflated_sharpe_matches_bailey_lopez_de_prado_example():
    # Their 2014 example: annual SR 2.5 over 1,250 days, 100 trials whose annual Sharpes vary by 0.5,
    # skew -3, kurtosis 10 -> SR0 about 0.1132 a day and DSR about 0.90.
    sr0 = H.expected_max_sr(100, 0.5 / 250)
    assert sr0 == pytest.approx(0.1132, abs=5e-4)
    assert H.psr_from(2.5 / math.sqrt(250), 1250, -3, 10, sr0) == pytest.approx(0.9004, abs=2e-3)


def test_one_trial_has_no_haircut():
    assert H.expected_max_sr(1, 0.01) == 0.0
    x = list(np.random.default_rng(1).normal(0.1, 1, 500))
    assert H.deflated(x, 1, 0.01, 252)["dsr"] == pytest.approx(H.psr(x, 0.0), abs=1e-4)


def test_harvey_liu_bonferroni():
    x = list(np.random.default_rng(2).normal(0.2, 1, 250))
    one, many = H.harvey_liu(x, 1, 252), H.harvey_liu(x, 50, 252)
    assert one["p_adjusted"] == one["p"] and many["p_adjusted"] == pytest.approx(min(1, 50 * many["p"]), abs=3e-3)   # p is rounded to 4 dp
    assert many["haircut_sharpe_ann"] <= one["haircut_sharpe_ann"] <= one["sharpe_ann"]
    assert H.harvey_liu([-1.0, 0.5, -0.2] * 50, 1, 252)["passes"] is False


def test_label_shuffle_is_seeded_and_ranks_a_clear_pick_high():
    delta = [10.0] * 10 + [-1.0] * 90
    a, b = H.label_shuffle(delta, list(range(10))), H.label_shuffle(delta, list(range(10)))
    assert a == b and a["pct_rank"] == 100.0 and a["passes"]
    assert H.label_shuffle(delta, list(range(90, 100)))["passes"] is False


def test_walk_forward_picks_on_train_and_reports_test():
    months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05"]
    by = {"as-is": {m: 0.0 for m in months},
          "A": {"2025-01": 5, "2025-02": 5, "2025-03": 5, "2025-04": -2, "2025-05": 1}}
    wf = H.walk_forward(by, months, {m: 1.0 for m in months})
    assert [f["test"] for f in wf["folds"]] == ["2025-04", "2025-05"]
    assert [f["picked"] for f in wf["folds"]] == ["A", "A"]
    assert wf["oos_ret_pct"] == -1.0 and wf["oos_vs_as_is_pts"] == -1.0 and wf["passes"] is False


def test_walk_forward_ties_go_to_as_is():
    months = ["a", "b", "c", "d"]
    wf = H.walk_forward({"as-is": {}, "A": {}}, months, {})
    assert wf["folds"][0]["picked"] == "as-is"


def test_regime_splits_by_spy_month_sign():
    dates = ["2025-01-02", "2025-02-03", "2025-03-03"]
    spy = {"2025-01": 2.0, "2025-02": -1.0, "2025-03": 0.5}
    r = H.regime(dates, [100.0, -50.0, 30.0], spy, spy, "SPY")
    assert r["up"]["months"] == 2 and r["up"]["ret_pct"] == 1.3 and r["up"]["edge_pts"] == -1.2
    assert r["down"]["ret_pct"] == -0.5 and r["down"]["edge_pts"] == 0.5 and r["passes"] is False
    btc = {"2025-01": -5.0, "2025-02": -5.0, "2025-03": 0.0}          # another benchmark, same SPY split
    assert H.regime(dates, [100.0, -50.0, 30.0], spy, btc, "BTC")["up"]["edge_pts"] == 6.3
    assert H.regime(dates, [100.0, -50.0, 30.0], spy, None, "as-is")["passes"] is False


def test_risk():
    k = H.risk([-100.0, 50.0, -200.0, 0.0], ["d1", "d2", "d3", "d4"], [-1, -2, 3, -4, 0, -1], -2.5)
    assert k["longest_losing_streak"] == 3 and k["worst_day"] == {"day": "d3", "pnl_usd": -200.0}
    assert k["max_drawdown_pct"] == pytest.approx(-2.5, abs=0.01)


def row(**kw):
    base = {"trades": 100, "edge_pts": 2.0, "luck": {"passes": True}, "shuffle": {"passes": True},
            "walk_forward": None, "sensitivity": {"passes": True}, "regime": {"passes": True}}
    return H.verdict({**base, **kw})


def test_proven_only_when_every_test_that_applies_passes():
    assert row()["proven"] and row()["label"] == "survives"
    assert row(regime={"passes": False})["why_not"] == ["regime failed"]
    assert row(edge_pts=-1.0)["label"] == "not proven"
    assert "fewer than 30 trades" in row(trades=1, luck=None, shuffle=None)["why_not"]
