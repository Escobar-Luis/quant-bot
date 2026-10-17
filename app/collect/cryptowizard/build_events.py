"""Merge everything into the shared record shape: DATA_DIR/cryptowizard/events.jsonl.

  events.calls.jsonl   (parse_posts.py)     calls, TP-hit trims, closes, with quote/number checks
  enrich.v2.jsonl      (enrich_why.py v2)   `why` paraphrase + setup tags (falls back to v1 when v2 is missing)
  chart_text.jsonl     (charts_vision.py)   chart timeframe, patterns, levels-match flag
  checks.prices.json   (score_calls.py)     ticker_ok, price_ok
  events.rules.jsonl   (extract_rules.py)   rule events from the lessons

An event is `ok` only when every check that ran passed; anything else is `needs_review`, never dropped.
Run: python build_events.py
"""
import json
from collections import Counter

from common import CW, read_jsonl, write_jsonl


def load(name):
    p = CW / name
    return read_jsonl(p) if p.exists() else []


def main():
    calls = load("events.calls.jsonl")
    why = {r["event_id"]: r for r in load("enrich.v1.jsonl")}
    why.update({r["event_id"]: r for r in load("enrich.v2.jsonl")})
    charts = {r["event_id"]: r for r in load("chart_text.jsonl")}
    pc = json.loads((CW / "checks.prices.json").read_text()) if (CW / "checks.prices.json").exists() else {}
    out = []
    for e in calls:
        w = why.get(e["event_id"])
        if w:
            e["why"] = w["why"]
            e["setup_tags"] = w["tags"]
            e["model"], e["prompt_version"] = w["model"], w["prompt_version"]
            e["checks"]["why_ok"] = w["checks"]["why_words_ok"] and w["checks"]["why_numbers_ok"]
        ch = charts.get(e["event_id"])
        if ch:
            e["chart"] = {"timeframe": ch.get("timeframe"), "patterns": ch.get("patterns"),
                          "projection": ch.get("projection"), "matches_post": ch.get("chart_matches_post")}
            e["checks"]["chart_ok"] = bool(ch.get("chart_matches_post"))
        p = pc.get(e["event_id"])
        if p:
            e["checks"]["ticker_ok"] = p["ticker_ok"]
            e["checks"]["price_ok"] = p["price_ok"]
            if "price_dev_pct" in p:
                e["checks"]["price_dev_pct"] = p["price_dev_pct"]
        problems = [k for k, v in e["checks"].items() if v is False]
        if e["type"] == "trade" and not e.get("links_to"):
            problems.append("unlinked")
        e["status"] = "needs_review" if problems else "ok"
        e["review_reasons"] = problems
        e.pop("reason_text_chars", None)
        out.append(e)
    rules = load("events.rules.jsonl")
    out += rules
    write_jsonl(CW / "events.jsonl", out)
    c = Counter((e["type"], e.get("action"), e["status"]) for e in out)
    print("events", len(out))
    for k, v in sorted(c.items(), key=str):
        print(" ", k, v)
    print("review reasons", Counter(r for e in out for r in e.get("review_reasons", [])))


if __name__ == "__main__":
    main()
