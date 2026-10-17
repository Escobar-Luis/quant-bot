# PRISM proofs (story 2)

`prism.json` is what the web app's proof drawer reads (shape in `contracts.md`). It is built from `parts/` by
`cd app && uv run python -m prism.proofs build`; a value we don't have yet stays `null`.

| Proof | Made by | Shows in PRISM |
|---|---|---|
| Knowledge Base | `prism.kb build` + `upload`, then `prism.verdict` | a `daytrader-verdict` run whose Steps tab starts with `kb_search` |
| Root Cause | `extract-lpp-v1` runs that failed a code check, then "Analyze now" | a cluster of 3+ failed runs, its cause |
| Evaluator | "Numbers grounded" on `extract-lpp-v1` and `-v2`, same sessions | two pass rates |

## Credits (200 on the workspace; our cap is 150)

Logged with `uv run python -m prism.proofs spend --credits N --what "..."`. Prices from PRISM's credit catalog:
evaluator 1 per run scored, Root Cause 5, Intelligence 1 per unanalysed trace (automatic analyses are free).

<!-- spend:start -->
| When (UTC) | What | Credits |
|---|---|---|
| 2026-10-17T19:23:44Z | Root Cause Analyze now (pressed by the orchestrator in the UI) | 5 |
| 2026-10-17T19:23:44Z | Numbers grounded on 30 extract-lpp-v1 traces (Luis approved) | 30 |
| 2026-10-17T19:29:15Z | Numbers grounded on 30 extract-lpp-v2 traces (Luis approved; PRISM shows 135 of 200 left) | 30 |
| | **Total** (cap 150 of 200) | **65** |
<!-- spend:end -->

## Steps only Luis can do in PRISM

Page paths checked live (they exist); button names come from PRISM's docs, so check them on screen.

**K. Knowledge Base (done by code, just look)**
1. Open prism.blockconvey.com/knowledge-base.
2. See 9 docs on `daytrader-verdict-v1`.
3. And 9 copies on `-v2`.

**R. Root Cause (the 30 v1 runs are in)**
1. Open prism.blockconvey.com/root-cause.
2. Press "Analyze now" (5 credits).
3. Tell me when it finishes.
4. I read the cluster by API.

**E. Evaluator "Numbers grounded"**
1. Open prism.blockconvey.com/evaluators.
2. Press New, pick LLM judge.
3. Copy name and rubric from `proofs/evaluators.md`.
4. Labels `grounded`, `ungrounded`; pass `grounded`.
5. Save.
6. Score the 30 `extract-lpp-v1` runs.
7. Score the 30 `extract-lpp-v2` runs.
8. Send me both pass rates.

If step E1 or E2 is blocked (Free plan), stop and tell me: the API key's project (…e515ae) still says Free.

**E-bonus. Second evaluator (only if credits allow)**
1. Same steps, rubric "Verdict numbers from results".
2. Score the 4 v1 and 4 v2 verdict runs.
