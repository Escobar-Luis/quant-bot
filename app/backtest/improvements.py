"""daytrader-improver-v2: rule changes from his losses, written as code filters on HIS trades (spec-audit CAP-15,
story audit-20-improve). Shape and rules: contracts.md, section `improvements`.

  cd app && uv run python -m backtest.improver --v2 --estimate   # dev tables, prompt size and cost; no call
  cd app && uv run python -m backtest.improver --v2              # propose (cached), test, trace, write the key
  cd app && uv run python -m backtest.improver --v2 --no-trace   # same, without the PRISM run

The model proposes, the code decides (AGENTS.md rule 3); honest backtests (rule 4):
1. code: the headline's copied trades (rule 13, `all`, 5 min, after the cash cap), and the strategy_profile tables
   and losing patterns recomputed on the DEV months only (entries before window.sealed_from);
2. model (Claude Sonnet via Nicrron): given only those dev tables, his rules' wording and a menu of five kinds of
   change, it proposes up to 6 candidates, each a kind, a `when` over entry-time features and a number;
3. code: each candidate is checked (menu, features known at entry, value ranges), applied to every headline position
   (skip / only / no adds against the first buy / leave after N minutes / stop at X%), re-priced by the engine
   and run through the cash cap; dev and sealed months are slices of that one run. Kept only if it beats the
   as-is copy on dev AND does not lose on sealed AND keeps 30+ trades in each. Nothing is re-tuned on sealed.

Replies are cached in data/improver/v2/ (keyed by the prompt's sha256); this story's spend is capped at BUDGET_USD.
`backtest.run` re-attaches `improvements` on every rebuild from the cached reply, recomputing every number.
app/audit/improvements.py recomputes the numbers independently from the audit's own positions (audit.run).
"""
import copy
import datetime as dt
import json
import os
import uuid

from . import bars, engine, extras, strategy
from .common import DATA, DEFAULT_DELAY_MIN, MONEY_START, RESULTS, git_sha, public_json

AGENT_ID, PROMPT_VERSION = "daytrader-improver-v2", "improver-v2"
OUT = DATA / "improver" / "v2"
BUDGET_USD = 3.0
MAX_VARIANTS = 6
MIN_TRADES = 30                     # rule 9's floor, in dev and in sealed
ENTRY_FEATURES = ("side", "group", "ticker", "time15", "time30", "setup")   # known when the first buy fills
KINDS = {
    "skip": "don't copy a trade matching `when`",
    "only": "copy only the trades matching `when`",
    "no_add_against": "in trades matching `when`, skip every add whose fill is worse than the first buy's fill "
                      "(higher for a short, lower for a long)",
    "max_hold": "in trades matching `when`, leave whatever is still held `value` minutes after the first buy "
                "(5 to 390)",
    "stop_pct": "in trades matching `when`, leave when price moves `value` percent against the first buy's fill "
                "(0.5 to 10)",
}
RANGES = {"max_hold": (5, 390), "stop_pct": (0.5, 10.0)}
# The engineer's smoke tests of the machinery, run before the model's call with their sealed numbers seen
# (notes/research/backtesting.md section 6). They count toward every variant tried.
SMOKE_TESTS = [
    {"rule": "Skip TSLA shorts", "priced": True},
    {"rule": "No adds against the first buy, big tech", "priced": True, "same_as": "no_add_against big tech"},
    {"rule": "Leave shorts 60 min after the first buy", "priced": True},
    {"rule": "2% stop on every trade", "priced": True},
    {"rule": "Only crypto-linked or hot small and mid caps", "priced": True},
    {"rule": "Skip trades added to a loser", "priced": False, "why": "look_ahead_or_unknown_feature:adds"},
]
KEPT_LABEL = "held up (not proven)"
DISCLOSURE = [
    "The engineer ran 6 smoke tests before the model's call and saw their held-out numbers; they count as tried.",
    "The model saw dev-month tables only, but his rules' wording and the setup definitions came from the "
    "strategy profile, built from every month, held-out ones included.",
    "Kept means it held up on the held-out months, not that it is proven: small gains on about 100 trades can be "
    "luck after this many tries (story 27 tests that).",
]
KEEP_RULE = ("kept only if it beats the as-is copy on dev, does not lose on sealed, and keeps 30+ trades in each")


# ---- features known at entry (the strategy_profile definitions) ---------------------------------------------

UNKNOWN_SETUP = "unknown"


def first_fill_ts(p, r, delay: int) -> float:
    """The copy's first buy fill; a position not priced as-is: its first buy's post + delay."""
    if r is not None and r.status == "priced":
        return r.entry.ts
    return min(lg.posted_ts for lg in p.legs if lg.action in ("open", "add")) + delay * 60


def entry_setup(mod, p, whys: dict, at: float) -> str:
    """His stated reason, only from legs posted at or before the first fill (no look-ahead); none: unknown."""
    why = next((whys.get(lg.event_id) for lg in sorted(p.legs, key=lambda lg: lg.posted_ts)
                if lg.posted_ts <= at and whys.get(lg.event_id)), None)
    if not why:
        return UNKNOWN_SETUP
    q = copy.copy(p)
    q.why = why
    return mod.strategy_of(q)


def entry_features(mod, p, whys: dict, at: float) -> dict:
    t = dt.datetime.fromtimestamp(p.legs[0].posted_ts, bars.ET)
    return {"side": p.side, "group": strategy.group_of(p.ticker), "ticker": p.ticker,
            "time15": strategy.time15(t), "time30": strategy.time30(t), "setup": entry_setup(mod, p, whys, at)}


def all_features(mod, version: str, positions: list, base: dict, delay: int) -> dict:
    whys = {e["event_id"]: e.get("why") for e in mod.load(version)}
    return {p.pid: entry_features(mod, p, whys, first_fill_ts(p, base.get(p.pid), delay)) for p in positions}


def describe(v: dict, setups_by_id: dict) -> str:
    """The change in plain words, by code (what was actually tested)."""
    who = strategy.describe(v["when"], setups_by_id).lower() if v["when"] else "every trade"
    k, n = v["kind"], v.get("value")
    if k == "skip":
        return f"Skip: {who}"
    if k == "only":
        return f"Only copy: {who}"
    if k == "no_add_against":
        return f"No adds below the first buy (above it for shorts): {who}"
    if k == "max_hold":
        return f"Leave {n:g} min after the first buy: {who}"
    return f"Stop at {n:g}% against the first buy: {who}"


def check(v, values: dict) -> str | None:
    """None when code can apply the proposal; else the failing check's name."""
    if not isinstance(v, dict):
        return "proposal_not_a_map"
    if v.get("kind") not in KINDS:
        return "kind_not_on_menu"
    text = str(v.get("text") or "").strip()
    if not text or len(text.split()) > 20:
        return "text_missing_or_over_20_words"
    when = v.get("when") if v.get("when") is not None else {}
    if not isinstance(when, dict):
        return "when_not_a_map"
    for k, vals in when.items():
        if k not in ENTRY_FEATURES:
            return f"look_ahead_or_unknown_feature:{k}"
        vals = vals if isinstance(vals, list) else [vals]
        if not vals:
            return f"empty_values:{k}"
        bad = [x for x in vals if x not in values[k]]
        if bad:
            return f"unknown_value:{k}={bad[0]}"
    if v["kind"] in ("skip", "only") and not when:
        return "skip_or_only_needs_when"
    if v["kind"] in RANGES:
        lo, hi = RANGES[v["kind"]]
        if not isinstance(v.get("value"), (int, float)) or not lo <= v["value"] <= hi:
            return f"value_out_of_range:{lo}-{hi}"
    return None


def normalize(v: dict) -> dict:
    when = {k: sorted(x if isinstance(x, list) else [x]) for k, x in sorted((v.get("when") or {}).items())}
    out = {"kind": v["kind"], "when": when}
    if v["kind"] in RANGES:
        out["value"] = float(v["value"]) if v["kind"] == "stop_pct" else int(round(v["value"]))
    return out


# ---- code applies the change to his positions -----------------------------------------------------------------

def apply(mod, positions: list, base: dict, v: dict, delay: int, feats: dict) -> list:
    """Every headline position under the change: skipped, unchanged (the as-is Result), or re-priced."""
    out = []
    kind, when = v["kind"], v["when"]
    for p in positions:
        hit = strategy.matches(feats[p.pid], when)
        r0 = base[p.pid]
        if (kind == "skip" and hit) or (kind == "only" and not hit):
            continue
        if kind in ("skip", "only") or not hit or r0.status != "priced":
            out.append(r0)
            continue
        e, sign = r0.entry, 1 if p.side == "long" else -1
        q = copy.copy(p)
        if kind == "no_add_against":
            first = min((lg for lg in p.legs if lg.action in ("open", "add")), key=lambda lg: lg.posted_ts)
            keep = []
            for lg in p.legs:
                if lg.action == "add" and lg is not first:
                    got = bars.first_at_or_after(p.market, p.ticker, lg.posted_ts + delay * 60)
                    if got and sign * (got[1][0] - e.px) < 0:
                        continue
                keep.append(lg)
            if len(keep) == len(p.legs):
                out.append(r0)
                continue
            q.legs = keep
        elif kind == "max_hold":
            own = engine.default_exit_ts(p, e.ts)
            q.default_exit = f"at:{min(own, e.ts + v['value'] * 60)}"
        elif kind == "stop_pct":
            lvl = e.px * (1 - sign * v["value"] / 100)
            q.stop = lvl if p.stop is None else (max(p.stop, lvl) if sign > 0 else min(p.stop, lvl))
        out.append(engine.simulate(q, delay))
    return out


def split(results: list, sealed_from: str) -> dict:
    """One full-window run through the cash cap; dev and sealed are its slices by the first buy's day."""
    kept, *_ = engine.fit_to_cash([r for r in results if r.status == "priced"])
    out = {"dev": [], "sealed": []}
    for r, pnl in kept:
        out["dev" if bars.day_of(r.position.market, r.entry.ts).isoformat() < sealed_from else "sealed"].append(pnl)
    return {k: {"trades": len(x), "ret_pct": round(100 * sum(x) / MONEY_START, 2)} for k, x in out.items()}


def spy_split(mod) -> dict:
    """SPY total return (dividends reinvested, by_year's holding run): dev = window start to the last close before
    sealed_from; sealed = from that close to the window's last close."""
    h = extras.hold_paths(mod.MARKET, getattr(mod, "HOLD_BARS", mod.HOLD["symbol"]), mod.WINDOW)
    i = max(k for k, d in enumerate(h["dates"]) if d < mod.WINDOW["sealed_from"])
    return {"symbol": h["meta"]["symbol"], "basis": h["meta"]["basis"], "dev_to": h["dates"][i],
            "dev_ret_pct": round((h["total"][i] / MONEY_START - 1) * 100, 2),
            "sealed_ret_pct": round((h["total"][-1] / h["total"][i] - 1) * 100, 2)}


def decide(row: dict) -> dict:
    d, s = row["dev"], row["sealed"]
    if d["trades"] < MIN_TRADES or s["trades"] < MIN_TRADES:
        row["kept"], row["kept_reason"] = False, f"fewer than {MIN_TRADES} trades left (dev {d['trades']}, sealed {s['trades']})"
    elif d["vs_as_is_pts"] <= 0:
        row["kept"], row["kept_reason"] = False, "no gain on the months it was picked on (dev)"
    elif s["vs_as_is_pts"] < 0:
        row["kept"], row["kept_reason"] = False, "gained on dev, lost on the held-out (sealed) months"
    else:
        row["kept"], row["kept_reason"] = True, "gained on dev and did not lose on the held-out (sealed) months"
    return row


def evaluate(mod, positions: list, base: dict, proposals: list, delay: int, version: str = "v1") -> dict:
    """Every number of the key, from the positions and the model's proposals (checked here)."""
    sealed_from = mod.WINDOW["sealed_from"]
    names = {s["id"]: s["name"] for s in mod.STRATEGIES}
    feats = all_features(mod, version, positions, base, delay)
    values = {k: {f[k] for f in feats.values()} for k in ENTRY_FEATURES}
    as_is = split(list(base.values()), sealed_from)
    spy = spy_split(mod)
    variants, rejected = [], []
    for i, raw in enumerate(proposals if isinstance(proposals, list) else []):
        bad = f"over_{MAX_VARIANTS}_proposals" if i >= MAX_VARIANTS else check(raw, values)
        if bad:
            rejected.append({"text": str((raw or {}).get("text") if isinstance(raw, dict) else raw)[:120],
                             "why": bad})
            continue
        v = normalize(raw)
        got = split(apply(mod, positions, base, v, delay, feats), sealed_from)
        row = {"id": f"V{len(variants) + 1}", "text": raw["text"].strip(), "rule": describe(v, names), **v,
               "why": str(raw.get("why") or "").strip() or None}
        for part in ("dev", "sealed"):
            g, a = got[part], as_is[part]
            row[part] = {"trades": g["trades"], "ret_pct": g["ret_pct"], "as_is_ret_pct": a["ret_pct"],
                         "vs_as_is_pts": round(g["ret_pct"] - a["ret_pct"], 2),
                         "spy_ret_pct": spy[f"{part}_ret_pct"],
                         "vs_spy_pts": round(g["ret_pct"] - spy[f"{part}_ret_pct"], 2)}
        variants.append(decide(row))
    return {"as_is": as_is, "spy": spy, "variants": variants, "rejected": rejected}


# ---- the model's input: the strategy_profile tables, dev months only ------------------------------------------

def dev_tables(mod, kept: list, sealed_from: str) -> dict:
    rows = [x for x in strategy.features(mod, kept) if x["day"] < sealed_from]
    names = {s["id"]: s["name"] for s in mod.STRATEGIES}
    return {"summary": {k: v for k, v in strategy.summary(rows).items() if k in ("trades", "sessions", "pnl_usd",
                                                                               "won_pct", "adds")},
            "tables": [{"by": t["by"], "rows": t["rows"]} for t in strategy.tables_for(rows)],
            "losing_patterns": [{k: lp[k] for k in ("label", "when", "trades", "won_pct", "pnl_usd",
                                                    "avg_win_usd", "avg_loss_usd")}
                                for lp in strategy.losing_patterns(rows, n=5, setups_by_id=names)],
            "setups": strategy.setups(rows)}


def prompt(tabs: dict, rule_texts: list[str], defs: dict) -> str:
    return (
        "You improve a day trader's copy-trading results. He hosts a paid trading course; a copier followed every "
        "trade he posted on his live streams, $1,000 per first buy, after costs. Below are tables of the copied "
        "trades from the DEVELOPMENT months only, his strategy as rules, and his losing patterns. Each row: trades, "
        "won_pct, pnl_usd (copied P&L). Note: when he never said he closed, the copy leaves at 15:55 ET "
        "(`exit: assumed`), so long holds partly reflect the copy, not him."
        "\n\nPropose at most 6 rule changes that would have cut his losses, each written as a filter or exit "
        "on HIS trades that code applies. Kinds (pick one per change): "
        f"{json.dumps(KINDS)}. `when` maps features to allowed values and may use ONLY these entry-time features "
        f"(known when the first buy fills, never adds, exits or hold): {json.dumps({k: strategy.FEATURE_HELP[k] for k in ENTRY_FEATURES})}; "
        "use values that appear in the tables; {} = every trade (not allowed for skip or only). Prefer changes the "
        "numbers support across many trades, aimed at the losing patterns; keep 30+ trades left in the account. "
        "Make the 6 different from each other (different kinds or different trades)."
        "\n\nReply with JSON only: {\"changes\": [{\"text\": <the rule in plain words, 20 words or fewer>, "
        "\"kind\": <kind>, \"when\": {...}, \"value\": <number for max_hold or stop_pct, else null>, "
        "\"why\": <15 words or fewer>}]}"
        f"\n\nHis rules: {json.dumps(rule_texts)}\nDev summary: {json.dumps(tabs['summary'])}"
        f"\nDev losing patterns: {json.dumps(tabs['losing_patterns'])}\nDev tables: {json.dumps(tabs['tables'])}"
        f"\nDev setups (side, group, 30-min window, reason): {json.dumps(tabs['setups'])}"
        f"\nDefinitions: {json.dumps(defs)}")


def spent() -> float:
    return sum(strategy.cost(json.loads(p.read_text()).get("usage") or {}) for p in OUT.glob("reply-*.json"))


def stored(course: str = "lpp", version: str = "v1") -> dict | None:
    p = OUT / f"{course}-{version}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        print(f"  improvements skipped: {p.name} is not JSON ({e.msg})")
        return None
    return d if isinstance(d, dict) else None


def key(mod, version: str, positions: list, base: dict, cached: dict | None, delay: int = DEFAULT_DELAY_MIN) -> dict | None:
    """The `improvements` key (contracts.md): proposals from the cached reply, every number from code."""
    if not cached or not isinstance(cached.get("reply"), dict) or not isinstance(cached["reply"].get("changes"), list):
        return None
    ev = evaluate(mod, positions, base, cached["reply"]["changes"], delay, version)
    tid = cached.get("trajectory_id")
    return {"agent_id": AGENT_ID, "prompt_version": PROMPT_VERSION, "model": cached.get("model"),
            "trajectory_id": tid, "prism_url": strategy.PRISM_RUN.format(tid) if tid else None,
            "version": version, "portfolio": "all", "delay_min": delay,
            "window": {"dev_from": mod.WINDOW["start"], "sealed_from": mod.WINDOW["sealed_from"],
                       "sealed_to": mod.WINDOW["end"]},
            "basis": "The headline's positions (rule 13, all), each re-priced under the change, one full-window run "
                     "through the cash cap; dev and sealed are its slices by the first buy's day",
            "picked_on": "dev", "keep_rule": KEEP_RULE, "min_trades": MIN_TRADES,
            "kept_label": KEPT_LABEL, "variants_tried": tried(ev), "disclosure": DISCLOSURE,
            "luck_test": {"story": "27", "status": "not run"},
            "kept_all_trail_spy": all(v["dev"]["vs_spy_pts"] < 0 and v["sealed"]["vs_spy_pts"] < 0
                                      for v in ev["variants"] if v["kept"]),
            **ev}


def tried(ev: dict) -> dict:
    """Every variant tried: the model's priced proposals plus the engineer's smoke tests that priced and aren't
    the same change as one of the model's."""
    model = {f"{v['kind']} {' '.join(x for vals in v['when'].values() for x in vals)}" for v in ev["variants"]}
    extra = [t for t in SMOKE_TESTS if t["priced"] and t.get("same_as") not in model]
    return {"distinct_priced": len(ev["variants"]) + len(extra), "model_priced": len(ev["variants"]),
            "model_rejected": len(ev["rejected"]), "smoke_tests_run": len(SMOKE_TESTS),
            "smoke_tests_priced": sum(t["priced"] for t in SMOKE_TESTS), "smoke_tests": SMOKE_TESTS,
            "log": "notes/research/backtesting.md, section 6"}


# ---- run --------------------------------------------------------------------------------------------------------

def headline(mod, version: str, delay: int) -> tuple[list, dict]:
    """The headline's positions (unique ids, rule 13e sizing) and their as-is Results at one delay."""
    from .run import prefetch
    built = mod.build(version)
    seen: dict[str, int] = {}
    for p in built["positions"]:
        seen[p.pid] = seen.get(p.pid, 0) + 1
        if seen[p.pid] > 1:
            p.pid = f"{p.pid}-{seen[p.pid]}"
        p.scale = True
    prefetch(built["positions"])
    return built["positions"], {p.pid: engine.simulate(p, delay) for p in built["positions"]}


def trace(tabs: dict, res: dict, k: dict, version: str, delay: int) -> str | None:
    from prismtrace import PRISMtrace
    failed = None if res.get("reply") else "reply_not_json"
    if not failed and not k["variants"]:
        failed = "no_change_code_can_apply"
    steps = [
        {"step_type": "tool_call", "tool_name": "load_results", "label": "load_results",
         "input_summary": json.dumps({"results": f"results/lpp/{version}.json", "portfolio": "all", "delay_min": delay,
                                      "ledger": "rule 13", "months": "dev only", "before": k["window"]["sealed_from"]}),
         "output_summary": json.dumps(tabs["summary"])},
        {"step_type": "tool_call", "tool_name": "compute_dev_tables", "label": "compute_dev_tables",
         "input_summary": json.dumps({"tables": [t["by"] for t in tabs["tables"]]}),
         "output_summary": json.dumps({"losing_patterns": [lp["label"] for lp in tabs["losing_patterns"]]})},
        {"step_type": "reasoning", "label": "llm_propose_changes",
         "input_summary": json.dumps({"model": res.get("model"), "prompt_version": PROMPT_VERSION,
                                      "prompt_sha": res.get("prompt_sha"), "kinds": list(KINDS)}),
         "output_summary": json.dumps(res.get("reply"))[:4000], "duration_ms": int((res.get("secs") or 0) * 1000),
         "token_count": res["usage"].get("in", 0) + res["usage"].get("out", 0),
         "status": "error" if failed == "reply_not_json" else "success"},
        {"step_type": "tool_call", "tool_name": "check_changes", "label": "check_changes",
         "input_summary": json.dumps({"entry_features": list(ENTRY_FEATURES), "ranges": RANGES}),
         "output_summary": json.dumps({"applied": [v["rule"] for v in k["variants"]], "rejected": k["rejected"]}),
         "status": "error" if failed else "success"},
        {"step_type": "tool_call", "tool_name": "backtest_dev", "label": "backtest_dev",
         "input_summary": json.dumps({"as_is": k["as_is"]["dev"], "spy": k["spy"]["dev_ret_pct"]}),
         "output_summary": json.dumps([{"id": v["id"], **v["dev"]} for v in k["variants"]])},
        {"step_type": "tool_call", "tool_name": "backtest_sealed", "label": "backtest_sealed",
         "input_summary": json.dumps({"from": k["window"]["sealed_from"], "decided_before_reading": True,
                                      "as_is": k["as_is"]["sealed"]}),
         "output_summary": json.dumps([{"id": v["id"], **v["sealed"]} for v in k["variants"]])},
        {"step_type": "final_answer", "label": "improvements",
         "output_summary": json.dumps({"check": failed} if failed else
                                      [{"id": v["id"], "rule": v["rule"], "kept": v["kept"],
                                        "reason": v["kept_reason"]} for v in k["variants"]])},
    ]
    pt = PRISMtrace(api_key=os.environ["PRISMTRACE_API_KEY"], project_id=os.environ["PRISMTRACE_PROJECT_ID"],
                    host=os.getenv("PRISMTRACE_HOST", "https://api.prism.blockconvey.com"))
    meta = {"agent_version": "v2", "course": "lpp", "prompt_version": PROMPT_VERSION, "git_sha": git_sha(),
            "proof_set": False}
    body = {"project_id": pt.project_id, "conversation_id": f"improve-lpp-{version}", "request_id": str(uuid.uuid4()),
            "agent_id": AGENT_ID, "agent_name": "Day Trader AI improver v2", "steps": steps,
            "total_duration_ms": sum(s.get("duration_ms") or 0 for s in steps),
            "final_status": "error" if failed else "success", "model": res.get("model"), "metadata": meta}
    sent = pt._post_sync("/api/trajectories", body) or pt.submit_trajectory(
        steps, agent_id=AGENT_ID, agent_name=body["agent_name"], conversation_id=body["conversation_id"],
        model=body["model"], final_status=body["final_status"])
    return (sent or {}).get("id") if isinstance(sent, dict) else None


def main(version: str = "v1", estimate: bool = False, no_trace: bool = False) -> None:
    from . import lpp as mod
    d = DEFAULT_DELAY_MIN
    positions, base = headline(mod, version, d)
    kept, *_ = engine.fit_to_cash([r for r in base.values() if r.status == "priced"])
    tabs = dev_tables(mod, kept, mod.WINDOW["sealed_from"])
    prof = (json.loads((RESULTS / "lpp" / f"{version}.json").read_text()).get("strategy_profile") or {})
    rule_texts = [r["proposed_text"] for r in prof.get("rules") or []]
    defs = {k: v for k, v in strategy.definitions(mod).items() if k in ("ticker_groups", "setups")}
    text = prompt(tabs, rule_texts, defs)
    est = len(text) / 3.5 * strategy.PRICE["in"] + 4000 * strategy.PRICE["out"]
    print(f"dev trades {tabs['summary']['trades']}, P&L {tabs['summary']['pnl_usd']}, prompt ~{len(text) / 3.5:,.0f} "
          f"tokens, est ${est:.2f}, spent so far ${spent():.2f} of ${BUDGET_USD}")
    for lp in tabs["losing_patterns"]:
        print("  dev losing pattern:", lp["label"], lp["trades"], lp["pnl_usd"])
    if estimate:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    cp = OUT / strategy.cache_path(text).name
    if cp.exists():
        res = json.loads(cp.read_text())
        print("cached reply", cp.name)
    else:
        if spent() + est > BUDGET_USD:
            raise SystemExit(f"budget: ${spent():.2f} spent, this call ~${est:.2f}, cap ${BUDGET_USD}")
        res = strategy.call(text)
        res["prompt_version"] = PROMPT_VERSION
        res["prompt_sha"] = cp.stem.split("-", 1)[1]
        cp.write_text(json.dumps(res, indent=1))
        print(f"model reply in {res.get('secs')} s, ${strategy.cost(res['usage']):.3f}; errors {res['errors']}")
    store = {"agent_id": AGENT_ID, "model": res.get("model"), "prompt_version": PROMPT_VERSION,
             "prompt_sha": res.get("prompt_sha"), "reply": res.get("reply"), "usage": res["usage"],
             "trajectory_id": (stored("lpp", version) or {}).get("trajectory_id"),
             "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    k = key(mod, version, positions, base, store, d)
    if k is None:
        raise SystemExit(f"no usable reply: {res.get('errors')}")
    print(f"as-is: dev {k['as_is']['dev']}, sealed {k['as_is']['sealed']}; SPY {k['spy']}")
    for v in k["variants"]:
        print(f"  {v['id']} {'KEPT' if v['kept'] else 'not kept'} | {v['rule']} | dev {v['dev']['trades']} trades "
              f"{v['dev']['ret_pct']}% ({v['dev']['vs_as_is_pts']:+} pts) | sealed {v['sealed']['trades']} trades "
              f"{v['sealed']['ret_pct']}% ({v['sealed']['vs_as_is_pts']:+} pts) | {v['kept_reason']}")
    for x in k["rejected"]:
        print(f"  REJECTED {x['text']} | {x['why']}")
    if not no_trace:
        tid = trace(tabs, res, k, version, d)
        print("traced to PRISM:", tid)
        if tid:
            store["trajectory_id"] = tid
            k = key(mod, version, positions, base, store, d)
    (OUT / f"lpp-{version}.json").write_text(json.dumps(store, indent=1))
    rp = RESULTS / "lpp" / f"{version}.json"
    out = json.loads(rp.read_text())
    if out.get("same_sessions"):
        raise SystemExit("a proof-set file carries no improvements (rule 9)")
    out["improvements"] = k
    rp.write_text(public_json(out))
    print(f"wrote improvements to {rp}; spent ${spent():.2f} of ${BUDGET_USD}. "
          "Next: backtest.run --ledger-only, then audit.run")
