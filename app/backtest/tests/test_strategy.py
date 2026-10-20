"""daytrader-strategy-v1's code side: the model proposes rules, code measures and keeps or drops them."""
from types import SimpleNamespace as NS

from backtest import strategy as S


def _row(pid, side="short", group="big tech", t30="09:30", adds="none", exit_="assumed", pnl=-10.0, **kw):
    return {"pid": pid, "day": kw.get("day", "2025-01-02"), "ticker": kw.get("ticker", "TSLA"), "side": side,
            "group": group, "time15": t30, "time30": t30, "setup": kw.get("setup", "other-shorts"), "adds": adds,
            "exit": exit_, "hold": kw.get("hold", "3 h or more"), "size": "not stated", "portfolio": "day",
            "day_trades": "1", "pnl": pnl}


ROWS = [_row(f"s{i}", pnl=-10.0 if i % 4 else 20.0) for i in range(20)] + \
       [_row(f"l{i}", side="long", group="index funds", adds="to_loser", exit_="stated", pnl=5.0) for i in range(10)]


def test_a_supported_rule_is_kept_with_numbers_from_the_trades():
    kept, dropped = S.verify([{"text": "He shorts big tech", "when": {"group": ["big tech"]},
                               "does": {"side": ["short"]}, "quote_id": "Q1"}], ROWS,
                             [{"id": "Q1", "text": "I short tech", "cite": {"label": "x"}}])
    assert not dropped and kept[0]["situation_trades"] == 20 and kept[0]["follows_pct"] == 100.0
    assert kept[0]["trades"] == 20 and kept[0]["pnl_usd"] == round(15 * -10.0 + 5 * 20.0, 2)
    assert kept[0]["quote"]["text"] == "I short tech"


def test_rules_the_data_does_not_support_are_dropped_with_the_reason():
    props = [{"text": "He goes long", "when": {}, "does": {"side": ["long"]}},            # 10 trades
             {"text": "Index longs", "when": {"group": ["index funds"]}, "does": {"side": ["long"]}},
             {"text": "Bad feature", "when": {"mood": ["happy"]}, "does": {"side": ["long"]}},
             {"text": "Bad value", "when": {}, "does": {"side": ["sideways"]}},
             {"text": "No action", "when": {"side": ["short"]}, "does": {}}]
    kept, dropped = S.verify(props, ROWS, [])
    assert not kept
    assert [d["why"] for d in dropped] == ["fewer than 15 trades", "fewer than 15 trades", "unknown_feature:mood",
                                           "unknown_value:side=sideways", "does_empty"]
    kept, dropped = S.verify([{"text": "Mostly longs", "when": {}, "does": {"side": ["long"]}}],
                             ROWS + [_row(f"x{i}", side="long", group="other") for i in range(10)], [])
    assert not kept and dropped[0]["why"].startswith("followed 50.0% of the time")


def test_losing_patterns_skip_one_that_mostly_repeats_an_earlier_pick():
    pats = S.losing_patterns(ROWS)
    assert pats and pats[0]["pnl_usd"] < 0
    ids = [frozenset(x["pid"] for x in ROWS if S.matches(x, p["when"])) for p in pats]
    for i, a in enumerate(ids):
        for b in ids[:i]:
            assert len(a & b) <= 0.5 * min(len(a), len(b))


def _res(side, pxs):
    fills = [NS(kind="entry", px=px, qty=1.0) for px in pxs] + [NS(kind="exit", px=100.0, qty=len(pxs))]
    return NS(fills=fills, position=NS(side=side))


def test_adding_to_a_loser_depends_on_the_side():
    assert S.add_kind(_res("short", [100.0])) == "none"
    assert S.add_kind(_res("short", [100.0, 102.0])) == "to_loser"     # a short adds higher: losing
    assert S.add_kind(_res("short", [100.0, 98.0])) == "to_winner"
    assert S.add_kind(_res("long", [100.0, 98.0])) == "to_loser"       # a long adds lower: averaging down
    assert S.add_kind(_res("long", [100.0, 101.0, 99.0])) == "to_loser"


def test_buckets_hold_values_below_their_top():
    assert S._bucket(14.9, S.HOLD_BUCKETS) == "under 15 min" and S._bucket(15, S.HOLD_BUCKETS) == "15-60 min"
    assert S._bucket(1, S.DAY_BUCKETS) == "1" and S._bucket(3, S.DAY_BUCKETS) == "2-3"
    assert S._bucket(6, S.DAY_BUCKETS) == "6 or more"


def test_a_does_that_repeats_its_when_or_allows_every_value_is_dropped():
    props = [{"text": "Shorts are shorts", "when": {"side": ["short"]}, "does": {"side": ["short"]}},
             {"text": "Long or short", "when": {}, "does": {"side": ["long", "short"]}}]
    kept, dropped = S.verify(props, ROWS, [])
    assert not kept and [d["why"] for d in dropped] == ["does_repeats_when:side", "does_covers_every_value:side"]


def test_hedge_words_become_the_measured_number():
    assert S.plain("He mostly shorts, in about four of every five trades.", 80.1) == "He shorts (80% of the time)."
    assert S.plain("When he trades Tesla, he is almost always short.", 78.3) == \
        "When he trades Tesla, he is short (78% of the time)."
    assert S.plain("He opens most trades early.", 70.5) == "He opens trades early (71% of the time)."


def test_a_hidden_quote_and_a_malformed_reply_are_handled():
    q = [{"id": "Q1", "text": "I short tech", "cite": {"label": "x"}}]
    S.QUOTES_NOT_SUPPORTING["test-sha"] = {0: "does not say it"}
    try:
        kept, _ = S.verify([{"text": "He shorts big tech", "when": {"group": ["big tech"]},
                             "does": {"side": ["short"]}, "quote_id": "Q1"}], ROWS, q, "test-sha")
    finally:
        del S.QUOTES_NOT_SUPPORTING["test-sha"]
    assert kept[0]["quote"] is None and kept[0]["quote_hidden"] == "does not say it"
    assert S.verify("not a list", ROWS, q) == ([], [])
    assert S.verify(["junk"], ROWS, q)[1][0]["why"] == "proposal_not_a_map"
    assert S.profile(None, "v1", [], {"reply": {"rules": "nope"}, "quotes": q}) is None
