"""Audit of the money math (story audit-2-math-eval): a second calculator written from contracts.md, run as
`cd app && uv run python -m audit.run`. It never imports backtest.engine or backtest.extras directly; the course
loaders it reuses for the list of positions import engine's Leg/Position data classes only."""
