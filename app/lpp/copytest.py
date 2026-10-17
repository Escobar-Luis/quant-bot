"""Test design for "did the host's trading work?" (code decides; the model never scores outcomes).

  uv run python -m lpp.copytest      # writes data/lpp/tests/{trips,calls}.jsonl and prints a summary

1. Host's round trips: each (ticker, side) position from open to close, legs priced at the 1-minute bar at each
   leg's wall_utc (or at his stated fill when it sits inside that bar).
2. Copy the host: enter 60 s after he announces each entry, exit 60 s after he announces each trim/close, same
   share counts, costs per side (5 bps, 20 bps under $10); compared with SPY bought and held over the same minutes.
3. Calls: did the level trade that session after the call? With minute bars: between wall_utc and 16:00 ET.
   Without them: the day's high-low range only (weak evidence: the level may have traded before the call).

Minute bars need Alpaca keys (bars.minute). Without them trips and copy results are null and say why.
"""
import datetime as dt
import json
from collections import defaultdict

from . import bars
from .common import RES

DELAY_S = 60
TESTS = RES / "tests"


def _ts(wall):
    return int(dt.datetime.fromisoformat(wall.replace("Z", "+00:00")).timestamp())


def cost_bps(px):
    return 20 if px is not None and px < 10 else 5


def bar_at(mb, ts):
    """The 1-minute bar containing ts (bars are keyed by their open time)."""
    return mb.get(ts // 60 * 60) if mb else None


def trips_for(events):
    """Group a session's checked trade events into round trips per (ticker, side), in time order."""
    pos, out = {}, []
    for e in sorted((e for e in events if e["type"] == "trade" and e["ticker"] and e["action"]), key=lambda e: e["t_s"] or 0):
        key = (e["ticker"], e["side"] or "long")
        if e["action"] in ("open", "add"):
            p = pos.setdefault(key, {"ticker": key[0], "side": key[1], "session_date": e["session_date"], "legs": [], "qty": 0.0})
            p["legs"].append(e)
            p["qty"] = None if p["qty"] is None or e["qty"] is None else p["qty"] + e["qty"]
        elif key in pos:
            p = pos[key]
            p["legs"].append(e)
            p["qty"] = None if p["qty"] is None or e["qty"] is None else p["qty"] - e["qty"]
            if e["action"] == "close" or (p["qty"] is not None and p["qty"] <= 1e-9):
                out.append({**pos.pop(key), "closed": True})
    out += [{**p, "closed": False} for p in pos.values()]
    return out


def price_trip(trip):
    """Host P&L and copy-the-host P&L for one round trip, or a reason it can't be priced."""
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
        b_now, b_copy = bar_at(mb, t), bar_at(mb, t + DELAY_S)
        if not b_now or not b_copy:
            return {"status": "missing_bar", "at": e["wall_utc"]}
        stated = e.get("price")
        host_px = stated if stated and b_now[2] * 0.99 <= stated <= b_now[1] * 1.01 else b_now[3]
        copy_px = b_copy[3]
        entry = e["action"] in ("open", "add")
        qty = e["qty"] if e["qty"] is not None else (held if e["action"] == "close" else None)
        if qty is None:
            return {"status": "qty_unknown", "at": e["wall_utc"]}
        cost = copy_px * qty * cost_bps(copy_px) / 1e4
        flow = -1 if entry else 1  # cash out on entry for a long; signs flip for a short via `sign`
        host_pnl += sign * flow * host_px * qty
        copy_pnl += sign * flow * copy_px * qty - cost
        gross += copy_px * qty if entry else 0
        held += qty if entry else -qty
        legs.append({"event_id": e["event_id"], "host_px": host_px, "copy_px": copy_px, "qty": qty})
    t0, t1 = _ts(trip["legs"][0]["wall_utc"]) + DELAY_S, _ts(trip["legs"][-1]["wall_utc"]) + DELAY_S
    s0, s1 = bar_at(spy, t0), bar_at(spy, t1)
    spy_ret = (s1[3] / s0[3] - 1) if s0 and s1 else None
    return {"status": "priced" if abs(held) < 1e-9 else "qty_mismatch", "host_pnl": round(host_pnl, 2),
            "copy_pnl": round(copy_pnl, 2), "copy_ret": round(copy_pnl / gross, 5) if gross else None,
            "spy_ret_same_minutes": round(spy_ret, 5) if spy_ret is not None else None, "legs": legs}


def call_traded(e):
    """Did the call's level trade that session after the call? Minute bars when available, else the day's range."""
    if e.get("level") is None or not e.get("ticker") or not e.get("session_date"):
        return {"traded": None, "evidence": "no_level"}
    mb = bars.minute(e["ticker"], e["session_date"])
    if mb and e.get("wall_utc"):
        t = _ts(e["wall_utc"])
        close = int(dt.datetime.combine(dt.date.fromisoformat(e["session_date"]), dt.time(16, 0), bars.ET).timestamp())
        after = [b for k, b in mb.items() if t <= k < close]
        if after:
            return {"traded": min(b[2] for b in after) <= e["level"] <= max(b[1] for b in after), "evidence": "minute_after_call"}
    d = bars.day_bar(e["ticker"], e["session_date"])
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
        ok = [e for e in evs if e["status"] == "ok" or set(e["fail"]) <= {"open_never_closed", "price_decimal_shift"}]
        for t in trips_for(ok):
            trips.append({"source_id": src, "ticker": t["ticker"], "side": t["side"], "session_date": t["session_date"],
                          "closed": t["closed"], "legs": [e["event_id"] for e in t["legs"]], **price_trip(t)})
        for e in evs:
            if e["type"] == "call" and e["status"] == "ok":
                calls.append({"event_id": e["event_id"], "ticker": e["ticker"], "side": e["side"], "level": e["level"],
                              "level_kind": e["level_kind"], "session_date": e["session_date"], **call_traded(e)})
    with open(TESTS / "trips.jsonl", "w") as f:
        f.writelines(json.dumps(t) + "\n" for t in trips)
    with open(TESTS / "calls.jsonl", "w") as f:
        f.writelines(json.dumps(c) + "\n" for c in calls)
    from collections import Counter
    print("round trips", len(trips), dict(Counter(t["status"] for t in trips)))
    judged = [c for c in calls if c["traded"] is not None]
    print("calls (status ok)", len(calls), "judged", len(judged), "level traded that session",
          sum(c["traded"] for c in judged), dict(Counter(c["evidence"] for c in calls)))


if __name__ == "__main__":
    main()
