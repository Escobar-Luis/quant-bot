"""Synthetic bars and positions with expected values worked out by hand from contracts.md (never from the engine).

Each case: a position, the bars it sees, and the answer the contract gives, with the arithmetic written out.
`engine_divergences()` runs backtest.engine on the same positions and lists where it differs from that answer:

  cd app && uv run python -m audit.tests.synthetic
"""
import datetime as dt
from dataclasses import dataclass, field

from audit import bars as AB
from audit.positions import Leg, Position

DAY = dt.date(2024, 8, 15)            # a Thursday
NEXT = dt.date(2024, 8, 16)
BPS5, BPS20 = 5 / 1e4, 20 / 1e4


def at(hh: int, mm: int, day: dt.date = DAY, ss: int = 0) -> int:
    return AB.et_time(day, hh, mm) + ss


def flat(day: dt.date, px: float = 100.0) -> dict[int, list]:
    """A quiet session: every minute opens and closes at px, range +-0.5 (so no stop or target near it trades)."""
    t0 = at(9, 30, day)
    return {t0 + 60 * i: [px, px + 0.5, px - 0.5, px, 1000] for i in range(390)}


@dataclass
class Case:
    name: str
    position: Position
    delay: int
    bars: dict                        # {date: {ts: [o, h, l, c, v]}}
    expect: dict                      # status, entry (ts, px), exit (ts, px), pnl
    why: str                          # the hand arithmetic, from the contract
    sizing: str = "trade"
    tags: list = field(default_factory=list)


def pos(legs, side="long", course="zt", **kw) -> Position:
    base = dict(pid="syn", course=course, market="us_equities", ticker="SYN", side=side, portfolio="day",
                legs=legs, default_exit="day_close")
    base.update(kw)
    return Position(**base)


def book(*days, **over) -> dict:
    """Flat sessions with some bars overridden: over = {"HHMM": [o, h, l, c]} on DAY."""
    b = {d: flat(d) for d in days}
    for k, v in over.items():
        b[DAY][at(int(k[1:3]), int(k[3:5]))] = [*v, 1000]
    return b


def cases() -> list[Case]:
    out = []

    # 1. long at market, closed by his post. Entry: post 09:40:12 + 5 min = 09:45:12 -> the 09:46 bar's open.
    b = book(DAY, m0946=[100, 100.5, 99.5, 100], m1046=[102, 102.5, 101.5, 102])
    p = pos([Leg("o", at(9, 40, ss=12), "open"), Leg("c", at(10, 40, ss=30), "close")])
    out.append(Case("long, market entry, his close", p, 5, b,
                    {"status": "priced", "entry": (at(9, 46), 100.0), "exit": (at(10, 46), 102.0),
                     "pnl": 10 * (102 - 100) - (1000 + 1020) * BPS5},
                    "$1,000 / 100 = 10 sh; 10 x 2 = 20 gross; costs 5 bps x (1000 + 1020) = 1.01; 18.99"))

    # 2. the same as a short
    p = pos([Leg("o", at(9, 40, ss=12), "open"), Leg("c", at(10, 40, ss=30), "close")], side="short")
    out.append(Case("short, market entry, his close", p, 5, b,
                    {"status": "priced", "entry": (at(9, 46), 100.0), "exit": (at(10, 46), 102.0),
                     "pnl": 10 * (100 - 102) - (1000 + 1020) * BPS5},
                    "short 10 sh at 100, covered at 102: -20 - 1.01 = -21.01"))

    # 3. stop and target trade in one bar -> the stop (rule 4)
    b = book(DAY, m0940=[100, 101.5, 98.8, 100])
    p = pos([Leg("o", at(9, 30), "open")], stop=99.0, targets=[101.0])
    out.append(Case("stop and target in one bar: stop wins", p, 1, b,
                    {"status": "priced", "entry": (at(9, 31), 100.0), "exit": (at(9, 40), 99.0),
                     "pnl": 10 * (99 - 100) - (1000 + 990) * BPS5},
                    "09:40 bar trades 101 and 99: stop at 99; -10 - 0.995"))

    # 4. trigger with a gap past the level: price was 100, the 09:40 bar opens 101.6 (over the 101 trigger)
    b = book(DAY, m0940=[101.6, 102, 101.4, 101.8], m1555=[100, 100.5, 99.5, 100])
    for i in range(41, 60):
        b[DAY][at(9, i)] = [101.8, 102.2, 101.4, 101.8, 1000]
    p = pos([Leg("o", at(9, 30), "open")], trigger=101.0)
    q = 1000 / 101.6
    out.append(Case("trigger gapped past: fill at the gap bar's open", p, 1, b,
                    {"status": "priced", "entry": (at(9, 40), 101.6), "exit": (at(15, 55), 100.0),
                     "pnl": q * (100 - 101.6) - (1000 + q * 100) * BPS5},
                    "first trade past 101 is the 09:40 open 101.6; 15:55 default exit at 100"))

    # 5. trigger never trades -> not_triggered (rule 3)
    p = pos([Leg("o", at(9, 30), "open")], trigger=105.0)
    out.append(Case("trigger never trades", p, 1, book(DAY), {"status": "not_triggered"},
                    "105 is never reached that session"))

    # 6. two targets with fractions: half at each
    b = book(DAY, m0940=[100, 101.2, 99.8, 101], m0950=[101, 102.3, 100.8, 102])
    p = pos([Leg("o", at(9, 30), "open")], stop=98.0, targets=[101.0, 102.0], target_fracs=[0.5, 0.5])
    out.append(Case("two targets, fractions 50/50", p, 1, b,
                    {"status": "priced", "entry": (at(9, 31), 100.0), "exit": (at(9, 50), 102.0),
                     "pnl": 5 * 1 + 5 * 2 - (1000 + 505 + 510) * BPS5},
                    "5 sh at 101, 5 sh at 102: 15 - 1.0075"))

    # 7. two targets, no fractions: rule 4, the first target that trades is the exit
    p = pos([Leg("o", at(9, 30), "open")], stop=98.0, targets=[101.0, 102.0])
    out.append(Case("two targets, no fractions", p, 1, b,
                    {"status": "priced", "entry": (at(9, 31), 100.0), "exit": (at(9, 40), 101.0),
                     "pnl": 10 * 1 - (1000 + 1010) * BPS5},
                    "rule 4: exit = the target that trades first; 10 sh at 101: 10 - 1.005"))

    # 8. his adds and trims, sized and unsized (rule 6: all buys together $1,000 at the first fill, his ratios)
    b = book(DAY, m0931=[100, 100.5, 99.5, 100], m0941=[104, 104.5, 103.5, 104], m0951=[106, 106.5, 105.5, 106],
             m1001=[108, 108.5, 107.5, 108], m1011=[110, 110.5, 109.5, 110])
    p = pos([Leg("o", at(9, 30), "open", qty=100), Leg("a", at(9, 40), "add", qty=100),
             Leg("t1", at(9, 50), "trim", qty=50), Leg("t2", at(10, 0), "trim"), Leg("c", at(10, 10), "close")],
            course="lpp")
    out.append(Case("adds, sized trim, unsized trim, close (LPP)", p, 1, b,
                    {"status": "priced", "entry": (at(9, 31), 100.0), "exit": (at(10, 11), 110.0),
                     "pnl": 2.5 * 4 + 3.75 * 6 + 3.75 * 8 - (500 + 520 + 265 + 405 + 412.5) * BPS5},
                    "scale 1000/(100 x 200) = 0.05: 5 sh at 100 + 5 at 104 (avg 102); trim 50/200 = 2.5 sh at 106; "
                    "unsized = half of 7.5 at 108; rest 3.75 at 110: 62.5 - 1.05125"))

    # 8b. the same posts under rule 13(e), no look-ahead: the first buy is $1,000 whatever he adds later
    p = pos([Leg("o", at(9, 30), "open", qty=100), Leg("a", at(9, 40), "add", qty=100),
             Leg("t1", at(9, 50), "trim", qty=50), Leg("t2", at(10, 0), "trim"), Leg("c", at(10, 10), "close")],
            course="lpp")
    out.append(Case("adds, sized trim, unsized trim, close (LPP, no look-ahead)", p, 1, b,
                    {"status": "priced", "entry": (at(9, 31), 100.0), "exit": (at(10, 11), 110.0),
                     "pnl": 5 * 4 + 7.5 * 6 + 7.5 * 8 - (1000 + 1040 + 530 + 810 + 825) * BPS5},
                    "first buy $1,000 / 100 = 10 sh; add 10 x 100/100 = 10 sh at 104 (avg 102); trim 50/200 = 5 sh "
                    "at 106; unsized = half of 15 at 108; rest 7.5 at 110: 125 - 2.1025", sizing="known"))

    # 8c. no count on the first buy: an add with a count meets the median of what he had said (its own count)
    b2 = book(DAY, m0931=[100, 100.5, 99.5, 100], m0941=[104, 104.5, 103.5, 104], m1001=[108, 108.5, 107.5, 108])
    p = pos([Leg("o", at(9, 30), "open"), Leg("a", at(9, 40), "add", qty=300), Leg("c", at(10, 0), "close")],
            course="lpp")
    out.append(Case("first buy with no count, later add (LPP, no look-ahead)", p, 1, b2,
                    {"status": "priced", "entry": (at(9, 31), 100.0), "exit": (at(10, 1), 108.0),
                     "pnl": 10 * 8 + 10 * 4 - (1000 + 1040 + 2160) * BPS5},
                    "first buy 10 sh at 100; at the add his only count is 300, so both counts read 300: 10 sh at "
                    "104; close 20 at 108: 80 + 40 - 2.10", sizing="known"))

    # 9. break-even stop after TP2, filled in the same bar that hit TP2
    b = book(DAY, m0940=[100, 101.2, 99.8, 101], m0945=[100.5, 102.2, 99.9, 101])
    p = pos([Leg("o", at(9, 30), "open")], stop=98.0, targets=[101.0, 102.0, 103.0],
            target_fracs=[0.25, 0.25, 0.5], be_after_target=2)
    out.append(Case("break-even stop after TP2, same bar", p, 1, b,
                    {"status": "priced", "entry": (at(9, 31), 100.0), "exit": (at(9, 45), 100.0),
                     "pnl": 2.5 * 1 + 2.5 * 2 - (1000 + 252.5 + 255 + 500) * BPS5},
                    "TP1 2.5 sh at 101, TP2 2.5 at 102, stop -> 100, same bar trades 99.9: 5 sh at 100"))

    # 10. a day trade posted 15:58: + 5 min has no bar until tomorrow -> couldn't copy as a day trade
    p = pos([Leg("o", at(15, 58), "open")])
    out.append(Case("day trade, entry rolls to the next session", p, 5, book(DAY, NEXT), {"status": "too_late"},
                    "rules 4/8: a day trade exits 15:55 the session it was posted; no time left to copy it"))

    # 11. an `at:` horizon that passed before the entry
    p = pos([Leg("o", at(9, 40), "open")], default_exit=f"at:{at(9, 35)}", portfolio="swing")
    out.append(Case("at: exit before entry", p, 1, book(DAY), {"status": "too_late"},
                    "the stated horizon (09:35) passed before the copier could enter (09:41): couldn't copy"))

    # 12. no close: the 15:55 default exit
    b = book(DAY, m1555=[103, 103.5, 102.5, 103])
    p = pos([Leg("o", at(9, 30), "open")])
    out.append(Case("15:55 default exit", p, 1, b,
                    {"status": "priced", "entry": (at(9, 31), 100.0), "exit": (at(15, 55), 103.0),
                     "pnl": 10 * 3 - (1000 + 1030) * BPS5},
                    "rule 4: day trade with no close leaves at the 15:55 bar's open: 30 - 1.015"))

    # 13. under $10: 20 bps per side
    b = {DAY: flat(DAY, 8.0)}
    b[DAY][at(10, 0)] = [9.0, 9.1, 8.9, 9.0, 1000]
    p = pos([Leg("o", at(9, 30), "open"), Leg("c", at(9, 59), "close")])
    out.append(Case("costs under $10", p, 1, b,
                    {"status": "priced", "entry": (at(9, 31), 8.0), "exit": (at(10, 0), 9.0),
                     "pnl": 125 * 1 - (1000 + 1125) * BPS20},
                    "125 sh at 8 -> 9: 125 - 20 bps x 2125 = 120.75"))

    # 14. crossing the tier: buy at 9.50 (20 bps), sell at 10.50 (5 bps)
    b = {DAY: flat(DAY, 9.5)}
    b[DAY][at(10, 0)] = [10.5, 10.6, 10.4, 10.5, 1000]
    q = 1000 / 9.5
    out.append(Case("costs across the $10 line", pos([Leg("o", at(9, 30), "open"), Leg("c", at(9, 59), "close")]),
                    1, b, {"status": "priced", "entry": (at(9, 31), 9.5), "exit": (at(10, 0), 10.5),
                           "pnl": q * 1 - 1000 * BPS20 - q * 10.5 * BPS5},
                    "tier judged on each fill's price: 20 bps on the buy at 9.50, 5 bps on the sell at 10.50"))
    return out


# ---- the portfolio's cash rule (rule 6) ------------------------------------------------------------------------

def cash_cases():
    """The portfolio's cash rule (rule 6, per buy as it fills), worked out by hand. Each trade is its fills,
    (ts, price, shares, kind); costs 5 bps per side at these prices.

    1. A $9,950 trade still open when a $1,000 trade enters: $50 of cash left, so the second buy is sized down to
       $50 (no minimum in contracts.md): 0.5 sh, 0.5 x 2 - (50 + 51) x 5 bps = 0.9495; the first loses its costs,
       19,900 x 5 bps = 9.95. End 10,000 - 9.95 + 0.9495 = 9,991.00.
    2. A later add never shrinks an earlier buy: a buys $1,000 at 09:31, b $1,000 at 09:45, a's 95-share add at
       10:00 finds $8,000 and is sized down to 80 sh. a: 90 x 1 - (9,000 + 9,090) x 5 bps = 80.955; b: 10 -
       (1,000 + 1,010) x 5 bps = 8.995. End 10,089.95 (the old whole-trade reservation would have shrunk a's
       first buy)."""
    one = ([[(at(9, 31), 100.0, 99.5, "entry"), (at(15, 0), 100.0, 99.5, "exit")],
            [(at(10, 0), 100.0, 10.0, "entry"), (at(11, 0), 102.0, 10.0, "exit")]],
           {"trades": 2, "sized_down": 1, "couldnt_copy": 0, "end": 9_991.0})
    two = ([[(at(9, 31), 100.0, 10.0, "entry"), (at(10, 0), 100.0, 95.0, "entry"), (at(15, 0), 101.0, 105.0, "exit")],
            [(at(9, 45), 100.0, 10.0, "entry"), (at(15, 0), 101.0, 10.0, "exit")]],
           {"trades": 2, "sized_down": 1, "couldnt_copy": 0, "end": 10_089.95})
    return [("cash under $100", *one), ("later add never shrinks an earlier buy", *two)]


# ---- engine side -----------------------------------------------------------------------------------------------

def to_engine(p: Position, sizing: str = "trade"):
    from backtest.engine import Leg as ELeg, Position as EPos
    return EPos(pid=p.pid, course=p.course, market=p.market, ticker=p.ticker, side=p.side, portfolio=p.portfolio,
                legs=[ELeg(lg.event_id, int(lg.posted_ts), lg.action, lg.qty, lg.frac) for lg in p.legs],
                default_exit=p.default_exit, stop=p.stop, targets=list(p.targets),
                target_fracs=list(p.target_fracs), trigger=p.trigger, be_after_target=p.be_after_target,
                scale=p.course == "lpp", as_taught=sizing == "trade")


def outcome_engine(r) -> dict:
    if r.status != "priced":
        return {"status": r.status}
    return {"status": "priced", "entry": (r.entry.ts, r.entry.px), "exit": (r.last_exit.ts, r.last_exit.px),
            "pnl": r.pnl}


def outcome_audit(t) -> dict:
    if t.status != "priced":
        return {"status": t.status}
    return {"status": "priced", "entry": (t.entry.ts, t.entry.px), "exit": (t.exit.ts, t.exit.px), "pnl": t.pnl}


def same(a: dict, b: dict) -> bool:
    if a["status"] != b["status"]:
        return False
    if a["status"] != "priced":
        return True
    return (a["entry"][0] == b["entry"][0] and abs(a["entry"][1] - b["entry"][1]) < 1e-9
            and a["exit"][0] == b["exit"][0] and abs(a["exit"][1] - b["exit"][1]) < 1e-9
            and abs(a["pnl"] - b["pnl"]) < 1e-6)


def patch_bars(book_: dict, setattr_=setattr):
    """Point both calculators at one in-memory book. Returns the undo list."""
    from backtest import bars as EB
    undo = [(AB, "day_bars", AB.day_bars), (EB, "day_bars", EB.day_bars)]
    setattr_(AB, "day_bars", lambda m, s, d: {k: tuple(v[:4]) for k, v in book_.get(d, {}).items()})
    setattr_(EB, "day_bars", lambda m, s, d: book_.get(d, {}))
    return undo


def engine_cash(trades):
    from backtest import engine
    from backtest.engine import Fill, Result
    rs = []
    for i, fills in enumerate(trades):
        p = to_engine(pos([Leg(f"x{i}", fills[0][0], "open")]))
        p.pid = f"cash-{i}"
        rs.append(Result(p, 1, "priced", fills=[Fill(*f) for f in fills]))
    kept, sized_down, skipped, _ = engine.fit_to_cash(rs)
    return {"trades": len(kept), "sized_down": sized_down, "couldnt_copy": skipped,
            "end": round(10_000 + sum(v for _, v in kept), 2)}


def audit_cash(trades):
    from audit import calc
    ts = []
    for i, fills in enumerate(trades):
        t = calc.Trade(f"cash-{i}", "day", 1, "priced")
        t.fills = [calc.Fill(*f) for f in fills]
        ts.append(t)
    row = calc.portfolio(ts, {"end": 10_000.0, "ret_pct": 0.0})
    return {k: row[k] for k in ("trades", "sized_down", "couldnt_copy", "end")}


def engine_divergences() -> list[dict]:
    """Every case where backtest.engine's answer is not the contract's (hand-derived) answer."""
    from backtest import bars as EB
    from backtest import engine
    out = []
    for c in cases():
        undo = patch_bars(c.bars)
        try:
            got = outcome_engine(engine.simulate(to_engine(c.position, c.sizing), c.delay))
        finally:
            for mod, name, fn in undo:
                setattr(mod, name, fn)
        if not same(got, c.expect):
            out.append({"case": c.name, "contract": c.expect, "engine": got, "why": c.why})
    for name, trades, want in cash_cases():
        got = engine_cash(trades)
        if got != want:
            out.append({"case": name, "contract": want, "engine": got, "why": cash_cases.__doc__.strip()})
    EB.day_bars  # keep the import used
    return out


if __name__ == "__main__":
    for d in engine_divergences():
        print(f"- {d['case']}\n    contract: {d['contract']}\n    engine:   {d['engine']}\n    why: {d['why']}")
