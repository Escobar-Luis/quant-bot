"""Evaluator proof: our two rubrics for PRISM's LLM judge, plus a code mirror that scores the same runs locally.

  uv run python -m prism.evaluators show            # print both rubrics, to paste into PRISM (Evaluators -> New)
  uv run python -m prism.evaluators create          # create them by API when the key's workspace allows it
  uv run python -m prism.evaluators local           # code mirror: v1 vs v2 on the same proof-set sessions

PRISM fills {input}, {output} (the run's final answer) and {context} (what retrieval and tool steps returned).
The mirror is a cross-check, not the proof: the proof is PRISM's own score on the traced runs.
"""
import argparse
import json
import re

from .common import DATA, PROOFS, now, read_jsonl, write_public

NUMBERS_GROUNDED = {
    "name": "Numbers grounded",
    "description": "Every price, level and quantity an extracted event reports appears in the quote it cites.",
    "type": "llm_judge",
    "rails": ["grounded", "ungrounded"],
    "pass_label": "grounded",
    "pass_threshold": 1.0,
    "scope": ["extract-lpp-v1", "extract-lpp-v2"],
    "template_prompt": """You are checking one run of an extraction agent that reads a trading live-stream session.

Run output (JSON; its "events" list is what to check):
{output}

Each event may report numbers in "qty", "price" or "level", and cites the exact words it came from in "quote".
For every event that reports at least one of those numbers, check that each number appears in that same event's quote.
Captions may drop the decimal point (58.74 can appear as "5874") or say numbers as words ("a thousand" = 1000); count those as appearing.
Ignore events with no qty, price or level. Ignore the "failures" and "counts" fields.

Label "grounded" if every number of every event appears in its own quote.
Label "ungrounded" if any number does not, and name the first failing event_id and number.""",
}

VERDICT_GROUNDED = {
    "name": "Verdict numbers from results",
    "description": "Every number in the verdict is in the results it loaded; it cites a card and says Not advice.",
    "type": "llm_judge",
    "rails": ["grounded", "ungrounded"],
    "pass_label": "grounded",
    "pass_threshold": 1.0,
    "scope": ["daytrader-verdict-v1", "daytrader-verdict-v2"],
    "template_prompt": """You are checking a verdict written for someone new to trading.

Verdict:
{output}

What the run retrieved and loaded (course rules from the knowledge base, then the backtest results):
{context}

Label "grounded" only if all three hold:
1. Every number in the verdict (money, percent, trade count, minutes) appears in the backtest results above, as written or rounded.
2. The verdict cites at least one strategy card id (like LPP-ENTRY-1) that appears in the retrieved rules.
3. The verdict says "Not advice" and promises nothing: no "guaranteed", "risk-free" or "can't lose".
Otherwise label "ungrounded" and name the first number or rule that fails.""",
}

ALL = [NUMBERS_GROUNDED, VERDICT_GROUNDED]

# --- code mirror of "Numbers grounded" (same rule as app/lpp/evaluate.py on story/extract-lpp) ---------------------
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _norm(s: str) -> str:
    s = (s or "").lower().replace(",", "").replace("’", "'").replace("'", "")
    s = re.sub(r"[^\w\s.$%]", " ", s)
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)
    return " ".join(s.split())


def _num(x):
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    m = _NUM.search(str(x).replace(",", ""))
    return float(m.group()) if m else None


def _said(x: float, nums: set[float]) -> bool:
    return x in nums or any(abs(round(x * f) - x * f) < 1e-6 and round(x * f) in nums and x * f >= 100 for f in (10, 100))


def grounded(e: dict) -> bool:
    have = {float(n) for n in _NUM.findall(_norm(e.get("quote")).replace("$", " ").replace("%", " "))}
    return all(_said(n, have) for n in (_num(e.get(k)) for k in ("qty", "price", "level")) if n is not None)


def mirror() -> dict:
    """v1 vs v2 on the sessions both versions extracted, from the proof set (same inputs)."""
    ids = json.loads((DATA / "lpp" / "gold" / "proof_set.json").read_text())
    by = {}
    for ver, path in (("v1", DATA / "lpp" / "events.jsonl"), ("v2", DATA / "lpp" / "v2" / "events.jsonl")):
        runs = {}
        for e in read_jsonl(path):
            vid = e["source_id"].split(":", 1)[1]
            if vid in ids:
                runs.setdefault(vid, []).append(e)
        by[ver] = runs
    same = sorted(set(by["v1"]) & set(by["v2"]))
    out = {"inputs": f"The same {len(same)} LPP sessions (proof set of {len(ids)}; both versions extracted these)",
           "sessions": same, "at": now()}
    for ver in ("v1", "v2"):
        passed = sum(all(grounded(e) for e in by[ver][v]) for v in same)
        out[ver] = {"agent_id": f"extract-lpp-{ver}", "runs": len(same), "runs_pass": passed,
                    "pass_pct": round(100 * passed / len(same)) if same else None}
    return out


def create() -> None:
    from .common import can_write, client
    pt = client()
    if not can_write(pt, "evaluators_hub"):
        print("This key's workspace can't create evaluators (plan not Builder). Create them in the PRISM UI "
              "(proofs/README.md, step E1) or fix the key, then re-run.")
        pt.close()
        return
    have = {e.get("name") for e in (pt._get_sync(f"/api/evaluators?project_id={pt.project_id}") or {}).get("evaluators", [])}
    for ev in ALL:
        if ev["name"] in have:
            print(f"{ev['name']}: exists, skipped")
            continue
        body = {k: ev[k] for k in ("name", "description", "type", "template_prompt", "rails", "pass_threshold")}
        body["project_id"] = pt.project_id
        r = pt._post_sync("/api/evaluators", body)
        print(f"{ev['name']}: {'created ' + str(r.get('id')) if r else 'FAILED (create it in the UI)'}")
    pt.close()


def prism_scores(evaluator: str = "Numbers grounded") -> dict:
    """PRISM's own labels (GET /api/eval-results), per agent, on the sessions both versions have."""
    from .common import client
    pt = client()
    rows = [r for r in (pt._get_sync(f"/api/eval-results?project_id={pt.project_id}") or {}).get("results", [])
            if r.get("evaluator_name") == evaluator]
    traces = {}
    for aid in ("extract-lpp-v1", "extract-lpp-v2"):
        for t in (pt._get_sync(f"/api/traces?project_id={pt.project_id}&agent_id={aid}&limit=100") or {}).get("traces", []):
            traces[t["id"]] = (aid, t.get("session_id", "").rsplit("-lpp-", 1)[0])
    pt.close()
    by = {}
    for r in sorted(rows, key=lambda r: r["created_at"]):  # latest label per trace wins
        if r["trace_id"] in traces:
            aid, sess = traces[r["trace_id"]]
            cut = any(w in r["reasoning"].lower() for w in ("truncat", "incomplete"))
            by.setdefault(aid, {})[sess] = (r["label"], cut)
    same = sorted(set(by.get("extract-lpp-v1", {})) & set(by.get("extract-lpp-v2", {})))
    out = {"evaluator": evaluator, "inputs": f"The same {len(same)} LPP sessions (proof set), scored by PRISM",
           "task_id": next((r["task_id"] for r in rows), None), "at": now()}
    for v in ("v1", "v2"):
        got = [by[f"extract-lpp-{v}"][s] for s in same]
        labels = [g[0] for g in got]
        out[v] = round(100 * labels.count("grounded") / len(labels)) if labels else None
        out[f"{v}_counts"] = {"grounded": labels.count("grounded"), "ungrounded": labels.count("ungrounded"),
                              "judge_saw_cut_off_output": sum(g[1] for g in got)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["show", "create", "local", "prism"])
    a = ap.parse_args()
    if a.cmd == "show":
        md = ["# Evaluator rubrics (paste into PRISM -> Evaluators -> New)", "",
              "Written by `uv run python -m prism.evaluators show`. Copy each rubric exactly.", ""]
        for ev in ALL:
            md += [f"## {ev['name']}", "", f"- Type: LLM judge", f"- Labels: {', '.join(ev['rails'])}",
                   f"- Pass label: {ev['pass_label']} (threshold {ev['pass_threshold']})",
                   f"- Score runs of: {', '.join(ev['scope'])}", f"- Description: {ev['description']}", "",
                   "Rubric:", "", "```", ev["template_prompt"], "```", ""]
        write_public(PROOFS / "evaluators.md", "\n".join(md))
        print("\n".join(md))
    elif a.cmd == "create":
        create()
    elif a.cmd == "prism":
        ev = prism_scores()
        old = json.loads((PROOFS / "parts" / "evaluator.json").read_text()) if (PROOFS / "parts" / "evaluator.json").exists() else {}
        ev["url"] = old.get("url") or "https://prism.blockconvey.com/evaluators"
        write_public(PROOFS / "parts" / "evaluator.json", json.dumps(ev, indent=1))
        print(json.dumps(ev, indent=1))
    else:
        m = mirror()
        write_public(PROOFS / "parts" / "evaluator_mirror.json", json.dumps(m, indent=1))
        print(json.dumps({k: m[k] for k in ("inputs", "v1", "v2")}, indent=1))


if __name__ == "__main__":
    main()
