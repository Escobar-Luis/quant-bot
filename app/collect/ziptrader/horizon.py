"""Rule 12(a): a holding horizon said only in the quote counts as written and belongs in the event's `horizon`.

The model sometimes leaves `horizon` empty while the quote itself says it ("keep working for more than one
session"). Code, not the model, copies that phrase into `horizon`, so the backtest reads one field.

  uv run app/collect/ziptrader/horizon.py      # backfill data/ziptrader/events.jsonl (no model call)
"""
import json
import re

from common import DATA, read_jsonl, write_jsonl

# a span of time longer than the session: "more than one session", "3 days", "next few weeks", "overnight"
PHRASE = re.compile(r"\b(?:(?:more than|over|several|multiple|a few|next)\s+(?:\w+\s+)?|\d+\s*)"
                    r"(?:trading\s+)?(?:sessions?|days?|weeks?)\b|\bovernight\b|\bmulti-?day\b", re.I)


def from_quote(quote: str | None) -> str | None:
    """The horizon phrase as written in the quote, or None."""
    m = PHRASE.search(quote or "")
    return m.group(0) if m else None


def fill(ev: dict) -> bool:
    """Set an empty `horizon` from the quote; True when it changed."""
    if ev.get("horizon") or ev.get("type") == "rule":
        return False
    h = from_quote(ev.get("quote"))
    if h:
        ev["horizon"] = h
    return bool(h)


def main():
    path = DATA / "events.jsonl"
    evs = read_jsonl(path)
    n = sum(fill(e) for e in evs)
    write_jsonl(path, evs)
    print(f"horizon from quote: {n} of {len(evs)} events")


if __name__ == "__main__":
    main()
