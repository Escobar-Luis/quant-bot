"""One cost module for the copy-trade engine and the strategy lab: contracts.md rule 5's three cost cases.

  simple     5 bps a side, 20 bps under $10, 25 bps crypto; no borrow fee (what `portfolios` use)
  realistic  spread + slippage by price and 20-session dollar volume, plus a borrow fee on shorts per day held
  x2         realistic with every per-side cost and every borrow rate doubled

Borrow flags: Alpaca's `easy_to_borrow` (today's, not the trade date's: spec-audit story 32), cached in
data/lab/assets.json; a failed lookup is cached as null ("unknown", charged the hard-to-borrow rate) and retried on
the next run. Daily dollar volumes: Alpaca 1Day raw bars, cached in data/bars/daily_dv/<T>.json ({} = fetch failed).
"""
import datetime as dt
import json
import os

import httpx

from . import bars as B
from .common import BARS, COSTS_BPS, DATA

CASES = ("simple", "realistic", "x2")
DEFAULT_CASE = "realistic"
ADV_THIN = 50e6                                   # 20-session average daily dollar volume under this: +10 bps
BORROW_PCT_YR = {"easy": 0.5, "hard": 30.0, "unknown": 30.0, "crypto": 10.0}
DAYS_PER_YEAR = 360                               # borrow fees accrue on a 360-day year
DV_FROM, DV_TO = dt.date(2024, 6, 1), dt.date(2026, 10, 16)   # daily volumes cached for every window
ASSETS = DATA / "lab" / "assets.json"
CHECKED = DATA / "lab" / "assets_checked.json"

MODELS = {
    "simple": "5 bps a side, 20 bps under $10, 25 bps crypto; no borrow fee (contracts rule 5, the original)",
    "realistic": "spread and slippage a side: 5 bps at $10+, 30 bps from $5 to $10, 50 bps under $5, +10 bps when "
                 "the 20-session average dollar volume is under $50M; crypto 25 bps. Shorts pay a borrow fee per "
                 "day held: 0.5% a year easy to borrow, 30% hard or unknown, 10% crypto",
    "x2": "realistic with every cost and borrow rate doubled",
}
BPS_PER_SIDE = {"simple": COSTS_BPS,
                "realistic": {"stocks_10_up": 5, "stocks_5_to_10": 30, "stocks_under_5": 50,
                              "thin_volume_add": 10, "thin_volume_under_usd": ADV_THIN, "crypto": 25},
                "x2": "realistic x 2"}


# ---- per-side cost ---------------------------------------------------------------------------------------------

def simple_bps(market: str, px: float) -> float:
    if market == "crypto":
        return COSTS_BPS["crypto"]
    return COSTS_BPS["stocks_under_10"] if px < 10 else COSTS_BPS["stocks"]


def realistic_bps(market: str, px: float, adv: float | None) -> float:
    if market == "crypto":
        return 25
    return (50 if px < 5 else 30 if px < 10 else 5) + (10 if (adv or 0.0) < ADV_THIN else 0)


def side_bps(case: str, market: str, px: float, adv: float | None = None) -> float:
    if case == "simple":
        return simple_bps(market, px)
    if case == "realistic":
        return realistic_bps(market, px, adv)
    if case == "x2":
        return 2 * realistic_bps(market, px, adv)
    raise ValueError(f"unknown cost case {case}")


# ---- borrow ----------------------------------------------------------------------------------------------------

def flag_word(market: str, easy: bool | None) -> str:
    if market == "crypto":
        return "crypto"
    return "unknown" if easy is None else "easy" if easy else "hard"


def borrow_pct(case: str, flag: str) -> float:
    if case == "simple":
        return 0.0
    return BORROW_PCT_YR[flag] * (2 if case == "x2" else 1)


def days_held(d0: dt.date, d1: dt.date) -> int:
    return max(1, (d1 - d0).days)


def borrow_usd(case: str, flag: str, value: float, days: int) -> float:
    """The fee for covering shares whose entry value is `value`, held `days` calendar days."""
    return value * borrow_pct(case, flag) / 100 / DAYS_PER_YEAR * days


def _hdr() -> dict:
    return {"APCA-API-KEY-ID": os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY") or "",
            "APCA-API-SECRET-KEY": os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY") or ""}


def borrow_flags(tickers) -> dict[str, bool | None]:
    """{ticker: easy_to_borrow} from Alpaca's asset list (today's flag), cached in data/lab/assets.json with the
    lookup date in data/lab/assets_checked.json. A lookup that fails is cached as null and retried next run."""
    have = json.loads(ASSETS.read_text()) if ASSETS.exists() else {}
    when = json.loads(CHECKED.read_text()) if CHECKED.exists() else {}
    today = dt.date.today().isoformat()
    for t in sorted(set(tickers)):
        if have.get(t) is None:
            try:
                r = httpx.get(f"https://paper-api.alpaca.markets/v2/assets/{t}", headers=_hdr(), timeout=30)
                have[t] = bool(r.json()["easy_to_borrow"]) if r.status_code == 200 else None
            except (httpx.HTTPError, KeyError, ValueError):
                have[t] = None
            when[t] = today
        when.setdefault(t, today)
    ASSETS.parent.mkdir(parents=True, exist_ok=True)
    ASSETS.write_text(json.dumps(have, indent=1, sort_keys=True))
    CHECKED.write_text(json.dumps(when, indent=1, sort_keys=True))
    return {t: have[t] for t in tickers}


def checked_dates(tickers) -> dict[str, str]:
    when = json.loads(CHECKED.read_text()) if CHECKED.exists() else {}
    return {t: when[t] for t in tickers if t in when}


# ---- daily dollar volume ---------------------------------------------------------------------------------------

def dv_path(ticker: str):
    return BARS / "daily_dv" / f"{ticker}.json"


def daily_dv(ticker: str) -> dict[str, list]:
    """{ET date: [raw close, volume]} from DV_FROM to DV_TO (Alpaca 1Day raw), cached; {} when the fetch fails."""
    p = dv_path(ticker)
    if p.exists():
        return json.loads(p.read_text())
    out, token = {}, None
    try:
        while True:
            params = {"timeframe": "1Day", "start": DV_FROM.isoformat(), "end": B.to_iso(B.et_at(DV_TO, 17, 0)),
                      "limit": 10000, "feed": os.getenv("ALPACA_FEED", "sip"), "adjustment": "raw"}
            if token:
                params["page_token"] = token
            js = B._alpaca_get(f"{ticker}/bars", params)
            for b in js.get("bars") or []:
                out[B.et_date(B.to_ts(b["t"])).isoformat()] = [b["c"], b["v"]]
            token = js.get("next_page_token")
            if not token:
                break
    except B.NoBars:
        out = {}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    return out


_ADV: dict[tuple[str, str], float] = {}


def adv_before(ticker: str, day: dt.date) -> float:
    """Average raw close x volume over the 20 sessions before `day` (0.0 with none: thin)."""
    key = (ticker, day.isoformat())
    if key not in _ADV:
        dv = daily_dv(ticker)
        prev = sorted(d for d in dv if d < key[1])[-20:]
        _ADV[key] = sum(dv[d][0] * dv[d][1] for d in prev) / len(prev) if prev else 0.0
    return _ADV[key]


# ---- the model the engine prices fills with ---------------------------------------------------------------------

class Model:
    """One cost case for the engine: per-side cost of a fill, and the borrow fee of a cover."""

    def __init__(self, case: str = "simple", flags: dict[str, str] | None = None):
        if case not in CASES:
            raise ValueError(f"unknown cost case {case}")
        self.case, self.flags = case, flags or {}

    def fee(self, market: str, ticker: str, px: float, qty: float, ts: int) -> float:
        if self.case == "simple":
            return px * qty * simple_bps(market, px) / 1e4
        adv = adv_before(ticker, B.et_date(ts)) if market == "us_equities" else None
        return px * qty * side_bps(self.case, market, px, adv) / 1e4

    def borrow(self, market: str, ticker: str, side: str, value: float, ts0: int, ts1: int) -> float:
        if self.case == "simple" or side != "short":
            return 0.0
        flag = "crypto" if market == "crypto" else self.flags.get(ticker, "unknown")
        return borrow_usd(self.case, flag, value, days_held(B.day_of(market, ts0), B.day_of(market, ts1)))


SIMPLE = Model("simple")
