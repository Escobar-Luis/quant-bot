"""Draft StrategySpec (notes/strategy-pipeline.md section 2) for the Crypto Wizard "Risky-Scalp" calls.

Two sources, kept apart:
  1. The calls themselves (code-derived): every number below is computed from the 126 parsed trade posts.
  2. The lessons (model-extracted rules that passed the code checks), cited by event id and source id.
The hand-drawn "WZRD lines" exist only in their posts and charts, so a rules-only version can't pick
levels by itself; the testable v0 is "take the posted levels", scored by score_calls.py.

Writes DATA_DIR/cryptowizard/strategy.spec.json. Run: python strategy_spec.py
"""
import json
import statistics as st
from collections import Counter

from common import CW, load_raw, mid_of, read_jsonl

CORE_LESSONS = {3, 8, 27, 30, 84, 85, 100, 107}


def main():
    ev = read_jsonl(CW / "events.jsonl")
    calls = [e for e in ev if e["type"] == "call"]
    closes = [e for e in ev if e.get("action") == "close"]
    rules = [e for e in ev if e["type"] == "rule" and e["status"] == "ok"]
    risk = [abs(e["entry"] - e["stop"]) / e["entry"] for e in calls]
    rr = {f"tp{k + 1}": round(st.median(abs(e["targets"][k] - e["entry"]) / abs(e["entry"] - e["stop"])
                                        for e in calls if len(e["targets"]) > k), 2) for k in range(4)}
    tfs = Counter((e.get("chart") or {}).get("timeframe") for e in calls if e.get("chart"))
    texts = {p["message_id"]: p["text"] for p in load_raw()}
    h1h4 = [e for e in closes if "H1 & H4" in texts.get(mid_of(e["event_id"]), "")]
    first_call = min(calls, key=lambda e: e["wall_utc"])
    cite = {}

    def c(e, locator=None):
        k = f"C{len(cite) + 1}"
        cite[k] = {"source_id": e["source_id"], "event_id": e["event_id"], "kind": "discord_post",
                   "posted_at": e["wall_utc"], "locator": locator, "quote": e.get("quote")}
        return k

    core = [r for r in rules if (r.get("lesson") or {}).get("n") in CORE_LESSONS
            or r.get("rule_kind") in ("sizing", "risk", "time_exit")]
    spec = {
        "id": "cw-risky-scalp", "version": 0, "parent": None, "proposer": "extractor", "course": "cryptowizard",
        "market": "crypto",
        "timeframe": {"bar": (tfs.most_common(1)[0][0] if tfs else "1h"), "session": "24/7",
                      "holding": "scalp (posts say 'Risky-Scalp'); 24-hour cap assumed (AGENTS.md contract 2)",
                      "chart_timeframes_seen": dict(tfs.most_common())},
        "universe": [{"id": "U1", "expr": {"in": sorted({e["ticker"] for e in calls})},
                      "counts": dict(Counter(e["ticker"] for e in calls).most_common()),
                      "note": "coins they actually called, Oct 2025 - Oct 2026; priced on Binance spot USDT pairs",
                      "pairs": sorted({e["pair"] for e in calls}),
                      "cite": c(first_call, "first call in window")}],
        "filters": [
            {"id": "F1", "rule": "Skip or exit when Bitcoin turns weak (BTC drives every altcoin call)",
             "testable": False, "why_untestable": "discretionary BTC sentiment, no stated threshold",
             "evidence": f"{sum('btc_weakness' in (e.get('setup_tags') or []) for e in closes)} of {len(closes)} closes cite BTC weakness",
             "cite": c(closes[0], "close post") if closes else None}],
        "entry": [
            {"id": "E1", "side": "long|short", "rule": "Breakout of a hand-drawn WZRD line, confirmed on both H1 and H4",
             "expr": {"op": "and", "left": {"op": "crosses_above", "left": {"fn": "close", "tf": "1h"}, "right": {"fn": "level"}},
                      "right": {"op": ">", "left": {"fn": "close", "tf": "4h"}, "right": {"fn": "level"}}},
             "level_source": "the post's entry price (their lines are not published as data)",
             "evidence": f"{len(h1h4)} close posts restate 'entered on H1 & H4 breakouts'",
             "cite": c(h1h4[0], "close post restating the entry rule") if h1h4 else None},
            {"id": "E2", "rule": "Enter at the post: 'Now or as close to $X'",
             "expr": {"fill": "next 1m open after post"}, "share_of_calls": 1.0, "cite": c(calls[-1], "entry line")}],
        "exit": {
            "stop": {"id": "X1", "rule": "Fixed stop price given in the post",
                     "median_distance_pct": round(100 * st.median(risk), 2),
                     "p10_p90_pct": [round(100 * sorted(risk)[len(risk) // 10], 2),
                                     round(100 * sorted(risk)[9 * len(risk) // 10], 2)],
                     "cite": c(calls[-1], "SL line")},
            "targets": {"id": "X2", "rule": "Four take-profits, closing 25/30/25/20% of the position",
                        "ladder_pcts": dict(Counter(tuple(e["extra"]["close_pcts"]) for e in calls).most_common(1))
                        and list(Counter(tuple(e["extra"]["close_pcts"]) for e in calls).most_common(1)[0][0]),
                        "median_R_multiple": rr, "cite": c(calls[-1], "TP lines")},
            "breakeven": {"id": "X3", "rule": "Move stop to entry 'when it moves close to TP2'",
                          "coded_as": "stop = fill after TP2 trades", "assumed": True, "cite": c(calls[-1], "B/E line")},
            "discretionary": {"id": "X4", "rule": "Close early when BTC or macro turns ('please close the trade')",
                              "count": len(closes), "testable": "only as 'managed' replay of their own close posts"},
            "time": {"id": "X5", "at": "24 hours after entry", "assumed": True, "source": "AGENTS.md contract 2"},
        },
        "sizing": {"id": "S1", "rule": None, "assumed": "equal size per call", "note": "posts give no size; see lesson rules"},
        "costs": {"bps_per_side": 25, "assumed": True, "source": "notes/research/backtesting.md (taker fee)"},
        "lesson_rules": [{"event_id": r["event_id"], "kind": r.get("rule_kind"), "rule": r["rule"],
                          "testable": r["testable"], "expr": r.get("expr"), "lesson": r["lesson"],
                          "source_id": r["source_id"], "quote": r["quote"]} for r in core],
        "lesson_rules_total": {"extracted": sum(e["type"] == "rule" for e in ev), "ok": len(rules),
                               "testable": sum(r["testable"] for r in rules)},
        "citations": cite,
        "assumptions": [

            "Stop and target in the same minute: the stop counts (conservative).",
            "Breakeven after TP2 trades; the posts say 'close to TP2'.",
            "Positions still open after 24 hours close at the last bar (contract default for crypto).",
            "Entry at the first 1-minute open at or after post time + delay (default 5 minutes).",
            "25 bps per side for taker fee plus slippage.",
        ],
        "untestable": [
            {"paraphrase": "Where the WZRD lines are drawn", "why": "hand-drawn, only in their charts"},
            {"paraphrase": "When Bitcoin's mood allows a trade", "why": "discretionary"},
            {"paraphrase": "Macro and Trump-news risk calls", "why": "no point-in-time news data"},
            {"paraphrase": "Chart patterns (triangles, H&S, wedges) as entry triggers", "why": "needs a pattern detector"},
        ],
    }
    (CW / "strategy.spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    print("spec written; lesson rules in spec", len(core), "citations", len(cite), "timeframes", dict(tfs))


if __name__ == "__main__":
    main()
