"""Local copy of the PRISM evaluator "numbers grounded": every qty, price and level an event reports appears in the
quote that same event cites (captions may drop the decimal point: 58.74 may be quoted as "5874").

  uv run python -m lpp.evaluate                  # v1 (data/lpp/events.jsonl)
  LPP_VERSION=v2 uv run python -m lpp.evaluate   # v2 (data/lpp/v2/events.jsonl)
  ... --ids A B                                  # only these sessions (e.g. the proof set)

A run (one session) passes when every event passes (threshold 1.0), as the PRISM rubric is set up.
"""
import argparse
import json

from .checks import _nums_in, _num, _said
from .common import RES, VERSION
from .transcript import norm


def grounded(e: dict) -> bool:
    nums = [(n, sh) for n, sh in ((_num(e.get("qty")), False), (_num(e.get("price")), True), (_num(e.get("level")), True))
            if n is not None]
    have = _nums_in(norm(e.get("quote") or ""))
    return all(_said(n, have, sh) for n, sh in nums)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--proof-set", action="store_true")
    a = ap.parse_args()
    from .prism import proof_set
    ids = set(a.ids or (proof_set() if a.proof_set else []))
    by = {v: [] for v in ids}  # every requested session counts, even one with no events (it passes vacuously)
    for e in map(json.loads, open(RES / "events.jsonl")):
        vid = e["source_id"].split(":", 1)[1]
        if not ids or vid in ids:
            by.setdefault(vid, []).append(e)
    ev = [e for v in by.values() for e in v]
    with_nums = [e for e in ev if any(e.get(k) is not None for k in ("qty", "price", "level"))]
    runs_pass = sum(all(grounded(e) for e in v) for v in by.values())
    print(json.dumps({"version": VERSION, "sessions": len(by), "events": len(ev), "events_with_numbers": len(with_nums),
                      "events_grounded": sum(grounded(e) for e in with_nums),
                      "event_pass_rate": round(sum(grounded(e) for e in with_nums) / len(with_nums), 3) if with_nums else None,
                      "runs_pass": runs_pass, "run_pass_rate": round(runs_pass / len(by), 3) if by else None}))


if __name__ == "__main__":
    main()
