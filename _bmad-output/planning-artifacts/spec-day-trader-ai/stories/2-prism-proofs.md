---
title: 'story/2-prism-proofs: Knowledge Base, Root Cause, Evaluator'
type: 'feature'
created: '2026-10-17'
status: 'draft'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/planning-artifacts/spec-day-trader-ai/contracts.md'
  - '{project-root}/_bmad-output/planning-artifacts/spec-day-trader-ai/lanes.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Money Intelligence track needs three PRISM proofs (Knowledge Base, Root Cause, Evaluator) shown as failure → fix → score, and the web app's proof drawer (CAP-8) needs them as one file, `proofs/prism.json`.

**Approach:** Code in `app/prism/` builds course notes into `kb/`, uploads them to PRISM, runs the `daytrader-verdict-v1/v2` agent (retrieval logged as a `kb_search` step), holds the evaluator rubrics, and assembles `proofs/prism.json`. PRISM UI steps code can't do (create the evaluator, run it, "Analyze now") are written click by click for Luis.

## Boundaries & Constraints

**Always:** quotes ≤ 12 words, paraphrased rules ≤ 15 words, locators instead of raw text, in `kb/`, traces and `proofs/`; agent ids exactly as in `AGENTS.md`; verdict steps `kb_search → load_results → llm_verdict → check_numbers → final_answer`; `final_status="error"` naming the failed check; model calls through Nicrron; keys never printed; PRISM spend logged in `proofs/README.md` and kept under 150 of 200 credits.

**Never:** re-run or re-trace extraction (story `extract-lpp` owns `extract-lpp-v1/v2` runs); write outside `app/prism/`, `kb/`, `proofs/` (plus this spec); trace verdict runs on `results/_sample.json`; change PRISM workspace settings beyond the evaluator, KB docs, Root Cause and (bonus) one alert and one Regex rule; guardrails before the three proofs exist.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| KB build | `data/<course>/events.jsonl` | 3 md files per course, only `status: ok` events | course with no events file is skipped, logged |
| KB upload twice | docs already in PRISM for that agent | no duplicate upload | name + agent match → skip |
| Verdict, numbers ok | `results/<course>/<v>.json` | run `success`, answer cites a card id | N/A |
| Verdict, invented number | answer has a number not in the file | run `error`, `check_numbers` names the number | logged, still traced |
| Results missing or sample | no file, or `sample: true` | no trace sent | exits with a message |

</frozen-after-approval>

## Code Map

- `app/lpp/prism.py` (branch `story/extract-lpp`) -- how extract runs are traced: `conversation_id=lpp-<vid>-lpp-v<n>`, final answer JSON holds `events[]` with `quote`, `qty`, `price`, `level`, plus `failures[]`. The evaluator reads this.
- `app/lpp/evaluate.py` (same branch) -- code mirror of "Numbers grounded"; do not import (unmerged); mirror its rule (decimal point may be dropped in captions).
- `data/lpp/gold/proof_set.json` -- the fixed 30 sessions; v1 top failures today: `quote_too_long` 701, `open_never_closed` 206, `close_without_open` 189, `number_not_near_quote` 61.
- `prismtrace` 0.5.3 `client.py` -- `kb_upload(filename, content, agent_id=)`, `kb_search(query, agent_id=, limit=)`, `kb_list_documents`, `submit_trajectory` (no `metadata` arg: post the payload ourselves with `metadata`).
- PRISM API (verified 14:30): `GET /api/entitlements` says `plan: free`, `evaluators_hub.write: false`; `GET /api/evaluators` lists presets (shape: `template_prompt`, `rails`, `pass_threshold`); `GET /api/intelligence` has `failure_patterns`; credit catalog: evaluator 1/trace, Root Cause 5.
- `results/_sample.json` -- shape only; real `results/lpp/v1.json` comes from story 1 by 15:00.

## Tasks & Acceptance

**Execution:**
- [ ] `app/prism/common.py` -- env, paths, PRISM client, `submit()` with metadata, git sha -- one place for shared plumbing
- [ ] `app/prism/kb.py` -- `build` and `upload --agent` -- proof 1 inputs
- [ ] `app/prism/verdict.py` -- the verdict agent v1/v2, traced -- proof 1 run and second evaluator inputs
- [ ] `app/prism/evaluators.py` -- rubric texts + code mirrors scoring traced runs -- proof 3, cross-checks PRISM's pass rate
- [ ] `app/prism/proofs.py` -- assemble and validate `proofs/prism.json` from `proofs/parts/*.json` -- the web app's one file
- [ ] `proofs/README.md` -- credit log and Luis's click-by-click PRISM steps
- [ ] `kb/*.md`, `proofs/prism.json` -- generated, committed

**Acceptance Criteria:**
- Given events for a course, when `python -m prism.kb build` runs, then three `kb/<course>-*.md` files exist and no quote is over 12 words.
- Given the docs are uploaded to `daytrader-verdict-v1`, when a v1 verdict runs on real results, then its Steps tab shows a `kb_search` step with the query and snippets, and the answer cites a card.
- Given 3+ failed `extract-lpp-v1` runs in PRISM, when Luis presses "Analyze now", then the cluster name, tier, PRISM's cause and our sentence are in `proofs/prism.json`.
- Given the "Numbers grounded" evaluator scored v1 and v2 on the same 30 sessions, then both pass rates and links are in `proofs/prism.json` and `python -m prism.proofs check` passes.

## Design Notes

KB docs are uploaded once per agent (v1 and v2), since a doc belongs to one agent. Verdict v1 writes free text; v2 gets the list of allowed numbers and card ids. `check_numbers` (code) decides either way. Our Root Cause sentence is written from what PRISM's cluster says, not assumed in advance.

## Verification

**Commands:**
- `cd app && uv run python -m prism.kb build` -- expected: 3 files per course with events
- `cd app && uv run python -m prism.verdict --course lpp --version v1 --agent v1 --dry-run` -- expected: 5 steps printed, nothing sent
- `cd app && uv run python -m prism.proofs check` -- expected: `proofs/prism.json` matches contracts.md

## Implementation Notes

## Spec Change Log

## Review Triage Log
