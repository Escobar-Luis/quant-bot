"""Learn Plan Profit: the host's announced trades (open, add, trim, close) -> copyable positions.

Reads data/lpp/events.jsonl (v1) or data/lpp/v2/events.jsonl (v2), written by story/extract-lpp. Only `trade`
events are copied. Events that failed a code check are left out, except the ledger checks
(`open_never_closed`, `close_without_open`, `qty_exceeds_position`), which this ledger resolves itself: a position
he still holds at the end of a session carries to a later session only when his next word on it (within 7 days)
is an add, trim or close; otherwise it leaves at 15:55 ET (assumed).
"""
import datetime as dt
import json
from collections import Counter

from . import bars
from .common import DATA
from .engine import Leg, Position

COURSE, NAME, MARKET = "lpp", "Learn Plan Profit", "us_equities"
WINDOW = {"start": "2024-08-15", "end": "2025-09-12", "sealed_from": "2025-06-12"}
HOLD = {"symbol": "SPY", "label": "Just holding", "what": "Buy and keep the S&P 500 (SPY)"}
LEDGER_FAILS = {"open_never_closed", "close_without_open", "qty_exceeds_position"}
CARRY_DAYS = 7
OPTION_WORDS = ("option", "call", "put")


def events_path(version: str):
    return DATA / "lpp" / ("events.jsonl" if version == "v1" else f"{version}/events.jsonl")


def load(version: str) -> list[dict]:
    return [json.loads(line) for line in open(events_path(version)) if line.strip()]


def words(text: str | None, n: int) -> str | None:
    if not text:
        return None
    w = text.split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


def cite(e: dict) -> dict:
    t = int(e.get("t_s") or 0)
    return {"source_id": e["source_id"], "locator": f"t={t}s",
            "label": f"Live session, {e['session_date']}, {t // 60}:{t % 60:02d}"}


def usable(e: dict) -> bool:
    return e["type"] == "trade" and bool(e.get("ticker")) and bool(e.get("action")) and \
        (e["status"] == "ok" or set(e.get("fail") or []) <= LEDGER_FAILS)


def is_option(e: dict) -> bool:
    return any(w in (e.get("instrument") or "").lower() for w in OPTION_WORDS)


def build(version: str) -> dict:
    """Positions to copy, plus what the results file needs to say about the events."""
    evs = load(version)
    trades = sorted((e for e in evs if usable(e)), key=lambda e: bars.to_ts(e["wall_utc"]))
    options = [e for e in trades if is_option(e)]
    trades = [e for e in trades if not is_option(e) and e.get("side") in ("long", "short")]
    stats = Counter()
    positions, open_pos = [], {}

    def finish(key):
        legs, first = open_pos.pop(key)
        days = {bars.et_date(lg.posted_ts) for lg in legs}
        swing = len(days) > 1
        p = Position(pid=f"lpp-{first['source_id'][3:]}-{first['event_id'].rsplit(':', 1)[-1]}", course=COURSE,
                     market=MARKET, ticker=key[0], side=key[1], portfolio="swing" if swing else "day", legs=legs,
                     default_exit="sessions:5" if swing else "day_close", quote=words(first["quote"], 12),
                     cite=cite(first))
        positions.append(p)

    for i, e in enumerate(trades):
        key, ts = (e["ticker"], e["side"]), bars.to_ts(e["wall_utc"])
        if key in open_pos:
            last = open_pos[key][0][-1].posted_ts
            if bars.et_date(last) != bars.et_date(ts):
                carry = e["action"] in ("add", "trim", "close") and ts - last <= CARRY_DAYS * 86400
                if not carry:
                    finish(key)
        leg = Leg(e["event_id"], ts, e["action"], qty=e.get("qty"))
        if e["action"] in ("open", "add"):
            if key not in open_pos:
                open_pos[key] = ([], e)
            open_pos[key][0].append(leg)
        else:
            if key not in open_pos:
                stats["close_without_open"] += 1
                continue
            open_pos[key][0].append(leg)
            if e["action"] == "close":
                finish(key)
    for key in list(open_pos):
        finish(key)
    for e in trades:
        if e["action"] == "trim" and not e.get("qty"):
            stats["trim_size_unknown"] += 1
        if e["action"] in ("open", "add") and not e.get("qty"):
            stats["entry_size_unknown"] += 1

    rules = []
    for e in evs:
        if e["type"] == "rule" and e["status"] == "ok" and e.get("rule") and e.get("quote") \
                and len(e["quote"].split()) <= 12 and len(e["rule"].split()) <= 15:
            rules.append(e)
    step = max(1, len(rules) // 12)
    rules = [{"id": f"R{i + 1}", "text": e["rule"], "quote": e["quote"], "testable": False, "cite": cite(e)}
             for i, e in enumerate(rules[::step][:12])]

    days: dict[str, list] = {}
    for e in trades:
        t = dt.datetime.fromtimestamp(bars.to_ts(e["wall_utc"]), bars.ET)
        days.setdefault(e["session_date"], []).append(
            {"time_et": t.strftime("%H:%M"), "course": COURSE, "ticker": e["ticker"], "action": e["action"],
             "quote": words(e["quote"], 12)})

    return {
        "positions": positions,
        "options_count": len(options),
        "rules": rules,
        "days": days,
        "stats": stats,
        "checks": {"events_total": len(evs), "events_ok": sum(e["status"] == "ok" for e in evs),
                   "needs_review": sum(e["status"] != "ok" for e in evs),
                   "trade_events": sum(e["type"] == "trade" for e in evs), "trade_events_copied": len(trades)},
    }


SIZING = "His own share counts when he said them; $1,000 per entry when he didn't"


def unknown(stats, assumed, priced, total, status) -> list[str]:
    out = []
    if priced < total:
        out.append(f"Partial: {priced} of his {total} trades are priced so far.")
    if assumed.get("day"):
        out.append(f"Exit assumed at 15:55 for {assumed['day']} day trades he didn't say he closed.")
    if assumed.get("swing"):
        out.append(f"Exit assumed after 5 sessions for {assumed['swing']} swing trades he didn't say he closed.")
    if stats.get("trim_size_unknown"):
        out.append(f"Half the position assumed sold on {stats['trim_size_unknown']} trims with no size.")
    if stats.get("entry_size_unknown"):
        out.append(f"$1,000 assumed on {stats['entry_size_unknown']} entries with no share count.")
    if stats.get("close_without_open"):
        out.append(f"{stats['close_without_open']} exits had no matching entry and were skipped.")
    if status.get("no_bars"):
        out.append(f"{status['no_bars']} trade-delays had no price bars and were skipped.")
    out.append("Prices are 1-minute market bars, not his own fills.")
    out.append("Costs are estimates: 5 bps per side, 20 under $10.")
    return out
