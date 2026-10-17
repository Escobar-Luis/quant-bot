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
