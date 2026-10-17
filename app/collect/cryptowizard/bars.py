"""Keyless Binance 1-minute bars, cached per symbol per UTC day.

Cache: DATA_DIR/bars/binance/<SYMBOL>/1m/<YYYY-MM-DD>.json = [[open_ms, open, high, low, close, volume], ...]
Source: data-api.binance.vision/api/v3/klines (public market data, no key).

Run: python bars.py            # fetch every day the calls need (post day .. +HORIZON_DAYS)
"""
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request

from common import BARS, CW, read_jsonl

API = "https://data-api.binance.vision/api/v3"
HORIZON_DAYS = 7  # assumed max holding for a "Risky-Scalp"; the posts state no time limit


def _get(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-bot/0.1"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                raise
            time.sleep(2 ** k)
        except Exception:  # noqa: BLE001
            time.sleep(2 ** k)
    raise RuntimeError(f"failed: {url[:120]}")


def listed_symbols(symbols):
    """Return {symbol: status} for symbols Binance spot knows (missing ones are absent)."""
    out = {}
    for s in symbols:
        try:
            info = _get(f"{API}/exchangeInfo?symbol={s}")
            out[s] = info["symbols"][0]["status"]
        except urllib.error.HTTPError:
            pass
    return out


def day_path(symbol, day):
    return BARS / symbol / "1m" / f"{day.isoformat()}.json"


def fetch_day(symbol, day):
    """All 1440 minutes of one UTC day (fewer if the day is today or the pair is new)."""
    p = day_path(symbol, day)
    today = dt.datetime.now(dt.timezone.utc).date()
    if p.exists() and day < today:
        return json.loads(p.read_text())
    start = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
    end = start + 86_400_000
    rows, cur = [], start
    while cur < end:
        batch = _get(f"{API}/klines?symbol={symbol}&interval=1m&startTime={cur}&endTime={end - 1}&limit=1000")
        if not batch:
            break
        rows += [[b[0], float(b[1]), float(b[2]), float(b[3]), float(b[4]), float(b[5])] for b in batch]
        cur = batch[-1][0] + 60_000
        time.sleep(0.12)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows))
    return rows


def bars_between(symbol, t0_ms, t1_ms):
    """1-minute bars with open time in [t0, t1), from the cache (fetching missing days)."""
    d0 = dt.datetime.fromtimestamp(t0_ms / 1000, dt.timezone.utc).date()
    d1 = dt.datetime.fromtimestamp((t1_ms - 1) / 1000, dt.timezone.utc).date()
    out, d = [], d0
    while d <= d1:
        out += [b for b in fetch_day(symbol, d) if t0_ms <= b[0] < t1_ms]
        d += dt.timedelta(days=1)
    return out


def iso_ms(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def main():
    events = read_jsonl(CW / "events.calls.jsonl")
    calls = [e for e in events if e["type"] == "call"]
    symbols = sorted({e["pair"] for e in calls})
    listed = listed_symbols(symbols)
    print("symbols", len(symbols), "listed on Binance spot", len(listed), "missing", sorted(set(symbols) - set(listed)))
    (CW / "binance_symbols.json").write_text(json.dumps(listed, indent=1))
    need = set()
    for e in events:
        if e.get("pair") not in listed:
            continue
        d = dt.datetime.fromtimestamp(iso_ms(e["wall_utc"]) / 1000, dt.timezone.utc).date()
        span = HORIZON_DAYS + 1 if e["type"] == "call" else 0
        for k in range(span + 1):
            need.add((e["pair"], d + dt.timedelta(days=k)))
    today = dt.datetime.now(dt.timezone.utc).date()
    need = sorted(x for x in need if x[1] <= today)
    print("symbol-days to cache", len(need), flush=True)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        for i, _ in enumerate(ex.map(lambda x: fetch_day(*x), need)):
            if i % 100 == 0:
                print(i, flush=True)
    print("done", len(need))


if __name__ == "__main__":
    sys.exit(main())
