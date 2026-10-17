"""Code checks on every extracted event (the model proposes, the code decides).

quote_ok   the quote is an exact substring of the source transcript (after norm()), 12 words max
numbers_ok every number in the event's numeric fields and paraphrases appears in the source
ticker_ok  the symbol is a real US listing (Nasdaq Trader symbol directory in data/ref/); None if no list
price_ok   price plausible against the minute bar at wall_utc; None until minute bars exist (no Alpaca keys)
xcheck_ok  the quote is also in a second model's transcription of the same image; None if there is none
"""
from functools import cache

from common import ROOT, norm, numbers_in

REF = ROOT / "data" / "ref"
NUM_FIELDS = ("price", "entry", "stop", "level", "qty")
TEXT_FIELDS = ("why", "rule", "watch")


@cache
def symbols() -> frozenset[str] | None:
    """Every non-test symbol listed on Nasdaq, NYSE and the other US exchanges."""
    out = set()
    for name, sym_col, test_col in (("nasdaqlisted.txt", 0, 3), ("otherlisted.txt", 0, 6)):
        p = REF / name
        if not p.exists():
            return None
        for line in p.read_text().splitlines()[1:]:
            f = line.split("|")
            if len(f) > test_col and not line.startswith("File Creation") and f[test_col] != "Y":
                out.add(f[sym_col].replace(".", "-").upper())
    return frozenset(out)


def fmt(x) -> str:
    return f"{x:g}" if isinstance(x, float) else str(x)


def clip_quote(quote: str | None, source_text: str) -> str | None:
    """An exact quote longer than 12 words keeps its first 12 (still exact; the cap guards copyright)."""
    if quote and len(quote.split()) > 12 and norm(quote) in norm(source_text):
        return " ".join(quote.split()[:12])
    return quote


def check(ev: dict, source_text: str, xcheck_text: str | None = None) -> dict:
    src = norm(source_text)
    nums = numbers_in(source_text)
    q = norm(ev.get("quote"))
    quote_ok = bool(q) and len(q.split()) <= 12 and q in src
    vals = [ev.get(k) for k in NUM_FIELDS] + list(ev.get("targets") or [])
    bad = [fmt(v) for v in vals if isinstance(v, (int, float)) and fmt(v) not in nums]
    bad += [n for k in TEXT_FIELDS for n in numbers_in(ev.get(k) or "") if n not in nums]
    syms = symbols()
    t = (ev.get("ticker") or "").upper().replace(".", "-")
    ticker_ok = None if ev.get("ticker") is None and ev.get("type") == "rule" else (
        None if syms is None else bool(t) and t in syms)
    # price_ok needs 1-minute bars at wall_utc; no Alpaca keys in .env yet, so it stays None (unknown)
    checks = {"quote_ok": quote_ok, "numbers_ok": not bad, "ticker_ok": ticker_ok, "price_ok": None,
              "xcheck_ok": None if xcheck_text is None else (bool(q) and q in norm(xcheck_text))}
    if bad:
        checks["numbers_missing"] = sorted(set(bad))
    return checks


def status(checks: dict) -> str:
    hard = [checks["quote_ok"], checks["numbers_ok"]]
    soft = [checks[k] for k in ("ticker_ok", "price_ok", "xcheck_ok")]
    return "ok" if all(hard) and all(v is not False for v in soft) else "needs_review"
