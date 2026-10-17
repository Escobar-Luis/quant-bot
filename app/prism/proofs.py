"""proofs/prism.json: the one file the web app's proof drawer reads (contracts.md, written only by story 2).

  uv run python -m prism.proofs build                     # assemble from proofs/parts/*
  uv run python -m prism.proofs check                     # shape matches contracts.md; quotes and snippets short
  uv run python -m prism.proofs root-cause --cluster "..." --tier Likely --cause "..." --sentence "..." --runs 7 --url ...
  uv run python -m prism.proofs evaluator --v1 52 --v2 59 --url ...   # PRISM's own pass rates, read off its UI
  uv run python -m prism.proofs link --kind run --id <trajectory id> --url <PRISM page>
  uv run python -m prism.proofs spend --credits 30 --what "Numbers grounded on 60 runs"

Parts (proofs/parts/): kb_uploads.json, verdict_runs.jsonl (prism.kb, prism.verdict), evaluator_mirror.json
(prism.evaluators), root_cause.json, evaluator.json, links.json, credits.jsonl (the commands above).
A value we don't have yet stays null; nothing is made up.
"""
import argparse
import json
import sys

from .common import APP_URL, KB, PROOFS, RESULTS, now, read_jsonl, words

PARTS = PROOFS / "parts"
OUT = PROOFS / "prism.json"
BUDGET, CAP = 200, 150
OUR_SENTENCE_MAX = 30


def _load(name: str, default):
    p = PARTS / name
    return json.loads(p.read_text()) if p.exists() else default


def _save(name: str, value) -> None:
    PARTS.mkdir(parents=True, exist_ok=True)
    (PARTS / name).write_text(json.dumps(value, indent=1))


def run_url(trajectory_id: str | None) -> str | None:
    """PRISM's run page is /trajectories/<id> (route checked live); links.json can override one."""
    if not trajectory_id:
        return None
    return _load("links.json", {}).get(f"run:{trajectory_id}") or f"{APP_URL}/trajectories/{trajectory_id}"


def latest_runs() -> dict:
    """The latest traced verdict run per (agent, course, results version): the same inputs for v1 and v2."""
    rows = [r for r in read_jsonl(PARTS / "verdict_runs.jsonl") if r.get("trajectory_id")]
    current = {(r["course"], r["version"]): r.get("results_sha", "") for r in rows}  # the newest results file wins
    out = {}
    for r in rows:
        if r.get("results_sha", "") == current[(r["course"], r["version"])]:
            out[(r["agent_id"], r["course"], r["version"])] = r
    return out


def _cards(course: str) -> list[dict]:
    p = KB / f"{course}-cards.json"
    return json.loads(p.read_text()) if p.exists() else []


def knowledge_base() -> dict:
    runs = list(latest_runs().values())
    ok = [r for r in runs if r["final_status"] == "success" and r.get("kb_hits")]
    best = next((r for r in ok if (r["course"], r["version"]) == ("lpp", "v1")), None) or \
        (ok[-1] if ok else (runs[-1] if runs else None))
    uploads = _load("kb_uploads.json", [])
    agent = best["agent_id"] if best else "daytrader-verdict-v1"
    docs = sorted({u["doc"] for u in uploads if u["agent_id"] == agent})
    hits = []
    if best:
        # The cards the answer cites come first, shown by their rule; then the other retrieved notes.
        cards = {c["id"]: c for c in _cards(best["course"])}
        rows = best.get("kb_hit_rows") or []
        for cid in best.get("cites", []):
            doc = next((h["doc"] for h in rows if cid in (h.get("cards") or [])), f"{best['course']}-strategy-cards.md")
            if cid in cards:
                hits.append({"doc": doc, "card": cid, "snippet": cards[cid]["rule"], "locator": cards[cid]["locator"]})
        seen = {h["doc"] for h in hits}
        hits += [{"doc": h["doc"], "snippet": h["snippet"]} for h in rows if h["doc"] not in seen and
                 not seen.add(h["doc"])]
    per_course = [{"course": r["course"], "agent_id": r["agent_id"], "run_url": run_url(r["trajectory_id"]),
                   "cites": r.get("cites", []), "final_status": r["final_status"]}
                  for r in runs if r["agent_id"] == "daytrader-verdict-v1" and r["version"] == "v1"]
    return {"agent_id": agent if best or docs else None,
            "run_id": best.get("trajectory_id") if best else None,
            "run_url": run_url(best.get("trajectory_id")) if best else None,
            "docs": docs,
            "query": best.get("query") if best else None,
            "hits": hits[:5],
            "answer": best.get("answer") if best else None,
            "cites": best.get("cites", []) if best else [],
            "v1_run_per_course": per_course}


def _results(course: str, version: str) -> dict:
    p = RESULTS / course / f"{version}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def money_same_sessions() -> dict | None:
    """v1 vs v2 money on the same proof-set sessions, from story 1's results/lpp/v2.json (`same_sessions`)."""
    r = _results("lpp", "v2")
    d = str(r.get("default_delay_min", 5))
    v2 = next((p["by_delay"].get(d) for p in r.get("portfolios", []) if p["id"] == r.get("headline_portfolio")), None)
    v1 = ((r.get("same_sessions") or {}).get("by_delay") or {}).get(d)
    if not (v1 and v2):
        return None
    return {"delay_min": int(d), "sessions": (r.get("same_sessions") or {}).get("sessions"),
            "v1_end": v1["end"], "v2_end": v2["end"], "v1_trades": v1["trades"], "v2_trades": v2["trades"],
            "source": "results/lpp/v2.json"}


def failed_runs() -> dict | None:
    """Failed agent runs per version, as PRISM's Agent Runs page shows them: extract-lpp's own run log
    (data/lpp/prism_runs.jsonl, the latest run per session), else our trace records."""
    from .common import DATA
    last = {(r["agent_id"], r["video_id"]): r for r in read_jsonl(DATA / "lpp" / "prism_runs.jsonl")}
    if {a for a, _ in last} >= {"extract-lpp-v1", "extract-lpp-v2"}:
        out = {v: sum(r["final_status"] == "error" for (a, _), r in last.items() if a == f"extract-lpp-{v}")
               for v in ("v1", "v2")}
        n = sum(a == "extract-lpp-v1" for a, _ in last)
        return {**out, "of": n, "what": "Agent runs in PRISM where any event failed a code check",
                "source": "PRISM agent runs (extract-lpp-v1, -v2)"}
    log = _load("extract_traces.json", {})
    out = {v: sum(t["final_status"] == "error" for t in (log.get(f"extract-lpp-{v}") or {}).get("traces", []))
           for v in ("v1", "v2")}
    n = len((log.get("extract-lpp-v1") or {}).get("traces", []))
    return {**out, "of": n, "what": "Runs where any event failed a code check"} if n else None


def improver() -> dict | None:
    s = _results("lpp", "v1").get("suggestion")
    if not s:
        return None
    return {"agent_id": s.get("agent_id"), "run_url": run_url(s.get("trajectory_id")), "applies_to": s.get("applies_to"),
            "change": s.get("change"), "why": s.get("why"), "dev": s.get("dev"), "sealed": s.get("sealed"),
            "kept": s.get("kept"), "kept_reason": s.get("kept_reason"), "source": "results/lpp/v1.json"}


def caveat(ev: dict) -> str | None:
    """Said plainly when PRISM's judge mostly saw cut-off outputs, so its v1 vs v2 score can't be read as a result."""
    cut = [((ev.get(f"{v}_counts") or {}).get("judge_saw_cut_off_output"), sum(
        (ev.get(f"{v}_counts") or {}).get(k, 0) for k in ("grounded", "ungrounded"))) for v in ("v1", "v2")]
    if not all(c and n for c, n in cut) or max(c / n for c, n in cut) < 0.5:
        return None
    return (f"PRISM's judge saw a cut-off run output in {cut[0][0]} of {cut[0][1]} v1 runs and {cut[1][0]} of "
            f"{cut[1][1]} v2 runs, so its score can't separate the versions; our code check reads the full output.")


def evaluator() -> dict:
    ev = _load("evaluator.json", {})
    mirror = _load("evaluator_mirror.json", {})
    return {"name": "Numbers grounded",
            "checks": "Every price, level and quantity appears in the quote it cites",
            "inputs": ev.get("inputs") or mirror.get("inputs"),
            "v1": {"agent_id": "extract-lpp-v1", "pass_pct": ev.get("v1"), "counts": ev.get("v1_counts")},
            "v2": {"agent_id": "extract-lpp-v2", "pass_pct": ev.get("v2"), "counts": ev.get("v2_counts")},
            "caveat": caveat(ev),
            "code_mirror": {"v1_pass_pct": (mirror.get("v1") or {}).get("pass_pct"),
                            "v2_pass_pct": (mirror.get("v2") or {}).get("pass_pct"),
                            "what": "The same rule run by our code on the same sessions, as a cross-check"} if mirror else None,
            "failed_runs": failed_runs(),
            "money_same_sessions": money_same_sessions(),
            "framing": "The v2 fix shows in extraction quality (grounded numbers, fewer failed runs), not in money: "
                       "on the same sessions both versions end within a few dollars. Part of v2's gain is code "
                       "(quote trimming, a position-ledger rule), not only the prompt.",
            "url": ev.get("url")}


def evaluator_verdict() -> dict | None:
    ev = _load("evaluator_verdict.json", {})
    runs = latest_runs()
    inputs = sorted({(c, v) for (_, c, v) in runs if all((f"daytrader-verdict-{a}", c, v) in runs for a in ("v1", "v2"))})
    if not ev and not inputs:
        return None
    mirror = {}
    for a in ("v1", "v2"):
        passed = sum(runs[(f"daytrader-verdict-{a}", c, v)]["final_status"] == "success" for c, v in inputs)
        mirror[f"{a}_pass_pct"] = round(100 * passed / len(inputs)) if inputs else None
    return {"name": "Verdict numbers from results",
            "checks": "Every number in the verdict is in the results file; it cites a card and says Not advice",
            "inputs": f"The same {len(inputs)} results files: " + ", ".join(f"{c}/{v}" for c, v in inputs),
            "v1": {"agent_id": "daytrader-verdict-v1", "pass_pct": ev.get("v1")},
            "v2": {"agent_id": "daytrader-verdict-v2", "pass_pct": ev.get("v2")},
            "code_mirror": {**mirror, "what": "Our code checks (check_numbers, check_cites, check_language) on the same runs"},
            "url": ev.get("url")}


def credits() -> dict:
    log = read_jsonl(PARTS / "credits.jsonl")
    spent = sum(r["credits"] for r in log)
    return {"budget": BUDGET, "cap": CAP, "spent": spent, "log": "proofs/README.md"}


def build() -> dict:
    rc = _load("root_cause.json", {})
    doc = {
        "schema": "proofs/1",
        "updated_at": now(),
        "prism_app": APP_URL,
        "knowledge_base": knowledge_base(),
        "root_cause": {"agent_id": "extract-lpp-v1", "failed_runs": rc.get("failed_runs"), "cluster": rc.get("cluster"),
                       "tier": rc.get("tier"), "prism_cause": rc.get("prism_cause"),
                       "our_sentence": rc.get("our_sentence"), "url": rc.get("url")},
        "evaluator": evaluator(),
        "evaluator_verdict": evaluator_verdict(),
        "improver": improver(),
        "bonus": _load("bonus.json", {"alert": None, "guardrail": None}),
        "credits": credits(),
    }
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    write_readme_spend()
    return doc


def check(doc: dict) -> list[str]:
    """contracts.md shape, plus the copyright limits (snippets 40 words, our sentence one line)."""
    errs = []
    for k in ("schema", "updated_at", "knowledge_base", "root_cause", "evaluator", "evaluator_verdict", "bonus"):
        if k not in doc:
            errs.append(f"missing {k}")
    kb = doc.get("knowledge_base") or {}
    for k in ("agent_id", "run_url", "docs", "query", "hits"):
        if k not in kb:
            errs.append(f"knowledge_base.{k} missing")
    for h in kb.get("hits") or []:
        if len([w for w in words(h.get("snippet")) if w != "…"]) > 40:
            errs.append(f"snippet over 40 words: {h['doc']}")
    rc = doc.get("root_cause") or {}
    for k in ("agent_id", "failed_runs", "cluster", "tier", "prism_cause", "our_sentence", "url"):
        if k not in rc:
            errs.append(f"root_cause.{k} missing")
    if rc.get("failed_runs") is not None and rc["failed_runs"] < 3:
        errs.append("root_cause needs 3+ failed runs")
    if len(words(rc.get("our_sentence"))) > OUR_SENTENCE_MAX:
        errs.append("our_sentence is over 30 words")
    ev = doc.get("evaluator") or {}
    for v in ("v1", "v2"):
        p = (ev.get(v) or {}).get("pass_pct")
        if p is not None and not 0 <= p <= 100:
            errs.append(f"evaluator.{v}.pass_pct out of range")
    for k in ("alert", "guardrail"):
        if k not in (doc.get("bonus") or {}):
            errs.append(f"bonus.{k} missing")
    if (doc.get("credits") or {}).get("spent", 0) > CAP:
        errs.append(f"credits over the {CAP} cap")
    return errs


def write_readme_spend() -> None:
    """Rewrite the spend table between the markers in proofs/README.md."""
    p = PROOFS / "README.md"
    if not p.exists():
        return
    log = read_jsonl(PARTS / "credits.jsonl")
    rows = ["| When (UTC) | What | Credits |", "|---|---|---|"] + \
        [f"| {r['at']} | {r['what']} | {r['credits']} |" for r in log] + \
        [f"| | **Total** (cap {CAP} of {BUDGET}) | **{sum(r['credits'] for r in log)}** |"]
    text = p.read_text()
    a, b = "<!-- spend:start -->", "<!-- spend:end -->"
    if a in text and b in text:
        text = text.split(a)[0] + a + "\n" + "\n".join(rows) + "\n" + b + text.split(b)[1]
        p.write_text(text)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("check")
    r = sub.add_parser("root-cause")
    r.add_argument("--cluster", required=True)
    r.add_argument("--tier", required=True)
    r.add_argument("--cause", required=True, help="PRISM's cause, as PRISM states it")
    r.add_argument("--sentence", required=True, help="our one sentence on why it happens")
    r.add_argument("--runs", type=int, required=True, help="failed runs in the cluster")
    r.add_argument("--url")
    e = sub.add_parser("evaluator")
    e.add_argument("--v1", type=int, required=True)
    e.add_argument("--v2", type=int, required=True)
    e.add_argument("--inputs")
    e.add_argument("--url")
    e.add_argument("--verdict", action="store_true", help="the second evaluator (verdict v1 vs v2)")
    lk = sub.add_parser("link")
    lk.add_argument("--kind", choices=["run"], required=True)
    lk.add_argument("--id", required=True)
    lk.add_argument("--url", required=True)
    s = sub.add_parser("spend")
    s.add_argument("--credits", type=int, required=True)
    s.add_argument("--what", required=True)
    a = ap.parse_args()

    if a.cmd == "root-cause":
        _save("root_cause.json", {"cluster": a.cluster, "tier": a.tier, "prism_cause": a.cause,
                                  "our_sentence": a.sentence, "failed_runs": a.runs, "url": a.url, "at": now()})
    elif a.cmd == "evaluator":
        _save("evaluator_verdict.json" if a.verdict else "evaluator.json",
              {"v1": a.v1, "v2": a.v2, "inputs": a.inputs, "url": a.url, "at": now()})
    elif a.cmd == "link":
        links = _load("links.json", {})
        links[f"{a.kind}:{a.id}"] = a.url
        _save("links.json", links)
    elif a.cmd == "spend":
        PARTS.mkdir(parents=True, exist_ok=True)
        with open(PARTS / "credits.jsonl", "a") as f:
            f.write(json.dumps({"at": now(), "what": a.what, "credits": a.credits}) + "\n")
    if a.cmd == "check":
        errs = check(json.loads(OUT.read_text()))
        print("\n".join(errs) or "proofs/prism.json OK")
        sys.exit(1 if errs else 0)
    doc = build()
    errs = check(doc)
    print(json.dumps({k: doc[k] for k in ("knowledge_base", "root_cause", "evaluator", "credits")}, indent=1)[:2500])
    print("\n".join(errs) or "proofs/prism.json OK")


if __name__ == "__main__":
    main()
