"""Strategy lab, step 1: pick the "other stocks" universe by rule, from data before the test window only.

Rule v1 ranked crypto-linked names by correlation with BTC/USD daily closes (UTC midnight) and picked industrials and
brokers (CSW, AZZ, TTEK...): the clocks don't line up. v2 (this file) ranks by correlation with IBIT, which trades
on the same clock, and picks the crypto list before the hot list; over 60 sessions it still picked banks and brokers
(WT, TTEK, SNX: 60 points of noise rank above weakly linked names). v3 (this file): one year of sessions, and a
crypto-linked stock must also move at least as much as bitcoin (beta to IBIT >= 1). All three read only data up to
2025-09-12.

Spec: notes/research/strategy-as-code.md, section "Universe (b)". Run once, before any test-window price is read:
    cd app && uv run python -m backtest.lab_universe
Reads Alpaca's asset list and daily bars up to 2025-09-12 (the last session of his window). Writes data/lab/universe.json (gitignored) and prints the lists,
which the spec file records verbatim. Never prints key values.
"""
import datetime as dt
import json
import math
import os
import re
import sys

import httpx

from .common import DATA, has_alpaca

PAPER = "https://paper-api.alpaca.markets/v2/assets"
STOCK_BARS = "https://data.alpaca.markets/v2/stocks/bars"
ANCHOR = "IBIT"   # the spot-bitcoin ETF: bitcoin's price on the stock market's own clock (a reference, never traded)

ASOF = dt.date(2025, 9, 12)            # last session of his window; nothing after it is read here
ADV_FROM = dt.date(2025, 8, 15)         # 20 sessions ending ASOF (2025-08-15 .. 2025-09-12)
CORR_FROM = dt.date(2024, 9, 12)        # one year ending ASOF (a stock listed later: 60+ sessions)
NOT_COMMON = re.compile(r"\b(ETF|ETN|ETP|Trust|Fund|ProShares|Direxion|iShares|SPDR|Invesco|Leveraged|Inverse|"
                        r"Daily Target|Bull|Bear|Ultra|[0-9.]+[xX]|Warrants?|Units?|Rights?|Preferred|Notes?)\b",
                        re.I)
HOT_N, HOT_MIN_ADV, HOT_MIN_PX = 20, 100e6, 5.0
CRYPTO_N, CRYPTO_MIN_ADV, CRYPTO_MIN_PX = 10, 20e6, 1.0
CRYPTO_MIN_CORR, CRYPTO_MIN_BETA, CRYPTO_MIN_DAYS = 0.4, 1.0, 60


def _hdr() -> dict:
    return {"APCA-API-KEY-ID": os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY") or "",
            "APCA-API-SECRET-KEY": os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY") or ""}


def his_tickers() -> set[str]:
    """Every ticker in his record (LPP v1 and v2 events) plus every name in the code's ticker groups."""
    from .strategy import TICKER_GROUPS
    out = {t for ts in TICKER_GROUPS.values() for t in ts}
    for name in ("events.jsonl", "v2/events.jsonl"):
        p = DATA / "lpp" / name
        if p.exists():
            for line in p.open():
                t = json.loads(line).get("ticker")
                if t:
                    out.add(t)
    return out


def assets() -> list[dict]:
    r = httpx.get(PAPER, params={"status": "active", "asset_class": "us_equity"}, headers=_hdr(), timeout=60)
    r.raise_for_status()
    return [a for a in r.json() if a.get("tradable") and a.get("exchange") in ("NASDAQ", "NYSE", "AMEX", "ARCA",
                                                                                "BATS")]


def daily(symbols: list[str], start: dt.date, end: dt.date) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for i in range(0, len(symbols), 200):
        token = None
        while True:
            params = {"symbols": ",".join(symbols[i:i + 200]), "timeframe": "1Day", "start": start.isoformat(),
                      "end": end.isoformat(), "limit": 10000, "adjustment": "split", "feed": "sip"}
            if token:
                params["page_token"] = token
            r = httpx.get(STOCK_BARS, params=params, headers=_hdr(), timeout=60)
            r.raise_for_status()
            js = r.json()
            for s, bars in (js.get("bars") or {}).items():
                out.setdefault(s, []).extend(bars)
            token = js.get("next_page_token")
            if not token:
                break
    return out


def corr(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else 0.0


def beta(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    vy = sum((y - my) ** 2 for y in ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vy if vy else 0.0


def pick() -> dict:
    excl = his_tickers()
    universe = [a for a in assets() if not NOT_COMMON.search(a.get("name") or "") and a["symbol"] not in excl]
    names = {a["symbol"]: a["name"] for a in universe}
    print(f"{len(universe)} active common stocks after the name and his-ticker exclusions", file=sys.stderr)
    bars = daily(sorted(names), ADV_FROM, ASOF)
    stats = {}
    for s, bs in bars.items():
        bs = [b for b in bs if b["t"][:10] <= ASOF.isoformat()]
        if len(bs) < 18 or bs[-1]["t"][:10] != ASOF.isoformat():
            continue
        adv = sum(b["c"] * b["v"] for b in bs) / len(bs)
        rng = sum((b["h"] - b["l"]) / b["o"] for b in bs if b["o"]) / len(bs)
        stats[s] = {"adv_usd": adv, "range_pct": 100 * rng, "close": bs[-1]["c"]}
    pool = sorted(s for s, v in stats.items() if v["adv_usd"] >= CRYPTO_MIN_ADV and v["close"] >= CRYPTO_MIN_PX)
    long_bars = daily(pool + [ANCHOR], CORR_FROM, ASOF)
    anchor = {b["t"][:10]: b["c"] for b in long_bars.pop(ANCHOR) if b["t"][:10] <= ASOF.isoformat()}
    cs, betas = {}, {}
    for s in pool:
        closes = {b["t"][:10]: b["c"] for b in long_bars.get(s, []) if b["t"][:10] <= ASOF.isoformat()}
        days = [d for d in sorted(closes) if d in anchor]
        if len(days) < CRYPTO_MIN_DAYS:
            continue
        xs = [closes[days[i]] / closes[days[i - 1]] - 1 for i in range(1, len(days))]
        ys = [anchor[days[i]] / anchor[days[i - 1]] - 1 for i in range(1, len(days))]
        cs[s], betas[s] = corr(xs, ys), beta(xs, ys)
    crypto = sorted((s for s in cs if cs[s] >= CRYPTO_MIN_CORR and betas[s] >= CRYPTO_MIN_BETA),
                    key=lambda s: (-cs[s], s))[:CRYPTO_N]
    hot = sorted((s for s, v in stats.items() if v["adv_usd"] >= HOT_MIN_ADV and v["close"] >= HOT_MIN_PX
                  and s not in crypto), key=lambda s: (-stats[s]["range_pct"], s))[:HOT_N]
    row = lambda s: {"ticker": s, "name": names[s], "adv_usd_m": round(stats[s]["adv_usd"] / 1e6, 1),
                     "range_pct": round(stats[s]["range_pct"], 2), "close": stats[s]["close"],
                     **({"ibit_corr": round(cs[s], 3), "ibit_beta": round(betas[s], 2)} if s in cs else {})}
    return {"asof": ASOF.isoformat(), "excluded_his": sorted(excl), "hot": [row(s) for s in hot],
            "crypto": [row(s) for s in crypto], "pool_sizes": {"common": len(universe), "with_stats": len(stats),
                                                                "crypto_pool": len(pool), "with_corr": len(cs)}}


def main() -> int:
    if not has_alpaca():
        print("no Alpaca keys in .env", file=sys.stderr)
        return 2
    out = pick()
    p = DATA / "lab" / "universe.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1))
    for k in ("hot", "crypto"):
        print(k)
        for r in out[k]:
            print("  ", r)
    print(out["pool_sizes"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
