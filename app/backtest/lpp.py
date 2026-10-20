"""Learn Plan Profit: the host's announced trades (open, add, trim, close) -> copyable positions.

Reads data/lpp/events.jsonl (v1) or data/lpp/v2/events.jsonl (v2), written by story/extract-lpp. Only `trade`
events are copied. Events that failed a code check are left out, except the ledger checks
(`open_never_closed`, `close_without_open`, `qty_exceeds_position`), which this ledger resolves itself.

Two ledgers (contracts.md):
- `no_look_ahead` (rule 13, the headline since spec-audit story 18): a position leaves at 15:55 ET of its first
  session unless one of its legs, posted before that moment, states a horizon past the session; a later word
  starts afresh. The host states he closes every day (his Discord chat, notes/sources/lpp-discord-exits.md).
  v1's horizons come from the hold-intent pass (spec-audit story 17, `horizon_source: hold_intent_v1`).
- `as_taught` (rule 11, the `as_taught_stitched` key): a position he still holds at the end of a session carries
  to a later session when his NEXT word on it (within 7 days) is an add, trim or close. That reads the future.
"""
import datetime as dt
import json
from collections import Counter
from functools import lru_cache

from . import bars
from .common import DATA
from .engine import Leg, Position
from .ziptrader import default_exit as horizon_exit

COURSE, NAME, MARKET = "lpp", "Learn Plan Profit", "us_equities"
WINDOW = {"start": "2024-08-15", "end": "2025-09-12", "sealed_from": "2025-06-12"}
HOLD = {"symbol": "SPY", "label": "Just holding", "what": "Buy and keep the S&P 500 (SPY)"}
LEDGER_FAILS = {"open_never_closed", "close_without_open", "qty_exceeds_position"}
CARRY_DAYS = 7                     # rule 11 (the `as_taught_stitched` key)
LEDGERS = ("no_look_ahead", "as_taught")   # rule 13 (the headline) | rule 11 (`as_taught_stitched`)
HEADLINE_LEDGER = "no_look_ahead"
OPTION_WORDS = ("option", "call", "put")


def events_path(version: str):
    return DATA / "lpp" / ("events.jsonl" if version == "v1" else f"{version}/events.jsonl")


def load(version: str, only: set[str] | None = None) -> list[dict]:
    evs = [json.loads(line) for line in open(events_path(version)) if line.strip()]
    return [e for e in evs if e["source_id"] in only] if only else evs


def proof_set() -> set[str]:
    """The 30 LPP sessions PRISM's evaluator scores for extract-lpp-v1 and -v2 (data/lpp/gold/proof_set.json)."""
    return {f"yt:{v}" for v in json.loads((DATA / "lpp" / "gold" / "proof_set.json").read_text())}


def words(text: str | None, n: int) -> str | None:
    if not text:
        return None
    w = text.split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


@lru_cache(maxsize=1)
def _session_keys() -> dict[str, str]:
    """video_id -> public session key "lpp:<date>" (data/lpp/session_keys.json, gitignored; PR #43)."""
    p = DATA / "lpp" / "session_keys.json"
    return {v["video_id"]: k for k, v in json.loads(p.read_text()).items()} if p.exists() else {}


def public_key(e: dict) -> str:
    """The session key public files use instead of the unlisted video ID."""
    return _session_keys().get(e["source_id"].split(":", 1)[-1]) or f"lpp:{e['session_date']}"


def cite(e: dict) -> dict:
    t = int(e.get("t_s") or 0)
    at = f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"
    return {"source_id": public_key(e), "locator": f"t={t}s", "label": f"Live session, {e['session_date']}, {at}"}


@lru_cache(maxsize=1)
def _release() -> dict[str, float]:
    """source_id -> the video's release time (data/lpp/sources.jsonl), for rule 1's post time."""
    p = DATA / "lpp" / "sources.jsonl"
    rows = [json.loads(line) for line in open(p) if line.strip()] if p.exists() else []
    return {s["source_id"]: bars.post_ts(s["release_utc"]) for s in rows if s.get("release_utc")}


def post_ts(e: dict) -> float:
    """Rule 1: release_timestamp + t_s, kept to the fraction of a second (wall_utc is the same moment truncated
    to the whole second, which can put a fill one bar early); wall_utc only when the release time is unknown."""
    r = _release().get(e["source_id"])
    return r + float(e.get("t_s") or 0) if r is not None else bars.post_ts(e["wall_utc"])


def usable(e: dict) -> bool:
    return e["type"] == "trade" and bool(e.get("ticker")) and bool(e.get("action")) and \
        (e["status"] == "ok" or (bool(e.get("fail")) and set(e["fail"]) <= LEDGER_FAILS))


def is_option(e: dict) -> bool:
    return any(w in (e.get("instrument") or "").lower() for w in OPTION_WORDS)


def session_end(day: dt.date, n: int) -> int:
    """Rule 13(b): 15:55 ET of the n-th weekday after `day` (n = 0: that day)."""
    while n > 0:
        day += dt.timedelta(days=1)
        n -= day.weekday() < 5
    return bars.et_at(day, 15, 55)


def horizon_sessions(e: dict) -> int:
    """Sessions past its own that a leg's stated horizon holds (the extraction's `horizon` field, rule 12a)."""
    ex = horizon_exit(e.get("horizon"))
    return int(ex.split(":")[1]) if ex.startswith("sessions:") else 0


def build(version: str, only: set[str] | None = None, ledger: str = HEADLINE_LEDGER) -> dict:
    """Positions to copy, plus what the results file needs to say about the events."""
    if ledger not in LEDGERS:
        raise ValueError(f"unknown ledger {ledger}")
    look_ahead = ledger == "as_taught"
    evs = load(version, only)
    trades = sorted((e for e in evs if usable(e)), key=lambda e: (post_ts(e), e["event_id"]))
    options = [e for e in trades if is_option(e) and e["action"] == "open"]
    # rules 11/13(a): a buy (open or add) that names no side is skipped and counted; an exit with no side is
    # matched below to his one open position on that ticker
    no_side = sum(not is_option(e) and e["action"] in ("open", "add") and e.get("side") not in ("long", "short")
                  for e in trades)
    trades = [e for e in trades if not is_option(e) and (e.get("side") in ("long", "short")
                                                          or e["action"] in ("trim", "close"))]
    by_id = {e["event_id"]: e for e in trades}
    stats = Counter(calls_not_copied=sum(e["type"] == "call" and e["status"] == "ok" for e in evs),
                    entry_side_unknown=no_side)
    positions, open_pos, ends = [], {}, {}   # ends: rule 13, the moment each open position leaves

    def finish(key):
        legs, first = open_pos.pop(key)
        end = ends.pop(key, None)
        if look_ahead:
            swing = len({bars.et_date(lg.posted_ts) for lg in legs}) > 1
            exit_ = "sessions:5" if swing else "day_close"
        else:   # rule 13(d): a swing trade only when he said, in time, he'd hold it past its first session
            swing = end > session_end(bars.et_date(legs[0].posted_ts), 0)
            exit_ = f"at:{end}" if swing else "day_close"
        p = Position(pid=f"lpp-{public_key(first)[4:]}-{first['event_id'].rsplit(':', 1)[-1]}", course=COURSE,
                     market=MARKET, ticker=key[0], side=key[1], portfolio="swing" if swing else "day", legs=legs,
                     default_exit=exit_, quote=words(first["quote"], 12), as_taught=look_ahead,
                     cite=cite(first), why=next((by_id[lg.event_id].get("why") for lg in legs
                                                 if by_id[lg.event_id].get("why")), None))
        positions.append(p)

    for e in trades:
        ts = post_ts(e)
        if not look_ahead:   # rule 13(b, c): positions whose moment to leave has come leave before this word
            for k in [k for k, end in ends.items() if end <= ts]:
                finish(k)
        if e.get("side") not in ("long", "short"):   # an exit that didn't say long or short: his one open position
            sides = [k for k in open_pos if k[0] == e["ticker"]]
            if len(sides) != 1:
                stats["exit_side_unknown"] += 1
                continue
            e = {**e, "side": sides[0][1]}
        key = (e["ticker"], e["side"])
        if look_ahead and key in open_pos:
            last = open_pos[key][0][-1].posted_ts
            if bars.et_date(last) != bars.et_date(ts):
                carry = e["action"] in ("add", "trim", "close") and ts - last <= CARRY_DAYS * 86400
                if not carry:
                    finish(key)
        leg = Leg(e["event_id"], ts, e["action"], qty=e.get("qty"))
        if e["action"] in ("open", "add"):
            if key not in open_pos:
                open_pos[key] = ([], e)
                ends[key] = session_end(bars.et_date(ts), 0)
            open_pos[key][0].append(leg)
        else:
            if key not in open_pos:
                stats["close_without_open"] += 1
                continue
            open_pos[key][0].append(leg)
        if not look_ahead and horizon_sessions(e):   # rule 13(b): a horizon said in time keeps it open longer
            ends[key] = max(ends[key], session_end(bars.et_date(ts), horizon_sessions(e)))
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
            {"time_et": t.strftime("%H:%M"), "course": COURSE, "ticker": e["ticker"], "action": e["action"]})

    return {
        "positions": positions,
        "options_count": len(options),
        "rules": rules,
        "days": days,
        "stats": stats,
        "checks": {"sessions": len({e["source_id"] for e in evs}), "proof_set": bool(only), "events_total": len(evs), "events_ok": sum(e["status"] == "ok" for e in evs),
                   "needs_review": sum(e["status"] != "ok" for e in evs),
                   "trade_events": sum(e["type"] == "trade" for e in evs), "trade_events_copied": len(trades)},
    }


SIZING = "His own share counts when he said them; $1,000 per entry when he didn't"
SIZING_SCALED = ("$1,000 for his first buy; each add in his ratio to it, from the counts he had said by then; "
                 "capped at the cash")   # contracts.md rule 13(e), the headline since spec-audit story 18


def unknown(stats, assumed, priced, total, status) -> list[str]:
    out = []
    if priced < total:
        out.append(f"Partial: {priced} of his {total} trades are priced so far.")
    if assumed.get("day"):
        out.append(f"Exit assumed at 15:55 for {assumed['day']} day trades he didn't say he closed.")
    if assumed.get("swing"):
        out.append(f"Exit assumed at the end of his stated hold for {assumed['swing']} swing trades he didn't "
                   "say he closed.")
    if stats.get("trim_size_unknown"):
        out.append(f"Half the position assumed sold on {stats['trim_size_unknown']} trims with no size.")
    if stats.get("entry_size_unknown"):
        out.append(f"{stats['entry_size_unknown']} entries with no share count took the upper median of his "
                   "stated counts in that trade.")
    if stats.get("exit_side_unknown"):
        out.append(f"{stats['exit_side_unknown']} exits didn't say which position and were skipped.")
    if stats.get("calls_not_copied"):
        out.append(f"{stats['calls_not_copied']} calls (levels he watched, no trade) are not copied.")
    if stats.get("close_without_open"):
        out.append(f"{stats['close_without_open']} exits had no matching entry and were skipped.")
    if status.get("no_bars"):
        out.append(f"{status['no_bars']} trade-delays had no price bars and were skipped.")
    out.append("He says he closes every day: a position stays overnight only if he said he'd hold it before "
               "15:55 ET. Stitching sessions by his later words is in as_taught_stitched.")
    if stats.get("entry_side_unknown"):
        out.append(f"{stats['entry_side_unknown']} buys didn't say long or short and were skipped.")
    out.append("Prices are 1-minute market bars, not his own fills.")
    out.append("Costs are estimates: 5 bps per side, 20 under $10.")
    out.append("Just holding SPY leaves out its dividends (about 1% a year).")
    return out


# ---- named strategies (code, not the model: keyword rules on his stated reason, first match wins) ----------------

STRATEGIES = [
    {"id": "short-overbought", "name": "Short the overbought run", "side": "short",
     "words": ("overbought", "ran up", "run up", "pump", "extended", "rise", "rally", "pop", "rip", "spike", "squeeze"),
     "buy": "Short after a fast run-up he calls overbought",
     "sell": "Covers in pieces as it fades"},
    {"id": "short-resistance", "name": "Short into resistance", "side": "short",
     "words": ("resistance", "reject", "highs", "high of", "lower high", "double top", "ceiling"),
     "buy": "Short as it stalls at a prior high",
     "sell": "Covers into the next drop"},
    {"id": "short-breakdown", "name": "Short the breakdown", "side": "short",
     "words": ("break", "support", "weak", "downside", "drop", "gap down", "lower", "dump", "bearish", "sell-off"),
     "buy": "Short when support breaks or it looks weak",
     "sell": "Covers after the flush"},
    {"id": "buy-the-dip", "name": "Buy the oversold dip", "side": "long",
     "words": ("oversold", "dip", "bounce", "support", "recovery", "reversal", "bottom", "flush"),
     "buy": "Buy a sharp dip near support",
     "sell": "Sells the bounce in pieces"},
    {"id": "other-shorts", "name": "Other shorts (gut calls)", "side": "short", "words": (),
     "buy": "Shorts with no repeatable reason given", "sell": "Covers when it feels done"},
    {"id": "other-longs", "name": "Other longs", "side": "long", "words": (),
     "buy": "Longs with no repeatable reason given", "sell": "Sells when it feels done"},
]


def strategy_of(p) -> str:
    why = (p.why or "").lower()
    for s in STRATEGIES:
        if s["side"] == p.side and (not s["words"] or any(w in why for w in s["words"])):
            return s["id"]
    return "other-longs" if p.side == "long" else "other-shorts"


def untestable(version: str) -> list[str]:
    """His rules that need judgement a backtest can't copy (paraphrases, 15 words or fewer)."""
    soft = ("feel", "confirmation", "patience", "gut", "emotion", "discipline", "wait", "trust", "comfortable")
    out = []
    for e in load(version):
        r = e.get("rule") or ""
        if e["type"] == "rule" and e["status"] == "ok" and len(r.split()) <= 15 and any(w in r.lower() for w in soft):
            out.append(r)
    return out
