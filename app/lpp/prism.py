"""Trace extraction runs to PRISM: one agent run per session, locators and events only, never transcript text.

  uv run python -m lpp.prism --proof-set          # the 30-session proof set (gold 5 + 25 spread over the year)
  uv run python -m lpp.prism --ids A B --dry-run  # print the payload instead of sending

Budget (notes/strategy-pipeline.md section 7): only the proof set is traced; the other sessions stay untraced.
A run is final_status="error" when any event is needs_review, so Root Cause can cluster the failure kinds.
"""
import argparse
import json
import os

from .common import AGENT_ID, DATA, PROMPT_VERSION, RES, VERSION
from .gold import GOLD_IDS

PROOF_SET = DATA / "gold" / "proof_set.json"
EVENT_KEYS = ("event_id", "type", "t_s", "wall_utc", "ticker", "side", "action", "qty", "price", "level",
              "level_kind", "rule", "quote", "status", "fail")


def proof_set() -> list[str]:
    """Gold 5 plus 25 sessions spread evenly over the year (fixed once, saved, reused for v2)."""
    if PROOF_SET.exists():
        return json.loads(PROOF_SET.read_text())
    rows = [json.loads(line) for line in open(DATA / "sessions.jsonl")]  # always picked from the v1 run
    rest = [r["video_id"] for r in sorted(rows, key=lambda r: r["posted_at"] or "") if r["video_id"] not in GOLD_IDS
            and r["status"] != "no_captions"]
    step = len(rest) / 25
    ids = GOLD_IDS + [rest[int(i * step)] for i in range(25)]
    PROOF_SET.write_text(json.dumps(ids, indent=1))
    return ids


def steps_for(sess: dict, events: list[dict]) -> list[dict]:
    review = [e for e in events if e["status"] == "needs_review"]
    usage = sess.get("usage") or {}
    final = {"session": sess["source_id"], "session_date": sess["session_date"],
             "counts": {"trade": sess["trades"], "call": sess["calls"], "rule": sess["rules"],
                        "needs_review": sess["needs_review"], "round_trips": sess["round_trips"]},
             "failures": [{"event_id": e["event_id"], "check": e["fail"], "quote": e["quote"]} for e in review],
             "events": [{k: e.get(k) for k in EVENT_KEYS} for e in events]}
    return [
        {"step_type": "tool_call", "tool_name": "load_captions", "label": "load_captions",
         "input_summary": json.dumps({"source_id": sess["source_id"], "release_utc": sess["release_utc"]}),
         "output_summary": json.dumps({"words": sess["words"], "duration_s": sess["duration_s"], "captions": "youtube auto, en"}),
         "duration_ms": 50},
        {"step_type": "reasoning", "label": "llm_extract",
         "input_summary": json.dumps({"model": sess["model"], "prompt_version": PROMPT_VERSION, "source_id": sess["source_id"]}),
         "output_summary": json.dumps({"proposed_events": sum(sess["events"].values()), "airtime_pct": sess["airtime"],
                                       "call_errors": [e.get("error") for e in sess.get("call_errors") or []]}),
         "duration_ms": int((sess.get("secs") or 0) * 1000), "token_count": (usage.get("in") or 0) + (usage.get("out") or 0),
         "status": "success" if sess["model"] else "error"},
        {"step_type": "tool_call", "tool_name": "check_events", "label": "check_events",
         "input_summary": "quote_ok, numbers_ok, ticker_ok, price_ok (daily range), ledger_ok",
         "output_summary": json.dumps({"ok": sess["ok"], "needs_review": sess["needs_review"], "fail_kinds": sess["fail_kinds"]}),
         "duration_ms": 200, "status": "error" if review else "success"},
        {"step_type": "final_answer", "label": "events", "output_summary": json.dumps(final)[:30000]},
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--proof-set", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ids = a.ids or (proof_set() if a.proof_set else [])
    if not ids:
        ap.error("pass --ids or --proof-set (tracing all 247 would spend PRISM credits; see module docstring)")
    sessions = {r["video_id"]: r for r in map(json.loads, open(RES / "sessions.jsonl"))}
    events = {}
    for e in map(json.loads, open(RES / "events.jsonl")):
        events.setdefault(e["source_id"], []).append(e)
    pt = None
    if not a.dry_run:
        from prismtrace import PRISMtrace
        pt = PRISMtrace(api_key=os.environ["PRISMTRACE_API_KEY"], project_id=os.environ["PRISMTRACE_PROJECT_ID"],
                        host=os.getenv("PRISMTRACE_HOST", "https://api.prism.blockconvey.com"))
    log = []
    for vid in ids:
        s = sessions[vid]
        if s["status"] in ("no_captions", "extract_failed"):
            continue
        ev = events.get(s["source_id"], [])
        steps = steps_for(s, ev)
        status = "error" if s["needs_review"] else "success"
        if a.dry_run:
            print(json.dumps({"agent_id": AGENT_ID, "conversation_id": f"lpp-{vid}", "final_status": status,
                              "steps": steps}, indent=1)[:3000])
            continue
        r = pt.submit_trajectory(steps, agent_id=AGENT_ID, agent_name=f"LPP session extractor {VERSION}",
                                 conversation_id=f"lpp-{vid}-{PROMPT_VERSION}", model=s["model"], final_status=status)
        log.append({"video_id": vid, "final_status": status, "trajectory_id": (r or {}).get("id"), "sent": bool(r)})
        print(vid, status, "sent" if r else "FAILED")
    if pt:
        pt.flush(timeout=30)
        pt.close()
        with open(DATA / "prism_runs.jsonl", "a") as f:
            for row in log:
                f.write(json.dumps({**row, "agent_id": AGENT_ID, "prompt_version": PROMPT_VERSION}) + "\n")


if __name__ == "__main__":
    main()
