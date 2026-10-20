"""Rule 12(a): a holding horizon said only in the quote counts as written and belongs in the event's `horizon`.

The model sometimes leaves `horizon` empty while the quote itself says it ("keep working for more than one
session"). Code, not the model, copies that phrase into `horizon` (with `horizon_source` saying where it came
from), so the backtest reads one field. Only holding phrasing counts: "hold for 3 days", "over the next two
weeks", "for more than one session", "into the next session", "hold overnight". A number next to "day" that is
not a holding period ("200 day moving average", "5 day chart") is not a horizon; "0 days" is not a horizon.
A horizon longer than 15 sessions is kept and flagged (`horizon_flag`), never cut.

  uv run app/collect/ziptrader/horizon.py      # backfill data/ziptrader/events.jsonl (no model call), then
                                               # rerun the code checks on every event it changed
"""
import json
import re

from common import DATA, read_jsonl, write_jsonl

BACKFILL_SOURCE = "quote_backfill_2026-10-20"
MAX_SESSIONS = 15

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "twenty": 20,
         "thirty": 30}
COUNT = r"\d+|" + "|".join(WORDS) + r"|a few|a couple of|several|multiple"
LEAD = r"(?:hold(?:ing)?|held|keep(?:s|ing)?(?:\s+\w+)?|swing(?:ing)?|carry(?:ing)?|for|over|within|lasting)"
UNIT = r"(?:trading\s+)?(sessions?|days?|weeks?)"
NOT_A_HORIZON = r"(?!\s*(?:-|moving|average|ma\b|ema\b|sma\b|chart|high|low|range|line|candle|bar|period|rsi|of\b|ago\b|straight\b|in a row))"
PERIOD = re.compile(rf"\b{LEAD}\s+(?:it\s+)?(?:for\s+)?(?:the\s+)?(?:next\s+)?(more than\s+|at least\s+)?"
                    rf"({COUNT})\s+{UNIT}\b{NOT_A_HORIZON}", re.I)
NEXT = re.compile(rf"\b(?:into|for|until|through|hold\w*\s+(?:it\s+)?(?:into|until|through))\s+(?:the\s+)?"
                  rf"next\s+(?:trading\s+)?(?:day|session)\b(?!'s)", re.I)
OVERNIGHT = re.compile(r"\b(?:hold\w*|keep\w*|carry\w*|swing\w*)\s+(?:it\s+|them\s+)?overnight\b|"
                       r"\bovernight\s+(?:hold|swing)\b", re.I)


def sessions(n: int, unit: str) -> int:
    return n * 5 if unit.lower().startswith("week") else n


def from_quote(quote: str | None) -> tuple[str, int | None] | None:
    """(the horizon phrase as written, its length in sessions or None when it states no count), or None."""
    q = quote or ""
    m = PERIOD.search(q)
    if m:
        more, count, unit = m.group(1), m.group(2).lower(), m.group(3)
        n = int(count) if count.isdigit() else WORDS.get(count)
        if n == 0:
            return None                      # "0 days" is no horizon
        phrase = q[m.start(1) if more else m.start(2):m.end()]
        return phrase, (None if more or n is None else sessions(n, unit))
    for rx in (NEXT, OVERNIGHT):
        m = rx.search(q)
        if m:
            return m.group(0), 1
    return None


def fill(ev: dict, source: str = "quote") -> bool:
    """Set an empty `horizon` from the quote (with `horizon_source`, and `horizon_flag` past 15 sessions)."""
    if ev.get("horizon") or ev.get("type") == "rule":
        return False
    got = from_quote(ev.get("quote"))
    if not got:
        return False
    ev["horizon"], ev["horizon_source"] = got[0], source
    if got[1] is not None and got[1] > MAX_SESSIONS:
        ev["horizon_flag"] = f"over_{MAX_SESSIONS}_sessions"
    return True


def recheck(ev: dict) -> None:
    """Rerun the code checks on an event whose fields changed (the same checks the extractor runs)."""
    from checks import check, failed, panel_of, status
    from common import BRIEFING_XCHECK_MODEL, TRANSCRIPTS, VISION_BRIEFING_MODEL
    txs = {t["source_id"]: t for t in read_jsonl(DATA / "discord" / "transcripts.jsonl")
           if t["model"] == VISION_BRIEFING_MODEL}
    tx = txs.get(ev["source_id"])
    if tx is None:
        ev.setdefault("checks", {})["recheck"] = "no transcript"
        return
    text = (DATA / tx["path"]).read_text()
    mid = ev["source_id"].rsplit("/", 1)[-1]
    xpath = TRANSCRIPTS / f"{mid}.{BRIEFING_XCHECK_MODEL.split('/')[-1]}.txt"
    xtext = xpath.read_text() if xpath.exists() and xpath.name != (DATA / tx["path"]).name else None
    span = panel_of(text, ev["ticker"], ev["quote"]) or text
    xspan = panel_of(xtext, ev["ticker"], ev["quote"]) if xtext else None
    ev["checks"] = check(ev, span, (xspan or xtext) if xtext else None)
    ev["status"] = status(ev["checks"])
    ev["fail"] = failed(ev["checks"])


def main():
    path = DATA / "events.jsonl"
    evs = read_jsonl(path)
    changed = [e for e in evs if fill(e, BACKFILL_SOURCE)]
    for e in changed:
        before = e["status"]
        recheck(e)
        print(f"  {e['event_id']}: horizon {e['horizon']!r}, status {before} -> {e['status']}")
    write_jsonl(path, evs)
    print(f"horizon from quote: {len(changed)} of {len(evs)} events")


if __name__ == "__main__":
    main()
