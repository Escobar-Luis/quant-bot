"""Cached 1-minute bars, read straight from data/bars/. Never fetches: a missing file raises MissingBar.

Stocks: data/bars/alpaca_1m/<T>/<ET date>.json, else data/bars/yahoo_1m/<T>/<ET date>.json, each
{unix_s: [o, h, l, c, v]} for the regular session. A file holding {} is a session with no trading (a holiday);
no file at all on a weekday is a missing bar.
Crypto: data/bars/binance/<SYM>/1m/<UTC date>.json as [[open_ms, o, h, l, c, v], ...].
"""
import datetime as dt
import json
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from backtest.common import BARS

ET = ZoneInfo("America/New_York")
UTC = dt.UTC


class MissingBar(Exception):
    """A bar the calculation needs is not in the local cache (the audit never downloads)."""


def to_ts(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def et_day(ts: int) -> dt.date:
    return dt.datetime.fromtimestamp(ts, ET).date()


def et_time(day: dt.date, hh: int, mm: int) -> int:
    return int(dt.datetime.combine(day, dt.time(hh, mm), ET).timestamp())


def day_of(market: str, ts: int) -> dt.date:
    return et_day(ts) if market == "us_equities" else dt.datetime.fromtimestamp(ts, UTC).date()


def source_file(market: str, symbol: str, day: dt.date, root: Path = BARS) -> Path | None:
    if market == "us_equities":
        for src in ("alpaca_1m", "yahoo_1m"):
            p = root / src / symbol / f"{day.isoformat()}.json"
            if p.exists():
                return p
        return None
    p = root / "binance" / symbol / "1m" / f"{day.isoformat()}.json"
    return p if p.exists() else None


@lru_cache(maxsize=8192)
def day_bars(market: str, symbol: str, day: dt.date) -> dict[int, tuple]:
    """{bar open unix_s: (o, h, l, c)} for one session (stocks, ET date) or one UTC day (crypto)."""
    if market == "us_equities" and day.weekday() >= 5:
        return {}
    p = source_file(market, symbol, day)
    if p is None:
        raise MissingBar(f"{symbol} {day.isoformat()}: no cached 1-minute bars")
    raw = json.loads(p.read_text())
    if market == "us_equities":
        return {int(k): tuple(v[:4]) for k, v in raw.items()}
    return {int(k[0] // 1000): tuple(k[1:5]) for k in raw}


def first_bar_at_or_after(market: str, symbol: str, ts: int, max_days: int = 10) -> tuple[int, tuple]:
    """The first bar whose open time is >= ts, rolling into later days."""
    day = day_of(market, ts)
    for _ in range(max_days + 1):
        later = [k for k in day_bars(market, symbol, day) if k >= ts]
        if later:
            k = min(later)
            return k, day_bars(market, symbol, day)[k]
        day += dt.timedelta(days=1)
    raise MissingBar(f"{symbol}: no bar within {max_days} days after {iso(ts)}")


def bars_between(market: str, symbol: str, t0: int, t1: int):
    """Bars with t0 <= open time < t1, in time order."""
    day, last = day_of(market, t0), day_of(market, max(t0, t1 - 1))
    while day <= last:
        b = day_bars(market, symbol, day)
        for k in sorted(b):
            if t0 <= k < t1:
                yield k, b[k]
        day += dt.timedelta(days=1)


def daily_close(symbol: str, start: dt.date, end: dt.date, root: Path = BARS) -> float:
    """The last close in data/bars/daily/<SYM>_<start>_<end>.json ({date: close})."""
    p = root / "daily" / f"{symbol}_{start}_{end}.json"
    if not p.exists():
        raise MissingBar(f"{symbol} daily {start}..{end}: no cached daily closes")
    closes = json.loads(p.read_text())
    return closes[max(closes)]


def nth_session_after(symbol: str, day: dt.date, n: int) -> dt.date:
    """The n-th stock session after `day` (a session = a weekday whose bar file is not empty)."""
    seen = 0
    for _ in range(40):
        day += dt.timedelta(days=1)
        if day_bars("us_equities", symbol, day):
            seen += 1
            if seen == n:
                return day
    raise MissingBar(f"{symbol}: fewer than {n} sessions after {day}")
