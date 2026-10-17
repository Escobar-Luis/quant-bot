"""Turn collected Crypto Wizard posts into sources, call events and linked follow-up events.

The trade posts are rigid templates, so code (regex), not a model, reads every number:
  entry   "<COIN> [2ND] Trade Update: (Risky-Scalp) / [LONG|SHORT] Entry: Now or as close to $X / SL: $Y /
           B/E Move: ... / TP 1..4: $T (Close N%)"           -> type=call, action=open
  tp_hit  "OUR <COIN> TRADE JUST HIT THE FIRST TAKE PROFIT ... Please close 25% ... SL to breakeven"
                                                              -> type=trade, action=trim, linked to its entry
  close   "Please close the <COIN> trade [after smashing TP1]"  -> type=trade, action=close, linked
A model only paraphrases `why` later (enrich_why.py); it never sets a number.

Writes DATA_DIR/cryptowizard/{sources.jsonl, events.calls.jsonl, skipped.jsonl}.
Run: python parse_posts.py
"""
import re
from collections import Counter

from common import (COURSE, CW, SERVER_ID, STAFF, CHANNEL_IDS, coin_of, load_raw, message_url, num,
                    source_id, to_symbol, write_jsonl)

NUM_RE = re.compile(r"\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")
ORD = {"FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5}
CUT = ["Do not take big risk", "Is there a risk?", "Learn the WZRD Bible", "Thumbs up once read",
       "There is no obligation", "Thanks for playing", "Thanks for taking the trade", "SHOW THOSE PROFITS"]


def core(text):
    s = text
    for m in CUT:
        k = s.find(m)
        if k > 0:
            s = s[:k]
    return s.strip()


def numbers_in(text):
    return {num(m) for m in NUM_RE.findall(text)}


def first_words(sentence, n=12):
    """First n words of a sentence, as an exact substring of it (quotes stay verbatim)."""
    words = list(re.finditer(r"\S+", sentence))
    if not words:
        return None
    end = words[min(n, len(words)) - 1].end()
    return sentence[:end].rstrip(" ,;:")


def classify(p):
    t, T = p["text"], p["text"].upper()
    if p["channel"] == "wzrd-lessons":
        return "lesson"
    if re.search(r"Entry\s*:", t):
        return "entry"
    if re.search(r"JUST HIT THE \w+ TAKE PROFIT", T):
        return "tp_hit"
    if re.search(r"PLEASE CLOSE THE|EXIT THE .* TRADE", T):
        return "close"
    if "GIVEAWAY" in T:
        return "promo"
    if "MARKET UPDATE" in T:
        return "market_update"
    return "other"


def fix_numbers(t):
    """Repair typos before reading numbers: '$111, 928' (space after the thousands comma), '$0.0.06390' (doubled '0.')."""
    t = re.sub(r"(\d),\s+(\d{3})\b", r"\1,\2", t)
    return re.sub(r"\$\s*0\.(0\.\d+)", r"$\1", t)


def parse_entry(p):
    t = fix_numbers(p["text"])
    header = t.split("\n")[0]
    coin, nth = coin_of(header)
    m_side = re.search(r"(LONG|SHORT)\s+Entry", t, re.I)
    m_entry = re.search(r"Entry\s*:\s*Now or as close to\s*\$?\s*([\d,]+(?:\.\d+)?)", t)
    m_sl = re.search(r"\bSL\s*:\s*\$?\s*([\d,]+(?:\.\d+)?)", t)
    tps = re.findall(r"TP\s?(\d)\s*:\s*\$?\s*([\d,]+(?:\.\d+)?)\s*\(([^)]*)\)", t)
    be = re.search(r"B/E Move\s*:\s*([^\n]+)", t)
    if not (m_entry and m_sl and tps):
        return None
    entry, stop = num(m_entry.group(1)), num(m_sl.group(1))
    side = m_side.group(1).lower() if m_side else ("long" if stop < entry else "short")
    closes = [int(x) for _, _, c in tps for x in re.findall(r"(\d+)%", c)][:len(tps)]
    # Reasoning: the paragraph(s) after the last TP line, before the boilerplate.
    after = core(t[t.rfind(tps[-1][1]) + len(tps[-1][1]):])
    after = re.sub(r"^[^\n]*\n", "", after, count=1).strip()  # drop the rest of the last TP line
    reason_sentence = re.split(r"(?<=[.!?])\s+|\n", after.strip())[0] if after else ""
    return {
        "coin": coin, "nth": nth, "side": side, "side_inferred": not m_side, "entry": entry, "stop": stop,
        "targets": [num(v) for _, v, _ in tps], "close_pcts": closes, "be_move": be.group(1).strip() if be else None,
        "typo_fixed": t != p["text"],
        "label": (re.search(r"\(([^)]+)\)", header) or [None, None])[1], "reason": after,
        "quote": first_words(reason_sentence) if reason_sentence else None,
    }


def main():
    posts = load_raw()
    sources, events, skipped = [], [], []
    open_by_key = {}   # (coin, nth) -> latest entry event
    kinds = Counter()
    for p in posts:
        sid = source_id(p)
        sources.append({
            "source_id": sid, "course": COURSE, "kind": "discord_post", "server_id": SERVER_ID,
            "channel": p["channel"], "channel_id": CHANNEL_IDS[p["channel"]], "message_id": p["message_id"],
            "url": message_url(p), "posted_at": p["posted_at"], "author": p["author"],
            "author_role": "staff" if p["author"] in STAFF else "member",
            "queries": p["queries"], "tradingview": [l for l in p["links"] if "tradingview.com/x/" in l],
        })
        kind = classify(p)
        kinds[kind] += 1
        base = {"event_id": f"cw-{p['message_id']}", "source_id": sid, "course": COURSE, "t_s": None,
                "wall_utc": p["posted_at"], "market": "crypto", "qty": None, "price": None, "entry": None,
                "stop": None, "targets": [], "level": None, "level_kind": None, "horizon": None, "why": None,
                "rule": None, "quote": None, "model": None, "prompt_version": None}
        src_nums = numbers_in(fix_numbers(p["text"]))
        if kind == "entry":
            e = parse_entry(p)
            if e is None:
                skipped.append({"source_id": sid, "kind": kind, "reason": "entry template did not parse"})
                continue
            symbol = to_symbol(e["coin"])
            if symbol is None:
                skipped.append({"source_id": sid, "kind": kind, "reason": f"not crypto ({e['coin']})"})
                continue
            nums = [e["entry"], e["stop"], *e["targets"]]
            ev = {**base, "type": "call", "ticker_said": e["coin"], "ticker": symbol, "side": e["side"],
                  "action": "open", "entry": e["entry"], "stop": e["stop"], "targets": e["targets"],
                  "level": e["entry"], "level_kind": "entry", "horizon": e["label"], "quote": e["quote"],
                  "reason_text_chars": len(e["reason"]),
                  "extra": {"trade_no": e["nth"], "close_pcts": e["close_pcts"], "be_move": e["be_move"],
                            "side_inferred": e["side_inferred"], "number_typo_fixed": e["typo_fixed"],
                            "entry_wording": "Now or as close to"},
                  "checks": {"quote_ok": bool(e["quote"]) and e["quote"] in p["text"],
                             "numbers_ok": all(n in src_nums for n in nums),
                             "ticker_ok": None, "price_ok": None},
                  "links_to": None}
            open_by_key[(e["coin"], e["nth"])] = ev
            events.append(ev)
        elif kind in ("tp_hit", "close"):
            header = p["text"].split("\n")[0]
            coin, nth = coin_of(header)
            T = p["text"].upper()
            if re.search(r"\b(?:OUR|THE) (?:SECOND|2ND) (?!TAKE\b)\w+ (?:TRADE|SCALP)\b", T):
                nth = "2"
            parent = open_by_key.get((coin, nth))
            ev = {**base, "type": "trade", "ticker_said": coin, "ticker": to_symbol(coin),
                  "side": parent["side"] if parent else None, "links_to": parent["event_id"] if parent else None,
                  "checks": {"quote_ok": None, "numbers_ok": None, "ticker_ok": None, "price_ok": None}}
            if ev["ticker"] is None:
                skipped.append({"source_id": sid, "kind": kind, "reason": f"not crypto ({coin})"})
                continue
            if kind == "tp_hit":
                k = ORD.get(re.search(r"JUST HIT THE (\w+) TAKE PROFIT", T).group(1))
                pct = re.search(r"close (\d+)% of the trade", p["text"], re.I)
                gain = re.search(r"\+([\d,.]+)%\s*RAW GAIN", T)
                pips = re.search(r"\+([\d,.]+)\s*PIPS", T)
                q = re.search(r"(?:OUR )?(?:SECOND )?\w+ TRADE JUST HIT THE \w+ TAKE PROFIT", p["text"])
                ev.update({"action": "trim", "level_kind": "target",
                           "qty": int(pct.group(1)) / 100 if pct else None,
                           "price": parent["targets"][k - 1] if parent and k and k <= len(parent["targets"]) else None,
                           "quote": q.group(0) if q else None,
                           "extra": {"tp_index": k, "claimed_gain_pct": num(gain.group(1)) if gain else None,
                                     "claimed_pips": num(pips.group(1)) if pips else None,
                                     "move_stop": ("breakeven near TP2" if "CLOSE TO TP2" in T
                                                   else "breakeven" if "BREAKEVEN" in T else None)}})
                ev["level"] = ev["price"]
                ev["checks"]["quote_ok"] = bool(ev["quote"]) and ev["quote"] in p["text"]
                ev["checks"]["numbers_ok"] = all(x in src_nums for x in
                                                 [n for n in (ev["extra"]["claimed_gain_pct"],) if n is not None])
            else:
                q = re.search(r"Please close the [^.\n]*(?:trade|TRADE)[^.\n]*", p["text"])
                after_tp = re.search(r"after (?:smashing|hitting) (TP\d)", p["text"], re.I)
                ev.update({"action": "close", "quote": first_words(q.group(0)) if q else None,
                           "reason_text_chars": len(core(p["text"])),
                           "extra": {"after_tp": after_tp.group(1).upper() if after_tp else None,
                                     "says_profit": bool(re.search(r"\bIN PROFIT\b|ABOVE BREAKEVEN|RISK.FREE", T))}})
                ev["checks"]["quote_ok"] = bool(ev["quote"]) and ev["quote"] in p["text"]
                ev["checks"]["numbers_ok"] = True
            events.append(ev)
        elif kind == "lesson":
            continue  # lessons become rule events in extract_rules.py
        else:
            skipped.append({"source_id": sid, "kind": kind,
                            "reason": {"promo": "giveaway / social promo, no trade",
                                       "market_update": "market commentary, no levels to test",
                                       "other": "no trade template (commentary)"}[kind]})
    for ev in events:
        problems = [k for k, v in ev["checks"].items() if v is False]
        if ev["type"] == "trade" and not ev["links_to"]:
            problems.append("unlinked")
        ev["status"] = "needs_review" if problems else "ok"
    write_jsonl(CW / "sources.jsonl", sources)
    write_jsonl(CW / "events.calls.jsonl", events)
    write_jsonl(CW / "skipped.jsonl", skipped)
    by = Counter((e["type"], e.get("action")) for e in events)
    print("posts", len(posts), dict(kinds))
    print("events", len(events), dict(by), "needs_review", sum(e["status"] != "ok" for e in events))
    print("skipped", len(skipped), dict(Counter(s["reason"] for s in skipped)))


if __name__ == "__main__":
    main()
