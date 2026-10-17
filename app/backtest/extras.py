"""Optional results keys for the v2 answer screen (ui-v2-direction.md): strategies, ranges, best_stop.

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
        size = (f"His size, median {median(qty):,.0f} shares; copied at $1,000" if qty
                else "Not stated; copied at $1,000")
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


def strategies(mod, version: str, positions: list, by_pos: dict, dates: list, hold: dict, window: dict) -> list:
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
            rows[str(d)], series[str(d)] = engine.portfolio_stats(rs, dates, hold, window["sealed_from"])
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


def ranges(results_all: dict, dates: list, hold_series: list, window: dict) -> dict:
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
            money = round(MONEY_START + sum(r.pnl * f for r, f in kept), 2)
            ret = round((money / MONEY_START - 1) * 100, 2)
            rows[str(d)] = {"end": money, "ret_pct": ret, "hold_end": hold_end, "hold_ret_pct": hold_ret,
                            "trades": len(kept), "word": engine.word(len(kept), ret, hold_ret)}
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
