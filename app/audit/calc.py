"""The second calculator: contracts.md's copy-trade rules, written again from the contract alone.

It prices positions built by audit.positions from the events (never the engine's); every price, size, cost, exit
and portfolio number is worked out here from cached bars. Where the contract is silent, the choice made is written
next to the code as ASSUMPTION, so a mismatch with the engine can be traced to a rule, not a guess.
"""
import datetime as dt
import statistics
from dataclasses import dataclass, field

from . import bars as B

MONEY_START = 10_000.0
PER_TRADE = 1_000.0                                         # rule 6
COST_BPS = {"stocks": 5, "stocks_under_10": 20, "crypto": 25}   # rule 5
DELAYS = [1, 3, 5, 10, 15, 30, 60]                          # rule 2
DAY_EXIT = (15, 55)                                         # rule 4: 15:55 ET
SWING_SESSIONS = 5                                          # rule 4
MIN_TRADES = 30                                             # rule 9
MIN_CASH = 1.0                                              # rule 6: $1 or less of cash = couldn't copy


@dataclass
class Fill:
    ts: int
    px: float
    qty: float
    kind: str        # entry | exit | stop | target | default


@dataclass
class Trade:
    pid: str
    portfolio: str
    delay: int
    status: str      # priced | not_triggered | no_bars | too_late
    fills: list[Fill] = field(default_factory=list)
    pnl: float = 0.0
    cost: float = 0.0
    entry_notional: float = 0.0
    assumed_exit: bool = False
    why: str | None = None
    market: str = "us_equities"
    side: str = "long"

    @property
    def entry(self) -> Fill | None:
        return next((f for f in self.fills if f.kind == "entry"), None)

    @property
    def exit(self) -> Fill | None:
        """The last exit fill, or None (a priced trade always has one; guarded for callers)."""
        return next((f for f in reversed(self.fills) if f.kind != "entry"), None)


def cost_of(market: str, px: float, qty: float) -> float:
    if market == "crypto":
        bps = COST_BPS["crypto"]
    else:
        bps = COST_BPS["stocks_under_10"] if px < 10 else COST_BPS["stocks"]   # ASSUMPTION: judged per fill price
    return abs(px * qty) * bps / 10_000


def horizon_ts(p, entry_ts: int) -> int:
    """Rule 4's default exit: 15:55 ET that session (day), after 5 sessions (swing), N hours (crypto)."""
    kind, _, arg = p.default_exit.partition(":")
    if kind == "day_close":
        return B.et_time(B.et_day(entry_ts), *DAY_EXIT)
    if kind == "sessions":
        # ASSUMPTION: counted from the entry session; the exit is 15:55 ET on the n-th session after it.
        return B.et_time(B.nth_session_after(p.ticker, B.et_day(entry_ts), int(arg or SWING_SESSIONS)), *DAY_EXIT)
    if kind == "hours":
        return entry_ts + int(arg) * 3600          # ASSUMPTION: counted from the entry fill
    if kind == "at":
        return int(arg)
    raise ValueError(f"unknown default exit {p.default_exit}")


SIZINGS = ("known", "trade", "first")
# Rule 6 says LPP "scales the host's share counts so each trade starts at $1,000, keeping his add/trim ratios".
#   known: contracts.md rule 13(e), no look-ahead (provisional `no_look_ahead` key): the first buy is $1,000 at its fill; each add buys
#          the first buy's shares x (his count for the add / his count for the first buy), a count he didn't
#          state being the upper median of the counts he had stated on this position's buys posted up to that
#          add (both equal when he has stated none), never past $10,000 held at the add's price; a trim sells
#          the share of his stated holding he trimmed.
#   trade: rule 6 as taught (the headline): all his entries together are $1,000 at the first fill
#          price, in his ratios, which reads adds he only announces later; trims as in `known`.
#   first: rule 6 read literally: the first entry is $1,000; later adds and trims are his counts times the same factor.
DEFAULT_SIZING = "trade"   # contracts.md rule 6 as taught (the headline); "known" checks `no_look_ahead`


def simulate(p, delay: int, sizing: str = DEFAULT_SIZING) -> Trade:
    """Copy one position at one delay (rules 1-6). A missing bar marks the trade no_bars, naming the bar."""
    t = Trade(p.pid, p.portfolio, delay, "priced", market=p.market, side=p.side)
    try:
        return _simulate(p, delay, t, sizing)
    except B.MissingBar as e:
        return Trade(p.pid, p.portfolio, delay, "no_bars", why=str(e), market=p.market)


def _first_entry_bar(p, t0: float, until: float | None):
    """Rule 3: the open of the first bar at or after t0, or, with a trigger, the first bar that trades it."""
    if p.trigger is None:
        k, b = B.first_bar_at_or_after(p.market, p.ticker, t0)
        return k, b[0]
    last_close = None
    for k, b in B.bars_between(p.market, p.ticker, t0, until):
        o, h, lo, c = b
        if last_close is not None and (last_close - p.trigger) * (o - p.trigger) < 0:
            return k, o                  # ASSUMPTION: price crossed the level between bars (a gap): the first
                                         # trade past it is this bar's open, as a stop order would fill
        if lo <= p.trigger <= h:
            return k, p.trigger          # ASSUMPTION: filled at the trigger level
        last_close = c
    return None


def _bars_until(p, t0, t1):
    """bars_between, except days with no cached bars are passed over (the data may end before t1)."""
    day, last = B.day_of(p.market, t0), B.day_of(p.market, max(t0, t1 - 1))
    while day <= last:
        try:
            b = B.day_bars(p.market, p.ticker, day)
        except B.MissingBar:
            b = {}
        for k in sorted(b):
            if t0 <= k < t1:
                yield k, b[k]
        day += dt.timedelta(days=1)


def _last_bar_before(p, t0, t1):
    """(time, close) of the last cached bar with t0 <= open < t1, or None."""
    last = None
    for k, b in _bars_until(p, t0, t1):
        last = (k, b[3])
    return last


def _simulate(p, delay: int, t: Trade, sizing: str) -> Trade:
    d = delay * 60
    legs = sorted(p.legs, key=lambda lg: lg.posted_ts)
    first_i = next((i for i, lg in enumerate(legs) if lg.action in ("open", "add")), None)
    if first_i is None:
        return Trade(p.pid, p.portfolio, delay, "no_bars", why="no entry leg", market=p.market)
    first = legs[first_i]
    t0 = first.posted_ts + d
    if p.trigger is not None:
        # ASSUMPTION: a trigger may fill until the default exit measured from the post time + delay.
        until = horizon_ts(p, t0)
        if until <= t0:
            t.status = "too_late"        # rule 4/6: a stated horizon already past leaves nothing to copy
            return t
        got = _first_entry_bar(p, t0, until)
        if got is None:
            t.status = "not_triggered"
            return t
        e_ts, e_px = got
    else:
        e_ts, e_px = _first_entry_bar(p, t0, None)
    hz = horizon_ts(p, e_ts)
    if p.default_exit == "day_close":
        # rule 4/8: a day trade exits at 15:55 ET of the session it was posted in; an entry that only fills on a
        # later session (or after 15:55) can't be copied as a day trade
        hz = B.et_time(B.et_day(first.posted_ts), *DAY_EXIT)
    if e_ts >= hz:
        t.status = "too_late"            # rule 6: couldn't copy (entry at or after the exit time)
        return t
    try:
        hz_bar, hz_b = B.first_bar_at_or_after(p.market, p.ticker, hz)
        end_fill = (hz_bar, hz_b[0])     # rule 4: the default exit, at that bar's open
    except B.MissingBar:
        # ASSUMPTION: the cached bars end before the default exit: the position leaves at the close of the
        # last bar before it, and posts at or after hz are too late (no later bar to fill them)
        last = _last_bar_before(p, e_ts, hz)
        if last is None:
            raise
        hz_bar, end_fill = hz, last

    held, avg, scale = 0.0, 0.0, None
    start_qty = 0.0
    fills: list[Fill] = []

    def buy(ts, px, q):
        nonlocal held, avg
        avg = (avg * held + px * q) / (held + q)
        held += q
        fills.append(Fill(ts, px, q, "entry"))

    def sell(ts, px, q, kind):
        nonlocal held
        q = min(q, held)
        if q <= 1e-9:
            return
        held -= q
        fills.append(Fill(ts, px, q, kind))

    q0 = PER_TRADE / e_px
    entry_legs = [lg for lg in legs if lg.action in ("open", "add")]
    whole = p.course == "lpp" and sizing == "trade"
    so_far = p.course == "lpp" and sizing == "known"
    his = 0.0                            # trade/known sizing: his own stated holding, in his share counts
    if so_far:
        his = first.qty or 0.0           # q0 stays $1,000 at the first fill: nothing later is known yet
    elif whole:
        stated = [lg.qty for lg in entry_legs if lg.qty]
        known = statistics.median_high(stated) if stated else 1.0
        scale = PER_TRADE / (e_px * sum(lg.qty or known for lg in entry_legs))
        q0 = (first.qty or known) * scale
        his = first.qty or 0.0
    elif first.qty and p.course == "lpp":
        scale = q0 / first.qty           # rule 6: his share counts scaled so the trade starts at $1,000
    buy(e_ts, e_px, q0)
    start_qty = q0

    # the course's own later posts (adds, trims, closes), each at post time + delay (rule 2)
    events = []
    for lg in legs[first_i + 1:]:
        if lg.posted_ts + d >= hz:       # rule 4 order: posted at or after the default exit comes too late
            continue
        k, b = B.first_bar_at_or_after(p.market, p.ticker, lg.posted_ts + d)
        if k < hz_bar:                   # rule 4 order: anything at or after the default exit comes too late
            events.append((k, b[0], lg))

    stop = p.stop
    targets = list(p.targets or [])
    fracs = list(p.target_fracs or [])
    hit = 0
    long = p.side == "long"

    def do_leg(k, px, lg):
        nonlocal his, hit, stop
        if lg.action in ("open", "add"):

            if so_far:
                said = [x.qty for x in entry_legs if x.qty and x.posted_ts <= lg.posted_ts]
                typical = statistics.median_high(said) if said else None
                mine, base = lg.qty or typical, first.qty or typical
                q = q0 * mine / base if (mine and base) else q0
                q = min(q, max(0.0, MONEY_START / px - held))   # rule 13(e): never past $10,000 held
                if q <= 1e-12:
                    his += lg.qty or 0.0
                    return
                his += lg.qty or 0.0
            elif whole:
                q = (lg.qty or known) * scale
                his += lg.qty or 0.0
            else:
                q = lg.qty * scale if (lg.qty and scale) else PER_TRADE / px   # ASSUMPTION: $1,000 when no scale
            buy(k, px, q)
        elif lg.action == "close":
            sell(k, px, held, "exit")
        elif lg.action == "trim" and getattr(lg, "tp_index", None):
            # rule 12(c): their post reports take-profit n: nothing when the copier's own TP n order already
            # filled; else it sells, at post time + delay, the shares of every TP up to n that the copier's
            # own orders have not sold (ASSUMPTION: an earlier TP that never filled is sold with it)
            n = lg.tp_index
            if n <= hit:
                return
            q = held if (n >= len(targets) or not fracs) else sum(fracs[hit:n]) * start_qty
            sell(k, px, q, "exit")
            hit = n
            if p.be_after_target and hit >= p.be_after_target:
                stop = avg
        elif lg.action == "trim":
            if whole or so_far:
                f = min(1.0, lg.qty / his) if (lg.qty and his > 0) else 0.5
                his = his * (1 - f)
                q = f * held
            elif lg.frac:
                q = lg.frac * held
            elif lg.qty and scale:
                q = lg.qty * scale
            else:
                q = held / 2             # ASSUMPTION: half the position when no size is given
            sell(k, px, q, "exit")

    if stop is None and not targets:
        for k, px, lg in events:
            do_leg(k, px, lg)
    else:
        ev = {}
        for k, px, lg in events:
            ev.setdefault(k, []).append((px, lg))
        walk = B.bars_between if end_fill[0] == hz_bar else (lambda m, s_, a, b_: _bars_until(p, a, b_))
        for k, b in walk(p.market, p.ticker, e_ts, hz_bar):
            for px, lg in ev.get(k, []):
                do_leg(k, px, lg)
            if held <= 1e-12:
                break
            o, h, lo, _ = b
            stop_hit = stop is not None and (lo <= stop if long else h >= stop)
            tg_hit = [i for i in range(hit, len(targets)) if (h >= targets[i] if long else lo <= targets[i])]
            if stop_hit:                 # rule 4: stop and target in one bar = stop
                px = min(o, stop) if long else max(o, stop)   # ASSUMPTION: at the level, or the open if past it
                sell(k, px, held, "stop")
                break
            for i in tg_hit:
                lvl = targets[i]
                px = max(o, lvl) if long else min(o, lvl)
                last = i == len(targets) - 1
                q = held if (last or not fracs) else fracs[i] * start_qty
                sell(k, px, q, "target")
                hit = i + 1
                if p.be_after_target and hit >= p.be_after_target:
                    stop = avg            # their break-even move: stop to the average entry
                if held <= 1e-12:
                    break
            if held > 1e-12 and tg_hit and stop is not None and (lo <= stop if long else h >= stop):
                # ASSUMPTION: a stop moved by this bar's targets can still fill in this bar, at its level: the
                # bar's open came before the targets that moved it, so it can't be the fill
                sell(k, stop, held, "stop")
            if held <= 1e-12:
                break

    if held > 1e-12:
        sell(end_fill[0], end_fill[1], held, "default")   # rule 4: the default exit
        t.assumed_exit = True

    sign = 1 if long else -1
    gross, cost, basis_avg, basis_q = 0.0, 0.0, 0.0, 0.0
    for f in fills:
        cost += cost_of(p.market, f.px, f.qty)
        if f.kind == "entry":
            basis_avg = (basis_avg * basis_q + f.px * f.qty) / (basis_q + f.qty)
            basis_q += f.qty
        else:
            gross += sign * (f.px - basis_avg) * f.qty
            basis_q -= f.qty
    t.fills = fills
    t.cost = cost
    t.pnl = gross - cost
    t.entry_notional = sum(f.px * f.qty for f in fills if f.kind == "entry")
    return t


# ---- just holding (rule 7) and the portfolio headline (rules 6, 9) -------------------------------------------

HOLD_CLOSES = ("official", "minute")
# Rule 7 says "held to its end" without naming the price. official: the session's closing price from the cached
# daily file (data/bars/daily, the exchange close); minute: the close of the last 1-minute bar. Both are reported.
DEFAULT_HOLD_CLOSE = "official"


def _first_open(market: str, symbol: str, day: dt.date, last: dt.date) -> float:
    """The open of the first trading minute on or after `day` (bounded: MissingBar past `last`)."""
    while day <= last:
        b = B.day_bars(market, symbol, day)
        if b:
            return b[min(b)][0]
        day += dt.timedelta(days=1)
    raise B.MissingBar(f"{symbol}: no trading minute from {day} to {last}")


def hold(market: str, symbol: str, window: dict, close: str = DEFAULT_HOLD_CLOSE) -> dict:
    """Rule 7: $10,000 bought at the open of the window's first trading minute, sold at the window's last close.
    `sealed_ret_pct`: the same from the first trading minute on or after `sealed_from` (rule 10's block)."""
    start, end = dt.date.fromisoformat(window["start"]), dt.date.fromisoformat(window["end"])
    px0 = _first_open(market, symbol, start, end)
    official = B.daily_close(symbol, start, end)
    minute = None
    day = end
    while day >= start:
        try:
            last = B.day_bars(market, symbol, day)
        except B.MissingBar:
            break                       # no minute bars for the window's last day (crypto after 2026-09-30)
        if last:
            minute = last[max(last)][3]
            break
        day -= dt.timedelta(days=1)
    px1 = minute if (close == "minute" and minute is not None) else official
    sealed = window.get("sealed_from")
    s0 = _first_open(market, symbol, dt.date.fromisoformat(sealed), end) if sealed else None
    return {"px0": px0, "px1": px1, "official_close": official, "minute_close": minute, "used": close,
            "end": round(MONEY_START * px1 / px0, 2), "ret_pct": round((px1 / px0 - 1) * 100, 2),
            "sealed_px0": s0, "sealed_ret_pct": round((px1 / s0 - 1) * 100, 2) if s0 else None}


def word(trades: int, ret: float, hold_ret: float) -> str:
    if trades < MIN_TRADES:
        return "Not enough trades"
    diff = round(ret - hold_ret, 6)
    return "Yes" if diff >= 2 else "No" if diff <= -2 else "Barely"


def copy_with_cash(trades: list[Trade]) -> tuple[list[tuple[Trade, float]], int, int, float]:
    """Rule 6's cash cap, per buy (contracts.md, 2026-10-20): walk every fill of every trade by time, sells before
    buys at one moment, then by trade id. A buy spends its own money as it fills (nothing reserved for buys still
    to come); with less cash than it needs it is sized down to the cash, and with $1 or less it is skipped (a
    first buy skipped = couldn't copy, and that trade's later buys are skipped with it). A sell sells the same
    share of the copied position as the trade's own sell does of its position; it returns the money in what it
    sold plus its gain. ASSUMPTION: a trade's costs (rule 5, on the copied fills) leave cash at its last sell.
    Returns [(trade, copied P&L)], buys sized down or skipped, trades not copied, peak money in positions."""
    steps = sorted(((f.ts, 0 if f.kind != "entry" else 1, t.pid, k, n) for n, t in enumerate(trades)
                    for k, f in enumerate(t.fills)), key=lambda x: (x[0], x[1], x[2], x[3]))
    last_sell = {n: max(k for k, f in enumerate(t.fills) if f.kind != "entry") for n, t in enumerate(trades)}
    copied: dict[int, bool] = {}                 # n -> True copied, False couldn't copy
    own_q = [0.0] * len(trades)                  # the trade's own shares held (its fills)
    q = [0.0] * len(trades)                      # the copied shares held
    paid = [0.0] * len(trades)                   # money in the copied shares (average-cost basis)
    gain = [0.0] * len(trades)
    fees = [0.0] * len(trades)
    cash, shrunk, dropped, peak = MONEY_START, 0, 0, 0.0
    for ts, kind, _, k, n in steps:
        t = trades[n]
        f = t.fills[k]
        if kind == 1:                            # a buy
            own_q[n] += f.qty
            if copied.get(n) is False:
                continue
            want = f.qty
            if want * f.px > cash + 1e-9:
                if cash <= MIN_CASH:
                    if n not in copied:
                        copied[n] = False
                        dropped += 1
                    else:
                        shrunk += 1
                    continue
                want = cash / f.px
                shrunk += 1
            copied[n] = True
            cash -= want * f.px
            q[n] += want
            paid[n] += want * f.px
            fees[n] += cost_of(t.market, f.px, want)
            peak = max(peak, sum(paid))
            continue
        frac = f.qty / own_q[n] if own_q[n] > 1e-12 else 1.0
        own_q[n] -= f.qty
        if copied.get(n):
            sold = q[n] * min(frac, 1.0)
            if sold > 1e-12:
                avg = paid[n] / q[n]
                g = (f.px - avg) * sold * (1 if t.side == "long" else -1)
                gain[n] += g
                fees[n] += cost_of(t.market, f.px, sold)
                cash += avg * sold + g
                q[n] -= sold
                paid[n] -= avg * sold
            if k == last_sell[n]:
                cash -= fees[n]
    kept = [(t, gain[n] - fees[n]) for n, t in enumerate(trades) if copied.get(n)]
    return kept, shrunk, dropped, peak


def portfolio(trades: list[Trade], hold_row: dict, sealed_from: str | None = None) -> dict:
    """End value, return, trade count, word and the rest of a by_delay row, for one portfolio at one delay.

    Rule 6's cash cap, per buy: see copy_with_cash. ASSUMPTION: $1 of cash or less is couldn't-copy (contracts.md
    names no minimum; the $1 floor keeps sub-dollar trades out of rule 9's count; bankroll-rules.md's $100 is
    CAP-9's). sized_down counts buys sized down or skipped; couldnt_copy counts trades whose first buy was
    skipped, plus too_late. won_pct: copied trades with P&L > 0. worst_drop_pct: the deepest fall of closed-trade
    money from its high, booked on each exit's day (the contract's `unknown` says the drop counts closed trades
    only). sealed: the copied trades that entered on or after `sealed_from` (rule 10), P&L as % of $10,000."""
    priced = [t for t in trades if t.status == "priced" and t.entry and t.exit]
    kept, sized_down, couldnt, _ = copy_with_cash(priced)
    copied = len(kept)
    end = round(MONEY_START + sum(v for _, v in kept), 2)
    ret = round((end / MONEY_START - 1) * 100, 2)
    by_day: dict[dt.date, float] = {}
    for t, v in kept:
        day = B.day_of(t.market, t.exit.ts)
        by_day[day] = by_day.get(day, 0.0) + v
    money, high, worst = MONEY_START, MONEY_START, 0.0
    for day in sorted(by_day):
        money += by_day[day]
        high = max(high, money)
        worst = min(worst, (money - high) / high * 100)
    row = {"end": end, "ret_pct": ret, "hold_end": hold_row["end"], "hold_ret_pct": hold_row["ret_pct"],
           "trades": copied, "not_triggered": sum(t.status == "not_triggered" for t in trades),
           "couldnt_copy": couldnt + sum(t.status == "too_late" for t in trades), "sized_down": sized_down,
           "won_pct": round(100 * sum(v > 0 for _, v in kept) / len(kept)) if kept else 0,
           "worst_drop_pct": round(worst, 1),
           "word": word(copied, ret, hold_row["ret_pct"])}
    if sealed_from:
        sk = [(t, v) for t, v in kept if B.day_of(t.market, t.entry.ts).isoformat() >= sealed_from]
        row["sealed"] = {"ret_pct": round(100 * sum(v for _, v in sk) / MONEY_START, 2),
                         "hold_ret_pct": hold_row.get("sealed_ret_pct"), "trades": len(sk)}
    return row
