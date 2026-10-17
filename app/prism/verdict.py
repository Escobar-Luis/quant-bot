"""The verdict agent (daytrader-verdict-v1, -v2): "did copying every trade this course posted work?" for one course
and one results version. Code checks every number the model writes against the results file.

  uv run python -m prism.verdict --course lpp --version v1 --agent v1 --dry-run   # print the steps, send nothing
  uv run python -m prism.verdict --course lpp --version v1 --agent v1             # traced to PRISM

Steps (contracts.md): kb_search -> load_results -> llm_verdict -> check_numbers -> check_cites -> check_language
-> final_answer.
kb_search records no step in PRISM by itself, so we log it as a tool_call with the query and the snippets; that
retrieved text is what PRISM evaluators see as {context}.
v1 writes free text from the rules and results. v2 gets the exact numbers it may use and the card ids it may cite.
"""
import argparse
import json
import os
import re
import sys
import time

from .common import COURSES, KB, PROOFS, RESULTS, append_public, clip, git_sha, now, numbers_in

PROMPT_VERSION = {"v1": "verdict-v1", "v2": "verdict-v2"}
MODELS = ["anthropic/claude-sonnet-5-5", "anthropic/claude-haiku-5-5"]
CARD_ID = re.compile(r"\b(?:LPP|ZIPTRADER|CRYPTOWIZARD)-[A-Z]+-\d+\b")
SNIPPET_WORDS = 40
PROMISE = re.compile(r"guarantee|risk[- ]free|can.?t lose|sure thing", re.I)


def query_for(course: str) -> str:
    return f"{COURSES[course]} entry, exit and sizing rules"


def kb_hits(pt, course: str, agent_id: str, limit: int = 5) -> list[dict]:
    """PRISM kb_search, or (dry run) the local kb/ cards. `text` (the whole chunk, our own derived notes) goes to the
    model; the trace logs the doc, score, the card ids in the chunk and a 40-word snippet."""
    if pt is not None:
        rows = [{"doc": r.get("doc_name") or r.get("document_name") or r.get("doc_id"),
                 "chunk": r.get("chunk_index"), "score": r.get("relevance_score"), "text": r.get("content") or ""}
                for r in pt.kb_search(query_for(course), agent_id=agent_id, limit=3 * limit)]
        rows = [r for r in rows if str(r["doc"]).startswith(f"{course}-")][:limit]  # this course's notes only
    else:
        text = (KB / f"{course}-strategy-cards.md").read_text() if (KB / f"{course}-strategy-cards.md").exists() else ""
        blocks = [b for b in text.split("### ")[1:] if re.search(r"entr|exit|siz|stop", b, re.I)]
        rows = [{"doc": f"{course}-strategy-cards.md", "chunk": i, "score": None, "text": "### " + b}
                for i, b in enumerate(blocks[:limit])]
    for r in rows:
        r["cards"] = sorted(set(CARD_ID.findall(r["text"])))
        r["snippet"] = clip(" ".join(r["text"].split()), SNIPPET_WORDS)
    return rows


def logged(hits: list[dict]) -> list[dict]:
    return [{k: h[k] for k in ("doc", "chunk", "score", "cards", "snippet")} for h in hits]


def results_path(course: str, version: str, override: str | None):
    from pathlib import Path
    return Path(override) if override else RESULTS / course / f"{version}.json"


def headline(res: dict) -> dict:
    """The few numbers a verdict needs: headline portfolio at the default delay, plus each portfolio's word."""
    d = str(res.get("default_delay_min", 5))
    port = {p["id"]: p for p in res.get("portfolios", [])}
    head = port.get(res.get("headline_portfolio", "all"), {})
    cell = (head.get("by_delay") or {}).get(d, {})
    return {"course": res.get("course_name"), "version": res.get("version"), "window": res.get("window"),
            "money_start": res.get("money_start"), "delay_min": int(d), "hold": (res.get("hold") or {}).get("what"),
            "headline": {k: cell.get(k) for k in ("end", "ret_pct", "hold_end", "hold_ret_pct", "trades", "won_pct",
                                                  "worst_drop_pct", "word")},
            "portfolios": [{"id": p["id"], "label": p.get("label"), "testable": p.get("testable"),
                            "word": ((p.get("by_delay") or {}).get(d) or {}).get("word"),
                            "trades": ((p.get("by_delay") or {}).get(d) or {}).get("trades") or p.get("count")}
                           for p in res.get("portfolios", [])],
            "unknown": (res.get("unknown") or [])[:5]}


def prompt(agent: str, course: str, hits: list[dict], head: dict, card_ids: list[str]) -> list[dict]:
    rules = "\n\n".join(f"[{h['doc']}]\n{h['text']}" for h in hits) or "(no rules retrieved)"
    base = (f"You are Day Trader AI. A non-trader paid for the {COURSES[course]} course and asks: if I had copied "
            f"every trade it posted, with $10,000 of fake money, after costs, would it have beaten just holding?\n\n"
            f"Course rules retrieved from the knowledge base:\n{rules}\n\n"
            f"Backtest results (code, not you, priced every trade):\n{json.dumps(head, indent=1)}\n\n")
    if agent == "v1":
        task = ("Answer in 3 short sentences of plain words: the answer, what the money did, and the course rule "
                "that best explains it. Cite the rule's card.")
    else:
        allowed = sorted({n for n in numbers_in(json.dumps(head))})
        task = (f"Answer in 3 short sentences of plain words.\n"
                f"1. Start with the word exactly as the results give it: {head['headline'].get('word')}.\n"
                f"2. Use only numbers that appear in the results above, written as they appear there "
                f"(allowed: {', '.join(f'{n:g}' for n in allowed)}). Never round, estimate or compute new numbers.\n"
                f"3. Cite one or two rules by card id in brackets, chosen only from: {', '.join(card_ids) or 'none'}.\n"
                f"4. Never promise returns; no 'guaranteed', 'risk-free' or 'can't lose'.\n"
                f"5. End with: Not advice.")
    return [{"role": "system", "content": "You explain backtest results honestly to people new to trading."},
            {"role": "user", "content": base + task}]


def call_llm(messages: list[dict]) -> tuple[str, str, dict, int]:
    from openai import OpenAI
    llm = OpenAI(base_url=os.getenv("NICRRON_BASE_URL", "https://api.nicrron.ai/v1"),
                 api_key=os.environ["NICRRON_API_KEY"], timeout=120)
    t0 = time.monotonic()
    r = llm.chat.completions.create(model=MODELS[0], messages=messages, temperature=0, max_tokens=2000,
                                    extra_body={"models": MODELS})
    ms = int((time.monotonic() - t0) * 1000)
    u = r.usage
    return (r.choices[0].message.content or "").strip(), r.model or MODELS[0], \
        {"in": getattr(u, "prompt_tokens", 0) or 0, "out": getattr(u, "completion_tokens", 0) or 0}, ms


def _decimals(tok: str) -> int:
    t = tok.rstrip("%kK")
    return len(t.split(".")[1]) if "." in t else 0


def check_numbers(answer: str, res: dict) -> list[str]:
    """Every number in the answer must come from the results file (as written, or rounded, or in $k)."""
    allowed = set(numbers_in(json.dumps(res)))
    text = CARD_ID.sub(" ", answer)
    bad = []
    for m in re.finditer(r"(?<![\w.])\$?-?\d[\d,]*(?:\.\d+)?\s?[kK%]?(?![\w])", text):
        tok = m.group().replace("$", "").replace(",", "").replace(" ", "")
        mult = 1000 if tok[-1:] in "kK" else 1
        try:
            x = float(tok.rstrip("%kK"))
        except ValueError:
            continue
        d = _decimals(tok)
        if not any(round(abs(a) / mult, d) == abs(x) for a in allowed):
            bad.append(m.group().strip())
    return bad


def run(course: str, version: str, agent: str, dry: bool, results_override: str | None) -> dict:
    agent_id = f"daytrader-verdict-{agent}"
    rp = results_path(course, version, results_override)
    if not rp.exists():
        sys.exit(f"{rp} not found: story 1 writes results/{course}/{version}.json")
    res = json.loads(rp.read_text())
    if res.get("sample") and not dry:
        sys.exit(f"{rp} is sample data: verdict runs are traced on real results only (use --dry-run)")
    cards = json.loads((KB / f"{course}-cards.json").read_text()) if (KB / f"{course}-cards.json").exists() else []
    card_ids = [c["id"] for c in cards]
    pt = None
    if not dry:
        from .common import client
        pt = client()

    t0 = time.monotonic()
    hits = kb_hits(pt, course, agent_id)
    kb_ms = int((time.monotonic() - t0) * 1000)
    head = headline(res)
    retrieved = sorted({c for h in hits for c in h["cards"]}) or card_ids
    messages = prompt(agent, course, hits, head, retrieved)
    if dry and not os.getenv("VERDICT_CALL_LLM"):
        answer, model, usage, llm_ms = "(dry run: no model call)", MODELS[0], {"in": 0, "out": 0}, 0
    else:
        answer, model, usage, llm_ms = call_llm(messages)
    bad = check_numbers(answer, res) if not answer.startswith("(dry run") else []
    cites = sorted(set(CARD_ID.findall(answer)))
    known = [c for c in cites if c in card_ids]
    promises = PROMISE.findall(answer)
    language_ok = "not advice" in answer.lower() and not promises
    checks = {"check_numbers": "ok" if not bad else "fail", "check_cites": "ok" if known else "fail",
              "check_language": "ok" if language_ok else "fail"}
    failed = [k for k, v in checks.items() if v == "fail"] if not answer.startswith("(dry run") else []
    status = "error" if failed else "success"
    rsha = (res.get("git_sha") or "")[:7]  # results regenerate: a new file gets new conversations, so runs never mix
    conv = f"verdict-{course}-{version}" + (f"-{rsha}" if rsha else "")
    meta = {"agent_version": agent, "course": course, "prompt_version": PROMPT_VERSION[agent], "git_sha": git_sha(),
            "proof_set": False, "results_version": version, "results_git_sha": rsha}
    steps = [
        {"step_type": "tool_call", "tool_name": "kb_search", "label": "kb_search",
         "input_summary": json.dumps({"query": query_for(course), "agent_id": agent_id, "limit": 5}),
         "output_summary": json.dumps({"hits": logged(hits)}), "duration_ms": kb_ms,
         "status": "success" if hits else "error"},
        {"step_type": "tool_call", "tool_name": "load_results", "label": "load_results",
         "input_summary": json.dumps({"path": f"results/{course}/{version}.json", "git_sha": res.get("git_sha")}),
         "output_summary": json.dumps(head), "duration_ms": 5},
        {"step_type": "reasoning", "label": "llm_verdict",
         "input_summary": json.dumps({"model": model, "prompt_version": PROMPT_VERSION[agent], "kb_hits": len(hits)}),
         "output_summary": answer, "duration_ms": llm_ms, "token_count": usage["in"] + usage["out"]},
        {"step_type": "tool_call", "tool_name": "check_numbers", "label": "check_numbers",
         "input_summary": "every number in the answer appears in the results file (as written, rounded, or in $k)",
         "output_summary": json.dumps({"ok": not bad, "not_in_results": bad[:10]}), "duration_ms": 2,
         "status": "error" if bad else "success"},
        {"step_type": "tool_call", "tool_name": "check_cites", "label": "check_cites",
         "input_summary": "the answer cites at least one real strategy card id",
         "output_summary": json.dumps({"ok": bool(known), "cited": cites, "known": known}), "duration_ms": 1,
         "status": "success" if known else "error"},
        {"step_type": "tool_call", "tool_name": "check_language", "label": "check_language",
         "input_summary": "says 'Not advice' and promises nothing (no guaranteed, risk-free, can't lose)",
         "output_summary": json.dumps({"ok": language_ok, "not_advice": "not advice" in answer.lower(),
                                       "promises": promises}), "duration_ms": 1,
         "status": "success" if language_ok else "error"},
        {"step_type": "final_answer", "label": "verdict",
         "output_summary": answer if not failed else
         f"{answer}\n\nFAILED {', '.join(failed)}: " + "; ".join(
             x for x in (f"not in results: {', '.join(bad[:5])}" if bad else "",
                         "no card cited" if not known else "",
                         "no 'Not advice' or a promise word" if not language_ok else "") if x),
         "status": status},
    ]
    row = {"agent_id": agent_id, "course": course, "version": version, "results_sha": rsha, "conversation_id": conv,
           "final_status": status, "checks": checks,
           "not_in_results": bad, "cites": cites, "query": query_for(course), "kb_hits": [h["doc"] for h in hits],
           "kb_hit_rows": logged(hits), "answer": answer, "at": now()}
    if dry:
        print(json.dumps({"agent_id": agent_id, "conversation_id": conv,
                          "final_status": status, "metadata": meta, "steps": steps}, indent=1))
        return row
    from .common import submit
    r = submit(pt, steps, agent_id=agent_id, agent_name=f"Day Trader AI verdict {agent}",
               conversation_id=conv, model=model, final_status=status, metadata=meta)
    pt.trace_llm(model=model, input_messages=messages, output=answer, latency_ms=llm_ms,
                 token_count_input=usage["in"], token_count_output=usage["out"], agent_id=agent_id,
                 agent_name=f"Day Trader AI verdict {agent}", session_id=conv, metadata=meta)
    pt.flush(timeout=30)
    pt.close()
    row["trajectory_id"] = (r or {}).get("id")
    append_public(PROOFS / "parts" / "verdict_runs.jsonl", json.dumps(row))
    print(json.dumps({k: row[k] for k in ("agent_id", "course", "final_status", "checks", "not_in_results", "cites",
                                          "trajectory_id")}))
    print(answer)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", choices=list(COURSES), required=True)
    ap.add_argument("--version", default="v1", help="results version (the extraction version priced)")
    ap.add_argument("--agent", choices=["v1", "v2"], default="v1")
    ap.add_argument("--results", help="override the results file path")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.course, a.version, a.agent, a.dry_run, a.results)


if __name__ == "__main__":
    main()
