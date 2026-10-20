"""Trace extraction runs to PRISM: one agent run per session, locators and events only, never transcript text.

  uv run python -m lpp.prism --proof-set          # the 30-session proof set (gold 5 + 25 spread over the year)
  uv run python -m lpp.prism --ids A B --dry-run  # print the payload instead of sending

Budget (notes/strategy-pipeline.md section 7): only the proof set is traced; the other sessions stay untraced.
A run is final_status="error" when any event is needs_review, so Root Cause can cluster the failure kinds.
"""
import argparse
import json
import os
import subprocess
import uuid

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


def _final(sess: dict, events: list[dict], limit: int = 30000) -> str:
    """The final answer: counts, failures (check + quote) and events. Events are dropped from the end, never cut
    mid-JSON, when a busy session would pass PRISM's size limit."""
    review = [e for e in events if e["status"] == "needs_review"]
    final = {"session": sess["source_id"], "session_date": sess["session_date"],
             "counts": {"trade": sess["trades"], "call": sess["calls"], "rule": sess["rules"],
                        "needs_review": sess["needs_review"], "round_trips": sess["round_trips"]},
             "failures": [{"event_id": e["event_id"], "check": e["fail"], "quote": e["quote"]} for e in review],
             "events": [{k: e.get(k) for k in EVENT_KEYS} for e in events]}
    out = json.dumps(final)
    while len(out) > limit and final["events"]:
        final["events"].pop()
        final["events_left_out"] = final.get("events_left_out", 0) + 1
        out = json.dumps(final)
    return out


def steps_for(sess: dict, events: list[dict]) -> list[dict]:
    review = [e for e in events if e["status"] == "needs_review"]
    usage = sess.get("usage") or {}
    checks_ran = sorted({e["checks"].get("price_check") for e in events if e["checks"].get("price_check")})
    return [
        {"step_type": "tool_call", "tool_name": "load_captions", "label": "load_captions",
         "input_summary": json.dumps({"source_id": sess["source_id"], "release_utc": sess["release_utc"]}),
         "output_summary": json.dumps({"words": sess["words"], "duration_s": sess["duration_s"], "captions": "youtube auto, en"})},
        {"step_type": "reasoning", "label": "llm_extract",
         "input_summary": json.dumps({"model": sess["model"], "prompt_version": PROMPT_VERSION, "source_id": sess["source_id"]}),
         "output_summary": json.dumps({"proposed_events": sum(sess["events"].values()), "airtime_pct": sess["airtime"],
                                       "call_errors": [e.get("error") for e in sess.get("call_errors") or []]}),
         "duration_ms": int((sess.get("secs") or 0) * 1000), "token_count": (usage.get("in") or 0) + (usage.get("out") or 0),
         "status": "success" if sess["model"] else "error"},
        {"step_type": "tool_call", "tool_name": "check_events", "label": "check_events",
         "input_summary": f"quote_ok, numbers_ok, ticker_ok, price_ok ({' or '.join(checks_ran) or 'no bars'}), ledger_ok",
         "output_summary": json.dumps({"ok": sess["ok"], "needs_review": sess["needs_review"], "fail_kinds": sess["fail_kinds"]}),
         "status": "error" if review else "success"},
        {"step_type": "final_answer", "label": "events", "output_summary": _final(sess, events)},
    ]


def payload(vid: str, sess: dict, events: list[dict], proof: set, sha: str, conv: str = "lpp-{vid}") -> dict:
    """One trajectory, as printed by --dry-run and as sent (contracts.md, trace conventions)."""
    return {"agent_id": AGENT_ID, "agent_name": f"LPP session extractor {VERSION}", "conversation_id": conv.format(vid=vid),
            "model": sess["model"], "final_status": "error" if sess["needs_review"] else "success",
            "metadata": {"agent_version": VERSION, "course": "lpp", "prompt_version": PROMPT_VERSION, "git_sha": sha,
                         "proof_set": vid in proof},
            "steps": steps_for(sess, events)}


def send(pt, p: dict):
    """submit_trajectory in prismtrace-sdk 0.5.3 has no metadata argument, so post the same body it builds plus
    metadata; if the server refuses that, fall back to the SDK call without metadata."""
    body = {"project_id": pt.project_id, "conversation_id": p["conversation_id"], "request_id": str(uuid.uuid4()),
            "agent_id": p["agent_id"], "agent_name": p["agent_name"], "steps": p["steps"],
            "total_duration_ms": sum(s.get("duration_ms") or 0 for s in p["steps"]),
            "final_status": p["final_status"], "model": p["model"], "metadata": p["metadata"]}
    r = pt._post_sync("/api/trajectories", body)
    if r:
        return r
    return pt.submit_trajectory(p["steps"], agent_id=p["agent_id"], agent_name=p["agent_name"],
                                conversation_id=p["conversation_id"], model=p["model"], final_status=p["final_status"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--proof-set", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="send again even if prism_runs.jsonl says it was sent")
    ap.add_argument("--conversation-id", default="lpp-{vid}",
                    help='template; "lpp-{vid}-lpp-v1" pairs v2 runs with the 30 v1 runs already in PRISM')
    a = ap.parse_args()
    ids = a.ids or (proof_set() if a.proof_set else [])
    if not ids:
        ap.error("pass --ids or --proof-set (tracing all 247 would spend PRISM credits; see module docstring)")
    proof = set(proof_set())
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    sessions = {r["video_id"]: r for r in map(json.loads, open(RES / "sessions.jsonl"))}
    events = {}
    for e in map(json.loads, open(RES / "events.jsonl")):
        events.setdefault(e["source_id"], []).append(e)
    log_p = DATA / "prism_runs.jsonl"
    sent = {(r["agent_id"], r["video_id"]) for r in map(json.loads, open(log_p)) if r.get("sent")} if log_p.exists() else set()
    pt = None
    if not a.dry_run:
        from prismtrace import PRISMtrace
        pt = PRISMtrace(api_key=os.environ["PRISMTRACE_API_KEY"], project_id=os.environ["PRISMTRACE_PROJECT_ID"],
                        host=os.getenv("PRISMTRACE_HOST", "https://api.prism.blockconvey.com"))
    for vid in ids:
        s = sessions.get(vid)
        if s is None or s["status"] in ("no_captions", "extract_failed"):
            print(vid, "skipped:", "not extracted" if s is None else s["status"])
            continue
        p = payload(vid, s, events.get(s["source_id"], []), proof, sha, a.conversation_id)
        if a.dry_run:
            print(json.dumps(p, indent=1)[:3000])
            continue
        if (AGENT_ID, vid) in sent and not a.force:
            print(vid, "already sent")
            continue
        r = send(pt, p)
        with open(log_p, "a") as f:  # logged per run, so a crash midway never leads to double sends
            f.write(json.dumps({"video_id": vid, "final_status": p["final_status"], "trajectory_id": (r or {}).get("id"),
                                "sent": bool(r), "agent_id": AGENT_ID, "prompt_version": PROMPT_VERSION,
                                "conversation_id": p["conversation_id"], "git_sha": sha}) + "\n")
        print(vid, p["final_status"], "sent" if r else "FAILED")
    if pt:
        pt.flush(timeout=30)
        pt.close()


if __name__ == "__main__":
    main()
