"""daytrader-strategy-v1: LPP's strategy written down as rules (spec-audit CAP-14, story audit-19-strategy).

  cd app && uv run python -m backtest.strategy --estimate      # tables + prompt size and cost, no call
  cd app && uv run python -m backtest.strategy                 # propose (cached), verify, trace, write the key
  cd app && uv run python -m backtest.strategy --no-trace      # same, without the PRISM run

The model proposes, the code decides (AGENTS.md rule 3):
1. code: every number. The headline's copied trades (rule 13, `all`, 5 min, after the cash cap) get features from
   what he did (ticker, side, the time he posted the first leg, his stated reason, adds, exits, size, how many
   trades that day); tables, setups, worst days and losing patterns are group-bys over those features;
2. model (Claude Sonnet via Nicrron): given ONLY those tables and up to 40 short rule quotes, it proposes up to 8
   plain-words rules, each with a machine-readable `when` (the situation) and `does` (what he does in it);
3. code: each rule is checked against the trades. `follows_pct` = of the trades in the situation, the share where
   he does it; a rule is kept only with 15+ trades in the situation, 15+ following it and follows_pct >= 60.
   Its win rate and P&L are those of the trades that follow it. Dropped rules are listed with the reason.

Replies are cached in data/lpp/strategy/ (keyed by the prompt's sha256); spend is capped at BUDGET_USD.
`backtest.run` re-attaches `strategy_profile` on every rebuild from the cached reply, recomputing every number.
app/audit/strategy.py recomputes the numbers independently from the audit's own trades (audit.run).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from statistics import median

from . import bars, engine
from .common import DATA, DEFAULT_DELAY_MIN, RESULTS, git_sha, public_json

AGENT_ID, PROMPT_VERSION = "daytrader-strategy-v1", "strategy-v1.1"
MODEL = "anthropic/claude-sonnet-5-5"
PRICE = {"in": 2.0 / 1e6, "out": 10.0 / 1e6}      # Nicrron, per token (notes/sponsors.md)
BUDGET_USD = 3.0
OUT = DATA / "lpp" / "strategy"
PRISM_RUN = "https://prism.blockconvey.com/trajectories/{}"
MAX_RULES, MAX_QUOTES = 8, 40
MIN_TRADES, MIN_FOLLOWS = 15, 60                   # a kept rule: 15+ trades in its situation and following it, 60%+
PATTERN_MIN = 15                                   # a losing pattern covers 15+ trades
PATTERN_WHAT = ("side", "group", "ticker", "setup")
PATTERN_HOW = ("time30", "adds", "exit", "hold")              # paired with PATTERN_WHAT
PATTERN_ALSO = ("size", "day_trades")                        # single conditions only

# ---- definitions (written into the file; app/audit/strategy.py evaluates them on its own trades) ----------------

# By what the company is, not by how his trades in it did.
TICKER_GROUPS = {
    "big tech": ["TSLA", "NVDA", "AMD", "AVGO", "AMZN", "AAPL", "META", "MSFT", "GOOGL", "GOOG", "NFLX"],
    "crypto-linked": ["MSTR", "COIN", "HOOD", "MARA", "RIOT", "CLSK"],
    "hot small and mid caps": ["PLTR", "SOUN", "HIMS", "SOFI", "SMCI", "TEM", "RDDT", "DJT", "OPEN", "GME", "AI",
                               "CVNA", "IONQ", "RKLB", "RGTI", "QBTS", "OKLO", "APP", "UPST", "AFRM"],
    "index funds": ["SPY", "QQQ", "TQQQ", "SQQQ", "IWM", "SPXS", "SPXL"],
}
OTHER_GROUP = "other"
HOLD_BUCKETS = [(15, "under 15 min"), (60, "15-60 min"), (180, "1-3 h"), (None, "3 h or more")]
SIZE_BUCKETS = [(10_000, "under $10k"), (50_000, "$10k-50k"), (None, "$50k or more")]
DAY_BUCKETS = [(2, "1"), (4, "2-3"), (6, "4-5"), (None, "6 or more")]   # every bucket: value < its top
FEATURES = ("side", "group", "ticker", "time15", "time30", "setup", "adds", "exit", "hold", "size", "day_trades",
            "portfolio")
FEATURE_HELP = {
    "side": "long | short",
    "group": "the ticker's group (definitions.ticker_groups)",
    "ticker": "the symbol",
    "time15": "ET time he posted the first leg, 15-min bucket start (\"before 09:30\", \"09:30\", \"09:45\", ...)",
    "time30": "the same, 30-min buckets (\"09:30\", \"10:00\", \"10:30\", \"11:00 or later\")",
    "setup": "his stated reason, by keywords (definitions.setups, first match wins)",
    "adds": "none | to_loser (any add at a worse price than his average so far) | to_winner (every add better)",
    "exit": "stated (he said he closed on the stream) | assumed (rule 13: left at 15:55 ET, or his stated hold)",
    "hold": "copy's minutes from first entry to last exit (definitions.hold_buckets)",
    "size": "his first buy in dollars: his share count x the entry price (definitions.size_buckets)",
    "day_trades": "how many of these trades he opened that session (definitions.day_buckets)",
    "portfolio": "day | swing",
}


def _bucket(v, buckets):
    for top, label in buckets:
        if top is None or v < top:
            return label
    return buckets[-1][1]


def group_of(ticker: str) -> str:
    return next((g for g, ts in TICKER_GROUPS.items() if ticker in ts), OTHER_GROUP)


def setups_def(mod) -> list[dict]:
    return [{"id": s["id"], "name": s["name"], "side": s["side"], "words": list(s.get("words") or ())}
            for s in mod.STRATEGIES]


def time15(t: dt.datetime) -> str:
    if (t.hour, t.minute) < (9, 30):
        return "before 09:30"
    return f"{t.hour:02d}:{t.minute // 15 * 15:02d}"


def time30(t: dt.datetime) -> str:
    if (t.hour, t.minute) < (10, 0):
        return "09:30"
    if (t.hour, t.minute) >= (11, 0):
        return "11:00 or later"
    return f"{t.hour:02d}:{t.minute // 30 * 30:02d}"


def add_kind(r: engine.Result) -> str:
    """From the copy's own buys (rule 13e fills at the chosen delay): an add at a worse price than the average so
    far is an add to a loser (higher for a short, lower for a long)."""
    buys = [f for f in r.fills if f.kind == "entry"]
    if len(buys) < 2:
        return "none"
    sign = 1 if r.position.side == "long" else -1
    qty = notional = 0.0
    worse = False
    for k, f in enumerate(buys):
        if k and sign * (f.px - notional / qty) < 0:
            worse = True
        qty, notional = qty + f.qty, notional + f.qty * f.px
    return "to_loser" if worse else "to_winner"


def features(mod, kept: list) -> list[dict]:
    """One row per copied trade: what he did, and the copied P&L (the headline's own number)."""
    rows = []
    for r, pnl in kept:
        p = r.position
        t = dt.datetime.fromtimestamp(p.legs[0].posted_ts, bars.ET)
        first_qty = p.legs[0].qty
        size = _bucket(first_qty * r.entry.px, SIZE_BUCKETS) if first_qty else "not stated"
        rows.append({"pid": p.pid, "day": t.date().isoformat(), "ticker": p.ticker, "side": p.side,
                     "group": group_of(p.ticker), "time15": time15(t), "time30": time30(t),
                     "setup": mod.strategy_of(p), "adds": add_kind(r),
                     "exit": "assumed" if r.assumed_exit else "stated",
                     "hold": "overnight" if p.portfolio == "swing"
                     else _bucket((r.last_exit.ts - r.entry.ts) / 60, HOLD_BUCKETS),
                     "size": size, "portfolio": p.portfolio, "pnl": pnl,
                     "n_adds": sum(lg.action == "add" for lg in p.legs),
                     "n_trims": sum(lg.action == "trim" for lg in p.legs),
                     "his_qty": first_qty, "his_usd": first_qty * r.entry.px if first_qty else None})
    per_day = Counter(x["day"] for x in rows)
    for x in rows:
        x["day_trades"] = _bucket(per_day[x["day"]], DAY_BUCKETS)
    return rows


# ---- group-bys -------------------------------------------------------------------------------------------------

def stats(rows: list[dict], total: int | None = None) -> dict:
    wins = [x["pnl"] for x in rows if x["pnl"] > 0]
    losses = [x["pnl"] for x in rows if x["pnl"] <= 0]
    out = {"trades": len(rows), "won_pct": round(100 * len(wins) / len(rows)) if rows else 0,
           "pnl_usd": round(sum(x["pnl"] for x in rows), 2),
           "avg_win_usd": round(sum(wins) / len(wins), 2) if wins else None,
           "avg_loss_usd": round(sum(losses) / len(losses), 2) if losses else None}
    if total:
        out["share_pct"] = round(100 * len(rows) / total, 1)
    return out


def matches(x: dict, cond: dict | None) -> bool:
    """A condition is {feature: [allowed values]}; every listed feature must match. Empty = every trade."""
    for k, allowed in (cond or {}).items():
        if x.get(k) not in (allowed if isinstance(allowed, list) else [allowed]):
            return False
    return True


TABLES = [("side", "Long or short"), ("group", "What he trades"), ("ticker", "Tickers"),
          ("time15", "When he posts the first leg (ET, 15 min)"), ("setup", "His stated reason"),
          ("adds", "Adding to a position"), ("exit", "How it ended"), ("hold", "How long the copy held"),
          ("size", "His size on the first buy"), ("day_trades", "Trades he opened that day")]


ORDER = {"side": ["long", "short"], "adds": ["none", "to_loser", "to_winner"], "exit": ["stated", "assumed"],
         "hold": [lab for _, lab in HOLD_BUCKETS] + ["overnight"],
         "size": ["not stated"] + [lab for _, lab in SIZE_BUCKETS], "day_trades": [lab for _, lab in DAY_BUCKETS],
         "time15": ["before 09:30"], "portfolio": ["day", "swing"]}   # time15: then by clock (sorted)


def table(rows: list[dict], by: str, top: int | None = None) -> list[dict]:
    keys = Counter(x[by] for x in rows)
    fixed = ORDER.get(by)
    order = ([k for k in fixed if k in keys] + sorted(k for k in keys if k not in fixed)) if fixed \
        else sorted(keys, key=lambda k: (-keys[k], str(k)))
    out = []
    for k in order[:top] if top else order:
        out.append({"key": k, **stats([x for x in rows if x[by] == k], len(rows))})
    if top and len(order) > top:
        rest = [x for x in rows if x[by] not in order[:top]]
        out.append({"key": "other", "keys": len(order) - top, **stats(rest, len(rows))})
    return out


def worst_days(rows: list[dict], n: int = 10) -> list[dict]:
    by_day = defaultdict(list)
    for x in rows:
        by_day[x["day"]].append(x)
    days = sorted(by_day, key=lambda d: (sum(x["pnl"] for x in by_day[d]), d))[:n]
    out = []
    for d in days:
        g = by_day[d]
        out.append({"day": d, **stats(g), "shorts": sum(x["side"] == "short" for x in g),
                    "adds_to_loser": sum(x["adds"] == "to_loser" for x in g),
                    "exits_assumed": sum(x["exit"] == "assumed" for x in g),
                    "tickers": [t for t, _ in Counter(x["ticker"] for x in g).most_common(3)]})
    return out


def setups(rows: list[dict], min_trades: int = 10) -> list[dict]:
    """Clusters: (side, group, 30-min entry window, stated reason) with min_trades or more."""
    keys = Counter((x["side"], x["group"], x["time30"], x["setup"]) for x in rows)
    out = []
    for (side, group, t30, setup), n in keys.most_common():
        if n < min_trades:
            break
        when = {"side": [side], "group": [group], "time30": [t30], "setup": [setup]}
        out.append({"when": when, **stats([x for x in rows if matches(x, when)], len(rows))})
    return out


def describe(when: dict, setups_by_id: dict) -> str:
    """A condition in plain words (code, not the model): {"group": ["big tech"], "adds": ["to_loser"]} ->
    "Big tech, added to a loser"."""
    words = {"side": {"short": "shorts", "long": "longs"},
             "adds": {"to_loser": "added to a loser", "to_winner": "added to a winner", "none": "no adds"},
             "exit": {"assumed": "not closed on the stream", "stated": "closed on the stream"}}
    parts = []
    for k, vals in when.items():
        v = " or ".join(vals)
        if k in words:
            parts.append(" or ".join(words[k].get(x, x) for x in vals))
        elif k == "setup":
            parts.append(" or ".join(setups_by_id.get(x, x).lower() for x in vals))
        elif k in ("time15", "time30"):
            parts.append(f"posted at {v} ET")
        elif k == "hold":
            parts.append(f"held {v}")
        elif k == "size":
            parts.append(f"his size {v}")
        elif k == "day_trades":
            parts.append(f"{v} trades that day")
        else:
            parts.append(v)
    text = ", ".join(parts)
    return text[:1].upper() + text[1:]


def losing_patterns(rows: list[dict], n: int = 3, setups_by_id: dict | None = None) -> list[dict]:
    """The n patterns that lost the most money: every one-feature condition, and every pair of what he traded
    (side, group, ticker, reason) with another of those or how he traded it (time, adds, exit, hold), with
    PATTERN_MIN+ trades, by total P&L; a pattern sharing more than half its trades with one already picked is
    skipped."""
    cands = {}
    for a in PATTERN_WHAT + PATTERN_HOW + PATTERN_ALSO:
        for va in {x[a] for x in rows}:
            cands[((a, va),)] = None
    for i, a in enumerate(PATTERN_WHAT):   # pairs: what he traded x how he traded it
        for b in PATTERN_WHAT[i + 1:] + PATTERN_HOW:
            for va in {x[a] for x in rows}:
                for vb in {x[b] for x in rows if x[a] == va}:
                    cands[((a, va), (b, vb))] = None
    scored = []
    for c in cands:
        when = {k: [v] for k, v in c}
        ids = frozenset(x["pid"] for x in rows if matches(x, when))
        if len(ids) >= PATTERN_MIN:
            pnl = sum(x["pnl"] for x in rows if x["pid"] in ids)
            scored.append((round(pnl, 2), len(c), json.dumps(when, sort_keys=True), when, ids))
    scored.sort(key=lambda s: s[:3])
    losses = -sum(x["pnl"] for x in rows if x["pnl"] < 0)
    picked = []
    for pnl, _, _, when, ids in scored:
        if pnl >= 0 or len(picked) == n:
            break
        if any(len(ids & q) > 0.5 * min(len(ids), len(q)) for _, q in picked):
            continue
        picked.append((when, ids))
    out = []
    for when, ids in picked:
        g = [x for x in rows if x["pid"] in ids]
        lost = -sum(x["pnl"] for x in g if x["pnl"] < 0)
        out.append({"id": "-".join(f"{k}:{v[0]}" for k, v in when.items()).replace(" ", "_"), "when": when,
                    "label": describe(when, setups_by_id or {}),
                    **stats(g, len(rows)), "share_of_losses_pct": round(100 * lost / losses, 1) if losses else 0})
    return out


def tables_for(rows: list[dict]) -> list[dict]:
    return [{"id": by, "label": label, "by": by, "rows": table(rows, by, top=12 if by == "ticker" else None)}
            for by, label in TABLES]


def summary(rows: list[dict]) -> dict:
    per_day = Counter(x["day"] for x in rows)
    usd = sorted(x["his_usd"] for x in rows if x["his_usd"])
    qty = sorted(x["his_qty"] for x in rows if x["his_qty"])
    adds = [x for x in rows if x["n_adds"]]
    return {"trades": len(rows), "sessions": len(per_day), "pnl_usd": round(sum(x["pnl"] for x in rows), 2),
            "won_pct": stats(rows)["won_pct"],
            "trades_per_session": {"median": median(per_day.values()), "max": max(per_day.values())},
            "his_size": {"stated_on": len(qty), "median_shares": median(qty) if qty else None,
                         "median_usd": round(median(usd)) if usd else None,
                         "p90_usd": round(usd[int(0.9 * (len(usd) - 1))]) if usd else None},
            "adds": {"his_add_posts": sum(x["n_adds"] for x in rows), "trades_he_added_to": len(adds),
                     "copied_with_adds": sum(x["adds"] != "none" for x in rows),
                     "to_loser": sum(x["adds"] == "to_loser" for x in rows),
                     "to_winner": sum(x["adds"] == "to_winner" for x in rows)},
            "trims": {"his_trim_posts": sum(x["n_trims"] for x in rows),
                      "trades_he_trimmed": sum(bool(x["n_trims"]) for x in rows)}}


# ---- the model's input: tables + short rule quotes ------------------------------------------------------------

QUOTE_WORDS = ("short", "long", "overbought", "oversold", "add", "size", "open", "stop", "close", "resistance",
               "support", "momentum", "cover", "profit", "loss", "risk", "trim", "reduce", "morning", "first")


def rule_quotes(mod, version: str = "v1", n: int = MAX_QUOTES) -> list[dict]:
    """Up to n of his rules (status ok, quote 12 words or fewer, paraphrase 15 or fewer) that talk about how he
    trades, spread over the window: the most on-topic one per session, then evenly spaced."""
    best = {}
    for e in mod.load(version):
        q, rule = e.get("quote") or "", e.get("rule") or ""
        if e["type"] != "rule" or e["status"] != "ok" or not q or len(q.split()) > 12 or len(rule.split()) > 15:
            continue
        score = sum(w in (rule + " " + q).lower() for w in QUOTE_WORDS)
        key = e["source_id"]
        if score and (key not in best or score > best[key][0]):
            best[key] = (score, e)
    evs = sorted((e for _, e in best.values()), key=lambda e: (e["session_date"], e["t_s"]))
    step = max(1, len(evs) / n)
    picked = [evs[int(i * step)] for i in range(min(n, len(evs)))]
    return [{"id": f"Q{i + 1}", "rule": e["rule"], "text": e["quote"], "cite": mod.cite(e)}
            for i, e in enumerate(picked)]


def prompt(tabs: list[dict], summ: dict, sets: list[dict], worst: list[dict], quotes: list[dict],
           defs: dict) -> str:
    slim = [{"by": t["by"], "rows": [{k: v for k, v in r.items() if k != "avg_win_usd" and k != "avg_loss_usd"}
                                     for r in t["rows"]]} for t in tabs]
    return (
        "You describe a day trader's strategy from data. He is the host of a paid trading course; below is what "
        "he actually did on his live streams (2024-08 to 2025-09), copied with $1,000 per first buy after costs. "
        "Each row: trades, share_pct of all his trades, won_pct, pnl_usd (copied P&L, the sum over those trades)."
        "\n\nPropose at most 8 rules that describe HOW HE TRADES, in plain words a non-trader understands "
        "(e.g. \"He shorts big tech stocks in the first 30 minutes\"). Describe what he does, not advice. "
        "Each rule must be checkable on the trades: give `when` (the situation) and `does` (what he does in it), "
        "each a map from a feature to a list of allowed values, using ONLY these features and values that appear "
        f"in the tables: {json.dumps(FEATURE_HELP)}. `when` may be {{}} (all his trades). Code will measure, among "
        "trades matching `when`, the share that also match `does`, and drop rules the data doesn't support "
        "(fewer than 15 trades, or followed less than 60% of the time). Prefer specific rules that combine what he "
        "trades, when, why and how (e.g. side + group + time + reason, or what he does after entering: adds, "
        "exits, hold) over generic ones, as long as each still covers 15+ trades; cover his losing habits too. "
        "Pick one quote id whose words say the same thing as the rule (never one that contradicts it); null "
        "when none does."
        "\n\nReply with JSON only: {\"rules\": [{\"text\": <20 words or fewer>, \"when\": {...}, \"does\": {...}, "
        "\"quote_id\": <\"Q..\" or null>}]}"
        f"\n\nSummary: {json.dumps(summ)}\nTables: {json.dumps(slim)}\nSetups (side, group, 30-min window, reason): "
        f"{json.dumps(sets)}\nWorst days: {json.dumps(worst)}\nDefinitions: {json.dumps(defs)}"
        f"\nHis rules (paraphrase + quote): {json.dumps([{k: q[k] for k in ('id', 'rule', 'text')} for q in quotes])}")


def _parse(txt: str) -> dict:
    txt = re.sub(r"^```(?:json)?|```$", "", (txt or "").strip()).strip()
    return json.JSONDecoder().raw_decode(txt[txt.find("{"):])[0]


def cost(u: dict) -> float:
    return (u.get("in") or 0) * PRICE["in"] + (u.get("out") or 0) * PRICE["out"]


def spent() -> float:
    return sum(cost(json.loads(p.read_text()).get("usage") or {}) for p in OUT.glob("reply-*.json"))


def cache_path(text: str):
    return OUT / f"reply-{hashlib.sha256(text.encode()).hexdigest()[:16]}.json"


def call(text: str) -> dict:
    """One streamed Sonnet call through Nicrron (it drops non-streamed calls at ~30 s), retried once."""
    from openai import OpenAI
    client = OpenAI(base_url=os.getenv("NICRRON_BASE_URL", "https://api.nicrron.ai/v1"),
                    api_key=os.environ["NICRRON_API_KEY"], timeout=300, max_retries=1)
    errors = []
    for attempt in range(2):
        t0 = time.time()
        try:
            parts, usage, finish = [], None, None
            for ev in client.chat.completions.create(model=MODEL, temperature=0.0, max_tokens=12000, stream=True,
                                                     messages=[{"role": "user", "content": text}],
                                                     stream_options={"include_usage": True}):
                if ev.choices:
                    if ev.choices[0].delta.content:
                        parts.append(ev.choices[0].delta.content)
                    finish = ev.choices[0].finish_reason or finish
                if getattr(ev, "usage", None):
                    usage = ev.usage
            u = {"in": getattr(usage, "prompt_tokens", 0) or 0, "out": getattr(usage, "completion_tokens", 0) or 0}
            return {"reply": _parse("".join(parts)), "model": MODEL, "prompt_version": PROMPT_VERSION,
                    "secs": round(time.time() - t0, 1), "finish": finish, "usage": u, "errors": errors}
        except Exception as e:  # noqa: BLE001 - logged in the cache file and the trace
            errors.append({"attempt": attempt, "error": f"{type(e).__name__}: {str(e)[:160]}"})
    return {"reply": None, "model": MODEL, "prompt_version": PROMPT_VERSION, "usage": {"in": 0, "out": 0},
            "errors": errors}


# ---- code decides ---------------------------------------------------------------------------------------------

def check_cond(cond, rows: list[dict]) -> str | None:
    """None when the condition uses known features and values that occur; else the failing check's name."""
    if not isinstance(cond, dict):
        return "condition_not_a_map"
    for k, v in cond.items():
        if k not in FEATURES:
            return f"unknown_feature:{k}"
        vals = v if isinstance(v, list) else [v]
        if not vals:
            return f"empty_values:{k}"
        seen = {x[k] for x in rows}
        bad = [str(x) for x in vals if x not in seen]
        if bad:
            return f"unknown_value:{k}={bad[0]}"
    return None


def norm(cond: dict) -> dict:
    return {k: sorted(v if isinstance(v, list) else [v]) for k, v in sorted(cond.items())}


# Quotes a reviewer found don't say what their rule says (PR #67 review), by cached reply (prompt sha) and the
# proposal's index: shown as null until story 25 verifies every rule-quote pair.
QUOTES_NOT_SUPPORTING = {
    "671eacb1fbc558ea": {0: "says a reversal setup, not that he mostly shorts",
                         7: "says mind your size, not his size range"},
}
HEDGES = [r",? in about [\w ]+? of every [\w ]+?(?= *[,.]|$)", r"\b(?:almost always|usually|mostly|often|most of the time)\s+",
          r"\bmost (?=trades\b)"]


def plain(text: str, pct: float) -> str:
    """The model's hedge words ("usually", "almost always", "four of every five") are replaced by the number code
    measured: the hedges are removed and the computed follows_pct is appended."""
    out = text.strip().rstrip(".")
    for h in HEDGES:
        out = re.sub(h, "", out, flags=re.I)
    out = re.sub(r"\s+,", ",", re.sub(r"\s{2,}", " ", out)).strip(" ,")
    return f"{out} ({int(pct + 0.5)}% of the time)."


def check_does(when: dict, does: dict, rows: list[dict]) -> str | None:
    """A `does` that repeats its `when`, or allows every value its feature takes, says nothing."""
    for k, vals in does.items():
        if k in when and set(vals) & set(when[k]):
            return f"does_repeats_when:{k}"
        if set(vals) >= {x[k] for x in rows}:
            return f"does_covers_every_value:{k}"
    return None


def verify(proposed, rows: list[dict], quotes: list[dict], prompt_sha: str | None = None) -> tuple[list[dict], list[dict]]:
    """Each proposed rule against the trades. Kept: MIN_TRADES+ in the situation and following it, MIN_FOLLOWS%+."""
    qs = {q["id"]: q for q in quotes}
    hidden = QUOTES_NOT_SUPPORTING.get(prompt_sha or "", {})
    kept, dropped = [], []
    for i, p in enumerate((proposed if isinstance(proposed, list) else [])[:MAX_RULES]):
        if not isinstance(p, dict):
            dropped.append({"text": str(p)[:80], "why": "proposal_not_a_map"})
            continue
        text = str(p.get("text") or "").strip()
        bad = None if text and len(text.split()) <= 20 else "text_missing_or_over_20_words"
        bad = bad or check_cond(p.get("when", {}), rows) or check_cond(p.get("does"), rows)
        if not bad and not p.get("does"):
            bad = "does_empty"
        bad = bad or check_does(norm(p.get("when") or {}), norm(p["does"]), rows)
        if bad:
            dropped.append({"text": text, "why": bad})
            continue
        when, does = norm(p.get("when") or {}), norm(p["does"])
        situ = [x for x in rows if matches(x, when)]
        follow = [x for x in situ if matches(x, does)]
        pct = round(100 * len(follow) / len(situ), 1) if situ else 0.0
        row = {"text": plain(text, pct), "proposed_text": text, "when": when, "does": does,
               "situation_trades": len(situ), "follows_pct": pct, **stats(follow, len(rows))}
        if len(situ) < MIN_TRADES or len(follow) < MIN_TRADES:
            dropped.append({**row, "why": f"fewer than {MIN_TRADES} trades"})
            continue
        if pct < MIN_FOLLOWS:
            dropped.append({**row, "why": f"followed {pct}% of the time (under {MIN_FOLLOWS}%)"})
            continue
        q = qs.get(p.get("quote_id"))
        row["quote"] = {"text": q["text"], "cite": q["cite"]} if q and i not in hidden else None
        if q and i in hidden:
            row["quote_hidden"] = hidden[i]
        kept.append({"id": f"S{len(kept) + 1}", **row})
    return kept, dropped


def definitions(mod) -> dict:
    return {"ticker_groups": TICKER_GROUPS, "other_group": OTHER_GROUP, "setups": setups_def(mod),
            "hold_buckets_min": [[t, lab] for t, lab in HOLD_BUCKETS],
            "size_buckets_usd": [[t, lab] for t, lab in SIZE_BUCKETS],
            "day_buckets": [[t, lab] for t, lab in DAY_BUCKETS], "features": FEATURE_HELP,
            "kept_if": {"min_trades": MIN_TRADES, "min_follows_pct": MIN_FOLLOWS},
            "pattern_min_trades": PATTERN_MIN}


def computed(mod, kept_results: list) -> dict:
    rows = features(mod, kept_results)
    names = {s["id"]: s["name"] for s in mod.STRATEGIES}
    return {"rows": rows, "tables": tables_for(rows), "summary": summary(rows), "setups": setups(rows),
            "worst_days": worst_days(rows), "losing_patterns": losing_patterns(rows, setups_by_id=names)}


def profile(mod, version: str, kept_results: list, cached: dict | None, delay: int = DEFAULT_DELAY_MIN) -> dict | None:
    """The `strategy_profile` key (contracts.md): every number from the copied trades; rule wording from the cached
    model reply (None until `python -m backtest.strategy` has run)."""
    if not cached or not cached.get("reply"):
        return None
    reply = cached["reply"]
    if not isinstance(reply, dict) or not isinstance(reply.get("rules"), list) or not isinstance(cached.get("quotes"), list):
        print("  strategy_profile skipped: cached reply is malformed (no rules list or no quotes)")
        return None
    c = computed(mod, kept_results)
    rules, dropped = verify(reply["rules"], c["rows"], cached["quotes"], cached.get("prompt_sha"))
    return {"agent_id": AGENT_ID, "prompt_version": PROMPT_VERSION, "model": cached.get("model"),
            "trajectory_id": cached.get("trajectory_id"),
            "prism_url": PRISM_RUN.format(cached["trajectory_id"]) if cached.get("trajectory_id") else None,
            "version": version, "portfolio": "all", "delay_min": delay,
            "basis": "The headline's copied trades (rule 13, all, after the cash cap); P&L is the copied P&L",
            "summary": c["summary"], "tables": c["tables"], "setups": c["setups"], "worst_days": c["worst_days"],
            "rules": rules, "dropped": dropped, "losing_patterns": c["losing_patterns"],
            "definitions": definitions(mod)}


def stored(version: str = "v1") -> dict | None:
    """The cached reply backtest.run re-attaches (data/lpp/strategy/lpp-<version>.json)."""
    p = OUT / f"lpp-{version}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        print(f"  strategy_profile skipped: {p.name} is not JSON ({e.msg})")
        return None
    return d if isinstance(d, dict) else None


# ---- PRISM (contract 5) ---------------------------------------------------------------------------------------

def trace(c: dict, quotes: list, res: dict, rules: list, dropped: list, version: str, delay: int) -> str | None:
    from prismtrace import PRISMtrace
    import uuid
    failed = None if res.get("reply") else "reply_not_json"
    if not failed and not rules:
        failed = "no_rule_supported_by_data"
    steps = [
        {"step_type": "tool_call", "tool_name": "load_results", "label": "load_results",
         "input_summary": json.dumps({"results": f"results/lpp/{version}.json", "portfolio": "all",
                                      "delay_min": delay, "ledger": "rule 13"}),
         "output_summary": json.dumps({k: c["summary"][k] for k in ("trades", "sessions", "pnl_usd", "won_pct")})},
        {"step_type": "tool_call", "tool_name": "compute_tables", "label": "compute_tables",
         "input_summary": json.dumps({"features": list(FEATURES)}),
         "output_summary": json.dumps({"tables": [t["by"] for t in c["tables"]], "setups": len(c["setups"]),
                                       "losing_patterns": [p["id"] for p in c["losing_patterns"]]})},
        {"step_type": "tool_call", "tool_name": "load_rule_quotes", "label": "load_rule_quotes",
         "input_summary": json.dumps({"events": f"data/lpp/events.jsonl ({version})", "type": "rule",
                                      "status": "ok", "max": MAX_QUOTES}),
         "output_summary": json.dumps({"quotes": len(quotes), "cites": [q["cite"]["label"] for q in quotes[:5]]})},
        {"step_type": "reasoning", "label": "llm_propose_rules",
         "input_summary": json.dumps({"model": res.get("model"), "prompt_version": PROMPT_VERSION,
                                      "prompt_sha": res.get("prompt_sha")}),
         "output_summary": json.dumps(res.get("reply"))[:4000],
         "duration_ms": int((res.get("secs") or 0) * 1000),
         "token_count": (res["usage"].get("in", 0) + res["usage"].get("out", 0)),
         "status": "error" if failed == "reply_not_json" else "success"},
        {"step_type": "tool_call", "tool_name": "verify_rules", "label": "verify_rules",
         "input_summary": json.dumps({"min_trades": MIN_TRADES, "min_follows_pct": MIN_FOLLOWS}),
         "output_summary": json.dumps({"kept": [{k: r[k] for k in ("text", "follows_pct", "trades", "won_pct",
                                                                    "pnl_usd")} for r in rules],
                                       "dropped": [{k: d.get(k) for k in ("text", "why")} for d in dropped]}),
         "status": "error" if failed else "success"},
        {"step_type": "final_answer", "label": "strategy_profile",
         "output_summary": json.dumps({"check": failed} if failed else
                                      {"rules": [r["text"] for r in rules],
                                       "losing_patterns": [p["id"] for p in c["losing_patterns"]]})},
    ]
    pt = PRISMtrace(api_key=os.environ["PRISMTRACE_API_KEY"], project_id=os.environ["PRISMTRACE_PROJECT_ID"],
                    host=os.getenv("PRISMTRACE_HOST", "https://api.prism.blockconvey.com"))
    meta = {"agent_version": "v1", "course": "lpp", "prompt_version": PROMPT_VERSION, "git_sha": git_sha(),
            "proof_set": False}
    body = {"project_id": pt.project_id, "conversation_id": f"strategy-lpp-{version}", "request_id": str(uuid.uuid4()),
            "agent_id": AGENT_ID, "agent_name": "Day Trader AI strategy v1", "steps": steps,
            "total_duration_ms": sum(s.get("duration_ms") or 0 for s in steps),
            "final_status": "error" if failed else "success", "model": res.get("model"), "metadata": meta}
    sent = pt._post_sync("/api/trajectories", body) or pt.submit_trajectory(
        steps, agent_id=AGENT_ID, agent_name=body["agent_name"], conversation_id=body["conversation_id"],
        model=body["model"], final_status=body["final_status"])
    return (sent or {}).get("id") if isinstance(sent, dict) else None


def headline_kept(mod, version: str, delay: int):
    """The headline's copied trades at one delay: rule 13 positions, priced, through the cash cap."""
    from .run import prefetch
    built = mod.build(version)
    seen = Counter()
    for p in built["positions"]:   # the same unique ids backtest.run gives
        seen[p.pid] += 1
        if seen[p.pid] > 1:
            p.pid = f"{p.pid}-{seen[p.pid]}"
        p.scale = True
    prefetch(built["positions"])
    rs = [engine.simulate(p, delay) for p in built["positions"]]
    kept, *_ = engine.fit_to_cash([r for r in rs if r.status == "priced"])
    return kept


def main():
    from . import lpp as mod
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    ap.add_argument("--estimate", action="store_true", help="tables, prompt size and cost; no call")
    ap.add_argument("--no-trace", action="store_true")
    a = ap.parse_args()
    d = DEFAULT_DELAY_MIN
    c = computed(mod, headline_kept(mod, a.version, d))
    quotes = rule_quotes(mod, a.version)
    defs = {k: v for k, v in definitions(mod).items() if k in ("ticker_groups", "setups")}
    text = prompt(c["tables"], c["summary"], c["setups"], c["worst_days"], quotes, defs)
    est = len(text) / 3.5 * PRICE["in"] + 6000 * PRICE["out"]
    print(f"trades {c['summary']['trades']}, P&L {c['summary']['pnl_usd']}, quotes {len(quotes)}, "
          f"prompt ~{len(text) / 3.5:,.0f} tokens, est ${est:.2f}, spent so far ${spent():.2f} of ${BUDGET_USD}")
    for p in c["losing_patterns"]:
        print("  losing pattern", p["id"], p["trades"], p["pnl_usd"], f"{p['won_pct']}% won")
    if a.estimate:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    cp = cache_path(text)
    if cp.exists():
        res = json.loads(cp.read_text())
        print("cached reply", cp.name)
    else:
        if spent() + est > BUDGET_USD:
            raise SystemExit(f"budget: ${spent():.2f} spent, this call ~${est:.2f}, cap ${BUDGET_USD}")
        res = call(text)
        res["prompt_sha"] = cp.stem.split("-", 1)[1]
        cp.write_text(json.dumps(res, indent=1))
        print(f"model reply in {res.get('secs')} s, ${cost(res['usage']):.3f}; errors {res['errors']}")
    if not res.get("reply"):
        print("no usable reply:", res.get("errors"))
    rules, dropped = verify((res.get("reply") or {}).get("rules") or [], c["rows"], quotes, res.get("prompt_sha"))
    for r in rules:
        print(f"  KEPT {r['id']} {r['text']} | follows {r['follows_pct']}% of {r['situation_trades']}, "
              f"{r['trades']} trades, won {r['won_pct']}%, P&L {r['pnl_usd']}")
    for x in dropped:
        print(f"  DROPPED {x['text']} | {x['why']}")
    tid = None
    if not a.no_trace:
        tid = trace(c, quotes, res, rules, dropped, a.version, d)
        print("traced to PRISM:", tid)
    store = {"agent_id": AGENT_ID, "model": res.get("model"), "prompt_version": PROMPT_VERSION,
             "prompt_sha": res.get("prompt_sha"), "reply": res.get("reply"), "quotes": quotes, "usage": res["usage"],
             "trajectory_id": tid or (stored(a.version) or {}).get("trajectory_id"),
             "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    (OUT / f"lpp-{a.version}.json").write_text(json.dumps(store, indent=1))
    rp = RESULTS / "lpp" / f"{a.version}.json"
    out = json.loads(rp.read_text())
    if out.get("same_sessions"):
        raise SystemExit("a proof-set file carries no strategy_profile (rule 9)")
    sp = profile(mod, a.version, headline_kept(mod, a.version, d), store, d)
    out["strategy_profile"] = sp
    rp.write_text(public_json(out))
    print(f"wrote strategy_profile to {rp}: {len(sp['rules'])} rules kept, {len(sp['dropped'])} dropped; "
          f"spent ${spent():.2f} of ${BUDGET_USD}. Next: backtest.run --ledger-only, then audit.run")


if __name__ == "__main__":
    main()
