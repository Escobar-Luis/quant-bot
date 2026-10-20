"""Every committed results file keeps the contracts.md shape the web app and PRISM lane read."""
import json

import pytest

from backtest import engine
from backtest.common import DELAYS_MIN, RESULTS

FILES = sorted(p for p in RESULTS.glob("*/*.json"))
WORDS = {"Yes", "Barely", "No", "Not enough trades"}


def assert_judged(d, pid, k, row):
    """Rule 9 (CAP-7): word, outcome and vs on the row and its sealed block, against the file's benchmark."""
    cw = d["compare_with"]
    if cw["kind"] == "hold":
        assert cw["name"] == engine.bench_name(d["hold"]["symbol"])
        bench, sealed_bench = row["hold_ret_pct"], row["sealed"]["hold_ret_pct"]
    else:   # a proof-set file: only the headline is compared, and only with v1 on the same sessions
        assert cw == {"kind": "same_sessions", "name": d["same_sessions"]["version"]}
        assert not {"strategies", "ranges", "combos", "best_stop"} & set(d)
        base = d["same_sessions"]["by_delay"][k] if pid == d["same_sessions"]["portfolio"] else None
        bench, sealed_bench = (base["ret_pct"], base["sealed"]["ret_pct"]) if base else (None, None)
    want = engine.judge(json.loads(json.dumps(row)), bench, sealed_bench, cw["name"])
    for f in ("word", "outcome", "vs"):
        assert row[f] == want[f] and row["sealed"][f] == want["sealed"][f], (pid, k, f)
    assert row["word"] in WORDS | {None}
    if row["ret_pct"] < 0:
        assert row["word"] not in {"Yes", "Barely"} and row["outcome"] == "Lost money"


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
    if d["course"] == "lpp":
        assert d["sizing"] == "His share counts, scaled to $1,000 per trade"   # contracts.md rule 6
    need = {"end", "ret_pct", "hold_end", "hold_ret_pct", "trades", "not_triggered", "couldnt_copy", "won_pct",
            "worst_drop_pct", "word", "outcome", "vs", "sealed"}
    words = {"Yes", "Barely", "No", "Not enough trades"}
    if d["course"] == "lpp":   # rule 13, provisional: shown beside the as-taught headline
        nla = d["no_look_ahead"]
        assert nla["provisional"] is True and nla["rules"]
        assert [p["id"] for p in nla["portfolios"]] == ["all", "day", "swing"]
        for p in nla["portfolios"]:
            assert set(p["by_delay"]) == {str(x) for x in DELAYS_MIN}
            assert all(need <= set(r) and r["word"] in words | {None} for r in p["by_delay"].values())
    for p in d["portfolios"]:
        if not p["testable"]:
            assert "count" in p and p["why"]
            continue
        assert set(p["by_delay"]) == {str(x) for x in DELAYS_MIN}
        assert len(p["series"]["dates"]) == len(p["series"]["hold"])
        for k, row in p["by_delay"].items():
            assert need <= set(row) and {"ret_pct", "hold_ret_pct"} <= set(row["sealed"])
            assert_judged(d, p["id"], k, row)
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


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_optional_v2_keys(path):
    d = json.loads(path.read_text())
    n = len(d["portfolios"][0]["series"]["dates"])
    for s in d.get("strategies", []):
        assert s["id"] and s["name"] and set(s["entails"]) == {"buy", "sell", "stop", "size", "time"}
        assert set(s["by_delay"]) == {str(x) for x in DELAYS_MIN}
        assert all(len(v) == n for v in s["series"]["by_delay"].values())
        assert all(len(q["text"].rstrip("…").split()) <= 12 and q["cite"]["source_id"] for q in s["quotes"])
        assert all(len(u.split()) <= 15 for u in s["untestable"])
        for row in s["by_delay"].values():
            assert row["word"] == engine.word(row["trades"], row["ret_pct"], row["hold_ret_pct"])
    for r in d.get("ranges", {}).values():
        assert set(r["by_delay"]) == {str(x) for x in DELAYS_MIN}
        for row in r["by_delay"].values():
            assert row["word"] == engine.word(row["trades"], row["ret_pct"], row["hold_ret_pct"])
            assert row["outcome"] == engine.outcome(row["trades"], row["ret_pct"])
            assert row["vs"] == engine.versus(row["trades"], row["ret_pct"], row["hold_ret_pct"],
                                              d["compare_with"]["name"])
    if "best_stop" in d:
        dates = d["portfolios"][0]["series"]["dates"]
        for k, b in d["best_stop"]["by_delay"].items():
            curve = d["portfolios"][0]["series"]["by_delay"][k]
            assert b["date"] in dates and b["end"] == max(curve)


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_combos_are_picked_on_dev_and_reported_on_sealed(path):
    d = json.loads(path.read_text())
    for c in d.get("combos", []):
        assert c["picked_on"] == "dev" and c["window"]["start"] == d["window"]["sealed_from"]
        assert len(c["ids"]) == 2 and all(i.startswith(d["course"] + ":") for i in c["ids"])
        assert c["word"] == engine.word(c["sealed"]["trades"], c["sealed"]["ret_pct"], c["sealed"]["hold_ret_pct"])


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_suggestion_is_the_improver_picked_on_dev(path):
    s = json.loads(path.read_text()).get("suggestion")
    if s:
        assert s["agent_id"] == "daytrader-improver-v1" and s["picked_on"] == "dev"
        assert s["kept"] == (s["dev"]["after_pct"] > s["dev"]["before_pct"]
                             and s["sealed"]["after_pct"] > s["sealed"]["before_pct"]) and s["kept_reason"]
        if s.get("trajectory_id"):
            assert s["prism_url"] == f"https://prism.blockconvey.com/trajectories/{s['trajectory_id']}"


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_no_private_video_ids_in_results(path):
    """Luis's security rule: unlisted video IDs and YouTube links never reach tracked files."""
    import re
    from backtest.common import private_video_ids
    text = path.read_text()
    assert not re.search(r"yt:[A-Za-z0-9_-]{11}", text)
    assert "youtube.com" not in text and "youtu.be" not in text
    assert not [v for v in private_video_ids() if v in text]


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_optional_by_year_key(path):
    """contracts.md section by_year: every testable portfolio and delay; `all` is the headline."""
    d = json.loads(path.read_text())
    if "by_year" not in d:
        assert "same_sessions" in d   # rule 9: only a proof-set file has no by_year
        return
    assert "same_sessions" not in d
    by = d["by_year"]
    ids = [p["id"] for p in by["periods"]]
    assert ids[-1] == "all" and ids[:-1] == sorted(ids[:-1]) and all(len(y) == 4 for y in ids[:-1])
    assert by["periods"][0]["from"] >= d["window"]["start"] and by["periods"][-1]["to"] <= d["window"]["end"]
    assert by["hold"]["basis"] in {"total_return", "price"}
    heads = {p["id"]: p for p in d["portfolios"] if p["testable"]}
    assert set(by["portfolios"]) == set(heads)
    for pid, pf in by["portfolios"].items():
        assert set(pf["by_delay"]) == {str(x) for x in DELAYS_MIN}
        for k, rows in pf["by_delay"].items():
            assert list(rows) == ids
            head = heads[pid]["by_delay"][k]
            assert (rows["all"]["end"], rows["all"]["ret_pct"], rows["all"]["trades"]) == \
                (head["end"], head["ret_pct"], head["trades"])
            assert sum(rows[y]["trades"] for y in ids[:-1]) == rows["all"]["trades"]
            assert rows[ids[-2]]["end"] == pytest.approx(rows["all"]["end"], abs=0.02)
            for y in ids:
                r = rows[y]
                assert r["word"] == engine.word(r["trades"], r["ret_pct"], r["hold_ret_pct"])
                assert r["outcome"] == engine.outcome(r["trades"], r["ret_pct"])
            assert rows["all"]["outcome"] == head["outcome"]
            for a, b in zip(ids[:-2], ids[1:-1]):
                assert rows[b]["start"] == pytest.approx(rows[a]["end"], abs=0.02)
                assert rows[b]["hold_start"] == pytest.approx(rows[a]["hold_end"], abs=0.02)
