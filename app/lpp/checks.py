"""Code checks on every proposed event. The model proposes; these decide `status`.

Each failed check adds a failure kind to `fail` (these are what PRISM's Root Cause clusters).
"""
import datetime as dt
import math
import re

from . import bars
from .common import COURSE, PROMPT_VERSION, VERSION
from .transcript import Transcript, norm

NUM = re.compile(r"\d+(?:\.\d+)?")
TICKER = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z])?$")
INDEXES = {"SPX": "^GSPC", "NDX": "^NDX", "VIX": "^VIX", "DJI": "^DJI", "RUT": "^RUT"}
FUTURES = {"ES", "NQ", "YM", "RTY", "MES", "MNQ"}  # no free 2024-25 futures bars; price checks stay null


def _num(x):
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    m = NUM.search(str(x).replace(",", ""))
    return float(m.group()) if m else None


def _nums_in(text: str) -> set[float]:
    return {float(n) for n in NUM.findall(text.replace("$", " ").replace("%", " "))}


def _said(x: float, nums: set[float], shift: bool = True) -> bool:
    """x appears as said, or (prices and levels only: shift=True) as captions write it with the decimal point
    dropped (58.74 -> "5874", 320.5 -> "32050"). Share counts never get the shift: qty 5 is not "500"."""
    return x in nums or (shift and any(abs(round(x * f) - x * f) < 1e-6 and round(x * f) in nums and x * f >= 100
                                       for f in (10, 100)))


def _sym(ticker: str) -> str:
    """Our symbol -> the yfinance symbol (indexes, class shares like BRK.B -> BRK-B)."""
    return INDEXES.get(ticker, ticker.replace(".", "-"))


def _words(s):
    return len((s or "").split())


def build(tr: Transcript, raw: dict, src_id: str, carry_in: set | None = None) -> list[dict]:
    """Model events -> records in the shared shape, with checks and status."""
    ntext = tr.ntext
    out = []
    for i, e in enumerate(raw.get("events") or []):
        if not isinstance(e, dict):
            continue
        typ = e.get("type")
        if typ not in ("trade", "call", "rule"):
            continue
        fail = []
        quote = " ".join(str(e.get("quote") or "").split())
        t_model = _num(e.get("t"))
        t_quote = tr.find(quote, near=t_model) if quote else None
        qty, price, level = _num(e.get("qty")), _num(e.get("price")), _num(e.get("level"))
        numbers = [(n, sh) for n, sh in ((qty, False), (price, True), (level, True)) if n is not None]
        trimmed = False
        if VERSION != "v1" and t_quote is not None and _words(quote) > 12:
            # v2: the model can't count to 12, so code keeps the 12-word window of its (verified) quote that holds
            # the most of the event's numbers; a consecutive slice of a caption span is still exact caption words
            w = quote.split()
            best = max(range(len(w) - 11), key=lambda j: (sum(_said(n, _nums_in(norm(" ".join(w[j:j + 12]))), sh)
                                                             for n, sh in numbers), -j))
            quote, trimmed = " ".join(w[best:best + 12]), True
            t_quote = tr.find(quote, near=t_model)
        quote_ok = bool(quote) and _words(quote) <= 12 and t_quote is not None
        if not quote:
            fail.append("quote_missing")
        elif _words(quote) > 12:
            fail.append("quote_too_long")
        elif t_quote is None:
            fail.append("quote_not_in_source")
        t_s = t_quote if t_quote is not None else t_model
        wall = None
        if tr.release_ts and t_s is not None:
            wall = dt.datetime.fromtimestamp(tr.release_ts + t_s, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        # every number the event carries must be said within 3 minutes before / 1 minute after the quote
        numbers_ok = None
        if numbers:
            win = _nums_in(tr.window((t_s or 0) - 180, (t_s or 0) + 60)) if t_s is not None else _nums_in(ntext)
            numbers_ok = all(_said(n, win, sh) for n, sh in numbers)
            if not numbers_ok:
                fail.append("number_not_in_source" if not all(_said(n, _nums_in(ntext), sh) for n, sh in numbers)
                            else "number_not_near_quote")
        # numbers inside a rule paraphrase ("first 15 minutes", "2%") must be said near the quote too
        rule_txt = str(e.get("rule") or "") if typ == "rule" else ""
        if rule_txt and _nums_in(rule_txt) and t_s is not None:
            win = _nums_in(tr.window(t_s - 180, t_s + 60))
            if not all(_said(n, win, False) for n in _nums_in(rule_txt)):
                fail.append("rule_number_not_in_source")
        paraphrase_ok = all(_words(str(e.get(k) or "")) <= 15 for k in ("rule", "why"))  # shared shape: 15 max

        ticker = str(e.get("ticker") or "").upper().strip().lstrip("$") or None
        ticker_ok, price_ok, price_check = None, None, None
        date = bars.session_date(tr.release_ts) if tr.release_ts else None
        if typ != "rule":
            if not ticker:
                ticker_ok = False
                fail.append("ticker_unresolved")
            elif ticker in FUTURES:
                ticker_ok = True
            elif not TICKER.match(ticker):
                ticker_ok = False
                fail.append("ticker_malformed")
            else:
                ticker_ok = bars.daily(_sym(ticker)) is not None
                if not ticker_ok:
                    fail.append("ticker_unknown")
            inst = e.get("instrument") or "stock"
            px = price if typ == "trade" else level
            if ticker_ok and px is not None and inst == "stock" and ticker not in FUTURES and date:
                price_ok, why, price_check = _price_ok(ticker, date, wall, px, typ)
                if price_ok is False:
                    fail.append(why)

        side = str(e.get("side") or "").lower() or None
        side = side if side in ("long", "short") else None
        action = str(e.get("action") or "").lower() if typ == "trade" else None
        action = action if action in ("open", "add", "trim", "close") else None
        lk = str(e.get("level_kind") or "").lower()
        lk = lk if lk in ("entry", "stop", "target", "support", "resistance") else None
        if typ == "trade" and not action:
            fail.append("trade_without_action")
        if typ == "trade" and not side:
            fail.append("trade_without_side")
        if typ == "call" and level is None:
            fail.append("call_without_level")
        if typ == "call" and not side:
            fail.append("call_without_side")
        status = "needs_review" if fail else "ok"
        out.append({
            "event_id": f"lpp:{tr.video_id}:{i:03d}", "source_id": src_id, "course": COURSE, "type": typ,
            "t_s": round(t_s, 1) if t_s is not None else None, "wall_utc": wall, "session_date": date,
            "market": "us_futures" if ticker in FUTURES else "us_equities", "ticker_said": e.get("ticker_said"),
            "ticker": ticker if typ != "rule" else (ticker or None),
            "side": side, "action": action, "instrument": e.get("instrument") if typ != "rule" else None,
            "qty": qty, "price": price if typ == "trade" else None,
            "entry": level if lk == "entry" else (price if typ == "trade" and action == "open" else None),
            "stop": level if lk == "stop" else None, "targets": [level] if lk == "target" and level is not None else [],
            "level": level if typ == "call" else None, "level_kind": lk if typ == "call" else None,
            "horizon": None, "why": e.get("why"), "rule": e.get("rule") if typ == "rule" else None,
            "quote": " ".join(quote.split()[:12]),
            "checks": {"quote_ok": quote_ok, "numbers_ok": numbers_ok, "ticker_ok": ticker_ok, "price_ok": price_ok,
                       "ledger_ok": None, "quote_trimmed": trimmed, "paraphrase_ok": paraphrase_ok,
                       "price_check": price_check},
            "fail": fail, "status": status, "model": raw.get("model"), "prompt_version": PROMPT_VERSION,
        })
    out.sort(key=lambda e: (e["t_s"] is None, e["t_s"] or 0))
    for i, e in enumerate(out):
        e["event_id"] = f"lpp:{tr.video_id}:{i:03d}"
    ledger(out, carry_in)
    return out


def _price_ok(ticker, date, wall, px, typ):
    """Returns (ok, failure kind, which check ran). With Alpaca keys: the as-traded 1-minute bars within 2 minutes
    of wall_utc (trade fills 1% slack; call levels within 25%). Without them, or for an index: the day's high-low
    from yfinance daily bars (split-adjusted, so a split inside the window can misfire; the check says "daily")."""
    lo = hi = None
    check = None
    if wall and ticker not in INDEXES:
        mb = bars.minute(ticker, date)
        if mb:
            t = int(dt.datetime.fromisoformat(wall.replace("Z", "+00:00")).timestamp()) // 60 * 60
            near = [mb[k] for k in range(t - 120, t + 180, 60) if k in mb]
            if near:
                lo, hi, check = min(b[2] for b in near), max(b[1] for b in near), "minute"
    if lo is None:
        b = bars.day_bar(_sym(ticker), date)
        if not b:
            return None, None, None
        lo, hi, check = b[2], b[1], "daily"
    slack = 0.01 if typ == "trade" else 0.25
    if lo * (1 - slack) <= px <= hi * (1 + slack):
        return True, None, check
    for f in (100, 10, 0.1, 0.01):  # captions often drop the decimal point: "5874" for 58.74
        if lo * (1 - slack) <= px / f <= hi * (1 + slack):
            return False, "price_decimal_shift", check
    return False, f"price_off_{'minute_bar' if check == 'minute' else 'day_range'}", check


def ledger(events: list[dict], carry_in: set | None = None) -> list[dict]:
    """Reconcile the host's trades into round trips per (ticker, side, instrument). Marks ledger_ok on trades and
    returns the round trips. v1: a close with nothing open, or an open never closed, fails the ledger check.
    v2: a trim or close of a position still open at the end of the previous session is a carried position, and
    a position still open when the stream ends is reported (open_at_end), not failed: he holds past the stream."""
    pos, trips = {}, []
    carry_in = (carry_in or set()) if VERSION != "v1" else set()
    for e in events:
        if e["type"] != "trade" or not e["ticker"] or not e["action"]:
            continue
        key = (e["ticker"], e["side"] or "long")
        pkey = key + (e.get("instrument") or "stock",)
        p = pos.get(pkey)
        ok = True
        if e["action"] in ("open", "add"):
            if p is None:  # v2: adding to a position carried in from yesterday keeps its size unknown
                carried = e["action"] == "add" and key in carry_in
                p = pos[pkey] = {"ticker": key[0], "side": key[1], "instrument": pkey[2], "legs": [], "qty": 0.0,
                                 "qty_known": not carried, "carried_in": carried}
            p["legs"].append(e["event_id"])
            if e["qty"] is None:
                p["qty_known"] = False
            else:
                p["qty"] += e["qty"]
        else:
            if p is None and key in carry_in:
                p = pos[pkey] = {"ticker": key[0], "side": key[1], "instrument": pkey[2], "legs": [], "qty": 0.0,
                                 "qty_known": False, "carried_in": True}
            if p is None:
                ok = False
                e["fail"].append("close_without_open")
            else:
                p["legs"].append(e["event_id"])
                if e["qty"] is not None and p["qty_known"]:
                    p["qty"] -= e["qty"]
                    if p["qty"] < -1e-9:
                        ok = False
                        e["fail"].append("qty_exceeds_position")
                if e["action"] == "close" or (p["qty_known"] and p["qty"] <= 1e-9):  # an over-trim also closes it
                    trips.append({**p, "closed": True})
                    del pos[pkey]
        e["checks"]["ledger_ok"] = ok
    by_id = {e["event_id"]: e for e in events}
    for p in pos.values():  # every leg fails ledger_ok; the failure kind goes on the opening leg only
        trips.append({**p, "closed": False})
        if VERSION != "v1":
            continue
        for leg in p["legs"]:
            by_id[leg]["checks"]["ledger_ok"] = False
        if "open_never_closed" not in by_id[p["legs"][0]]["fail"]:
            by_id[p["legs"][0]]["fail"].append("open_never_closed")
    for e in events:
        if e["fail"]:
            e["status"] = "needs_review"
    return trips
