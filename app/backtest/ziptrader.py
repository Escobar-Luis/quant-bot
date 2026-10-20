"""ZipTrader: the morning briefing's calls -> copyable positions, only when a call says which way to trade.

Reads data/ziptrader/events.jsonl (story/collect-ziptrader). Most briefing items are watch-list notes ("whether
$32 holds") with no direction: they are counted, not traded. A call with a side enters at post time + delay (a
pre-market post fills at the first regular-session bar). The extracted `horizon` decides the kind (rules 4, 8,
12a): "N days/sessions/weeks" is a swing trade held N sessions; a longer-than-a-session phrase with no count ("more
than one session", "overnight") is a swing trade with rule 4's 5-session default; anything else is a day trade.
"""
import json
import re

from . import bars
from .common import DATA, has_alpaca
from .engine import Leg, Position

COURSE, NAME, MARKET = "ziptrader", "ZipTrader", "us_equities"
WINDOW = {"start": "2026-10-01", "end": "2026-10-16", "sealed_from": "2026-10-01"}
HOLD = {"symbol": "SPY", "label": "Just holding", "what": "Buy and keep the S&P 500 (SPY)"}
SIZING = "$1,000 per call (they never state a size)"
CHANNEL = "#morning-briefing"


def words(text: str | None, n: int) -> str | None:
    if not text:
        return None
    w = text.split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


def cite(e: dict) -> dict:
    return {"source_id": e["source_id"], "locator": e["source_id"].rsplit("/", 1)[-1],
            "label": f"{CHANNEL}, {e['wall_utc'][:10]}"}


HORIZON_N = re.compile(r"(\d+)\s*(day|session|week)", re.I)
HORIZON_LONG = re.compile(r"\b(?:more than|over|several|multiple|a few|next)\s+(?:\w+\s+)?(?:trading\s+)?"
                          r"(?:sessions?|days?|weeks?)\b|\bovernight\b|\bmulti-?day\b", re.I)


def default_exit(horizon: str | None) -> str:
    """Rule 4's "horizon as written" (the extraction's `horizon` field, rule 12a) -> the default exit."""
    m = HORIZON_N.search(horizon or "")
    if m:
        return f"sessions:{int(m.group(1)) * (5 if m.group(2).lower() == 'week' else 1)}"
    return "sessions:5" if HORIZON_LONG.search(horizon or "") else "day_close"


def build(version: str) -> dict:
    p = DATA / "ziptrader" / "events.jsonl"
    evs = [json.loads(line) for line in open(p) if line.strip()]
    items = [e for e in evs if e["type"] in ("call", "setup", "trade") and e["status"] == "ok" and e.get("ticker")]
    positions, watch = [], 0
    for e in sorted(items, key=lambda e: e["wall_utc"]):
        if e.get("side") not in ("long", "short"):
            watch += 1
            continue
        exit_ = default_exit(e.get("horizon"))
        positions.append(Position(
            pid=f"zt-{e['event_id'].split(':', 1)[-1].replace(':', '-')}", course=COURSE, market=MARKET,
            ticker=e["ticker"], side=e["side"], portfolio="day" if exit_ == "day_close" else "swing",
            legs=[Leg(e["event_id"], bars.post_ts(e["wall_utc"]), "open")],
            default_exit=exit_, stop=e.get("stop"), targets=list(e.get("targets") or []),
            trigger=e.get("entry"), quote=words(e.get("quote"), 12), cite=cite(e)))
    rules = [{"id": f"R{i + 1}", "text": e["rule"], "quote": words(e["quote"], 12), "testable": False, "cite": cite(e)}
             for i, e in enumerate([e for e in evs if e["type"] == "rule" and e["status"] == "ok" and e.get("rule")
                                    and len(e["rule"].split()) <= 15][:12])]
    return {"positions": positions, "options_count": 0, "rules": rules, "days": None,
            "stats": {"watch_only": watch, "briefings": len({e["source_id"] for e in evs})},
            "checks": {"events_total": len(evs), "events_ok": sum(e["status"] == "ok" for e in evs),
                       "needs_review": sum(e["status"] != "ok" for e in evs), "briefing_items": len(items),
                       "watch_only": watch}}


def unknown(stats, assumed, priced, total, status) -> list[str]:
    out = [f"{stats['watch_only']} briefing items are watch-list notes with no direction: counted, not traded.",
           f"Only {stats['briefings']} briefings ({WINDOW['start']} to {WINDOW['end']}): too few to judge."]
    if assumed.get("swing"):
        out.append(f"Exit assumed at the stated horizon (5 sessions when no count) for {assumed['swing']} "
                   "calls with no exit.")
    if assumed.get("day"):
        out.append(f"Exit assumed at 15:55 for {assumed['day']} calls with no exit.")
    out.append("$1,000 per call: they never state a size.")
    out.append(f"Prices are {'Alpaca' if has_alpaca() else 'Yahoo'} 1-minute bars; costs 5 bps per side.")
    out.append("Just holding SPY leaves out its dividends (about 1% a year).")
    return out
