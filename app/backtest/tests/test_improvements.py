"""daytrader-improver-v2's code checks and keep rule (contracts.md section improvements): the model proposes,
code decides."""
from backtest import improvements as I

VALUES = {"side": {"long", "short"}, "group": {"big tech", "other"}, "ticker": {"TSLA", "PLTR"},
          "time15": {"09:30"}, "time30": {"09:30"}, "setup": {"short-resistance"}}


def ok(**kw):
    return {"text": "Skip Tesla shorts", "kind": "skip", "when": {"ticker": ["TSLA"], "side": ["short"]},
            "value": None, "why": "lost money", **kw}


def test_a_menu_change_on_entry_features_passes():
    assert I.check(ok(), VALUES) is None
    assert I.check(ok(kind="max_hold", when={}, value=60), VALUES) is None
    assert I.check(ok(kind="stop_pct", when={"group": ["big tech"]}, value=2.5), VALUES) is None


def test_look_ahead_off_menu_and_bad_values_fail_with_the_check_name():
    assert I.check(ok(when={"adds": ["to_loser"]}), VALUES) == "look_ahead_or_unknown_feature:adds"
    assert I.check(ok(when={"exit": ["assumed"]}), VALUES) == "look_ahead_or_unknown_feature:exit"
    assert I.check(ok(kind="double_size"), VALUES) == "kind_not_on_menu"
    assert I.check(ok(when={"ticker": ["GME"]}), VALUES) == "unknown_value:ticker=GME"
    assert I.check(ok(when={}), VALUES) == "skip_or_only_needs_when"
    assert I.check(ok(kind="max_hold", value=600), VALUES).startswith("value_out_of_range")
    assert I.check(ok(kind="stop_pct", value=None), VALUES).startswith("value_out_of_range")
    assert I.check(ok(text=" ".join(["word"] * 21)), VALUES) == "text_missing_or_over_20_words"


def row(dev_pts, sealed_pts, dev_n=239, sealed_n=103):
    return {"dev": {"trades": dev_n, "vs_as_is_pts": dev_pts}, "sealed": {"trades": sealed_n, "vs_as_is_pts": sealed_pts}}


def test_kept_needs_dev_gain_no_sealed_loss_and_30_trades_each():
    assert I.decide(row(1.0, 0.0))["kept"] is True
    assert I.decide(row(1.0, 0.5))["kept"] is True
    r = I.decide(row(0.0, 3.0))
    assert r["kept"] is False and "(dev)" in r["kept_reason"]
    r = I.decide(row(2.0, -0.01))
    assert r["kept"] is False and "lost on the held-out" in r["kept_reason"]
    r = I.decide(row(5.0, 5.0, sealed_n=29))
    assert r["kept"] is False and "fewer than 30" in r["kept_reason"]


def test_rule_words_come_from_code():
    names = {"short-resistance": "Short into resistance"}
    v = I.normalize(ok(kind="max_hold", when={"group": "big tech"}, value=59.6))
    assert v == {"kind": "max_hold", "when": {"group": ["big tech"]}, "value": 60}
    assert I.describe(v, names) == "Leave 60 min after the first buy: big tech"
    assert I.describe(I.normalize(ok()), names) == "Skip: shorts, tsla"


class _Leg:
    def __init__(self, eid, ts, action="open"):
        self.event_id, self.posted_ts, self.action = eid, ts, action


class _Pos:
    def __init__(self, legs, side="short"):
        self.legs, self.side, self.why = legs, side, None


class _Mod:
    @staticmethod
    def strategy_of(p):
        return "short-resistance" if "resistance" in (p.why or "") else "other-shorts"


def test_setup_uses_only_reasons_stated_by_the_first_fill():
    p = _Pos([_Leg("a", 100.0), _Leg("b", 900.0, "add")])
    whys = {"b": "into resistance"}
    assert I.entry_setup(_Mod, p, whys, at=400.0) == "unknown"          # said after the first fill: not used
    assert I.entry_setup(_Mod, p, whys, at=900.0) == "short-resistance"
    assert I.entry_setup(_Mod, p, {"a": "gut call"}, at=400.0) == "other-shorts"


def test_proposals_past_six_are_logged_not_dropped():
    import pytest
    from backtest import lpp
    from backtest.common import DATA
    if not (DATA / "lpp" / "events.jsonl").exists():
        pytest.skip("needs the local data/ folder")
    pos, base = I.headline(lpp, "v1", 5)
    props = [{"text": f"Skip PLTR {i}", "kind": "skip", "when": {"ticker": ["PLTR"]}} for i in range(7)]
    ev = I.evaluate(lpp, pos, base, props, 5)
    assert len(ev["variants"]) == 6 and ev["rejected"] == [{"text": "Skip PLTR 6", "why": "over_6_proposals"}]
