"""Our evaluator (Money Intelligence proof 3): score extractor v1 and v2 on the same 208 trade posts.

A paraphrase passes when all hold:
  present      the model returned a `why` for the post (v1 lost whole batches to broken JSON)
  short        15 words or fewer (copyright cap and UI rule)
  no_new_nums  every number in the paraphrase appears in the post ("every number comes from the source")
  tags_valid   tags come from the closed list
Score = share of posts that pass. Same inputs, same model, only the extractor version changes.

Writes DATA_DIR/cryptowizard/eval.why.json. Run: python evaluate.py
"""
import json

from common import CW, read_jsonl


def score(rows):
    n = len(rows)
    crit = {
        "present": sum(bool(r["why"]) for r in rows),
        "short": sum(r["checks"]["why_words_ok"] for r in rows),
        "no_new_nums": sum(r["checks"]["why_numbers_ok"] for r in rows),
        "tags_valid": sum(r["checks"]["tags_ok"] for r in rows),
    }
    passed = sum(all(r["checks"].values()) for r in rows)
    return {"n": n, "pass": passed, "score": round(passed / n, 3), **{k: f"{v}/{n}" for k, v in crit.items()},
            "prism_runs": len({r.get("prism_run_id") for r in rows}),
            "failed_runs": len({r.get("prism_run_id") for r in rows if not all(r["checks"].values())})}


def main():
    out = {}
    for v in ("v1", "v2"):
        p = CW / f"enrich.{v}.jsonl"
        if p.exists():
            out[v] = score(read_jsonl(p))
    (CW / "eval.why.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
