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
    if d["course"] == "lpp":
        assert d["sizing"] == ("His share counts, scaled so his first buy is $1,000; "
                              "each add uses only what he had said by then")   # rule 13(e)
    need = {"end", "ret_pct", "hold_end", "hold_ret_pct", "trades", "not_triggered", "couldnt_copy", "won_pct",
            "worst_drop_pct", "word", "sealed"}
    words = {"Yes", "Barely", "No", "Not enough trades"}
    if d["course"] == "lpp":   # rule 13: the look-ahead numbers stay visible beside the headline
        taught = d["as_taught"]
        assert taught["rules"] and [p["id"] for p in taught["portfolios"]] == ["all", "day", "swing"]
        for p in taught["portfolios"]:
            assert set(p["by_delay"]) == {str(x) for x in DELAYS_MIN}
            assert all(need <= set(r) and r["word"] in words for r in p["by_delay"].values())
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
