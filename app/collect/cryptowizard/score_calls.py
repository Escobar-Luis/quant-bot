"""Code checks on prices + a SKETCH of the call test (not the backtest engine).

Checks (written into events.jsonl by build_events.py):
  ticker_ok  the pair is listed on Binance spot (their charts are BINANCE:<COIN>USDT)
  price_ok   call: the stated entry is within 2% of the 1-minute close at the post minute ("Now or as close to")
             TP-hit post: the claimed target traded between the entry post and the TP post (their claim, checked)

Sketch of the test (follows AGENTS.md contract 2; the real engine is story/1-copy-trade-backtest):
  fill       open of the first 1-minute bar at or after post time + delay (default 5 min); 25 bps per side
  tp1        all out at TP1 or the stop, whichever trades first; both inside one bar = stop (conservative)
  ladder     as posted: close 25/30/25/20% at TP1..TP4 (their percentages), stop to entry once TP2 trades
  managed    ladder, but any remaining size is closed at their "please close" post + delay, as a member would
  horizon    24 hours after entry, then the rest closes at the last bar (contract default for crypto, assumed)
  hold       the same coin bought at the fill and sold when `managed` ends (the "just hold it" baseline)
  R          (exit - fill) / (fill - stop) for longs, mirrored for shorts, after costs

Writes DATA_DIR/cryptowizard/{checks.prices.json, scores.d<delay>.jsonl, scores.d<delay>.summary.json}.
Run: python score_calls.py [delay_minutes]
"""
import json
import statistics as st

import sys

from bars import bars_between, iso_ms
from common import CW, read_jsonl, write_jsonl

COST = 0.0025          # per side
PRICE_TOL = 0.02
MIN = 60_000
HORIZON_MS = 24 * 3_600_000
DELAY_MIN = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def minute_bar(symbol, t_ms):
    b = bars_between(symbol, t_ms - t_ms % MIN, t_ms - t_ms % MIN + MIN)
    return b[0] if b else None


def simulate(call, bars, close_ms=None, mode="ladder"):
    """Walk 1-minute bars; return exit legs [(fraction, price, t_ms, why)] and the fill."""
    long = call["side"] == "long"
    fill = bars[0][1]
    stop = call["stop"]
    tps = call["targets"]
    pcts = call["extra"].get("close_pcts") or []
    if mode == "tp1" or len(pcts) != len(tps) or sum(pcts) == 0:
        fracs = [1.0] + [0.0] * (len(tps) - 1) if mode == "tp1" else [1 / len(tps)] * len(tps)
    else:
        fracs = [p / sum(pcts) for p in pcts]
    left, legs, k = 1.0, [], 0
    # A stop already beyond the fill (gap through it) exits at the fill.
    if (long and fill <= stop) or (not long and fill >= stop):
        return fill, [(1.0, fill, bars[0][0], "stop_at_fill")]
    for t, o, h, l, c, _ in bars:
        if close_ms is not None and t >= close_ms and left > 1e-9:
            legs.append((left, o, t, "their_close"))
            return fill, legs
        hit_stop = (l <= stop) if long else (h >= stop)
        if hit_stop:  # stop first when both trade inside one bar
            legs.append((left, stop, t, "stop" if k < 2 else "breakeven"))
            return fill, legs
        while k < len(tps) and ((h >= tps[k]) if long else (l <= tps[k])):
            f = min(fracs[k], left)
            if f > 0:
                legs.append((f, tps[k], t, f"tp{k + 1}"))
                left -= f
            k += 1
            if k == 2:
                stop = fill  # breakeven once TP2 trades (their updates: "move your SL to breakeven")
            if mode == "tp1" or left <= 1e-9:
                return fill, legs
    if left > 1e-9:
        legs.append((left, bars[-1][4], bars[-1][0], "horizon"))
    return fill, legs


def ret(call, fill, legs):
    sgn = 1 if call["side"] == "long" else -1
    gross = sum(f * sgn * (p - fill) / fill for f, p, _, _ in legs)
    return gross - 2 * COST


def main():
    events = read_jsonl(CW / "events.calls.jsonl")
    listed = json.loads((CW / "binance_symbols.json").read_text())
    by_id = {e["event_id"]: e for e in events}
    closes = {}
    for e in events:
        if e["action"] == "close" and e["links_to"]:
            closes.setdefault(e["links_to"], iso_ms(e["wall_utc"]) + DELAY_MIN * MIN)
    checks, scores = {}, []
    for e in events:
        sym = e["ticker"]
        c = {"ticker_ok": sym in listed and listed[sym] in ("TRADING", "BREAK"), "price_ok": None}
        t = iso_ms(e["wall_utc"])
        if c["ticker_ok"] and e["type"] == "call":
            b = minute_bar(sym, t)
            if b:
                dev = e["entry"] / b[4] - 1
                c.update({"price_ok": abs(dev) <= PRICE_TOL, "price_dev_pct": round(100 * dev, 2), "bar_close": b[4]})
        elif c["ticker_ok"] and e["action"] == "trim" and e["links_to"] and e["price"] is not None:
            parent = by_id[e["links_to"]]
            bs = bars_between(sym, iso_ms(parent["wall_utc"]), t + MIN)
            if bs:
                touched = any((h >= e["price"]) if parent["side"] == "long" else (l <= e["price"])
                              for _, _, h, l, _, _ in bs)
                c.update({"price_ok": touched})
        elif c["ticker_ok"] and e["action"] == "close":
            b = minute_bar(sym, t)
            if b:
                c["bar_close"] = b[4]
        checks[e["event_id"]] = c
        if e["type"] != "call" or not c["ticker_ok"]:
            continue
        te = t + DELAY_MIN * MIN
        t0 = te - te % MIN + (MIN if te % MIN else 0)   # first bar opening at or after post + delay
        bars = bars_between(sym, t0, t0 + HORIZON_MS)
        if len(bars) < 60:
            scores.append({"event_id": e["event_id"], "skipped": "not enough bars after the post"})
            continue
        row = {"event_id": e["event_id"], "ticker": sym, "side": e["side"], "wall_utc": e["wall_utc"],
               "entry_said": e["entry"], "stop": e["stop"], "targets": e["targets"]}
        for mode in ("tp1", "ladder", "managed"):
            fill, legs = simulate(e, bars, closes.get(e["event_id"]) if mode == "managed" else None,
                                  "tp1" if mode == "tp1" else "ladder")
            r = ret(e, fill, legs)
            risk = abs(fill - e["stop"]) / fill
            row[mode] = {"fill": fill, "net_ret": round(r, 5), "R": round(r / risk, 3) if risk else None,
                         "exits": [x[3] for x in legs], "end_utc_ms": legs[-1][2]}
        end = row["managed"]["end_utc_ms"]
        last = [b for b in bars if b[0] <= end][-1]
        row["hold"] = {"net_ret": round(last[4] / bars[0][1] - 1 - 2 * COST, 5)}
        row["their_close_post"] = e["event_id"] in closes
        row["tp_hits_claimed"] = sorted({x["extra"]["tp_index"] for x in events
                                         if x["action"] == "trim" and x["links_to"] == e["event_id"]})
        row["tp_hits_on_bars"] = sum(1 for x in row["ladder"]["exits"] if x.startswith("tp"))
        scores.append(row)
    (CW / "checks.prices.json").write_text(json.dumps(checks, indent=0))
    write_jsonl(CW / f"scores.d{DELAY_MIN}.jsonl", scores)
    ok = [s for s in scores if "skipped" not in s]

    def agg(mode):
        rs = [s[mode]["net_ret"] for s in ok]
        Rs = [s[mode]["R"] for s in ok if s[mode]["R"] is not None]
        return {"n": len(rs), "win_rate": round(sum(r > 0 for r in rs) / len(rs), 3),
                "avg_net_ret_pct": round(100 * st.mean(rs), 3), "median_net_ret_pct": round(100 * st.median(rs), 3),
                "sum_net_ret_pct": round(100 * sum(rs), 2), "avg_R": round(st.mean(Rs), 3),
                "stopped_out": sum(1 for s in ok if s[mode]["exits"][-1] in ("stop", "stop_at_fill")
                                   and not any(x.startswith("tp") for x in s[mode]["exits"]))}
    hold = [s["hold"]["net_ret"] for s in ok]
    trims = [e for e in events if e["action"] == "trim" and checks.get(e["event_id"], {}).get("price_ok") is not None]
    summary = {
        "calls_scored": len(ok), "calls_skipped": len(scores) - len(ok),
        "window": [min(s["wall_utc"] for s in ok), max(s["wall_utc"] for s in ok)],
        "delay_min": DELAY_MIN,
        "assumptions": {"cost_per_side": COST, "horizon_hours": HORIZON_MS // 3_600_000,
                        "fill": "first 1m open at or after post + delay",
                        "same_bar": "stop first", "breakeven": "after TP2", "bars": "Binance spot 1m"},
        "tp1": agg("tp1"), "ladder": agg("ladder"), "managed": agg("managed"),
        "hold_same_coin": {"avg_net_ret_pct": round(100 * st.mean(hold), 3), "sum_net_ret_pct": round(100 * sum(hold), 2),
                           "win_rate": round(sum(r > 0 for r in hold) / len(hold), 3)},
        "managed_beats_hold": sum(s["managed"]["net_ret"] > s["hold"]["net_ret"] for s in ok),
        "calls_with_announced_tp": sum(1 for s in ok if s["tp_hits_claimed"]),
        "calls_stopped_without_any_tp": sum(1 for s in ok if not any(x.startswith("tp") for x in s["ladder"]["exits"])
                                            and s["ladder"]["exits"][-1] in ("stop", "stop_at_fill")),
        "tp_claims_checked": len(trims), "tp_claims_verified": sum(checks[e["event_id"]]["price_ok"] for e in trims),
        "entry_price_ok": sum(1 for e in events if e["type"] == "call" and checks[e["event_id"]].get("price_ok")),
        "entry_price_checked": sum(1 for e in events if e["type"] == "call"
                                   and checks[e["event_id"]].get("price_ok") is not None),
    }
    (CW / f"scores.d{DELAY_MIN}.summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
