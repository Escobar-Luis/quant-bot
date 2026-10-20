"""audit.howsure: its own luck-test math (never imports backtest), and that the check catches an altered file."""
import json
import math

import numpy as np
import pytest

from audit import howsure as A


def test_dsr_reproduces_the_bailey_lopez_de_prado_example_from_series():
    # members whose daily Sharpes have a known variance; the claim's own series long enough to estimate it
    rng = np.random.default_rng(5)
    members = [list(rng.normal(m, 1, 4000)) for m in np.linspace(-0.1, 0.1, 10)]
    p, sr0, var = A.dsr(members[-1], 10, members)
    srs = [np.mean(m) / np.std(m, ddof=1) for m in members]
    assert var == pytest.approx(np.var(srs, ddof=1), rel=1e-9)
    want = math.sqrt(var) * ((1 - A.G) * A.Z.inv_cdf(0.9) + A.G * A.Z.inv_cdf(1 - 1 / (10 * math.e)))
    assert sr0 == pytest.approx(want, rel=1e-9) and 0 < p < 1


def test_stats_and_hl():
    sr, sk, ku, n = A._stats([1.0, -1.0] * 50)
    assert sr == 0 and sk == pytest.approx(0) and ku == pytest.approx(1) and n == 100
    sr, p, pa = A.hl([0.5, 1.5] * 50, 3)
    assert p < 1e-6 and pa == pytest.approx(min(1, 3 * p))


def _file(tmp_path, claim, fams=None):
    d = {"schema": "how-sure/1", "seed": 28, "draws": 1000, "families": fams or {}, "calendars": {"c": ["d1", "d2"]},
         "claims": [claim], "summary": {"proven": int(bool(claim.get("proven")))}}
    p = tmp_path / "how-sure.json"
    p.write_text(json.dumps(d))
    return p


def test_check_flags_a_label_that_ignores_a_failed_test(tmp_path, monkeypatch):
    # a lab claim with no shuffle; its run exists in a minimal strategy-lab file
    lab = tmp_path / "strategy-lab.json"
    lab.write_text(json.dumps({"variants_tried": 2, "runs": [{"rule": "C", "variant": "control", "universe": "u",
                                                              "pnl_usd": 3.0, "vs_spy_pts": 1.0}]}))
    lpp = tmp_path / "lpp"
    lpp.mkdir()
    (lpp / "v1.json").write_text(json.dumps({"improvements": {"variants": [], "variants_tried": {}}}))
    monkeypatch.setattr(A, "RESULTS", tmp_path)
    series = [1.0, 2.0]
    claim = {"id": "lab:C|control|u", "family": "strategy-lab", "card": "lab", "rule": "C", "variant": "control",
             "universe": "u", "trades": 40, "edge_pts": 1.0, "series": {"calendar": "c", "pnl": series},
             "luck": None, "shuffle": None, "walk_forward": None, "sensitivity": None,
             "regime": {"passes": False},
             "tests": {"luck": None, "shuffle": None, "walk_forward": None, "sensitivity": None, "regime": False},
             "proven": True, "label": "survives"}
    rep = A.check(_file(tmp_path, claim), lab)
    fields = {m["field"] for m in rep["details"]}
    assert not rep["pass"] and "proven/label" in fields and "luck" in fields
