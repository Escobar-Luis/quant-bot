"""Copy-trade engine: price one position at one delay, then roll positions into a $10k portfolio.

The rules are contracts.md "Copy-trade rules" (code decides, never the model):
- every action the course announces (entry, add, trim, close) is copied at post time + delay, at the open of the
  first 1-minute bar whose open time is at or after that moment;
- an entry with a trigger level fills when price trades the level after post time + delay, else `not_triggered`;
- a stop or target, when stated, exits as soon as a bar trades it (both in one bar = stop); several targets with
  no stated shares: the first that trades is the exit (rule 4);
- a take-profit post (a trim naming TP n) sells, at post time + delay, the shares of TP 1..n the copier's own
  orders have not sold, and nothing when its own TP n order already filled (rule 12c);
- whatever is still held after the last announced exit leaves at the position's default exit (`assumed`); a post
  whose fill would land at or after that exit comes too late, a horizon that passed before the entry leaves
  nothing to copy (`too_late`), and when the bars end before the exit it leaves at the last bar's close;
- costs per side on every fill: 5 bps stocks, 20 bps under $10, 25 bps crypto;
- scaled sizing (rule 13e): the first buy is $1,000; each add is sized only from the counts he had stated by then
  (rule 6's whole-trade scaling, which reads later adds, survives only as `as_taught`).
"""
import bisect
import datetime as dt
from dataclasses import dataclass, field

from . import bars
from .common import COSTS_BPS, MONEY_START, PER_TRADE_USD


@dataclass
class Leg:
    event_id: str
    posted_ts: float                # rule 1's post time, unix seconds to the fraction (never truncated)
    action: str                     # open | add | trim | close
    qty: float | None = None        # the course's own size (shares, coins); None = not stated
    frac: float | None = None       # exits only: share of the held position to sell; None = work it out from qty
    tp_index: int | None = None     # a trim that reports the course's own take-profit n (Crypto Wizard)


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
    scale: bool = False             # True: his share counts scaled to $1,000 (keeps his ratios), see `as_taught`
    as_taught: bool = False         # scaled sizing: False = rule 13(e), the first buy is $1,000 and each add uses only
                                    # the counts he had stated by then; True = rule 6 as taught, all buys together
                                    # are $1,000 (reads his later adds: the `as_taught` alternative only)
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
        return int(arg)   # may lie before the entry: the caller counts that trade as too late to copy
    if kind == "hours":
        return entry_ts + int(arg) * 3600
    day = bars.day_of(p.market, entry_ts)
    if kind == "sessions":
        # bounded so a halted or delisted ticker stops; the bound grows with n, so a long horizon is never cut
        n = int(arg)
        last = day + dt.timedelta(days=2 * n + 15)
        while n and day < last:
            day += dt.timedelta(days=1)
            if day.weekday() < 5 and bars.day_bars(p.market, p.ticker, day):
                n -= 1
    return bars.et_at(day, 15, 55)


def _fill_at(p: Position, ts: int) -> tuple[int, float] | None:
    hit = bars.first_at_or_after(p.market, p.ticker, ts)
    return (hit[0], hit[1][0]) if hit else None


def _exit_bar(p: Position, hz: float) -> tuple[int, float] | None:
    """The default exit's fill: the open of the first bar at or after hz; None when the bars end before it."""
    try:
        return _fill_at(p, hz)
    except bars.NoBars:
        return None


def _last_before(p: Position, t0: float, t1: float) -> tuple[int, float] | None:
    """The last bar with t0 <= open time < t1, as (its time, its close): where the bars end before the exit."""
    day, first = bars.day_of(p.market, t1 - 1), bars.day_of(p.market, t0)
    while day >= first:
        try:
            b = bars.day_bars(p.market, p.ticker, day)
        except bars.NoBars:
            b = {}
        ks = [k for k in b if t0 <= k < t1]
        if ks:
            return max(ks), b[max(ks)][3]
        day -= dt.timedelta(days=1)
    return None


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
    # rule 4: with no stated shares, the first target that trades is the exit (it sells everything held)
    targets = list(zip(p.targets, p.target_fracs or [1.0] * len(p.targets)))
    n_targets = len(targets)
    host_held = 0.0

    def hit_count() -> int:
        """Targets done: filled by the copier's own orders, or passed by the course's take-profit posts."""
        return n_targets - len(targets)

    def break_even():
        nonlocal stop
        if p.be_after_target and hit_count() >= p.be_after_target:
            stop = r.entry_notional / start_qty   # their break-even move: stop to the average entry
            return True
        return False  # the course's own running size, to turn a stated trim into a share of the position

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

    scanned = [0.0]   # bars before this moment were already watched: never watch a bar twice (a stop moved
                      # later, e.g. to break-even, must not fill in a bar that came before the move)

    def scan(t0, t1):
        """Stops and targets between two moments; returns True when the position went flat."""
        nonlocal stop
        t0 = max(t0, scanned[0])
        if held <= 0 or (stop is None and not targets) or t1 <= t0:
            return False   # nothing to watch (already flat after his own trim, or no levels)
        scanned[0] = t1
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
                if break_even():
                    if (sign > 0 and l <= stop) or (sign < 0 and h >= stop):
                        book(k, stop, held, "stop")
                        return True
        return False

    clock, factor, hz, hz_bar = None, None, None, None
    entries = [lg for lg in p.legs if lg.action in ("open", "add")]
    known = sorted(lg.qty for lg in entries if lg.qty)
    typical = known[len(known) // 2] if known else 1.0
    weight = {id(lg): (lg.qty or typical) for lg in entries}   # as taught: his legs' shares of one $1,000 trade
    total_w = sum(weight.values()) or 1.0
    first_leg, first_qty = None, 0.0   # rule 13(e): the first buy, the yardstick for each later add

    def said_by(leg) -> float | None:
        """Upper median of the counts he stated on this position's buys posted up to `leg` (None: none yet)."""
        c = sorted(x.qty for x in entries if x.qty and x.posted_ts <= leg.posted_ts)
        return c[len(c) // 2] if c else None

    for leg in sorted(p.legs, key=lambda x: x.posted_ts):
        t = leg.posted_ts + d
        if leg.action in ("open", "add"):
            if clock is None and p.trigger is not None:
                until = default_exit_ts(p, t)
                if until <= t:   # an at: horizon that passed before the post + delay: nothing to copy
                    return Result(p, delay_min, "too_late", why="the stated horizon passed before the entry")
                hit = _trigger_fill(p, t, until)
            else:
                if clock is not None and scan(clock, min(t, hz)):
                    break
                if clock is not None and t >= hz:   # posted at or after the default exit: too late to copy
                    break
                hit = _fill_at(p, t)
            if hit is None:
                if clock is None:
                    return Result(p, delay_min, "not_triggered" if p.trigger is not None else "no_bars")
                continue
            if clock is not None and hit[0] >= hz_bar:   # at or after the default exit: too late to copy
                break
            ts, px = hit
            if clock is None and p.portfolio == "day" and (
                    bars.et_date(ts) != bars.et_date(leg.posted_ts) or ts >= bars.et_at(bars.et_date(ts), 15, 55)):
                return Result(p, delay_min, "too_late", why="day trade: no time left that session to copy it")
            if clock is None:
                hz = default_exit_ts(p, ts)
                if ts >= hz:
                    return Result(p, delay_min, "too_late", why="the stated horizon passed before the entry")
                end_hit = _exit_bar(p, hz)
                hz_bar = end_hit[0] if end_hit else float("inf")   # no bar after hz: the bars end first
            if p.scale and p.as_taught:
                factor = factor or PER_TRADE_USD / (px * total_w)
                qty = weight[id(leg)] * factor
            elif p.scale:
                if first_leg is None:   # rule 13(e): the first buy is $1,000 at its fill
                    first_leg, qty = leg, PER_TRADE_USD / px
                    first_qty = qty
                else:                   # an add: the first buy's shares x (his add / his first buy), as known now
                    med = said_by(leg)
                    c_first, c_add = first_leg.qty or med, leg.qty or med
                    qty = first_qty * (c_add / c_first if c_first and c_add else 1.0)
                    qty = min(qty, max(0.0, MONEY_START / px - held))   # 13(e): never past $10,000 held
            elif leg.qty:
                qty = leg.qty
            else:
                qty = PER_TRADE_USD / px
            book(ts, px, qty, "entry")
            start_qty += qty
            host_held += leg.qty or 0
            clock = ts
        else:
            if clock is None:
                continue
            if scan(clock, min(t, hz)):
                break
            if t >= hz:   # posted at or after the default exit: too late to copy
                break
            hit = _fill_at(p, t)
            if hit is None:
                continue
            if hit[0] >= hz_bar:   # at or after the default exit: too late to copy
                break
            if leg.tp_index:
                # rule 12(c): their post reporting take-profit n sells at post time + delay what TP 1..n would
                # have sold and the copier's own orders haven't (TP n's share, plus any earlier TP that never
                # filled); nothing when the copier's own TP n order already filled. Either way TP 1..n are done.
                clock, n = hit[0], leg.tp_index
                if n <= hit_count():
                    continue
                q = held if (n >= n_targets or not p.target_fracs) else \
                    sum(p.target_fracs[hit_count():n]) * start_qty
                book(hit[0], hit[1], q, "exit")
                del targets[:n - hit_count()]
                break_even()
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
        if not scan(clock, hz):
            hit = _exit_bar(p, max(hz, clock)) or _last_before(p, clock, hz)   # bars end first: their last bar
            if hit is None:
                return Result(p, delay_min, "no_bars", why="no exit bar")
            book(hit[0], hit[1], held, "default")
            r.assumed_exit = True
    r.pnl -= r.cost
    return r


# ---- portfolios ------------------------------------------------------------------------------------------------

def word(trades: int, ret_pct: float, hold_ret_pct: float) -> str:
    """contracts.md rule 9 (CAP-7): a copy that lost money is never Yes or Barely."""
    if trades < 30:
        return "Not enough trades"
    if ret_pct < 0:
        return "No"
    gap = round(ret_pct - hold_ret_pct, 2)
    if gap >= 2:
        return "Yes"
    if gap <= -2:
        return "No"
    return "Barely"


BENCH_NAMES = {"SPY": "the S&P", "BTC": "Bitcoin"}


def bench_name(symbol: str) -> str:
    return BENCH_NAMES.get(symbol.upper(), symbol)


def outcome(trades: int, ret_pct: float) -> str:
    """Rule 9's absolute outcome: what the copy did to the money, before any comparison."""
    if trades == 0:
        return "No trades"
    return "Made money" if ret_pct > 0 else "Lost money" if ret_pct < 0 else "Broke even"


def versus(trades: int, ret_pct: float, bench_ret_pct: float, name: str) -> str | None:
    """Rule 9's comparison in plain words, never reading as a win when the copy lost money."""
    if trades == 0:
        return None
    gap = round(ret_pct - bench_ret_pct, 2)
    if gap >= 2:
        return f"less than {name}" if ret_pct < 0 else f"beat {name}"
    if gap > -2:
        return f"about the same as {name}"
    return f"more than {name}" if bench_ret_pct < 0 else f"{name} did better"


def judge(row: dict, bench_ret: float | None, bench_sealed_ret: float | None, name: str | None) -> dict:
    """Set word, outcome and vs on a by_delay row and its sealed block (rule 9). A None benchmark means the row
    is not compared (a proof-set file's non-headline portfolios): word and vs are null."""
    n, ret = row["trades"], row["ret_pct"]
    row["word"] = word(n, ret, bench_ret) if bench_ret is not None else None
    row["outcome"] = outcome(n, ret)
    row["vs"] = versus(n, ret, bench_ret, name) if bench_ret is not None else None
    s = row.get("sealed")
    if s is not None:
        sn, sr = s["trades"], s["ret_pct"]
        ok = bench_sealed_ret is not None
        s["word"] = word(sn, sr, bench_sealed_ret) if ok else None
        s["outcome"] = outcome(sn, sr)
        s["vs"] = versus(sn, sr, bench_sealed_ret, name) if ok else None
    return row


MIN_CASH_USD = 1.0   # at $1 of cash or less a trade is couldn't-copy: no sub-dollar trade counts toward rule 9's 30


def fit_to_cash(results: list[Result]) -> tuple[list[tuple[Result, float]], int, int, float]:
    """Copy every fill in time order with $10k of cash (rule 6's cash cap, per buy): each buy takes its own money
    as it fills, never a later add's; when too little is left it is sized down to the cash, or skipped at $1 or
    less (a first buy skipped = the trade couldn't be copied, and its later buys go with it). Each sell returns
    its share of the money in the position plus its gain; the trade's costs are paid at its last sell. At one
    moment sells go before buys, then by trade id, except that a trade's own fills keep their order. Returns [(result, copied P&L)], buys sized down or skipped,
    trades skipped, and the most money ever in open positions."""
    order = []
    for i, r in enumerate(results):
        for j, f in enumerate(r.fills):
            # a sell that follows its own trade's buy in the same bar keeps that order (it sells what it bought)
            after_own_buy = any(g.kind == "entry" and g.ts == f.ts for g in r.fills[:j])
            order.append((f.ts, f.kind == "entry" or after_own_buy, r.position.pid, i, j))
    order.sort(key=lambda x: x[:3] + (x[4],))
    cash, sized_down, skipped, peak = MONEY_START, 0, 0, 0.0
    st = [{"on": None, "sim": 0.0, "held": 0.0, "basis": 0.0, "gross": 0.0, "cost": 0.0, "last": -1, "fs": []}
          for _ in results]
    for i, r in enumerate(results):
        st[i]["last"] = max(j for j, f in enumerate(r.fills) if f.kind != "entry")
    for _ts, _rank, _pid, i, j in order:
        r, f, s = results[i], results[i].fills[j], st[i]
        sign = 1 if r.position.side == "long" else -1
        if f.kind == "entry":
            s["sim"] += f.qty
            if s["on"] is False:
                continue
            q = f.qty
            if f.px * q > cash + 1e-9:
                if cash <= MIN_CASH_USD:
                    if s["on"] is None:
                        s["on"], skipped = False, skipped + 1
                    else:
                        sized_down += 1
                        s["fs"].append(0.0)
                    continue
                q, sized_down = cash / f.px, sized_down + 1
            s["on"] = True
            s["fs"].append(q / f.qty if f.qty else 1.0)
            cash -= f.px * q
            s["held"] += q
            s["basis"] += f.px * q
            s["cost"] += f.px * q * cost_bps(r.position.market, f.px) / 1e4
            peak = max(peak, sum(x["basis"] for x in st))
        else:
            share = min(1.0, f.qty / s["sim"]) if s["sim"] > 1e-12 else 1.0
            s["sim"] = max(0.0, s["sim"] - f.qty)
            if not s["on"]:
                continue
            q = s["held"] * share
            if q > 1e-12:
                avg = s["basis"] / s["held"]
                s["gross"] += sign * (f.px - avg) * q
                s["cost"] += f.px * q * cost_bps(r.position.market, f.px) / 1e4
                s["held"] -= q
                s["basis"] -= avg * q
                cash += avg * q + sign * (f.px - avg) * q
            if j == s["last"]:
                cash -= s["cost"]
    def copied_pnl(r, s):
        """Every buy copied at one fraction f: the trade scales, P&L = f x its own. Else from the copied fills."""
        fs = s["fs"]
        if fs and max(fs) - min(fs) <= 1e-12:
            return r.pnl * fs[0]
        return s["gross"] - s["cost"]

    kept = [(r, copied_pnl(r, st[i])) for i, r in enumerate(results) if st[i]["on"]]
    kept.sort(key=lambda x: x[0].entry.ts)
    return kept, sized_down, skipped, peak


def portfolio_stats(results: list[Result], dates: list[str], hold: dict, sealed_from: str,
                    name: str = "just holding") -> tuple[dict, list]:
    """One delay of one portfolio: the by_delay entry and its daily money series (realized at each exit)."""
    kept, sized_down, skipped, peak = fit_to_cash([r for r in results if r.status == "priced"])
    pnl_by_day: dict[str, float] = {}
    for r, pnl in kept:
        day = bars.day_of(r.position.market, r.last_exit.ts).isoformat()
        pnl_by_day[day] = pnl_by_day.get(day, 0.0) + pnl
    by_point = [0.0] * len(dates)  # a day off the date list counts on the next listed date (or the last one)
    for day, v in pnl_by_day.items():
        by_point[min(bisect.bisect_left(dates, day), len(dates) - 1)] += v
    series, money, high, worst = [], MONEY_START, MONEY_START, 0.0
    for v in by_point:
        money += v
        series.append(round(money, 2))
        high = max(high, money)
        worst = min(worst, (money - high) / high * 100 if high else 0.0)
    end = round(MONEY_START + sum(pnl for _, pnl in kept), 2)
    ret = round((end / MONEY_START - 1) * 100, 2)   # the word is decided on the numbers the file shows
    sealed = [(r, pnl) for r, pnl in kept if bars.day_of(r.position.market, r.entry.ts).isoformat() >= sealed_from]
    entry = {
        "end": round(end, 2), "ret_pct": round(ret, 2),
        "hold_end": hold["end"], "hold_ret_pct": hold["ret_pct"],
        "trades": len(kept),
        "not_triggered": sum(r.status == "not_triggered" for r in results),
        "couldnt_copy": skipped + sum(r.status == "too_late" for r in results), "sized_down": sized_down,
        "peak_invested_usd": round(peak),
        "won_pct": round(100 * sum(pnl > 0 for _, pnl in kept) / len(kept)) if kept else 0,
        "worst_drop_pct": round(worst, 1),
        "sealed": {"ret_pct": round(100 * sum(pnl for _, pnl in sealed) / MONEY_START, 2),
                   "hold_ret_pct": hold["sealed_ret_pct"], "trades": len(sealed)},
    }
    return judge(entry, hold["ret_pct"], hold["sealed_ret_pct"], name), series
