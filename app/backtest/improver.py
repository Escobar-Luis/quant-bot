"""daytrader-improver-v1: the model proposes ONE change to one strategy; code tests it and decides (CAP-9).

  cd app && uv run python -m backtest.improver --course lpp --version v1 [--dry-run]

Honest-backtest rules: the model sees only dev-month numbers (entries before window.sealed_from), never the sealed
months; code keeps the change only if it beats the parent on dev, then reports both on the sealed months. The change
is one of a small menu code can apply at entry time (skip early entries, skip late entries, skip one side).
The run is traced to PRISM as `daytrader-improver-v1`; the result lands in data/improver/ and in the results file
as `suggestion` (run.py re-attaches it on every rebuild).
"""
import argparse
import datetime as dt
import json
import os
import time
import uuid

from . import bars, engine, extras
from .common import DATA, DEFAULT_DELAY_MIN, RESULTS, git_sha, public_json
from .run import course_module, hold_numbers, prefetch

AGENT_ID, PROMPT_VERSION = "daytrader-improver-v1", "improver-v1"
PRISM_RUN = "https://prism.blockconvey.com/trajectories/{}"   # same pattern as story 2's run_url
MENU = {"skip_before": "HH:MM (ET): don't copy entries before this time",
        "skip_after": "HH:MM (ET): don't copy entries at or after this time",
        "skip_side": "long or short: don't copy that side"}
BUCKETS = ["09:30", "10:00", "10:30", "11:00", "12:00", "16:00"]


def decide(s: dict) -> dict:
    """Kept only if it beats the parent on dev (where it was picked) AND a sealed test agrees."""
    if s["dev"]["after_pct"] <= s["dev"]["before_pct"]:
        s["kept"], s["kept_reason"] = False, "no gain on the months it was picked on (dev)"
    elif s["sealed"]["after_pct"] <= s["sealed"]["before_pct"]:
        s["kept"], s["kept_reason"] = False, "no gain on new (sealed) months"
    else:
        s["kept"], s["kept_reason"] = True, "gained on dev and on new (sealed) months"
    return s


def suggestion_path(course: str, version: str):
    return DATA / "improver" / f"{course}-{version}.json"


def _et(r) -> str:
    return dt.datetime.fromtimestamp(r.entry.ts, bars.ET).strftime("%H:%M")


def applies(change: dict, r) -> bool:
    """True when the change keeps this trade."""
    kind, v = change["change_type"], change["value"]
    if kind == "skip_before":
        return _et(r) >= v
    if kind == "skip_after":
        return _et(r) < v
    if kind == "skip_side":
        return r.position.side != v
    raise ValueError(kind)


def dev_stats(groups: dict, sealed: str) -> dict:
    """Dev months only: per strategy, the account return, win rate and P&L by entry time and side."""
    out = {}
    for sid, rs in groups.items():
        dev = [r for r in rs if r.status == "priced" and bars.day_of(r.position.market, r.entry.ts).isoformat() < sealed]
        if not dev:
            continue
        ret, n = extras._account(dev)
        by_time = {}
        for a, b in zip(BUCKETS, BUCKETS[1:]):
            sub = [r for r in dev if a <= _et(r) < b]
            if sub:
                by_time[f"{a}-{b}"] = {"trades": len(sub), "pnl_usd": round(sum(r.pnl for r in sub), 2)}
        by_side = {s: {"trades": len(sub), "pnl_usd": round(sum(r.pnl for r in sub), 2)}
                   for s in ("long", "short") if (sub := [r for r in dev if r.position.side == s])}
        out[sid] = {"trades": n, "ret_pct": ret, "won_pct": round(100 * sum(r.pnl > 0 for r in dev) / len(dev)),
                    "pnl_by_entry_time_et": by_time, "pnl_by_side": by_side}
    return out


def propose(stats: dict, names: dict) -> tuple[dict, dict]:
    from openai import OpenAI
    client = OpenAI(base_url=os.getenv("NICRRON_BASE_URL", "https://api.nicrron.ai/v1"),
                    api_key=os.environ["NICRRON_API_KEY"], timeout=120, max_retries=1)
    model = "anthropic/claude-sonnet-5-5"
    prompt = (
        "You improve a copy-trading strategy. Below are numbers from the development months only, per strategy "
        "(a $10k account, $1,000 per trade, after costs). Propose exactly ONE change to ONE strategy, chosen from "
        f"this menu: {json.dumps(MENU)}. Prefer a change the numbers support across many trades, not one lucky "
        "bucket. Reply with JSON only: {\"applies_to\": <strategy id>, \"change_type\": <menu key>, "
        "\"value\": <HH:MM or long/short>, \"why\": <15 words or fewer>}.\n\n"
        f"Strategies: {json.dumps(names)}\nDev numbers: {json.dumps(stats)}")
    t0 = time.time()
    r = client.chat.completions.create(model=model, max_tokens=300, messages=[{"role": "user", "content": prompt}])
    text = r.choices[0].message.content.strip()
    meta = {"model": model, "secs": round(time.time() - t0, 1),
            "tokens": (r.usage.prompt_tokens + r.usage.completion_tokens) if r.usage else None}
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1]), meta


def check(change: dict, names: dict) -> str | None:
    """Code checks on the model's proposal; the name of the failing check, or None."""
    if change.get("applies_to") not in names:
        return "applies_to_unknown_strategy"
    if change.get("change_type") not in MENU:
        return "change_not_on_menu"
    v = str(change.get("value"))
    if change["change_type"] == "skip_side" and v not in ("long", "short"):
        return "side_not_long_or_short"
    if change["change_type"] != "skip_side" and not (len(v) == 5 and v[2] == ":" and "09:30" <= v <= "16:00"):
        return "time_not_in_session"
    if len((change.get("why") or "").split()) > 15:
        return "why_too_long"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", default="lpp")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    mod = course_module(a.course)
    built = mod.build(a.version)
    positions = built["positions"]
    for p in positions:
        p.scale = True
    prefetch(positions)
    d = DEFAULT_DELAY_MIN
    sealed = mod.WINDOW["sealed_from"]
    groups: dict[str, list] = {}
    for p in positions:
        groups.setdefault(mod.strategy_of(p), []).append(engine.simulate(p, d))
    names = {s["id"]: s["name"] for s in mod.STRATEGIES if s["id"] in groups}
    stats = dev_stats(groups, sealed)

    change, meta = propose(stats, names)
    failed = check(change, names)
    steps = [
        {"step_type": "tool_call", "tool_name": "load_results", "label": "load_results",
         "input_summary": json.dumps({"course": a.course, "version": a.version, "delay_min": d, "months": "dev only",
                                      "before": sealed}),
         "output_summary": json.dumps({k: {"trades": v["trades"], "ret_pct": v["ret_pct"]} for k, v in stats.items()})},
        {"step_type": "reasoning", "label": "llm_propose",
         "input_summary": json.dumps({"model": meta["model"], "prompt_version": PROMPT_VERSION, "menu": list(MENU)}),
         "output_summary": json.dumps(change), "duration_ms": int(meta["secs"] * 1000),
         "token_count": meta["tokens"], "status": "error" if failed else "success"},
    ]
    if failed:
        steps.append({"step_type": "final_answer", "label": "rejected",
                      "output_summary": json.dumps({"check": failed, "proposal": change})})
        result = None
    else:
        rs = groups[change["applies_to"]]
        on_dev = lambda r: bars.day_of(r.position.market, r.entry.ts).isoformat() < sealed  # noqa: E731
        priced = [r for r in rs if r.status == "priced"]
        dev, late = [r for r in priced if on_dev(r)], [r for r in priced if not on_dev(r)]
        before_dev, _ = extras._account(dev)
        after_dev, n_dev = extras._account([r for r in dev if applies(change, r)])
        picked = after_dev > before_dev
        steps.append({"step_type": "tool_call", "tool_name": "backtest_dev", "label": "backtest_dev",
                      "input_summary": json.dumps({"applies_to": change["applies_to"], "change": change["change_type"],
                                                   "value": change["value"], "trades": len(dev)}),
                      "output_summary": json.dumps({"before_pct": before_dev, "after_pct": after_dev,
                                                    "trades_after": n_dev, "passes_dev": picked})})
        before_s, _ = extras._account(late)
        after_s, n_s = extras._account([r for r in late if applies(change, r)])
        steps.append({"step_type": "tool_call", "tool_name": "backtest_sealed", "label": "backtest_sealed",
                      "input_summary": json.dumps({"from": sealed, "decided_before_reading": True}),
                      "output_summary": json.dumps({"before_pct": before_s, "after_pct": after_s, "trades_after": n_s})})
        label = {"skip_before": f"Skip entries before {change['value']} ET",
                 "skip_after": f"Skip entries from {change['value']} ET",
                 "skip_side": f"Skip the {change['value']}s"}[change["change_type"]]
        result = {"agent_id": AGENT_ID, "applies_to": change["applies_to"], "change": label,
                  "why": change.get("why"), "delay_min": d,
                  "dev": {"before_pct": before_dev, "after_pct": after_dev},
                  "sealed": {"before_pct": before_s, "after_pct": after_s, "trades": n_s},
                  "kept": None, "prism_url": None, "trajectory_id": None,
                  "picked_on": "dev", "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
        decide(result)
        steps.append({"step_type": "final_answer", "label": "suggestion", "output_summary": json.dumps(result)})

    payload = {"agent_id": AGENT_ID, "agent_name": "Day Trader AI improver v1",
               "conversation_id": f"improver-{a.course}-{a.version}", "model": meta["model"],
               "final_status": "error" if failed else "success",
               "metadata": {"agent_version": "v1", "course": a.course, "prompt_version": PROMPT_VERSION,
                            "git_sha": git_sha(), "proof_set": False},
               "steps": steps}
    if a.dry_run:
        print(json.dumps(payload, indent=1)[:4000])
        return
    from prismtrace import PRISMtrace
    pt = PRISMtrace(api_key=os.environ["PRISMTRACE_API_KEY"], project_id=os.environ["PRISMTRACE_PROJECT_ID"],
                    host=os.getenv("PRISMTRACE_HOST", "https://api.prism.blockconvey.com"))
    body = {"project_id": pt.project_id, "conversation_id": payload["conversation_id"], "request_id": str(uuid.uuid4()),
            "agent_id": AGENT_ID, "agent_name": payload["agent_name"], "steps": steps,
            "total_duration_ms": sum(s.get("duration_ms") or 0 for s in steps), "final_status": payload["final_status"],
            "model": payload["model"], "metadata": payload["metadata"]}
    sent = pt._post_sync("/api/trajectories", body) or pt.submit_trajectory(
        steps, agent_id=AGENT_ID, agent_name=payload["agent_name"], conversation_id=payload["conversation_id"],
        model=payload["model"], final_status=payload["final_status"])
    tid = (sent or {}).get("id") if isinstance(sent, dict) else None
    print("traced to PRISM:", payload["final_status"], "trajectory", tid)
    if result is None:
        print("rejected by code check:", failed, change)
        return
    result["trajectory_id"] = tid
    result["prism_url"] = PRISM_RUN.format(tid) if tid else None
    p = suggestion_path(a.course, a.version)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=1))
    rp = RESULTS / a.course / f"{a.version}.json"
    res = json.loads(rp.read_text())
    res["suggestion"] = result
    rp.write_text(public_json(res))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
