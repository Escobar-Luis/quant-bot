"""Code checks on every extracted event (the model proposes, the code decides).

Each check runs against the event's span: the briefing panel of its ticker, or the card line of its rule.
quote_ok   the quote is an exact substring of the span (whitespace, quote marks and dashes unified; case kept),
           on word boundaries, 12 words max
numbers_ok every number in the event's numeric fields and paraphrases appears in the span
ticker_ok  a real US listing (Nasdaq Trader symbol directory in data/ref/) that the span names; None if no list
price_ok   price plausible against the minute bar at wall_utc; None until minute bars exist (no Alpaca keys)
xcheck_ok  the quote is also in a second model's reading of the same image; None if there is none
"""
import re
from functools import cache

from common import ROOT, canon, is_num, norm, numbers_in

REF = ROOT / "data" / "ref"
NUM_FIELDS = ("price", "entry", "stop", "level", "qty")
TEXT_FIELDS = ("why", "rule", "watch", "horizon")


@cache
def symbols() -> frozenset[str] | None:
    """Every non-test symbol listed on Nasdaq, NYSE and the other US exchanges."""
    out = set()
    for name, test_col in (("nasdaqlisted.txt", 3), ("otherlisted.txt", 6)):
        p = REF / name
        if not p.exists():
            return None
        for line in p.read_text().splitlines()[1:]:
            f = line.split("|")
            if len(f) > test_col and not line.startswith("File Creation") and f[test_col] != "Y":
                out.add(f[0].replace(".", "-").upper())
    return frozenset(out) or None


def clip_quote(quote: str | None, source_text: str) -> str | None:
    """An exact quote longer than 12 words keeps its first 12 (still exact; the cap guards copyright)."""
    if isinstance(quote, str) and len(quote.split()) > 12 and norm(quote, case=True) in norm(source_text, case=True):
        return " ".join(quote.split()[:12])
    return quote


def quote_in(quote: str | None, text: str | None) -> bool:
    """Exact match on word boundaries; only the first letter may differ in case (a quote may start a sentence)."""
    q = norm(quote, case=True)
    if not q:
        return False
    head = f"[{re.escape(q[0].lower())}{re.escape(q[0].upper())}]" if q[0].isalpha() else re.escape(q[0])
    return re.search(r"(?<!\w)" + head + re.escape(q[1:]) + r"(?!\w)", norm(text, case=True)) is not None


def panel_of(text: str, ticker: str | None = None, quote: str | None = None) -> str | None:
    """The '## ' block of a transcript that carries this ticker's badge, else the block holding the quote."""
    blocks = re.split(r"\n(?=#{1,3} |=== column)", text)
    if ticker:
        for b in blocks:
            if re.search(rf"\[ticker:\s*{re.escape(ticker)}\]", b, re.I):
                return b
    if quote:
        for b in blocks:
            if quote_in(quote, b):
                return b
    return None


def check(ev: dict, span: str, xcheck_text: str | None = None) -> dict:
    nums = numbers_in(span)
    q = ev.get("quote")
    quote_ok = isinstance(q, str) and len(q.split()) <= 12 and quote_in(q, span)
    vals = [ev.get(k) for k in NUM_FIELDS] + list(ev.get("targets") or [])
    bad = [canon(v) for v in vals if is_num(v) and canon(v) not in nums]
    bad += [n for k in TEXT_FIELDS for n in numbers_in(ev.get(k) if isinstance(ev.get(k), str) else "") if n not in nums]
    syms = symbols()
    t = (ev.get("ticker") or "").upper().replace(".", "-")
    if ev.get("type") == "rule" and not t:
        ticker_ok = None
    elif syms is None:
        ticker_ok = None
    else:
        named = bool(t) and (re.search(rf"(?<![A-Za-z]){re.escape(t)}(?![A-Za-z])", span) is not None
                             or (isinstance(ev.get("ticker_said"), str) and norm(ev["ticker_said"]) in norm(span)))
        ticker_ok = bool(t) and t in syms and named
    # price_ok needs 1-minute bars at wall_utc; no Alpaca keys in .env yet, so it stays None (unknown)
    checks = {"quote_ok": quote_ok, "numbers_ok": not bad, "ticker_ok": ticker_ok, "price_ok": None,
              "xcheck_ok": None if xcheck_text is None else quote_in(q, xcheck_text)}
    if bad:
        checks["numbers_missing"] = sorted(set(bad))
    return checks


def failed(checks: dict) -> list[str]:
    """Names of the checks that failed, for the loader's `fail` field."""
    return [k for k in ("quote_ok", "numbers_ok", "ticker_ok", "price_ok", "xcheck_ok") if checks.get(k) is False] + (
        ["rule_errors"] if checks.get("rule_errors") else [])


def status(checks: dict) -> str:
    hard = [checks["quote_ok"], checks["numbers_ok"]]
    soft = [checks[k] for k in ("ticker_ok", "price_ok", "xcheck_ok")]
    return "ok" if all(hard) and all(v is not False for v in soft) else "needs_review"
