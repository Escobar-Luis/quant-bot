"""Audit of the money math (story audit-2-math-eval): a second calculator written from contracts.md.

  cd app && uv run python -m audit.run         # rebuild positions, recompute, reconcile with results/
  cd app && uv run python -m audit.gate        # may the post and the video render go ahead?

Independent of the engine: audit.positions builds the positions from data/<course>/ events, audit.calc prices
them from cached bars, and neither imports backtest.*. Only the comparison imports the engine-side loaders
(backtest.<course>.build), to diff their positions with the audit's.

Two readings to know:
- LPP's headline follows rule 11 with sizing "trade" (all of a trade's buys together are $1,000): both read his
  later words. Rule 13 (no look-ahead: overnight only on a horizon said before 15:55 ET, sizing "known" from the
  counts said by then) is checked on the provisional `no_look_ahead` key. Both sizings are superseded by the
  bankroll model (spec-audit CAP-9). Rule 6's cash cap is applied per buy as it fills.
- Just holding ends at the official daily close (what a holder gets); the last 1-minute close is reported as an
  alternative (--hold-close minute).
"""
