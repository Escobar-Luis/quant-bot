"""Trace records for the extract-lpp v1/v2 proof-set runs, so PRISM evaluators and Root Cause can read them.

  uv run python -m prism.extract_traces --version v1 --dry-run
  uv run python -m prism.extract_traces --version v1 v2

PRISM's evaluators and Root Cause read traces, not agent runs (trajectories). story/extract-lpp sent the v1 runs
as trajectories only, so this sends one trace per proof-set session from the files that run already wrote
(data/lpp/, read-only): input = locators, output = the run's events JSON with its failed checks. Nothing is
re-extracted. The trace id is fixed per agent and session, so sending twice returns the same trace.
"""
import argparse
import json
import uuid

from .common import DATA, PROOFS, git_sha, now, read_jsonl, write_public

EVENT_KEYS = ("event_id", "type", "t_s", "wall_utc", "ticker", "side", "action", "qty", "price", "level",
              "level_kind", "rule", "quote", "status", "fail")
NS = uuid.UUID("6f1c2a52-6b8e-4c0e-9a51-2f0d3c1e7a10")


def res_dir(version: str):
    return DATA / "lpp" if version == "v1" else DATA / "lpp" / version


def records(version: str) -> list[dict]:
    ids = json.loads((DATA / "lpp" / "gold" / "proof_set.json").read_text())
    sessions = {s["video_id"]: s for s in read_jsonl(res_dir(version) / "sessions.jsonl")}
    events = {}
    for e in read_jsonl(res_dir(version) / "events.jsonl"):
        events.setdefault(e["source_id"], []).append(e)
    agent_id, pv = f"extract-lpp-{version}", f"lpp-{version}"
    out = []
    for vid in ids:
        s = sessions.get(vid)
        if not s or s.get("status") in ("no_captions", "extract_failed") or not s.get("model"):
            continue
        ev = events.get(s["source_id"], [])
        review = [e for e in ev if e["status"] == "needs_review"]
        status = "error" if review else "success"
        answer = {"session": s["source_id"], "session_date": s["session_date"],
                  "counts": {"trade": s["trades"], "call": s["calls"], "rule": s["rules"],
                             "needs_review": s["needs_review"], "round_trips": s["round_trips"]},
                  "failures": [{"event_id": e["event_id"], "check": e["fail"], "quote": e["quote"]} for e in review],
                  "events": [{k: e.get(k) for k in EVENT_KEYS} for e in ev]}
        usage = s.get("usage") or {}
        out.append({
            "trace_id": str(uuid.uuid5(NS, f"{agent_id}:{vid}")),
            "agent_id": agent_id, "agent_name": f"LPP session extractor {version}",
            "session_id": f"lpp-{vid}-{pv}", "model": s["model"],
            "input_messages": [{"role": "user", "content": json.dumps(
                {"task": "List the trades, calls and rules in one LPP live session, each with a quote of 12 words or fewer",
                 "source_id": s["source_id"], "release_utc": s["release_utc"], "prompt_version": pv})}],
            "output": json.dumps(answer),
            "latency_ms": int((s.get("secs") or 0) * 1000),
            "token_count_input": usage.get("in") or 0, "token_count_output": usage.get("out") or 0,
            "metadata": {"agent_version": version, "course": "lpp", "prompt_version": pv, "git_sha": git_sha(),
                         "proof_set": True, "final_status": status,
                         "failed_checks": sorted({k for e in review for k in e["fail"]})},
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", nargs="+", default=["v1"], choices=["v1", "v2"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pt = None
    if not a.dry_run:
        from .common import client
        pt = client()
    log_path = PROOFS / "parts" / "extract_traces.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    for v in a.version:
        recs = records(v)
        errs = sum(r["metadata"]["final_status"] == "error" for r in recs)
        print(f"extract-lpp-{v}: {len(recs)} sessions, {errs} with a failed check")
        if a.dry_run:
            print(json.dumps({k: (r if k != "output" else r[:300]) for k, r in recs[0].items()}, indent=1)[:2000])
            continue
        for r in recs:
            pt.trace_llm(**r)
        log[f"extract-lpp-{v}"] = {"sent_at": now(), "traces": [{"trace_id": r["trace_id"], "session_id": r["session_id"],
                                                                 "final_status": r["metadata"]["final_status"]}
                                                                for r in recs]}
    if pt:
        pt.flush(timeout=60)
        pt.close()
        write_public(log_path, json.dumps(log, indent=1))  # PRISM keeps the ids (private); git gets dates


if __name__ == "__main__":
    main()
