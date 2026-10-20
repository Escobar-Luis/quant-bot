"""Strategy lab (spec-audit story 21): the rule mechanics, on synthetic bars; and the audit's independent fill
agrees with the lab's on random sessions."""
import datetime as dt
import random

from audit import lab as audit_lab
from backtest import lab
from backtest.bars import et_at

DAY = dt.date(2026, 3, 2)


def bars(rows):
    """rows: [(hh, mm, o, h, l, c)] -> {unix_s: [o, h, l, c, v]}"""
    return {et_at(DAY, hh, mm): [o, h, l, c, 1000] for hh, mm, o, h, l, c in rows}


def test_time_exit_at_1555():
    b = bars([(9, 45, 10, 10.1, 9.9, 10), (12, 0, 9.5, 9.6, 9.4, 9.5), (15, 55, 9.0, 9.1, 8.9, 9.0)])
    t = lab.short_trade(b, DAY, "09:45", 5, "15:55")
    assert (t["entry"], t["exit"], t["kind"]) == (10, 9.0, "time")


def test_stop_fills_at_level_or_gap_open():
    b = bars([(9, 45, 10, 10.2, 9.9, 10), (10, 0, 10.3, 10.6, 10.2, 10.5), (15, 55, 9, 9, 9, 9)])
    assert lab.short_trade(b, DAY, "09:45", 5, "15:55")["exit"] == 10.5          # 10 * 1.05
    b = bars([(9, 45, 10, 10.2, 9.9, 10), (10, 0, 11, 11.2, 10.9, 11), (15, 55, 9, 9, 9, 9)])
    assert lab.short_trade(b, DAY, "09:45", 5, "15:55")["exit"] == 11             # gapped through: the open
    assert lab.short_trade(b, DAY, "09:45", None, "15:55")["exit"] == 9           # no stop


def test_no_bar_after_entry_and_last_close():
    assert lab.short_trade(bars([(9, 30, 10, 10, 10, 10)]), DAY, "09:45", 5, "15:55") is None
    t = lab.short_trade(bars([(9, 45, 10, 10, 10, 10), (14, 0, 9, 9, 9, 9.2)]), DAY, "09:45", 5, "15:55")
    assert (t["exit"], t["kind"]) == (9.2, "last")


def test_gap_is_inclusive_at_exactly_5pct():
    split = {"2025-10-08": [12, 12.7, 11.9, 12.3, 1], "2025-10-09": [12.915, 13.7, 12.6, 13.6, 1]}
    assert lab.gap_sessions(split, 5) == ["2025-10-09"]
    assert audit_lab._gap_days(split, 5, "2025-09-15", "2026-10-16") == ["2025-10-09"]


def test_session_sizing_and_costs():
    trades = [{"ticker": f"T{i}", "day": "2025-09-15", "entry_ts": i, "entry": 20.0, "exit": 19.0, "adv": 1e9,
               "htb": False} for i in range(20)]
    r = lab.book(trades, ["2025-09-15"])
    assert r["sized_down"] == 20 and all(abs(t["notional"] - 500) < 1e-9 for t in r["trades"])
    one = r["trades"][0]["pnl"]   # 25 shares x $1, less 5 bps on $500 and on $475
    assert abs(one - (25 - 500 * 5e-4 - 475 * 5e-4)) < 1e-9


def test_cost_models():
    assert lab.bps("base", 9.99, 1e9) == 20 and lab.bps("x2", 12, 1e9) == 10
    assert lab.bps("small_cap", 4, 1e9) == 50 and lab.bps("small_cap", 8, 1e7) == 40 and lab.bps("small_cap", 20, 1e9) == 5


def test_word_rule():
    assert lab.word(29, 50, 10)[0] == "Not enough trades"
    assert lab.word(30, -1, -10)[0] == "No"
    assert lab.word(30, 12, 10)[0] == "Yes" and lab.word(30, 11, 10)[0] == "Barely" and lab.word(30, 8, 10)[0] == "No"


def test_audit_fill_agrees_with_lab():
    rng = random.Random(21)
    for _ in range(300):
        px, rows = 10.0, []
        for m in range(390):
            o = px * (1 + rng.gauss(0, 0.01))
            h, lo = o * (1 + abs(rng.gauss(0, 0.01))), o * (1 - abs(rng.gauss(0, 0.01)))
            px = rng.uniform(lo, h)
            rows.append((9 + (30 + m) // 60, (30 + m) % 60, o, h, lo, px))
        b = bars(rows)
        stop = rng.choice([None, 5, 2])
        mine = lab.short_trade(b, DAY, "09:45", stop, "15:55")
        theirs = audit_lab._fill_short(sorted(b.items()), DAY.isoformat(), "09:45", stop, "15:55")
        assert (mine["entry_ts"], mine["entry"], mine["exit"]) == theirs
