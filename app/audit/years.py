"""by_year, recomputed (contracts.md section `by_year`, spec-audit CAP-4): calendar years and all time.

Written from the contract, not from backtest/extras.py. The copied trades are the audit's own (audit.calc, from
its own positions), sized by its own cash cap (calc.copied_trades); holding reads the cached daily closes and the
cached dividend list in data/bars/ (never the network: a missing file raises MissingBar).
"""
import datetime as dt
import json

from . import bars as B
from . import calc
from .paths import BARS

MONEY_FIELDS = ("start", "end", "hold_start", "hold_end")
POINT_FIELDS = ("ret_pct", "hold_ret_pct", "hold_price_ret_pct")
EXACT_FIELDS = ("trades", "word")


def _cached(kind: str, symbol: str, window: dict) -> dict:
    p = BARS / kind / f"{symbol}_{window['start']}_{window['end']}.json"
    if not p.exists():
        raise B.MissingBar(f"{symbol} {kind} {window['start']}..{window['end']}: not cached ({p})")
    return json.loads(p.read_text())


def hold_values(market: str, symbol: str, window: dict) -> dict:
    """Rule 7's one holding run, valued at every official close: price only, and with each dividend reinvested
    at its ex-date's close (ASSUMPTION per the contract: an ex-date on the buy day pays nothing; an ex-date with
    no close of its own is reinvested at the next close)."""
    closes = _cached("daily", symbol, window)
    days = sorted(closes)
    px0 = calc._first_open(market, symbol, dt.date.fromisoformat(window["start"]),
                           dt.date.fromisoformat(window["end"]))
    divs = _cached("dividends", symbol, window) if market == "us_equities" else {}
    todo = sorted((d, a) for d, a in divs.items() if d > days[0])
    shares = calc.MONEY_START / px0
    units, price, total = shares, {}, {}
    for d in days:
        while todo and todo[0][0] <= d:
            units += units * todo.pop(0)[1] / closes[d]
        price[d], total[d] = shares * closes[d], units * closes[d]
    return {"days": days, "price": price, "total": total,
            "dividends": sum(1 for d in divs if d > days[0]),
            "basis": "total_return" if market == "us_equities" else "price"}


def periods(hv: dict) -> list[dict]:
    days = hv["days"]
    years = sorted({d[:4] for d in days})
    out = [{"id": y, "from": min(d for d in days if d[:4] == y), "to": max(d for d in days if d[:4] == y)}
           for y in years]
    return out + [{"id": "all", "from": days[0], "to": days[-1]}]


def by_year(trades: list[calc.Trade], hv: dict) -> dict:
    """{period id: row} for one portfolio at one delay (contracts.md by_year rules 1-6)."""
    ps = periods(hv)
    years = [p["id"] for p in ps if p["id"] != "all"]
    kept, _, _ = calc.copied_trades(trades)
    pnl = {y: 0.0 for y in years}
    count = {y: 0 for y in years}
    for t, f in kept:
        y = str(B.day_of(t.market, t.exit.ts).year)
        y = min(max(y, years[0]), years[-1])        # rule 2: after the last trading day = the last year
        pnl[y] += t.pnl * f
        count[y] += 1
    out, money, hold_prev, price_prev = {}, calc.MONEY_START, calc.MONEY_START, calc.MONEY_START
    for p in ps[:-1]:
        y, last = p["id"], p["to"]
        ret = round(pnl[y] / money * 100, 2)
        h_ret = round((hv["total"][last] / hold_prev - 1) * 100, 2)
        out[y] = {"start": round(money, 2), "end": round(money + pnl[y], 2), "ret_pct": ret,
                  "hold_start": round(hold_prev, 2), "hold_end": round(hv["total"][last], 2),
                  "hold_ret_pct": h_ret, "hold_price_ret_pct": round((hv["price"][last] / price_prev - 1) * 100, 2),
                  "trades": count[y], "word": calc.word(count[y], ret, h_ret)}
        money += pnl[y]
        hold_prev, price_prev = hv["total"][last], hv["price"][last]
    last = hv["days"][-1]
    end = round(calc.MONEY_START + sum(t.pnl * f for t, f in kept), 2)
    ret = round((end / calc.MONEY_START - 1) * 100, 2)
    h_ret = round((hv["total"][last] / calc.MONEY_START - 1) * 100, 2)
    out["all"] = {"start": calc.MONEY_START, "end": end, "ret_pct": ret, "hold_start": calc.MONEY_START,
                  "hold_end": round(hv["total"][last], 2), "hold_ret_pct": h_ret,
                  "hold_price_ret_pct": round((hv["price"][last] / calc.MONEY_START - 1) * 100, 2),
                  "trades": len(kept), "word": calc.word(len(kept), ret, h_ret)}
    return out


def compare(by_year_key: dict, mine: dict, delays: list[int], hv: dict, money_tol: float, ret_tol: float) -> list:
    """Mismatches between the file's by_year and this recompute (mine: {(pid, delay): Trade})."""
    out = []

    def miss(where, field, theirs, ours, diff=None):
        out.append({"kind": "by_year", "portfolio": where, "field": field, "theirs": theirs, "ours": ours,
                    **({} if diff is None else {"diff": round(diff, 4)})})

    ps = periods(hv)
    if by_year_key.get("periods") != ps:
        miss("periods", "periods", by_year_key.get("periods"), ps)
    basis = (by_year_key.get("hold") or {}).get("basis")
    if basis != hv["basis"]:
        miss("hold", "basis", basis, hv["basis"])
    if (by_year_key.get("hold") or {}).get("dividends", 0) != hv["dividends"]:
        miss("hold", "dividends", (by_year_key.get("hold") or {}).get("dividends"), hv["dividends"])
    for pid, pf in (by_year_key.get("portfolios") or {}).items():
        if set(pf["by_delay"]) != {str(d) for d in delays}:
            miss(pid, "delays", sorted(pf["by_delay"]), [str(d) for d in delays])
        for dl, rows in pf["by_delay"].items():
            ts = [t for (_, x), t in mine.items() if x == int(dl) and (pid == "all" or t.portfolio == pid)]
            ours = by_year(ts, hv)
            if set(rows) != set(ours):
                miss(f"{pid}@{dl}", "periods", sorted(rows), sorted(ours))
            for y in set(rows) & set(ours):
                a, b = rows[y], ours[y]
                for f in MONEY_FIELDS + POINT_FIELDS + EXACT_FIELDS:
                    if f not in a:
                        miss(f"{pid}@{dl}:{y}", f, "missing", b[f])
                    elif f in EXACT_FIELDS:
                        if a[f] != b[f]:
                            miss(f"{pid}@{dl}:{y}", f, a[f], b[f])
                    elif abs(a[f] - b[f]) > (money_tol if f in MONEY_FIELDS else ret_tol) + 1e-9:
                        miss(f"{pid}@{dl}:{y}", f, a[f], b[f], abs(a[f] - b[f]))
    return out
