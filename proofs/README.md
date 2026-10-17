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
| | **Total** (cap 150 of 200) | **0** |
<!-- spend:end -->

## Steps only Luis can do in PRISM

Labels come from PRISM's docs; the exact button names get checked on screen and fixed here.

**K. Knowledge Base (after I upload)**
1. Left menu → Knowledge Base.
2. Check 9 docs, agent `daytrader-verdict-v1`.

**R. Root Cause (after the 30 v1 runs)**
1. Left menu → Intelligence → Root Cause.
2. Agent filter: `extract-lpp-v1`.
3. Press "Analyze now" (5 credits).
4. Open the biggest cluster.
5. Send me its link.

**E. Evaluator "Numbers grounded"**
1. Left menu → Evaluators → New.
2. Type: LLM judge.
3. Paste the rubric: `uv run python -m prism.evaluators show`.
4. Labels `grounded`, `ungrounded`; pass `grounded`.
5. Save, then run on `extract-lpp-v1` runs.
6. Run again on `extract-lpp-v2` runs.
7. Send me both pass rates.
