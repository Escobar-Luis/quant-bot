"""Crypto Wizard: each "Trade Update" setup (entry now, stop, TP1-TP4 with close shares) -> one copyable position.

Reads data/cryptowizard/events.calls.jsonl and events.rules.jsonl, written by story/collect-cryptowizard. A setup's
targets close their stated shares (`close_pcts`) when price trades them; the stop moves to break-even once TP2
fills (their "B/E" move, assumed at TP2); a linked "please close" post exits the rest at post time + delay. With no
close post, the rest leaves 24 h after entry, or after the setup's last linked follow-up if that came later.
"""
import json
import math

from . import bars
from .common import DATA
from .engine import Leg, Position

COURSE, NAME, MARKET = "cryptowizard", "Crypto Wizard", "crypto"
WINDOW = {"start": "2025-10-17", "end": "2026-10-16", "sealed_from": "2026-07-16"}
HOLD = {"symbol": "BTCUSDT", "label": "Just holding", "what": "Buy and keep Bitcoin (BTC)"}
SIZING = "$1,000 per setup (they never state a size)"
CHANNEL = "#wzrd-chat-crypto"


def load(name: str) -> list[dict]:
    p = DATA / "cryptowizard" / name
    return [json.loads(line) for line in open(p) if line.strip()] if p.exists() else []


def words(text: str | None, n: int) -> str | None:
    if not text:
        return None
    w = text.split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


def symbol(e: dict) -> str | None:
    s = e.get("pair") or e.get("ticker")
    if s and not s.endswith("USDT") and s.endswith("USD"):
        s += "T"
    return s


def cite(e: dict, label: str) -> dict:
    return {"source_id": e["source_id"], "locator": e["source_id"].rsplit("/", 1)[-1],
            "label": f"{label}, {e['wall_utc'][:10]}"}


def build(version: str) -> dict:
    evs = load("events.calls.jsonl")
    calls = [e for e in evs if e["type"] == "call" and e["status"] == "ok" and e.get("entry") and symbol(e)]
    follow: dict[str, list] = {}
    for e in evs:
        if e["type"] == "trade" and e.get("links_to") and e["status"] == "ok":
            follow.setdefault(e["links_to"], []).append(e)
    positions, stats = [], {"no_close_post": 0}
    for c in sorted(calls, key=lambda e: e["wall_utc"]):
        t0 = bars.to_ts(c["wall_utc"])
        legs = [Leg(c["event_id"], t0, "open")]
        fus = sorted(follow.get(c["event_id"], []), key=lambda e: e["wall_utc"])
        closes = [e for e in fus if e["action"] == "close"]
        legs += [Leg(e["event_id"], bars.to_ts(e["wall_utc"]), "close") for e in closes[:1]]
        if not closes:
            stats["no_close_post"] += 1
        last = max([bars.to_ts(e["wall_utc"]) for e in fus] or [t0])
        hours = max(24, math.ceil((last - t0) / 3600))
        pcts = (c.get("extra") or {}).get("close_pcts") or []
        fracs = [p / 100 for p in pcts] if len(pcts) == len(c["targets"]) else []
        p = Position(pid=f"cw-{c['source_id'].rsplit('/', 1)[-1]}", course=COURSE, market=MARKET,
                     ticker=symbol(c), side=c.get("side") or "long", portfolio="crypto", legs=legs,
                     default_exit=f"hours:{hours}", stop=c.get("stop"), targets=list(c["targets"]),
                     target_fracs=fracs, quote=words(c.get("quote"), 12), cite=cite(c, CHANNEL))
        p.be_after_target = 2
        positions.append(p)

    rules = []
    for e in load("events.rules.jsonl"):
        if e["status"] == "ok" and e.get("rule") and e.get("quote") and len(e["quote"].split()) <= 12 \
                and len(e["rule"].split()) <= 15:
            label = f"Lesson {e['lesson']}" if e.get("lesson") else "Discord post"
            rules.append({"text": e["rule"], "quote": e["quote"], "testable": bool(e.get("testable")),
                          "cite": cite(e, label)})
    step = max(1, len(rules) // 12)
    rules = [{"id": f"R{i + 1}", **r} for i, r in enumerate(rules[::step][:12])]

    return {"positions": positions, "options_count": 0, "rules": rules, "days": None, "stats": stats,
            "checks": {"events_total": len(evs), "events_ok": sum(e["status"] == "ok" for e in evs),
                       "needs_review": sum(e["status"] != "ok" for e in evs), "setups": len(calls)}}


def unknown(stats, assumed, priced, total, status) -> list[str]:
    out = []
    if priced < total:
        out.append(f"Partial: {priced} of {total} setups are priced so far.")
    out.append("Break-even stop assumed once the second target fills.")
    if assumed.get("crypto"):
        out.append(f"Exit assumed for {assumed['crypto']} setups they never closed (24 h or last update).")
    if status.get("no_bars"):
        out.append(f"{status['no_bars']} setup-delays had no price bars and were skipped.")
    out.append("$1,000 per setup: they never state a size.")
    out.append("Prices are Binance 1-minute bars; costs 25 bps per side.")
    return out
