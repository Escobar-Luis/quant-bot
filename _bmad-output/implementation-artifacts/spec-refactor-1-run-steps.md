---
title: 'Backtest entry point reads as named steps'
type: 'refactor'
created: '2026-10-20'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `app/backtest/run.py` `main()` is one ~130-line function that loads trades, prices them, builds portfolios, prices v1 on the same sessions, writes the "what we don't know" notes and the file. Someone explaining the app (Luis, on camera) cannot point at the steps.

**Approach:** Split `main()` into small named functions, one per step of the pipeline, so `main()` reads top to bottom as load → price → portfolios → same-sessions baseline → unknowns → assemble and write. Behavior-preserving: every results file is identical except `generated_at` and `git_sha`.

</frozen-after-approval>

## Implementation Notes

- Baseline: origin/main (937e399) run with `--out` for lpp v1, lpp v2, cryptowizard v1, ziptrader v1 into the session scratchpad; after the refactor the same four runs must match byte for byte once `generated_at` and `git_sha` are dropped.
- Not touched: `results/`, `proofs/`, `web/` (the live demo reads them), CLI flags, printed log lines.

## Verification (2026-10-20)

- `cd app && uv run pytest -q`: 116 passed.
- lpp v1, lpp v2, cryptowizard v1, ziptrader v1 re-run with `--out`: all four JSON files equal the 937e399 baseline once `generated_at` and `git_sha` are dropped; printed logs identical.

### Review Findings (bmad-code-review, 2026-10-20)
- [x] [Review][Patch] prefetch and hold_numbers sat inline in main() [app/backtest/run.py] — moved into price_positions.
- [x] [Review][Patch] sample_trades unnumbered; steps renumbered 1–8.
- [x] [Review][Patch] add_v2_keys hides the data/improver write — named in its docstring.
- [x] [Review][Patch] dropped "why" comment on the baseline — restored.
- Re-verified after patches: four files and logs identical, 116 passed.

Rejected: no proof of unchanged output (false, byte-compare done); no unit tests per step, long parameter lists, repeated d5, loose return types (low, beyond a behavior-preserving split); duplicated lpp-v2 condition and `--limit 0` / negative / empty proof set (pre-existing, not changed here).
