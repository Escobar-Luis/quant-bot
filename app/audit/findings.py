"""Story 2 findings: every difference between the engine and the audit, classified, with its money effect.

  cd app && uv run python -m audit.findings     # writes notes/audit/findings-story-2.md and proofs/audit.json:findings

Classes: (a) the engine deviates from contracts.md (a bug), (b) the contract is silent (Luis decides; a rule is
proposed), (c) the audit's own error (fixed in app/audit, listed for the record).

The $ effect of an (a) or (b) item is the change in the 5-minute "all" end value when that one fix is applied
alone to the engine's own positions (backtest.<course>.build), priced by audit.calc. On identical positions
audit.calc and the engine agree on every trade, fill and headline (audit.run's "math alone": 0 mismatches), so
this is the engine's number with that fix, without changing the engine.
"""
import copy
import json
from collections import Counter

from . import calc
from . import positions as P
from .paths import PROOFS, REPO, RESULTS
from .run import HOLD_BARS, MARKET, audit_row

DELAY = 5
NOTE = REPO / "notes" / "audit" / "findings-story-2.md"


def end_value(results: dict, positions: list) -> tuple[float, dict]:
    hold = calc.hold(MARKET[results["course"]], HOLD_BARS[results["hold"]["symbol"]], results["window"])
    trades = {p.pid: calc.simulate(p, DELAY) for p in positions}
    return calc.portfolio(list(trades.values()), hold)["end"], trades


def effect(results: dict, base: list, fixed: list, base_end: float, base_trades: dict) -> dict:
    end, trades = end_value(results, fixed)
    changed = sum(audit_row(trades[k]) != audit_row(base_trades[k]) for k in trades if k in base_trades)
    return {"trades_affected_5m": changed, "end_5m": end, "delta_usd": round(end - base_end, 2)}


def with_posted_times(theirs: list, ours: list) -> list:
    """The engine's positions, each leg at rule 1's post time (the audit's, to the fraction of a second)."""
    exact = {lg.event_id: lg.posted_ts for p in ours for lg in p.legs}
    out = copy.deepcopy(theirs)
    for p in out:
        for lg in p.legs:
            lg.posted_ts = exact.get(lg.event_id, lg.posted_ts)
    return out


def course_items(course: str, version: str, only=None) -> tuple[dict, list, list]:
    res = json.loads((RESULTS / course / f"{version}.json").read_text())
    theirs, ours = P.loader_positions(course, version, only), P.build(course, version, only)
    base_end, base_trades = end_value(res, theirs)
    published = next(p for p in res["portfolios"] if p["id"] == "all")["by_delay"][str(DELAY)]["end"]
    own_end, _ = end_value(res, ours)
    head = {"file": f"{course}/{version}", "published_end_5m": published, "engine_positions_end_5m": base_end,
            "audit_positions_end_5m": own_end}
    a, b = [], []
    exact = {lg.event_id: lg.posted_ts for p in ours for lg in p.legs}
    moved = sum(lg.event_id in exact and not P._same_ts(lg.posted_ts, exact[lg.event_id])
                for p in theirs for lg in p.legs)
    if moved:
        a.append({"id": "posted-time-truncated", "file": head["file"], "legs": moved,
                  "rule": "contracts.md rule 1/3: post time + delay, then the first bar at or after it",
                  "what": "the loader truncates the post time to the whole second (LPP wall_utc is release + t_s "
                          "truncated; Discord's milliseconds dropped); when the true time is just past a minute, "
                          "the fill lands one bar early",
                  **effect(res, theirs, with_posted_times(theirs, ours), base_end, base_trades)})
    if course == "cryptowizard":
        fixed = copy.deepcopy(theirs)
        n = 0
        for p in fixed:
            if p.default_exit != "hours:24":
                p.default_exit, n = "hours:24", n + 1
        a.append({"id": "cw-24h-default-exit", "file": head["file"], "positions": n,
                  "rule": "contracts.md rule 4: crypto setups leave after 24 hours when never closed",
                  "what": "the loader extends the default exit to the setup's last linked follow-up "
                          "(up to hours:100)", **effect(res, theirs, fixed, base_end, base_trades)})
        fixed = copy.deepcopy(theirs)
        tp = {p.legs[0].event_id: [lg for lg in p.legs if lg.action == "trim"] for p in ours}
        n = 0
        for p in fixed:
            extra = tp.get(p.legs[0].event_id, [])
            n += len(extra)
            p.legs = sorted(p.legs + copy.deepcopy(extra), key=lambda lg: lg.posted_ts)
        a.append({"id": "cw-take-profit-trims-dropped", "file": head["file"], "posts": n,
                  "rule": "contracts.md rule 4: the course's own close or trim (+ delay) applies first",
                  "what": "the loader drops their take-profit posts; with them, a TP post sells that TP's share at "
                          "post + delay unless the copier's own TP order already filled (proposal b2)",
                  **effect(res, theirs, fixed, base_end, base_trades)})
    if course == "ziptrader":
        b.append({"id": "zt-horizon-from-quote", "file": head["file"], "positions": 1,
                  "question": "Is a horizon said only in the quote ('more than one session') a swing horizon "
                              "when the extracted `horizon` field is empty?",
                  "engine": "swing (reads the quote text)", "audit": "day (reads the structured field)",
                  "proposal": "Yes: rule 4's 'horizon as written' includes the quote; move it into the "
                              "extraction's horizon field so code reads one place.",
                  "if_audit_reading": effect(res, theirs, ours, base_end, base_trades)})
    return head, a, b


def zero_effect_items() -> list[dict]:
    """Engine deviations the synthetic tests found that no real position triggers today."""
    lpp1 = P.loader_positions("lpp", "v1")
    cw = P.loader_positions("cryptowizard", "v1")
    zt = P.loader_positions("ziptrader", "v1")
    allp = lpp1 + cw + zt
    no_frac = sum(len(p.targets) > 1 and not p.target_fracs for p in allp)
    at = sum(p.default_exit.startswith("at:") for p in allp)
    return [
        {"id": "targets-split-equally", "positions": no_frac, "delta_usd": 0.0,
         "rule": "contracts.md rule 4: stop or target, whichever trades first, is the exit",
         "what": "with several targets and no stated shares the engine sells 1/n at each; the contract exits "
                 "at the first target that trades (synthetic: 13.99 vs 8.995)"},
        {"id": "at-exit-before-entry", "positions": at, "delta_usd": 0.0,
         "rule": "contracts.md rule 4/6: a horizon that passed before the entry leaves nothing to copy",
         "what": "the engine opens and closes in the entry bar (costs only, synthetic: -1.00)"},
        {"id": "hundred-dollar-minimum", "positions": 0, "delta_usd": 0.0,
         "rule": "contracts.md rule 6: sized down to the cash left, or couldn't-copy",
         "what": "the engine skips any trade with under $100 of cash; contracts.md names no minimum "
                 "(bankroll-rules.md's $100 is CAP-9's). sized_down and couldnt_copy match at every delay today"},
    ]


SILENT = [
    {"id": "b1-ledger-look-ahead", "question": "Rule 11 decides a position's overnight carry from his later "
     "words (look-ahead).", "proposal": "Keep for the as-taught numbers; CAP-12 replaces it with a carry decided "
     "only from what was said before 15:55."},
    {"id": "b2-tp-post-after-own-order", "question": "When a take-profit post arrives after the copier's own TP "
     "order filled, does it sell again?", "proposal": "No: skip it; it sells only when the TP order has not "
     "filled (what audit.calc does)."},
    {"id": "b3-gap-trigger", "question": "A trigger level crossed by a gap between bars: fill at the level or at "
     "the gap bar's open?", "proposal": "At the gap bar's open (a stop order's fill). Engine and audit agree."},
    {"id": "b4-moved-stop-same-bar", "question": "A break-even stop moved by targets in a bar that also trades "
     "the new stop: fill?", "proposal": "Yes, at the stop level (not the bar's open). Engine and audit agree."},
    {"id": "b5-sizing-reference-price", "question": "Rule 6 scales all buys to $1,000 at which price?",
     "proposal": "The first fill's price (only price known then); CAP-9's bankroll model supersedes it."},
    {"id": "b6-unsized-trim", "question": "A trim with no size?", "proposal": "Half the position (engine, audit "
     "and bankroll-rules.md agree); write it into rule 6."},
    {"id": "b7-hold-close", "question": "Just holding ends at which price?", "proposal": "The official daily "
     "close; report the last 1-minute close as an alternative."},
]

AUDIT_FIXED = [
    {"id": "c1-ok-only", "what": "round 1 copied only status-ok LPP events; rule 11 (now in contracts.md) keeps "
     "the ledger-check failures. Fixed: audit.positions follows rule 11."},
    {"id": "c2-open-joins", "what": "round 1 joined a later-session `open` to the held position and carried for 5 "
     "sessions; rule 11 says 7 days and only add/trim/close carry. Fixed."},
    {"id": "c3-subsecond-noise", "what": "round 1 flagged post-time differences under a second that reach the "
     "same bar (LPP t_s is stored to 0.1 s). Fixed: only a different first bar is a difference."},
    {"id": "c4-cw-second-close", "what": "round 1 kept a setup's second close post (a no-op). Fixed: the first "
     "close ends the position."},
]


def money(x: float) -> str:
    return f"{'+' if x > 0 else '−' if x < 0 else '±'}${abs(x):,.2f}"


def write_note(heads, a, b) -> str:
    L = ["# Story 2 findings: engine vs contracts.md", "",
         "Generated by `cd app && uv run python -m audit.findings` (PR #55). $ effect = the change in the 5-minute "
         "\"all\" end value when that one fix is applied alone to the engine's positions, priced by audit.calc "
         "(identical to the engine on identical positions).", "",
         "## 5-minute \"all\" end value", "",
         "| file | published | audit's own positions |", "|---|---|---|"]
    L += [f"| {h['file']} | ${h['published_end_5m']:,.2f} | ${h['audit_positions_end_5m']:,.2f} |" for h in heads]
    L += ["", "## (a) The engine deviates from contracts.md", "",
          "| finding | file | affected | 5-min trades changed | $ effect on end | rule | what |",
          "|---|---|---|---|---|---|---|"]
    for x in a:
        n = x.get("legs") or x.get("positions") or x.get("posts") or 0
        unit = "legs" if "legs" in x else "posts" if "posts" in x else "positions"
        L.append(f"| {x['id']} | {x.get('file', 'all')} | {n} {unit} | {x.get('trades_affected_5m', 0)} | "
                 f"{money(x['delta_usd'])} | {x['rule']} | {x['what']} |")
    L += ["", "## (b) The contract is silent: Luis decides", "", "| id | question | proposal |", "|---|---|---|"]
    for x in b:
        extra = ""
        if "if_audit_reading" in x:
            extra = f" (audit reading: {money(x['if_audit_reading']['delta_usd'])} on the 5-min end)"
        L.append(f"| {x['id']} | {x['question']} | {x['proposal']}{extra} |")
    L += ["", "## (c) The audit's own errors (fixed)", ""] + [f"- **{x['id']}**: {x['what']}" for x in AUDIT_FIXED]
    L += ["", "Nothing in results/ or the engine's math was changed; each (a) item is a separate fix for a "
          "spec-approved story.", ""]
    return "\n".join(L)


def main() -> int:
    heads, a, b = [], [], []
    for course, version, only in (("lpp", "v1", None), ("lpp", "v2", P.lpp_proof_set()),
                                  ("cryptowizard", "v1", None), ("ziptrader", "v1", None)):
        h, ai, bi = course_items(course, version, only)
        heads.append(h)
        a += ai
        b += bi
    a += zero_effect_items()
    b = b + SILENT
    NOTE.parent.mkdir(parents=True, exist_ok=True)
    NOTE.write_text(write_note(heads, a, b))
    path = PROOFS / "audit.json"
    rec = json.loads(path.read_text()) if path.exists() else {}
    rec["findings"] = {"note": "notes/audit/findings-story-2.md", "end_5m_all": heads,
                       "engine_deviates": [{k: v for k, v in x.items() if k not in ("rule", "what")} for x in a],
                       "contract_silent": [{"id": x["id"], "proposal": x["proposal"]} for x in b],
                       "audit_fixed": [x["id"] for x in AUDIT_FIXED],
                       "counts": dict(Counter({"a": len(a), "b": len(b), "c": len(AUDIT_FIXED)}))}
    path.write_text(json.dumps(rec, indent=1) + "\n")
    for h in heads:
        print(h)
    for x in a:
        print("(a)", x["id"], x.get("file", ""), x.get("trades_affected_5m", 0), x["delta_usd"])
    print("wrote", NOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
