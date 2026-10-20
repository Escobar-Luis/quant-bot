"""Unit tests for the deterministic parts of the ZipTrader collectors (no network, synthetic text only).

Run: uv run --with pytest --with openai --with python-dotenv --with pillow --with numpy pytest app/collect/ziptrader -q
"""
import numpy as np
import pytest
from PIL import Image

import checks
from checks import check, clip_quote, panel_of, quote_in, status
from common import canon, numbers_in, parse_json
from extract_calls import to_event
from nutshell_spec import assemble, walk
from transcribe import gutters

SRC = {"source_id": "dc:1/2", "message_id": "2", "posted_at": "2026-10-16T12:56:48.488Z", "channel": "morning-briefing"}
BRIEFING = """=== column 1 ===
# ON THE RADAR TODAY

## ACME CORP
[ticker: ACME]
Acme fell 4.4% to $32.50 on Thursday as the Dow closed at 52,177.69 after a long day.
NEWS: Guidance cut
WATCH: Whether $32.50 holds or Thursday's low gets retested

## OTHER CO
[ticker: OTHR]
Other Co rallied 3% after earnings and looks set to keep running.
WATCH: Whether the gap holds past the open
"""


@pytest.fixture(autouse=True)
def fake_symbols(monkeypatch):
    monkeypatch.setattr(checks, "symbols", lambda: frozenset({"ACME", "OTHR"}))


# numbers

def test_canon_matches_source_spelling():
    assert canon(32.5) in numbers_in("$32.50")
    assert canon(52177.69) in numbers_in("52,177.69")
    assert canon(-15) == "15"
    assert canon(True) is None


def test_numbers_in_keeps_lists_apart():
    assert numbers_in("80,90") == {"80", "90"}
    assert numbers_in("1,234,567") == {"1234567"}


def test_parse_json_fence_and_prose():
    assert parse_json('```JSON\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here it is: {"a": 1}') == {"a": 1}


# checks

def test_quote_exact_case_and_word_boundary():
    assert quote_in("Whether $32.50 holds", BRIEFING)
    assert not quote_in("whether $32.50 HOLDS", BRIEFING)
    assert not quote_in("Whether $32.5", BRIEFING)  # cut mid-number
    assert quote_in("Acme fell 4.4%", BRIEFING) and quote_in("whether the gap holds", BRIEFING.replace("Whether the", "whether the"))
    assert quote_in("Whether the gap holds", BRIEFING.replace("Whether the", "whether the"))  # first letter only
    assert not quote_in("whether the Gap holds", BRIEFING)


def test_clip_quote_trims_only_exact_quotes():
    long_exact = "Acme fell 4.4% to $32.50 on Thursday as the Dow closed at 52,177.69 after a long day."
    assert len(clip_quote(long_exact, BRIEFING).split()) == 12
    made_up = "Acme will surely rally hard today because every single trader loves it a lot"
    assert clip_quote(made_up, BRIEFING) == made_up


def test_numbers_and_quote_checked_against_the_tickers_panel():
    span = panel_of(BRIEFING, "OTHR")
    ev = {"type": "call", "ticker": "OTHR", "ticker_said": "OTHR", "level": 32.5, "quote": "looks set to keep running"}
    c = check(ev, span)
    assert c["quote_ok"] and not c["numbers_ok"] and c["numbers_missing"] == ["32.5"]
    assert status(c) == "needs_review"


def test_ticker_must_be_real_and_named_in_span():
    span = panel_of(BRIEFING, "ACME")
    assert check({"type": "call", "ticker": "ACME", "quote": "Guidance cut"}, span)["ticker_ok"] is True
    assert check({"type": "call", "ticker": "OTHR", "quote": "Guidance cut"}, span)["ticker_ok"] is False
    assert check({"type": "call", "ticker": "ZZZZ", "quote": "Guidance cut"}, span)["ticker_ok"] is False
    assert check({"type": "rule", "ticker": None, "quote": "Guidance cut"}, span)["ticker_ok"] is None


def test_status_soft_none_passes_soft_false_fails():
    base = {"quote_ok": True, "numbers_ok": True, "ticker_ok": None, "price_ok": None, "xcheck_ok": None}
    assert status(base) == "ok"
    assert status({**base, "xcheck_ok": False}) == "needs_review"
    assert status({**base, "quote_ok": False}) == "needs_review"


# call vs setup

def ev_for(item):
    return to_event(SRC, 1, item, BRIEFING, None, "test-model")


def test_side_alone_makes_a_call():
    e = ev_for({"ticker": "OTHR", "side": "long", "levels": [], "quote": "looks set to keep running"})
    assert e["type"] == "call" and e["side"] == "long" and e["status"] == "ok"
    assert e["event_id"] == "zt:2:001" and e["fail"] == []


def test_failed_checks_listed_for_the_loader():
    e = ev_for({"ticker": "OTHR", "levels": [{"value": 32.5, "kind": "support"}], "quote": "looks set to keep running"})
    assert e["status"] == "needs_review" and e["fail"] == ["numbers_ok"]


def test_named_level_alone_makes_a_call():
    e = ev_for({"ticker": "ACME", "side": None, "levels": [{"value": None, "kind": "support", "ref": "prev_low"}],
                "quote": "Thursday's low gets retested"})
    assert e["type"] == "call" and e["level_ref"] == "prev_low" and e["level"] is None


def test_unknown_ref_and_no_side_make_a_setup():
    e = ev_for({"ticker": "OTHR", "side": "watch", "levels": [{"value": None, "kind": "support", "ref": "moon"}],
                "quote": "Whether the gap holds past the open"})
    assert e["type"] == "setup" and e["level_kind"] is None and e["levels"] == []


def test_several_levels_fill_entry_stop_targets():
    e = ev_for({"ticker": "ACME", "levels": [{"value": 32.5, "kind": "support"}, {"value": 4.4, "kind": "stop"},
                                             {"value": True, "kind": "target"}], "quote": "Whether $32.50 holds"})
    assert e["level"] == 32.5 and e["stop"] == 4.4 and e["targets"] == []
    assert e["checks"]["numbers_ok"]


# StrategySpec assembly

CARD = """## SWING [MAIN]

A. Buy Weakness In Quality Names
B. Set Stop Loss 15%-20% Down
C. Exit Fast
"""
SRC_CARD = {"source_id": "dc:9/9", "posted_at": "2026-01-08T03:02:16.127Z"}
STOP15 = {"op": "<=", "left": {"fn": "pct_from_entry"}, "right": {"fn": "const", "args": [-15]}}
STOP7 = {"op": "<=", "left": {"fn": "pct_from_entry"}, "right": {"fn": "const", "args": [-7]}}
ENTRY = {"op": "<", "left": {"fn": "close"}, "right": {"fn": "sma", "args": [50]}}


def rule(item, kind, quote, expr, assumptions=None, params=None):
    return {"strategy": "SWING", "item": item, "kind": kind, "paraphrase": quote, "params": params, "expr": expr,
            "assumptions": assumptions or [], "testable": True, "quote": quote}


def test_sourced_stop_beats_assumed_stop_listed_first():
    rules = [rule("C", "stop", "Exit Fast", STOP7, ["exit fast = -7% from entry"]),
             rule("B", "stop", "Set Stop Loss 15%-20% Down", STOP15, params={"low": 15, "high": 20})]
    _, specs, _ = assemble(rules, CARD, None, SRC_CARD, "m")
    ex = specs[0]["exit"]
    assert ex["stop"]["quote"] == "Set Stop Loss 15%-20% Down"
    assert [v["quote"] for v in ex["variants"]] == ["Exit Fast"]


def test_undeclared_number_makes_rule_untestable():
    rules = [rule("A", "entry", "Buy Weakness", ENTRY, ["weakness = close below its average"])]
    _, specs, events = assemble(rules, CARD, None, SRC_CARD, "m")
    assert specs[0]["entry"] == [] and events[0]["status"] == "needs_review"
    rules = [rule("A", "entry", "Buy Weakness", ENTRY, ["weakness = close below sma(50)"])]
    _, specs, events = assemble(rules, CARD, None, SRC_CARD, "m")
    assert len(specs[0]["entry"]) == 1 and events[0]["status"] == "ok"


def test_param_not_on_cited_line_is_rejected():
    rules = [rule("C", "stop", "Exit Fast", STOP7, ["-7%"], params={"pct": 7})]
    _, specs, _ = assemble(rules, CARD, None, SRC_CARD, "m")
    assert "stop" not in specs[0]["exit"] and "params not on the cited line" in specs[0]["untestable"][0]["why"]


def test_entry_without_exit_gets_window_end():
    rules = [rule("A", "entry", "Buy Weakness", ENTRY, ["weakness = close below sma(50)"])]
    _, specs, _ = assemble(rules, CARD, None, SRC_CARD, "m")
    assert specs[0]["exit"]["time"]["at"] == "window_end" and specs[0]["testable"]


@pytest.mark.parametrize("tree", [
    {"op": ">", "left": {"fn": "close"}},
    {"fn": "sma"},
    {"op": "between", "x": {"fn": "close"}},
    {"op": ">", "left": {"fn": "close"}, "rigth": {"fn": "open"}},
    {"fn": "macd", "args": [12]},
    {"fn": "time_between", "args": [9, 11]},
])
def test_walk_rejects_malformed_trees(tree):
    bad = []
    walk(tree, set(), bad)
    assert bad


def test_walk_accepts_valid_tree():
    bad, nums = [], set()
    walk({"op": "and", "args": [ENTRY, {"fn": "time_between", "args": ["09:30", "11:00"]}]}, nums, bad)
    assert not bad and nums == {"50"}


# column cropping

def test_gutters_found_in_three_column_grid():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (300, 900), dtype=np.uint8)
    img[:, 290:310] = 30
    img[:, 590:610] = 30
    cuts = gutters(Image.fromarray(img))
    assert len(cuts) == 2 and 290 <= cuts[0] <= 310 and 590 <= cuts[1] <= 610


def test_no_gutters_returns_empty():
    rng = np.random.default_rng(1)
    assert gutters(Image.fromarray(rng.integers(0, 255, (300, 900), dtype=np.uint8))) == []


def test_horizon_said_only_in_the_quote_fills_the_field():
    """Rule 12(a): the quote's horizon moves into `horizon`, with where it came from; existing ones are kept."""
    from horizon import fill
    ev = {"type": "call", "horizon": None, "quote": "keep working for more than one session"}
    assert fill(ev, "quote_backfill_2026-10-20")
    assert ev["horizon"] == "more than one session" and ev["horizon_source"] == "quote_backfill_2026-10-20"
    kept = {"type": "call", "horizon": "today", "quote": "hold for 3 days"}
    assert not fill(kept) and kept["horizon"] == "today"


@pytest.mark.parametrize("quote", ["above the 200 day moving average", "the 5 day chart looks strong",
                                   "looks set to bounce for the day", "hold for 0 days", "overnight news hit it",
                                   "next day's high is the level", "up for 3 days straight", "over 2 days of gains"])
def test_not_a_horizon(quote):
    from horizon import from_quote
    assert from_quote(quote) is None


@pytest.mark.parametrize("quote,phrase,n", [
    ("keep working for more than one session", "more than one session", None),
    ("hold for 3 days", "3 days", 3), ("swing it over the next two weeks", "two weeks", 10),
    ("could run into the next session", "into the next session", 1), ("hold it overnight", "hold it overnight", 1),
    ("holding for a few days", "a few days", None)])
def test_horizon_phrasing(quote, phrase, n):
    from horizon import from_quote
    assert from_quote(quote) == (phrase, n)


def test_horizon_past_15_sessions_is_flagged_not_cut():
    from horizon import fill
    ev = {"type": "call", "horizon": None, "quote": "hold for 20 sessions"}
    assert fill(ev) and ev["horizon"] == "20 sessions" and ev["horizon_flag"] == "over_15_sessions"
