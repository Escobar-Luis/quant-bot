"""1-minute and daily price bars, cached under data/bars/ (gitignored).

Stocks: Alpaca 1-minute bars, regular session 09:30-16:00 ET, cached per ticker and ET date in
data/bars/alpaca_1m/<T>/<date>.json as {unix_s: [o, h, l, c, v]} (the same cache app/lpp/bars.py writes).
Needs APCA_API_KEY_ID / APCA_API_SECRET_KEY in ~/dev/quant-bot/.env; without them stock minutes are None.
Crypto: Binance spot 1-minute klines (keyless data-api.binance.vision), cached per symbol and UTC date in
data/bars/binance/<SYM>/1m/<date>.json as [[open_ms, o, h, l, c, v], ...] (the Crypto Wizard collector's cache).

Every bar is keyed by its open time (unix seconds). A copier acting at time t can only get the open of the first
bar whose open time is >= t: that is `first_at_or_after`.
"""
import datetime as dt
import json
import os
import time
from functools import lru_cache
from zoneinfo import ZoneInfo

import httpx

from .common import BARS, has_alpaca

ET = ZoneInfo("America/New_York")
UTC = dt.UTC
BINANCE = "https://data-api.binance.vision/api/v3/klines"
ALPACA = "https://data.alpaca.markets/v2/stocks"


class NoBars(Exception):
    """Raised when bars for a symbol cannot be loaded (no keys, unknown symbol, outside the data)."""


def to_ts(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def post_ts(iso: str) -> float:
    """Rule 1's post time, to the fraction of a second (never truncated: a post at 09:45:00.4 + 5 min fills on the
    09:51 bar, not 09:50)."""
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def to_iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def et_date(ts: int) -> dt.date:
    return dt.datetime.fromtimestamp(ts, ET).date()


def et_at(day: dt.date, hh: int, mm: int) -> int:
    return int(dt.datetime.combine(day, dt.time(hh, mm), ET).timestamp())


# ---- stocks (Alpaca) -------------------------------------------------------------------------------------------

def _alpaca_get(path: str, params: dict) -> dict:
    key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
    sec = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
    for attempt in range(5):
        try:
            r = httpx.get(f"{ALPACA}/{path}", params=params, timeout=30,
                          headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec})
        except httpx.HTTPError as e:
            if attempt == 4:
                raise NoBars(f"alpaca {path}: {type(e).__name__}") from e
            time.sleep(2)
            continue
        if r.status_code == 429:
            time.sleep(2 + attempt * 3)
            continue
        if r.status_code != 200:
            raise NoBars(f"alpaca {path} http {r.status_code}")
        return r.json()
    raise NoBars(f"alpaca {path} rate limited")


@lru_cache(maxsize=4096)
def stock_day(ticker: str, day: dt.date) -> dict[int, list]:
    """{unix_s: [o, h, l, c, v]} for one regular session; {} on weekends, holidays or no trading."""
    if day.weekday() >= 5:
        return {}
    d = BARS / "alpaca_1m" / ticker
    p = d / f"{day.isoformat()}.json"
    if p.exists():
        return {int(k): v for k, v in json.loads(p.read_text()).items()}
    if day >= dt.date.today():
        raise NoBars(f"{ticker} {day} not closed yet")
    if not has_alpaca():
        if (dt.date.today() - day).days <= 28:
            return yahoo_day(ticker, day)
        raise NoBars("no Alpaca keys in .env (APCA_API_KEY_ID / APCA_API_SECRET_KEY)")
    rows, token = {}, None
    while True:
        params = {"timeframe": "1Min", "start": to_iso(et_at(day, 9, 30)), "end": to_iso(et_at(day, 16, 0) - 1),
                  "limit": 10000, "feed": os.getenv("ALPACA_FEED", "sip"), "adjustment": "raw"}
        if token:
            params["page_token"] = token
        js = _alpaca_get(f"{ticker}/bars", params)
        for b in js.get("bars") or []:
            rows[to_ts(b["t"])] = [b["o"], b["h"], b["l"], b["c"], b["v"]]
        token = js.get("next_page_token")
        if not token:
            break
    d.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows))
    return rows


def _yahoo(ticker: str, interval: str, t0: int, t1: int) -> list[tuple[int, list]]:
    r = httpx.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}", timeout=30,
                  headers={"User-Agent": "Mozilla/5.0"},
                  params={"interval": interval, "period1": t0, "period2": t1, "includePrePost": "false"})
    if r.status_code != 200:
        raise NoBars(f"yahoo {ticker} http {r.status_code}")
    res = (r.json().get("chart") or {}).get("result") or []
    if not res or not res[0].get("timestamp"):
        return []
    q = res[0]["indicators"]["quote"][0]
    return [(ts, [q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]])
            for i, ts in enumerate(res[0]["timestamp"]) if q["open"][i] is not None]


@lru_cache(maxsize=4096)
def yahoo_day(ticker: str, day: dt.date) -> dict[int, list]:
    """Keyless fallback for the last ~28 days only (Yahoo keeps 1-minute bars 30 days): regular session, cached."""
    d = BARS / "yahoo_1m" / ticker
    p = d / f"{day.isoformat()}.json"
    if p.exists():
        return {int(k): v for k, v in json.loads(p.read_text()).items()}
    if day >= dt.date.today():
        raise NoBars(f"{ticker} {day} not closed yet")
    rows = {ts: v for ts, v in _yahoo(ticker, "1m", et_at(day, 9, 30), et_at(day, 16, 0))
            if et_at(day, 9, 30) <= ts < et_at(day, 16, 0)}
    d.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows))
    return rows


# ---- crypto (Binance) ------------------------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def crypto_day(symbol: str, day: dt.date) -> dict[int, list]:
    """{unix_s: [o, h, l, c, v]} for one UTC day of Binance spot 1-minute klines."""
    d = BARS / "binance" / symbol / "1m"
    p = d / f"{day.isoformat()}.json"
    if p.exists():
        raw = json.loads(p.read_text())
    else:
        if day >= dt.datetime.now(UTC).date():
            raise NoBars(f"{symbol} {day} not closed yet")
        t0 = int(dt.datetime.combine(day, dt.time(0, 0), UTC).timestamp()) * 1000
        raw, start = [], t0
        while start < t0 + 86_400_000:
            try:
                r = httpx.get(BINANCE, params={"symbol": symbol, "interval": "1m", "startTime": start,
                                               "endTime": t0 + 86_400_000 - 1, "limit": 1000}, timeout=30)
            except httpx.HTTPError as e:
                raise NoBars(f"binance {symbol}: {type(e).__name__}") from e
            if r.status_code != 200:
                raise NoBars(f"binance {symbol} http {r.status_code}")
            page = [[k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in r.json()]
            if not page:
                break
            raw += page
            start = page[-1][0] + 60_000
        d.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(raw))
    return {int(k[0] // 1000): list(k[1:]) for k in raw}


# ---- one API for both markets ----------------------------------------------------------------------------------

def day_of(market: str, ts: int) -> dt.date:
    return et_date(ts) if market == "us_equities" else dt.datetime.fromtimestamp(ts, UTC).date()


def day_bars(market: str, symbol: str, day: dt.date) -> dict[int, list]:
    return stock_day(symbol, day) if market == "us_equities" else crypto_day(symbol, day)


def first_at_or_after(market: str, symbol: str, ts: int, max_days: int = 7) -> tuple[int, list] | None:
    """The first bar whose open time is >= ts (rolling into later sessions), as (bar_ts, [o, h, l, c, v])."""
    day = day_of(market, ts)
    for _ in range(max_days + 1):
        bars = day_bars(market, symbol, day)
        later = [k for k in bars if k >= ts]
        if later:
            k = min(later)
            return k, bars[k]
        day += dt.timedelta(days=1)
    return None


def between(market: str, symbol: str, t0: int, t1: int):
    """Bars with t0 <= open time < t1, in time order."""
    day, last = day_of(market, t0), day_of(market, t1)
    while day <= last:
        bars = day_bars(market, symbol, day)
        for k in sorted(bars):
            if t0 <= k < t1:
                yield k, bars[k]
        day += dt.timedelta(days=1)


def sessions(start: dt.date, end: dt.date, market: str, symbol: str) -> list[dt.date]:
    """Days in [start, end] that have bars for symbol (trading sessions for stocks, every day for crypto)."""
    out, day = [], start
    while day <= end:
        if day_bars(market, symbol, day):
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def last_close_on(market: str, symbol: str, day: dt.date) -> float | None:
    bars = day_bars(market, symbol, day)
    return bars[max(bars)][3] if bars else None


def daily_closes(market: str, symbol: str, start: dt.date, end: dt.date) -> dict[str, float]:
    """{date: close} for [start, end] in one request (Alpaca 1Day for stocks, Binance 1d for crypto), cached."""
    p = BARS / "daily" / f"{symbol}_{start}_{end}.json"
    if p.exists():
        return json.loads(p.read_text())
    out = {}
    if market == "us_equities" and not has_alpaca():
        for ts, v in _yahoo(symbol, "1d", et_at(start, 0, 0), et_at(end, 23, 59)):
            out[et_date(ts).isoformat()] = v[3]
    elif market == "us_equities":
        params = {"timeframe": "1Day", "start": start.isoformat(), "end": to_iso(et_at(end, 17, 0)),  # never today
                  "limit": 10000, "feed": os.getenv("ALPACA_FEED", "sip"), "adjustment": "raw"}
        for b in _alpaca_get(f"{symbol}/bars", params).get("bars") or []:
            out[et_date(to_ts(b["t"])).isoformat()] = b["c"]
    else:
        t0 = int(dt.datetime.combine(start, dt.time(0, 0), UTC).timestamp()) * 1000
        t1 = int(dt.datetime.combine(end, dt.time(23, 59), UTC).timestamp()) * 1000
        r = httpx.get(BINANCE, params={"symbol": symbol, "interval": "1d", "startTime": t0, "endTime": t1,
                                       "limit": 1000}, timeout=30)
        if r.status_code != 200:
            raise NoBars(f"binance {symbol} 1d http {r.status_code}")
        for k in r.json():
            out[dt.datetime.fromtimestamp(k[0] // 1000, UTC).date().isoformat()] = float(k[4])
    out = {k: v for k, v in sorted(out.items()) if start.isoformat() <= k <= end.isoformat()}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    return out
