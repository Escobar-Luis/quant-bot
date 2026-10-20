"""Audit of the money math (story audit-2-math-eval): a second calculator written from contracts.md.

  cd app && uv run python -m audit.run         # rebuild positions, recompute, reconcile with results/
  cd app && uv run python -m audit.gate        # may the post and the video render go ahead?

Independent of the engine: audit.positions builds the positions from data/<course>/ events, audit.calc prices
them from cached bars, and neither imports backtest.*. Only the comparison imports the engine-side loaders
(backtest.<course>.build), to diff their positions with the audit's.

Two readings to know:
- LPP's headline follows rule 13 (no look-ahead: overnight only on a horizon said before 15:55 ET) with sizing
  "known" (each add sized from the counts said by then), since spec-audit story 18. Rule 11 with sizing "trade"
  (sessions stitched by his later words; all of a trade's buys together are $1,000) is checked on the
  `as_taught_stitched` key. Rule 6's cash cap is applied per buy as it fills.
- Just holding ends at the official daily close (what a holder gets); the last 1-minute close is reported as an
  alternative (--hold-close minute).
"""
