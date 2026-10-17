"""Copy-trade engine: price one position at one delay, then roll positions into a $10k portfolio.

The rules are contracts.md "Copy-trade rules" (code decides, never the model):
- every action the course announces (entry, add, trim, close) is copied at post time + delay, at the open of the
  first 1-minute bar whose open time is at or after that moment;
- an entry with a trigger level fills when price trades the level after post time + delay, else `not_triggered`;
- a stop or target, when stated, exits as soon as a bar trades it (both in one bar = stop);
- whatever is still held after the last announced exit leaves at the position's default exit (`assumed`);
- costs per side on every fill: 5 bps stocks, 20 bps under $10, 25 bps crypto.
"""
import bisect
import datetime as dt
from dataclasses import dataclass, field

from . import bars
from .common import COSTS_BPS, MONEY_START, PER_TRADE_USD


@dataclass
class Leg:
    event_id: str
    posted_ts: int
    action: str                     # open | add | trim | close
    qty: float | None = None        # the course's own size (shares, coins); None = not stated
    frac: float | None = None       # exits only: share of the held position to sell; None = work it out from qty


@dataclass
class Position:
    pid: str
    course: str
    market: str                     # us_equities | crypto
    ticker: str
    side: str                       # long | short
    portfolio: str                  # day | swing | crypto
    legs: list[Leg]
    default_exit: str               # day_close | sessions:5 | hours:24 | at:<unix>
    stop: float | None = None
    targets: list[float] = field(default_factory=list)
    target_fracs: list[float] = field(default_factory=list)   # share of the start size closed at each target
    trigger: float | None = None    # entry level to wait for; None = enter at market
    be_after_target: int | None = None   # move the stop to the average entry once this many targets have filled
    scale: bool = False             # True: his share counts scaled so the first entry is $1,000 (keeps his ratios)
    quote: str | None = None
    cite: dict | None = None
    why: str | None = None          # the course's stated reason (paraphrase), used to name the strategy
    notes: list[str] = field(default_factory=list)            # assumptions made while building it


@dataclass
class Fill:
    ts: int
    px: float
    qty: float
    kind: str                       # entry | exit | stop | target | default


@dataclass
class Result:
    position: Position
    delay_min: int
    status: str                     # priced | not_triggered | no_bars
    fills: list[Fill] = field(default_factory=list)
    pnl: float = 0.0
    cost: float = 0.0
    entry_notional: float = 0.0
    assumed_exit: bool = False
    why: str | None = None

    @property
    def entry(self) -> Fill:
        return next(f for f in self.fills if f.kind == "entry")

    @property
    def last_exit(self) -> Fill:
        return [f for f in self.fills if f.kind != "entry"][-1]

    @property
    def ret_pct(self) -> float:
        return 100 * self.pnl / self.entry_notional if self.entry_notional else 0.0


def cost_bps(market: str, px: float) -> int:
    if market == "crypto":
        return COSTS_BPS["crypto"]
    return COSTS_BPS["stocks_under_10"] if px < 10 else COSTS_BPS["stocks"]


def default_exit_ts(p: Position, entry_ts: int) -> int:
    """When whatever is still held leaves if the course never said: 15:55 ET same session, 5 sessions, or 24 h."""
    kind, _, arg = p.default_exit.partition(":")
    if kind == "at":
        return max(int(arg), entry_ts)
    if kind == "hours":
        return entry_ts + int(arg) * 3600
    day = bars.day_of(p.market, entry_ts)
    if kind == "sessions":
        n, last = int(arg), day + dt.timedelta(days=15)   # bounded: a halted or delisted ticker stops here
        while n and day < last:
            day += dt.timedelta(days=1)
            if day.weekday() < 5 and bars.day_bars(p.market, p.ticker, day):
                n -= 1
    return bars.et_at(day, 15, 55)


def _fill_at(p: Position, ts: int) -> tuple[int, float] | None:
    hit = bars.first_at_or_after(p.market, p.ticker, ts)
    return (hit[0], hit[1][0]) if hit else None


def _trigger_fill(p: Position, t0: int, t1: int) -> tuple[int, float] | None:
    """First time price trades the trigger level in [t0, t1): fill at the level, or at the open if it gapped past."""
    prev = None
    for k, (o, h, l, c, _v) in bars.between(p.market, p.ticker, t0, t1):
        if prev is not None and (prev - p.trigger) * (o - p.trigger) < 0:
            return k, o
        if l <= p.trigger <= h:
            return k, p.trigger
        prev = c
    return None


def simulate(p: Position, delay_min: int) -> Result:
    """Copy one position at one delay. Fills only ever use bars at or after post time + delay."""
    try:
        return _simulate(p, delay_min)
    except bars.NoBars as e:
        return Result(p, delay_min, "no_bars", why=str(e))


def _simulate(p: Position, delay_min: int) -> Result:
    r = Result(p, delay_min, "priced")
    d = delay_min * 60
    sign = 1 if p.side == "long" else -1
    held, start_qty, stop = 0.0, 0.0, p.stop
    targets = list(zip(p.targets, p.target_fracs or [1.0 / max(len(p.targets), 1)] * len(p.targets)))
    host_held = 0.0  # the course's own running size, to turn a stated trim into a share of the position

    def book(ts, px, qty, kind):
        nonlocal held
        qty = min(qty, held) if kind != "entry" else qty
        if qty <= 0:
            return
        r.fills.append(Fill(ts, px, qty, kind))
        r.cost += px * qty * cost_bps(p.market, px) / 1e4
        if kind == "entry":
            r.pnl -= sign * px * qty
            r.entry_notional += px * qty
            held += qty
        else:
            r.pnl += sign * px * qty
            held -= qty

    def scan(t0, t1):
        """Stops and targets between two moments; returns True when the position went flat."""
        nonlocal stop
        if held <= 0 or (stop is None and not targets) or t1 <= t0:
            return False   # nothing to watch (already flat after his own trim, or no levels)
        for k, (o, h, l, c, _v) in bars.between(p.market, p.ticker, t0, t1):
            if stop is not None and ((sign > 0 and l <= stop) or (sign < 0 and h >= stop)):
                px = min(o, stop) if sign > 0 else max(o, stop)
                book(k, px, held, "stop")
                return True
            while targets and ((sign > 0 and h >= targets[0][0]) or (sign < 0 and l <= targets[0][0])):
                lvl, frac = targets.pop(0)
                px = max(o, lvl) if sign > 0 else min(o, lvl)
                book(k, px, held if not targets else start_qty * frac, "target")
                if held <= 1e-12:
                    return True
                hit_targets = sum(f.kind == "target" for f in r.fills)
                if p.be_after_target and hit_targets >= p.be_after_target:
                    stop = r.entry_notional / start_qty
                    if (sign > 0 and l <= stop) or (sign < 0 and h >= stop):
                        book(k, stop, held, "stop")
                        return True
        return False

    clock, factor, cutoff = None, None, None
    entries = [lg for lg in p.legs if lg.action in ("open", "add")]
    known = sorted(lg.qty for lg in entries if lg.qty)
    typical = known[len(known) // 2] if known else 1.0
    weight = {id(lg): (lg.qty or typical) for lg in entries}   # scaled mode: his legs' shares of one $1,000 trade
    total_w = sum(weight.values()) or 1.0
    for leg in sorted(p.legs, key=lambda x: x.posted_ts):
        t = leg.posted_ts + d
        if cutoff is not None and t >= cutoff:   # a day trade's later legs can't be copied after 15:55
            break
        if leg.action in ("open", "add"):
            if clock is None and p.trigger is not None:
                hit = _trigger_fill(p, t, default_exit_ts(p, t))
            else:
                if clock is not None and scan(clock, t):
                    break
                hit = _fill_at(p, t)
            if hit is None:
                if clock is None:
                    return Result(p, delay_min, "not_triggered" if p.trigger is not None else "no_bars")
                continue
            ts, px = hit
            if clock is None and p.portfolio == "day" and (
                    bars.et_date(ts) != bars.et_date(leg.posted_ts) or ts >= bars.et_at(bars.et_date(ts), 15, 55)):
                return Result(p, delay_min, "too_late", why="day trade: no time left that session to copy it")
            if p.scale:
                factor = factor or PER_TRADE_USD / (px * total_w)
                qty = weight[id(leg)] * factor
            elif leg.qty:
                qty = leg.qty
            else:
                qty = PER_TRADE_USD / px
            book(ts, px, qty, "entry")
            start_qty += qty
            host_held += leg.qty or 0
            if clock is None and p.portfolio == "day":
                cutoff = bars.et_at(bars.et_date(ts), 15, 55)
            clock = ts
        else:
            if clock is None:
                continue
            if scan(clock, t):
                break
            hit = _fill_at(p, t)
            if hit is None:
                continue
            if leg.action == "close":
                frac = 1.0
            elif leg.frac is not None:
                frac = leg.frac
            elif leg.qty and host_held > 0:
                frac = min(1.0, leg.qty / host_held)
            else:
                frac = 0.5
            host_held = max(0.0, host_held - (leg.qty or host_held * frac))
            book(hit[0], hit[1], held * frac if frac < 1 else held, "exit")
            clock = hit[0]   # flat after a full trim is not the end: a later add re-enters
    if clock is None:
        return Result(p, delay_min, "no_bars", why="no entry bar")
    if held > 1e-12:
        first_entry = r.fills[0].ts
        end = default_exit_ts(p, first_entry)
        if not scan(clock, end):
            hit = _fill_at(p, max(end, clock))
            if hit is None:
                return Result(p, delay_min, "no_bars", why="no exit bar")
            book(hit[0], hit[1], held, "default")
            r.assumed_exit = True
    r.pnl -= r.cost
    return r


# ---- portfolios ------------------------------------------------------------------------------------------------

def word(trades: int, ret_pct: float, hold_ret_pct: float) -> str:
    """contracts.md rule 9."""
    if trades < 30:
        return "Not enough trades"
    gap = round(ret_pct - hold_ret_pct, 2)
    if gap >= 2:
        return "Yes"
    if gap <= -2:
        return "No"
    return "Barely"


MIN_TRADE_USD = 100.0


def fit_to_cash(results: list[Result]) -> tuple[list[tuple[Result, float]], int, int]:
    """Copy trades in entry order with $10k of cash: a trade uses its entry money until it exits, and realized
    gains or losses change the cash. When open trades leave too little, the next trade is sized down to what is
    left, or skipped below $100 (counted as "couldn't copy"), so the account never spends money it doesn't have."""
    kept, sized_down, skipped, peak = [], 0, 0, 0.0
    open_: list[tuple[int, float, float]] = []      # (exit ts, money in use, pnl to book at exit)
    cash = MONEY_START
    for r in sorted(results, key=lambda r: r.entry.ts):
        still = []
        for ts, used, pnl in open_:
            if ts <= r.entry.ts:
                cash += used + pnl
            else:
                still.append((ts, used, pnl))
        open_ = still
        need = r.entry_notional
        if cash < MIN_TRADE_USD or need <= 0:
            skipped += 1
            continue
        f = min(1.0, cash / need)
        if f < 1.0:
            if cash < MIN_TRADE_USD:
                skipped += 1
                continue
            sized_down += 1
        cash -= need * f
        open_.append((r.last_exit.ts, need * f, r.pnl * f))
        peak = max(peak, sum(u for _, u, _ in open_))
        kept.append((r, f))
    return kept, sized_down, skipped, peak


def portfolio_stats(results: list[Result], dates: list[str], hold: dict, sealed_from: str) -> tuple[dict, list]:
    """One delay of one portfolio: the by_delay entry and its daily money series (realized at each exit)."""
    kept, sized_down, skipped, peak = fit_to_cash([r for r in results if r.status == "priced"])
    pnl_by_day: dict[str, float] = {}
    for r, f in kept:
        day = bars.day_of(r.position.market, r.last_exit.ts).isoformat()
        pnl_by_day[day] = pnl_by_day.get(day, 0.0) + r.pnl * f
    by_point = [0.0] * len(dates)  # a day off the date list counts on the next listed date (or the last one)
    for day, v in pnl_by_day.items():
        by_point[min(bisect.bisect_left(dates, day), len(dates) - 1)] += v
    series, money, high, worst = [], MONEY_START, MONEY_START, 0.0
    for v in by_point:
        money += v
        series.append(round(money, 2))
        high = max(high, money)
        worst = min(worst, (money - high) / high * 100 if high else 0.0)
    end = round(MONEY_START + sum(r.pnl * f for r, f in kept), 2)
    ret = round((end / MONEY_START - 1) * 100, 2)   # the word is decided on the numbers the file shows
    sealed = [(r, f) for r, f in kept if bars.day_of(r.position.market, r.entry.ts).isoformat() >= sealed_from]
    entry = {
        "end": round(end, 2), "ret_pct": round(ret, 2),
        "hold_end": hold["end"], "hold_ret_pct": hold["ret_pct"],
        "trades": len(kept),
        "not_triggered": sum(r.status == "not_triggered" for r in results),
        "couldnt_copy": skipped + sum(r.status == "too_late" for r in results), "sized_down": sized_down,
        "peak_invested_usd": round(peak),
        "won_pct": round(100 * sum(r.pnl > 0 for r, _ in kept) / len(kept)) if kept else 0,
        "worst_drop_pct": round(worst, 1),
        "word": word(len(kept), ret, hold["ret_pct"]),
        "sealed": {"ret_pct": round(100 * sum(r.pnl * f for r, f in sealed) / MONEY_START, 2),
                   "hold_ret_pct": hold["sealed_ret_pct"], "trades": len(sealed)},
    }
    return entry, series
