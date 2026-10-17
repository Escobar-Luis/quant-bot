"""Price bars for plausibility checks and the copy-the-host test.

Daily bars come from yfinance (cached per ticker in data/bars/yf_1d/). 1-minute bars for 2024-25 need Alpaca
keys (APCA_API_KEY_ID / APCA_API_SECRET_KEY in ~/dev/quant-bot/.env); without them minute() returns None and
every minute-level check stays null.
"""
import datetime as dt
import json
import os
import sys
import threading
import time
from zoneinfo import ZoneInfo

from .common import BARS, has_alpaca

ET = ZoneInfo("America/New_York")
START, END = "2024-08-01", "2025-09-30"
_daily: dict[str, dict] = {}
_warned: set[int] = set()


def _write(p, obj):
    """Atomic cache write: worker threads may read the same ticker's file while another writes it."""
    tmp = p.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(obj))
    os.replace(tmp, p)


def session_date(unix_ts: float) -> str:
    return dt.datetime.fromtimestamp(unix_ts, ET).date().isoformat()


def daily(ticker: str) -> dict | None:
    """{date: [open, high, low, close, volume]} for the extraction window, or None when the symbol has no data."""
    if ticker in _daily:
        return _daily[ticker]
    d = BARS / "yf_1d"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{ticker}.json"
    if p.exists():
        rows = json.loads(p.read_text())
    else:
        import yfinance as yf
        try:
            df = yf.Ticker(ticker).history(start=START, end=END, interval="1d", auto_adjust=False, raise_errors=True)
            rows = {i.date().isoformat(): [float(r.Open), float(r.High), float(r.Low), float(r.Close), int(r.Volume)]
                    for i, r in df.iterrows()}
        except Exception as e:  # noqa: BLE001
            # an unknown symbol is cached as {} ("no such ticker"); a network or rate-limit error is not cached
            if "rate" in str(e).lower() or "timed out" in str(e).lower() or "connection" in str(e).lower():
                return None
            rows = {}
        _write(p, rows)
    _daily[ticker] = rows or None
    return _daily[ticker]


def day_bar(ticker: str, date: str) -> list | None:
    rows = daily(ticker)
    return rows.get(date) if rows else None


def minute(ticker: str, date: str) -> dict | None:
    """{unix_minute: [o, h, l, c, v]} for one regular session, from Alpaca (cached), else None."""
    if not has_alpaca():
        return None
    d = BARS / "alpaca_1m" / ticker
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{date}.json"
    if p.exists():
        return {int(k): v for k, v in json.loads(p.read_text()).items()} or None
    import httpx
    key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
    sec = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
    day = dt.date.fromisoformat(date)
    t0 = dt.datetime.combine(day, dt.time(9, 30), ET).astimezone(dt.UTC)
    t1 = dt.datetime.combine(day, dt.time(16, 0), ET).astimezone(dt.UTC)
    rows, token = {}, None
    while True:
        params = {"timeframe": "1Min", "start": t0.isoformat().replace("+00:00", "Z"),
                  "end": t1.isoformat().replace("+00:00", "Z"), "limit": 10000, "feed": os.getenv("ALPACA_FEED", "sip"),
                  "adjustment": "raw"}
        if token:
            params["page_token"] = token
        for wait in (0, 5, 20, 60):
            time.sleep(wait)
            try:
                r = httpx.get(f"https://data.alpaca.markets/v2/stocks/{ticker}/bars", params=params,
                              headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}, timeout=30)
            except httpx.HTTPError:
                continue
            if r.status_code != 429:
                break
        else:
            return None
        if r.status_code != 200:
            if r.status_code not in _warned:  # say once why minute bars are missing (403: feed not in plan)
                _warned.add(r.status_code)
                print(f"alpaca {r.status_code} for {ticker} {date}: {r.text[:120]}", file=sys.stderr)
            return None
        js = r.json()
        for b in js.get("bars") or []:
            ts = int(dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp())
            rows[ts] = [b["o"], b["h"], b["l"], b["c"], b["v"]]
        token = js.get("next_page_token")
        if not token:
            break
    _write(p, rows)
    return {int(k): v for k, v in rows.items()} or None
