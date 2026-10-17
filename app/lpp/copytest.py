"""Test design for "did the host's trading work?" (code decides; the model never scores outcomes).
The full engine is story 1 (`app/backtest/`, contracts.md); this is the LPP-side design and a first pass.

  uv run python -m lpp.copytest      # writes <results>/tests/{trips,calls}.jsonl and prints a summary

1. Host's round trips: the same ledger as checks.py, on trades that pass the validity checks (ticker, side,
   action, numbers, price, quote found). Legs are priced at the 1-minute bar at each leg's wall_utc (his stated
   fill when it sits inside that bar).
2. Copy the host (contracts.md rules 2-5): each entry and each announced trim/close is copied DELAY_S later, at
   the open of the first 1-minute bar at or after announce + delay; same share counts; costs per side 5 bps,
   20 bps under $10; compared with SPY bought and held over the same minutes.
3. Calls: did the level trade that session after the call? With minute bars: between wall_utc and 16:00 ET.
   Without them: the day's high-low range only (weak: the level may have traded before the call).

Minute bars need Alpaca keys (bars.minute). Without them trips say "no_minute_bars".
"""
import copy
import datetime as dt
import json
from collections import Counter, defaultdict

from . import bars, checks
from .common import RES

DELAY_S = 60
TESTS = RES / "tests"
# a leg is usable unless a check says the trade itself may be wrong (a long quote or a carried position isn't)
INVALID = {"ticker_unresolved", "ticker_unknown", "ticker_malformed", "number_not_in_source", "number_not_near_quote",
           "price_off_minute_bar", "price_off_day_range", "quote_not_in_source", "quote_missing",
           "trade_without_action", "trade_without_side"}


def _ts(wall):
    return int(dt.datetime.fromisoformat(wall.replace("Z", "+00:00")).timestamp())


def cost_bps(px):
    return 20 if px is not None and px < 10 else 5


def bar_at(mb, ts):
    """The 1-minute bar containing ts (bars are keyed by their open time)."""
    return mb.get(ts // 60 * 60) if mb else None


def bar_after(mb, ts):
    """The first 1-minute bar opening at or after ts (contracts.md rule 3)."""
    if not mb:
        return None
    later = [k for k in mb if k >= ts]
    return mb[min(later)] if later else None


def usable(e) -> bool:
    return (e["type"] == "trade" and e["ticker"] and e["action"] and e["side"] and e.get("wall_utc")
            and (e.get("instrument") or "stock") == "stock" and e["ticker"] not in checks.FUTURES
            and e["ticker"] not in checks.INDEXES and not set(e["fail"]) & INVALID)


def trips_for(events):
    """Round trips from the shared ledger (checks.ledger, v1 rules: no carry-in) over usable trades."""
    legs = [copy.deepcopy(e) for e in sorted(events, key=lambda e: e["t_s"] or 0) if usable(e)]
    for e in legs:
        e["fail"] = []
    by_id = {e["event_id"]: e for e in legs}
    return [{**t, "legs": [by_id[i] for i in t["legs"]], "session_date": by_id[t["legs"][0]]["session_date"]}
            for t in checks.ledger(legs) if t["legs"]]


def price_trip(trip):
    """Host P&L (gross) and copy-the-host P&L (net of costs) for one round trip, or why it can't be priced."""
    if trip.get("carried_in"):
        return {"status": "carried_in"}
    if not trip["closed"]:
        return {"status": "open_at_end"}
    mb = bars.minute(trip["ticker"], trip["session_date"])
    spy = bars.minute("SPY", trip["session_date"])
    if not mb or not spy:
        return {"status": "no_minute_bars"}
    sign = 1 if trip["side"] == "long" else -1
    held, host_pnl, copy_pnl, gross, legs = 0.0, 0.0, 0.0, 0.0, []
    for e in trip["legs"]:
        t = _ts(e["wall_utc"])
        b_now, b_copy = bar_at(mb, t), bar_after(mb, t + DELAY_S)
        if not b_now or not b_copy:
            return {"status": "missing_bar", "at": e["wall_utc"]}
        stated = e.get("price")
        host_px = stated if stated and b_now[2] * 0.99 <= stated <= b_now[1] * 1.01 else b_now[3]
        copy_px = b_copy[0]
        entry = e["action"] in ("open", "add")
        qty = e["qty"] if e["qty"] is not None else (held if e["action"] == "close" else None)
        if qty is None:
            return {"status": "qty_unknown", "at": e["wall_utc"]}
        cost = copy_px * qty * cost_bps(copy_px) / 1e4
        flow = -1 if entry else 1  # cash out on entry for a long; `sign` flips it for a short
        host_pnl += sign * flow * host_px * qty
        copy_pnl += sign * flow * copy_px * qty - cost
        gross += copy_px * qty if entry else 0
        held += qty if entry else -qty
        legs.append({"event_id": e["event_id"], "host_px": host_px, "copy_px": copy_px, "qty": qty})
    s0 = bar_after(spy, _ts(trip["legs"][0]["wall_utc"]) + DELAY_S)
    s1 = bar_after(spy, _ts(trip["legs"][-1]["wall_utc"]) + DELAY_S)
    spy_ret = (s1[0] / s0[0] - 1) if s0 and s1 else None
    return {"status": "priced" if abs(held) < 1e-9 else "qty_mismatch", "host_pnl_gross": round(host_pnl, 2),
            "copy_pnl_net": round(copy_pnl, 2), "copy_ret": round(copy_pnl / gross, 5) if gross else None,
            "spy_ret_same_minutes": round(spy_ret, 5) if spy_ret is not None else None, "legs": legs}


def call_traded(e):
    """Did the call's level trade that session after the call? Minute bars when available, else the day's range."""
    if e.get("level") is None or not e.get("ticker") or not e.get("session_date") or e["ticker"] in checks.FUTURES:
        return {"traded": None, "evidence": "not_testable"}
    mb = None if e["ticker"] in checks.INDEXES else bars.minute(e["ticker"], e["session_date"])
    if mb and e.get("wall_utc"):
        t = _ts(e["wall_utc"])
        close = int(dt.datetime.combine(dt.date.fromisoformat(e["session_date"]), dt.time(16, 0), bars.ET).timestamp())
        after = [b for k, b in mb.items() if t <= k < close]
        if after:
            return {"traded": min(b[2] for b in after) <= e["level"] <= max(b[1] for b in after), "evidence": "minute_after_call"}
    d = bars.day_bar(checks._sym(e["ticker"]), e["session_date"])
    if not d:
        return {"traded": None, "evidence": "no_bars"}
    return {"traded": d[2] <= e["level"] <= d[1], "evidence": "daily_range"}


def main():
    TESTS.mkdir(parents=True, exist_ok=True)
    by_src = defaultdict(list)
    for e in map(json.loads, open(RES / "events.jsonl")):
        by_src[e["source_id"]].append(e)
    trips, calls = [], []
    for src, evs in by_src.items():
        for t in trips_for(evs):
            trips.append({"source_id": src, "ticker": t["ticker"], "side": t["side"], "session_date": t["session_date"],
                          "closed": t["closed"], "legs": [e["event_id"] for e in t["legs"]], **price_trip(t)})
        for e in evs:
            if e["type"] == "call" and not set(e["fail"]) & (INVALID | {"call_without_level", "call_without_side"}):
                calls.append({"event_id": e["event_id"], "ticker": e["ticker"], "side": e["side"], "level": e["level"],
                              "level_kind": e["level_kind"], "session_date": e["session_date"], **call_traded(e)})
    with open(TESTS / "trips.jsonl", "w") as f:
        f.writelines(json.dumps(t) + "\n" for t in trips)
    with open(TESTS / "calls.jsonl", "w") as f:
        f.writelines(json.dumps(c) + "\n" for c in calls)
    priced = [t for t in trips if t["status"] == "priced"]
    print("round trips", len(trips), dict(Counter(t["status"] for t in trips)))
    if priced:
        print(f"priced {len(priced)}: host gross ${sum(t['host_pnl_gross'] for t in priced):,.0f}, "
              f"copy net ${sum(t['copy_pnl_net'] for t in priced):,.0f}, copy wins "
              f"{sum(t['copy_pnl_net'] > 0 for t in priced)}/{len(priced)}, beats SPY same minutes "
              f"{sum(t['copy_ret'] is not None and t['spy_ret_same_minutes'] is not None and t['copy_ret'] > t['spy_ret_same_minutes'] for t in priced)}")
    judged = [c for c in calls if c["traded"] is not None]
    print("calls", len(calls), "judged", len(judged), "level traded after the call", sum(c["traded"] for c in judged),
          dict(Counter(c["evidence"] for c in calls)))


if __name__ == "__main__":
    main()
