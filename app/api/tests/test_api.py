"""Story backend-1: the API repeats the results files exactly. Offline: real results/ plus small fixture folders."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import snapshot as snap
from api.main import REPO, create_app

RESULTS = REPO / "results"
REAL = sorted(p for p in RESULTS.glob("*/v*.json"))


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(REPO))


def headline_file(course: str) -> dict:
    return json.loads(snap.load(REPO).headline(course).raw)


def results_doc(course: str, version: str, *, proof_set: bool = False, delays=(1, 5)) -> dict:
    """The smallest file problem() accepts."""
    row = {"end": 10_100.0, "ret_pct": 1.0, "hold_end": 10_000.0, "hold_ret_pct": 0.0, "trades": 40, "word": "Barely"}
    doc = {"schema": "results/1", "course": course, "course_name": course.upper(), "version": version,
           "sample": False, "delays_min": list(delays), "default_delay_min": delays[-1], "money_start": 10000,
           "window": {"start": "2025-01-02", "end": "2025-03-31", "sealed_from": "2025-03-01"},
           "hold": {"symbol": "SPY", "label": "Just holding", "what": "SPY"}, "headline_portfolio": "all",
           "portfolios": [{"id": "all", "label": "All", "testable": True,
                           "by_delay": {str(d): {**row, "end": row["end"] + d} for d in delays}}],
           "unknown": ["fixture"]}
    if proof_set:
        doc["same_sessions"] = {"proof_set": True}
    return doc


def write(root: Path, doc: dict, name: str | None = None) -> Path:
    p = root / "results" / doc["course"] / (name or f"{doc['version']}.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc))
    return p


# ---- acceptance 1: every number equals the file ----------------------------------------------------------------

@pytest.mark.parametrize("course", sorted({p.parent.name for p in REAL}))
def test_verdict_numbers_equal_the_headline_file_at_every_delay(client, course):
    doc = headline_file(course)
    port = next(p for p in doc["portfolios"] if p["id"] == doc["headline_portfolio"])
    for d in doc["delays_min"]:
        r = client.get(f"/v1/courses/{course}/verdict", params={"delay": d})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["headline"] == port["by_delay"][str(d)]
        assert body["delay_min"] == d and body["version"] == doc["version"]
        assert body["window"] == doc["window"] and body["hold"] == doc["hold"] and body["unknown"] == doc["unknown"]


def test_verdict_defaults_to_the_files_default_delay(client):
    doc = headline_file("lpp")
    body = client.get("/v1/courses/lpp/verdict").json()
    assert body["delay_min"] == doc["default_delay_min"]


def test_courses_lists_every_course_with_its_default_headline(client):
    body = client.get("/v1/courses").json()
    assert [c["course"] for c in body["courses"]][:3] == ["lpp", "ziptrader", "cryptowizard"]
    for c in body["courses"]:
        doc = headline_file(c["course"])
        port = next(p for p in doc["portfolios"] if p["id"] == doc["headline_portfolio"])
        assert c["headline"] == port["by_delay"][str(doc["default_delay_min"])]


def test_results_endpoint_serves_the_file_bytes(client):
    for p in REAL:
        r = client.get(f"/v1/courses/{p.parent.name}/results/{p.stem}")
        assert r.status_code == 200 and r.content == p.read_bytes()
        assert r.headers["content-type"].startswith("application/json")


# ---- acceptance 2: headline rule and errors --------------------------------------------------------------------

def test_lpp_headline_is_v1_because_v2_is_the_proof_set(client):
    assert client.get("/v1/courses/lpp/verdict").json()["version"] == "v1"


@pytest.mark.parametrize("files,want", [
    ([("v1", False), ("v2", True)], "v1"),      # proof set never headlines
    ([("v1", False), ("v2", False)], "v2"),     # otherwise the newest
    ([("v1", True), ("v2", True)], "v2"),       # only proof sets: the newest
    ([("v2", False), ("v10", False)], "v10"),   # numeric, not string, order
])
def test_headline_rule(tmp_path, files, want):
    for v, proof in files:
        write(tmp_path, results_doc("lpp", v, proof_set=proof))
    assert snap.load(tmp_path).headline("lpp").version == want


def test_unknown_course_is_404_in_the_envelope(client):
    r = client.get("/v1/courses/nope/verdict")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_course"


def test_delay_outside_the_file_is_422_not_precomputed(client):
    r = client.get("/v1/courses/lpp/verdict", params={"delay": 7})
    assert r.status_code == 422 and r.json()["error"]["code"] == "delay_not_precomputed"


def test_non_integer_delay_is_422_bad_request(client):
    r = client.get("/v1/courses/lpp/verdict", params={"delay": "five"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "bad_request"


def test_unknown_version_is_404(client):
    r = client.get("/v1/courses/lpp/results/v99")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_version"


def test_unknown_route_uses_the_envelope(client):
    r = client.get("/v1/nothing-here")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


# ---- acceptance 3: snapshot id ---------------------------------------------------------------------------------

def test_snapshot_id_is_stable_and_changes_with_any_file(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    write(a, results_doc("lpp", "v1"))
    shutil.copytree(a, b)
    assert snap.load(a).snapshot_id == snap.load(b).snapshot_id
    doc = results_doc("lpp", "v1")
    doc["unknown"].append("one more line")
    write(b, doc)
    assert snap.load(a).snapshot_id != snap.load(b).snapshot_id


def test_every_response_carries_the_snapshot_id(client):
    sid = client.get("/health").json()["snapshot_id"]
    assert len(sid) == 12
    for path in ("/v1/courses", "/v1/courses/lpp/verdict", "/v1/courses/lpp/results/v1", "/v1/courses/nope/verdict"):
        assert client.get(path).headers["X-Snapshot-Id"] == sid
    assert client.get("/v1/courses").json()["snapshot_id"] == sid


# ---- files that break the contract are skipped, never half-served ----------------------------------------------

def test_broken_files_are_skipped_and_reported(tmp_path):
    write(tmp_path, results_doc("lpp", "v1"))
    write(tmp_path, {**results_doc("lpp", "v2"), "schema": "results/0"})
    missing_delay = results_doc("ziptrader", "v1")
    del missing_delay["portfolios"][0]["by_delay"]["1"]
    write(tmp_path, missing_delay)
    write(tmp_path, results_doc("cryptowizard", "v1"), name="latest.json")
    (tmp_path / "results" / "_sample.json").write_text(json.dumps(results_doc("lpp", "v9")))
    body = TestClient(create_app(tmp_path)).get("/health").json()
    assert body["courses"] == ["lpp"]
    assert sorted(sk["path"] for sk in body["skipped"]) == [
        "results/cryptowizard/latest.json", "results/lpp/v2.json", "results/ziptrader/v1.json"]


def test_empty_snapshot_still_starts(tmp_path):
    c = TestClient(create_app(tmp_path))
    assert c.get("/health").json()["courses"] == []
    assert c.get("/v1/courses").json()["courses"] == []
