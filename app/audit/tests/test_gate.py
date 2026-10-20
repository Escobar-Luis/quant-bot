"""The gate opens only on a passed audit, a matching hand-check sign-off and untouched results/."""
import json

from audit import gate, run
from audit.paths import RESULTS


def record(tmp_path, **kw):
    files = {f"{p.parent.name}/{p.stem}": run.sha256(p) for p in RESULTS.glob("*/*.json")}
    files |= {p.stem: run.sha256(p) for p in RESULTS.glob("*.json") if not p.stem.startswith("_")}   # strategy-lab
    rec = {"pass": True, "results_git_sha": run.results_git_sha(RESULTS), "results_sha256": files,
           "signoff": None, **kw}
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(rec))
    return path


def test_open_only_with_signed_sheet(tmp_path):
    sheet = tmp_path / "handcheck.md"
    sheet.write_text("ten trades\n")
    proofs = record(tmp_path)
    assert any("sign-off" in w for w in gate.check(proofs, sheet))
    gate.sign("Luis", proofs, sheet)
    assert gate.check(proofs, sheet) == []
    sheet.write_text("ten trades, edited\n")
    assert gate.check(proofs, sheet) == ["handcheck.md changed after it was signed"]


def test_closed_on_failed_audit_or_changed_results(tmp_path):
    sheet = tmp_path / "handcheck.md"
    sheet.write_text("x")
    proofs = record(tmp_path, **{"pass": False})
    gate.sign("Luis", proofs, sheet)
    assert any("did not pass" in w for w in gate.check(proofs, sheet))
    rec = json.loads(proofs.read_text())
    rec["pass"] = True
    rec["results_sha256"]["lpp/v1"] = "0" * 64
    proofs.write_text(json.dumps(rec))
    assert gate.check(proofs, sheet) == ["sha256 differs from the audited file: results/lpp/v1.json"]
