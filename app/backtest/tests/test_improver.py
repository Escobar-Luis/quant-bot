"""The improver's code checks: the model proposes, code decides."""
from backtest import improver

NAMES = {"short-breakdown": "Short the breakdown"}


def test_menu_change_passes():
    ok = {"applies_to": "short-breakdown", "change_type": "skip_after", "value": "10:00", "why": "late entries lost"}
    assert improver.check(ok, NAMES) is None


def test_off_menu_or_bad_values_fail_with_the_check_name():
    base = {"applies_to": "short-breakdown", "change_type": "skip_after", "value": "10:00", "why": "x"}
    assert improver.check({**base, "applies_to": "nope"}, NAMES) == "applies_to_unknown_strategy"
    assert improver.check({**base, "change_type": "double_size"}, NAMES) == "change_not_on_menu"
    assert improver.check({**base, "value": "08:00"}, NAMES) == "time_not_in_session"
    assert improver.check({**base, "change_type": "skip_side", "value": "both"}, NAMES) == "side_not_long_or_short"


def test_kept_needs_a_sealed_test_that_agrees():
    s = {"dev": {"before_pct": -1.34, "after_pct": 0.5}, "sealed": {"before_pct": -0.09, "after_pct": -0.09}}
    assert improver.decide(s)["kept"] is False and s["kept_reason"] == "no gain on new (sealed) months"
    s["sealed"]["after_pct"] = 0.2
    assert improver.decide(s)["kept"] is True
    s["dev"]["after_pct"] = -2.0
    assert improver.decide(s)["kept"] is False
