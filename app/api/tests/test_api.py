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
    """The AD-3 rule written out again here, so the tests don't check the code against itself."""
    docs = [json.loads(p.read_text()) for p in (RESULTS / course).glob("v*.json")]
    docs.sort(key=lambda d: int(d["version"][1:]), reverse=True)
    return next((d for d in docs if not (d.get("same_sessions") or {}).get("proof_set")), docs[0])


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
    assert body["courses"] == []          # lpp withheld (its v2 was skipped); the others have no v<n> file left
    assert sorted(sk["path"] for sk in body["skipped"]) == [
        "results/cryptowizard/latest.json", "results/lpp/v1.json", "results/lpp/v2.json",
        "results/ziptrader/v1.json"]


def test_empty_snapshot_starts_but_is_not_ok(tmp_path):
    (tmp_path / "results").mkdir()
    c = TestClient(create_app(tmp_path))
    assert c.get("/health").json() == {"ok": False, "snapshot_id": snap.snapshot_id({}), "courses": [], "skipped": []}
    assert c.get("/v1/courses").json()["courses"] == []


def test_missing_results_folder_refuses_to_start(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_app(tmp_path / "typo")


def test_health_answers_head(client):
    assert client.head("/health").status_code == 200


@pytest.mark.parametrize("breakage", ["portfolios_not_objects", "same_sessions_list", "default_delay_bool",
                                      "row_missing_keys", "private_video_id", "leading_zero_version"])
def test_malformed_files_are_skipped_not_served(tmp_path, breakage):
    doc, name = results_doc("lpp", "v1"), None
    if breakage == "portfolios_not_objects":
        doc["portfolios"] = ["x", None]
    elif breakage == "same_sessions_list":
        doc["same_sessions"] = ["x"]
    elif breakage == "default_delay_bool":
        doc["delays_min"], doc["default_delay_min"] = [1, 5], True
    elif breakage == "row_missing_keys":
        doc["portfolios"][0]["by_delay"]["5"] = {"end": 1}
    elif breakage == "private_video_id":
        doc["unknown"].append("see yt:A4929OT4Jls")
    elif breakage == "leading_zero_version":
        name = "v01.json"
    write(tmp_path, doc, name=name)
    c = TestClient(create_app(tmp_path))
    body = c.get("/health").json()
    assert body["courses"] == [] and len(body["skipped"]) == 1 and body["ok"] is False
    assert c.get("/v1/courses/lpp/verdict").status_code == 404


def test_a_skipped_newer_version_withholds_the_whole_course(tmp_path):
    """Else the API would headline v1 while the web app's latest() picks v2."""
    write(tmp_path, results_doc("lpp", "v1"))
    broken = results_doc("lpp", "v2")
    del broken["portfolios"][0]["by_delay"]["1"]
    write(tmp_path, broken)
    write(tmp_path, results_doc("ziptrader", "v1"))
    body = TestClient(create_app(tmp_path)).get("/health").json()
    assert body["courses"] == ["ziptrader"]
    assert {sk["path"] for sk in body["skipped"]} == {"results/lpp/v1.json", "results/lpp/v2.json"}


def test_private_url_pattern_matches_the_backtest_guard():
    from backtest.common import PRIVATE_URL
    assert snap.PRIVATE_URL.pattern == PRIVATE_URL.pattern


def test_snapshot_id_known_answer():
    """AD-1's formula pinned: sha256 over sorted "path:sha256" lines, first 12 hex."""
    import hashlib
    digests = {"results/b/v1.json": "22", "results/a/v1.json": "11"}
    want = hashlib.sha256(b"results/a/v1.json:11\nresults/b/v1.json:22").hexdigest()[:12]
    assert snap.snapshot_id(digests) == want


def test_snapshot_id_changes_when_a_skipped_file_changes(tmp_path):
    write(tmp_path, results_doc("lpp", "v1"))
    bad = tmp_path / "results" / "lpp" / "notes.json"
    bad.write_text("{}")
    before = snap.load(tmp_path).snapshot_id
    bad.write_text('{"x": 1}')
    assert snap.load(tmp_path).snapshot_id != before


def test_server_errors_use_the_envelope_and_carry_the_snapshot_id(tmp_path, monkeypatch):
    write(tmp_path, results_doc("lpp", "v1"))
    c = TestClient(create_app(tmp_path), raise_server_exceptions=False)

    def boom(_self):
        raise RuntimeError("boom")
    monkeypatch.setattr(snap.Snapshot, "courses", boom)
    r = c.get("/v1/courses")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert r.headers["X-Snapshot-Id"] == c.get("/v1/courses/lpp/verdict").headers["X-Snapshot-Id"]
