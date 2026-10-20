"""Optional results keys for the v2 answer screen (ui-v2-direction.md): strategies, ranges, best_stop; and by_year
(spec-audit CAP-4, contracts.md section `by_year`).

All code, no model: strategies come from each course module's keyword rules (`STRATEGIES`, `strategy_of`), and
every number is the same engine output the portfolios use.
"""
import datetime as dt
from statistics import median

from . import bars, engine
from .common import DELAYS_MIN, MONEY_START


def _clock(p, ts: int) -> str:
    tz = bars.ET if p.market == "us_equities" else dt.UTC
    return dt.datetime.fromtimestamp(ts, tz).strftime("%H:%M")


def _entails(spec: dict, group: list, results5: list, course: str) -> dict:
    priced = [r for r in results5 if r.status == "priced"]
    assumed = sum(r.assumed_exit for r in priced)
    sell = spec["sell"] + (f"; {round(100 * assumed / len(priced))}% never closed (assumed)" if priced and assumed
                           else "")
    with_stop = sum(p.stop is not None for p in group)
    if course == "cryptowizard":
        stop = "Stated stop; moved to entry after target 2"
        size = "$1,000 a setup (they never state one)"
    else:
        stop = f"Stated on {with_stop} of {len(group)} trades" if with_stop else "None stated"
        qty = [lg.qty for p in group for lg in p.legs if lg.action == "open" and lg.qty]
        size = (f"His share count (median {median(qty):,.0f}), scaled to $1,000" if qty
                else "Not stated; $1,000 per trade")
    times = sorted(_clock(r.position, r.entry.ts) for r in priced)
    tz = "ET" if course != "cryptowizard" else "UTC"
    time = f"Mostly {times[len(times) // 4]}-{times[3 * len(times) // 4]} {tz}" if times else "Not known"
    return {"buy": spec["buy"], "sell": sell, "stop": stop, "size": size, "time": time}


def _quotes(group: list, n: int = 3) -> list[dict]:
    out, seen = [], set()
    for p in group:
        if p.quote and p.cite and p.cite["source_id"] not in seen:
            out.append({"text": p.quote, "cite": p.cite})
            seen.add(p.cite["source_id"])
        if len(out) == n:
            break
    return out


def strategies(mod, version: str, positions: list, by_pos: dict, dates: list, hold: dict, window: dict,
               name: str = "just holding") -> list:
    if not hasattr(mod, "STRATEGIES"):
        return []
    soft = mod.untestable(version) if hasattr(mod, "untestable") else []
    out = []
    for spec in mod.STRATEGIES:
        group = [p for p in positions if mod.strategy_of(p) == spec["id"]]
        if not group:
            continue
        rows, series = {}, {}
        for d in DELAYS_MIN:
            rs = [by_pos[p.pid][d] for p in group]
            rows[str(d)], series[str(d)] = engine.portfolio_stats(rs, dates, hold, window["sealed_from"], name)
        kinds = [p.portfolio for p in group]
        words = spec.get("words") or ()
        mine = [r for r in soft if any(w in r.lower() for w in words)] or soft[len(out)::7]
        out.append({
            "id": spec["id"], "name": spec["name"], "portfolio": max(set(kinds), key=kinds.count),
            "testable": True, "sessions": len({p.cite["source_id"] for p in group if p.cite}),
            "entails": _entails(spec, group, [by_pos[p.pid][5] for p in group], mod.COURSE),
            "quotes": _quotes(group), "untestable": mine[:2],
            "by_delay": rows, "series": {"by_delay": series},
        })
    return out


def _add_months(day: dt.date, n: int) -> dt.date:
    m = day.month - 1 + n
    y, m = day.year + m // 12, m % 12 + 1
    for d in (day.day, 30, 29, 28):
        try:
            return dt.date(y, m, d)
        except ValueError:
            continue


def ranges(results_all: dict, dates: list, hold_series: list, window: dict, name: str = "just holding") -> dict:
    """3m / 6m / 1y from the window start: trades closed by then, against holding to the same day."""
    start, end = dt.date.fromisoformat(window["start"]), dt.date.fromisoformat(window["end"])
    out = {}
    for key, months in (("3m", 3), ("6m", 6), ("1y", 12)):
        stop = _add_months(start, months) - dt.timedelta(days=1)
        if stop > end:
            if (stop - end).days > 7:   # the window is shorter than this range: leave the chip out
                continue
            stop = end
        last = max(i for i, d in enumerate(dates) if d <= stop.isoformat())
        hold_end = hold_series[last]
        hold_ret = round((hold_end / MONEY_START - 1) * 100, 2)
        rows = {}
        for d in DELAYS_MIN:
            closed = [r for r in results_all[d] if r.status == "priced"
                      and bars.day_of(r.position.market, r.last_exit.ts) <= stop]
            kept, *_ = engine.fit_to_cash(closed)
            money = round(MONEY_START + sum(pnl for _, pnl in kept), 2)
            ret = round((money / MONEY_START - 1) * 100, 2)
            rows[str(d)] = {"end": money, "ret_pct": ret, "hold_end": hold_end, "hold_ret_pct": hold_ret,
                            "trades": len(kept), "word": engine.word(len(kept), ret, hold_ret),
                            "outcome": engine.outcome(len(kept), ret),
                            "vs": engine.versus(len(kept), ret, hold_ret, name)}
        out[key] = {"until": dates[last], "by_delay": rows}
    return out


def best_stop(all_portfolio: dict, hold_series: list) -> dict:
    """The day the money peaked, per delay: "stop then and you'd have had $X"."""
    dates = all_portfolio["series"]["dates"]
    rows = {}
    for d, curve in all_portfolio["series"]["by_delay"].items():
        i = max(range(len(curve)), key=lambda k: curve[k])
        rows[d] = {"date": dates[i], "end": curve[i], "hold_end": hold_series[i]}
    return {"by_delay": rows}


def _account(results: list) -> tuple[float, int]:
    kept, *_ = engine.fit_to_cash([r for r in results if r.status == "priced"])
    return round(100 * sum(pnl for _, pnl in kept) / MONEY_START, 2), len(kept)


def combos(mod, positions: list, by_pos: dict, dates: list, hold: dict, hold_series: list, window: dict,
           delay: int = 5) -> list:
    """The best two-strategy mix in one $10k account: picked on the dev months only, reported on the sealed months.
    Same course only (the courses' dates don't overlap)."""
    if not hasattr(mod, "STRATEGIES"):
        return []
    sealed = window["sealed_from"]
    groups = {s["id"]: [p for p in positions if mod.strategy_of(p) == s["id"]] for s in mod.STRATEGIES}
    groups = {k: v for k, v in groups.items() if v}
    dev_last = max((i for i, d in enumerate(dates) if d < sealed), default=0)
    hold_dev = round((hold_series[dev_last] / MONEY_START - 1) * 100, 2)

    def split(ids):
        rs = [by_pos[p.pid][delay] for k in ids for p in groups[k]]
        on = lambda r: bars.day_of(r.position.market, r.entry.ts).isoformat() >= sealed  # noqa: E731
        dev = [r for r in rs if r.status == "priced" and not on(r)]
        late = [r for r in rs if r.status == "priced" and on(r)]
        return _account(dev), _account(late)

    ids = list(groups)
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    if not pairs:
        return []
    scored = sorted(((split(pr), pr) for pr in pairs), key=lambda x: -x[0][0][0])
    ((dev_ret, dev_n), (sealed_ret, sealed_n)), best = scored[0]
    return [{"ids": [f"{mod.COURSE}:{k}" for k in best], "delay_min": delay, "picked_on": "dev",
             "window": {"start": sealed, "end": window["end"]},
             "dev": {"ret_pct": dev_ret, "hold_ret_pct": hold_dev, "trades": dev_n, "pairs_tried": len(pairs)},
             "sealed": {"ret_pct": sealed_ret, "hold_ret_pct": hold["sealed_ret_pct"], "trades": sealed_n},
             "word": engine.word(sealed_n, sealed_ret, hold["sealed_ret_pct"])}]


# ---- by_year (spec-audit CAP-4): calendar years and all time, as slices of the one all-time run ----------------

def hold_paths(market: str, symbol: str, window: dict) -> dict:
    """Just holding as one all-time run (rule 7): $10k bought at the open of the window's first trading minute,
    valued at each trading day's official close. `price`: without dividends (the headline's basis); `total`: each
    dividend reinvested at its ex-date's close (an ex-date on the buy day earns nothing). Unrounded."""
    start, end = dt.date.fromisoformat(window["start"]), dt.date.fromisoformat(window["end"])
    closes = bars.daily_closes(market, symbol, start, end)
    dates = list(closes)
    b = bars.day_bars(market, symbol, dt.date.fromisoformat(dates[0]))
    shares = MONEY_START / b[min(b)][0]
    divs = bars.dividends(market, symbol, start, end)
    pending = sorted((d, v) for d, v in divs.items() if d > dates[0])
    units, price, total = shares, [], []
    for day in dates:
        while pending and pending[0][0] <= day:   # reinvested at the close of the ex-date (or the next close)
            units *= 1 + pending.pop(0)[1] / closes[day]
        price.append(shares * closes[day])
        total.append(units * closes[day])
    basis = "total_return" if market == "us_equities" else "price"
    return {"dates": dates, "price": price, "total": total,
            "meta": {"symbol": symbol, "basis": basis,
                     "source": bars.DIVIDEND_SOURCE if market == "us_equities" else "No dividends (crypto)",
                     "dividends": len([d for d in divs if d > dates[0]])}}


def by_year(port_results: dict, hold: dict, name: str = "just holding") -> dict:
    """Per portfolio and delay, each calendar year in the window plus "all" (contracts.md section by_year).

    port_results: {portfolio id: {delay: [Result]}}. The copied trades and their sizes are the headline's own
    (`engine.fit_to_cash` over every priced trade); each one is booked in the calendar year of its exit day
    (ET for stocks, UTC for crypto), clamped to the window's years. Words follow rule 9 (`engine.judge`)."""
    dates, total, price = hold["dates"], hold["total"], hold["price"]
    years = sorted({d[:4] for d in dates})
    last = {y: max(i for i, d in enumerate(dates) if d[:4] == y) for y in years}
    first = {y: min(i for i, d in enumerate(dates) if d[:4] == y) for y in years}
    periods = [{"id": y, "from": dates[first[y]], "to": dates[last[y]]} for y in years] + \
        [{"id": "all", "from": dates[0], "to": dates[-1]}]

    def hold_row(i0: int | None, i1: int) -> dict:
        t0, p0 = (MONEY_START, MONEY_START) if i0 is None else (total[i0], price[i0])
        return {"hold_start": round(t0, 2), "hold_end": round(total[i1], 2),
                "hold_ret_pct": round((total[i1] / t0 - 1) * 100, 2),
                "hold_price_ret_pct": round((price[i1] / p0 - 1) * 100, 2)}

    holds = {y: hold_row(last[years[k - 1]] if k else None, last[y]) for k, y in enumerate(years)}
    holds["all"] = hold_row(None, len(dates) - 1)
    out = {}
    for pid, per_delay in port_results.items():
        rows = {}
        for d, results in per_delay.items():
            kept, *_ = engine.fit_to_cash([r for r in results if r.status == "priced"])
            pnl, n = {y: 0.0 for y in years}, {y: 0 for y in years}
            for r, v in kept:
                y = str(bars.day_of(r.position.market, r.last_exit.ts).year)
                y = min(max(y, years[0]), years[-1])
                pnl[y] += v
                n[y] += 1
            row, money = {}, MONEY_START
            for y in years:
                ret = round(100 * pnl[y] / money, 2)
                h = holds[y]
                row[y] = {"start": round(money, 2), "end": round(money + pnl[y], 2), "ret_pct": ret, **h,
                          "trades": n[y]}
                engine.judge(row[y], h["hold_ret_pct"], None, name)
                money += pnl[y]
            end = round(MONEY_START + sum(v for _, v in kept), 2)   # the headline's own sum
            ret = round((end / MONEY_START - 1) * 100, 2)
            h = holds["all"]
            row["all"] = {"start": MONEY_START, "end": end, "ret_pct": ret, **h, "trades": len(kept)}
            engine.judge(row["all"], h["hold_ret_pct"], None, name)
            rows[str(d)] = row
        out[pid] = {"by_delay": rows}
    return {"hold": hold["meta"], "periods": periods, "portfolios": out}
