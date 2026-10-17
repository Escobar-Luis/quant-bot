"""Price bars for plausibility checks and the copy-the-host test.

Daily bars come from yfinance (cached per ticker in data/bars/yf_1d/). 1-minute bars for 2024-25 need Alpaca
keys (APCA_API_KEY_ID / APCA_API_SECRET_KEY in ~/dev/quant-bot/.env); without them minute() returns None and
every minute-level check stays null.
"""
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

from .common import BARS, has_alpaca

ET = ZoneInfo("America/New_York")
START, END = "2024-08-01", "2025-09-30"
_daily: dict[str, dict] = {}


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
            df = yf.Ticker(ticker).history(start=START, end=END, interval="1d", auto_adjust=False)
            rows = {i.date().isoformat(): [float(r.Open), float(r.High), float(r.Low), float(r.Close), int(r.Volume)]
                    for i, r in df.iterrows()}
        except Exception:  # noqa: BLE001 - unknown symbols raise or return empty; both mean "no data"
            rows = {}
        p.write_text(json.dumps(rows))
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
        r = httpx.get(f"https://data.alpaca.markets/v2/stocks/{ticker}/bars", params=params,
                      headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}, timeout=30)
        if r.status_code != 200:
            return None
        js = r.json()
        for b in js.get("bars") or []:
            ts = int(dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp())
            rows[ts] = [b["o"], b["h"], b["l"], b["c"], b["v"]]
        token = js.get("next_page_token")
        if not token:
            break
    p.write_text(json.dumps(rows))
    return {int(k): v for k, v in rows.items()} or None
