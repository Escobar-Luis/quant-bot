"""Hand-check one trade straight from the raw bar cache, without the engine (lanes.md story 1, acceptance 3).

  cd app && uv run python -m backtest.handcheck --course lpp --version v1 [--trade <trade_id>] [--delay 5]

Reads results/<course>/<version>.json, takes the trade's posted_at, adds the delay, finds the first cached
1-minute bar whose open time is at or after that moment, and checks its open equals the file's entry price.
"""
import argparse
import datetime as dt
import json

from .bars import BARS, ET, to_iso, to_ts
from .common import RESULTS


def raw_bars(market: str, symbol: str, day: dt.date) -> dict[int, float]:
    """{bar open unix_s: open} read directly from the cache files."""
    if market == "us_equities":
        p = BARS / "alpaca_1m" / symbol / f"{day.isoformat()}.json"
        return {int(k): v[0] for k, v in json.loads(p.read_text()).items()} if p.exists() else {}
    p = BARS / "binance" / symbol / "1m" / f"{day.isoformat()}.json"
    return {int(k[0] // 1000): k[1] for k in json.loads(p.read_text())} if p.exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--version", default="v1")
    ap.add_argument("--trade", default=None)
    ap.add_argument("--delay", type=int, default=5)
    a = ap.parse_args()
    res = json.loads((RESULTS / a.course / f"{a.version}.json").read_text())
    market = "crypto" if a.course == "cryptowizard" else "us_equities"
    trades = [t for t in res["trades"] if (a.trade is None or t["trade_id"] == a.trade)
              and t["by_delay"].get(str(a.delay), {}).get("entry") is not None]
    t = trades[0]
    row = t["by_delay"][str(a.delay)]
    want = to_ts(t["posted_at"]) + a.delay * 60
    symbol = t["ticker"]
    day = dt.datetime.fromtimestamp(want, ET if market == "us_equities" else dt.UTC).date()
    b = {}
    for i in range(7):
        b = {k: v for k, v in raw_bars(market, symbol, day + dt.timedelta(days=i)).items() if k >= want}
        if b:
            break
    bar_ts = min(b)
    ok = to_iso(bar_ts) == row["entry_at"] and abs(b[bar_ts] - row["entry"]) < 1e-6
    print(f"trade      {t['trade_id']} {symbol} {t['side']} ({t['portfolio']})")
    print(f"posted_at  {t['posted_at']}  ({dt.datetime.fromtimestamp(to_ts(t['posted_at']), ET):%H:%M:%S} ET)")
    print(f"+ delay    {a.delay} min -> {to_iso(want)}")
    print(f"first bar  {to_iso(bar_ts)} open {b[bar_ts]}  (raw cache file)")
    print(f"file says  {row['entry_at']} entry {row['entry']}")
    print("MATCH" if ok else "MISMATCH")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
