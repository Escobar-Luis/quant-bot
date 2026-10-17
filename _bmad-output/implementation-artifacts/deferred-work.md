- source_spec: `_bmad-output/planning-artifacts/spec-day-trader-ai/stories/1-copy-trade-backtest.md`
  summary: Include SPY dividends in just holding (dividend-adjusted daily bars for the hold line).
  evidence: Raw closes leave out about 1.3 points over LPP's window, most of the ±2-point "Barely" band; disclosed in `unknown` for now.
- source_spec: `_bmad-output/planning-artifacts/spec-day-trader-ai/stories/1-copy-trade-backtest.md`
  summary: Drop or flag positions whose legs fall outside the course window.
  evidence: maybe-false today (data fits the windows); a wider re-extraction would clamp out-of-window exits onto the first or last date.
- source_spec: `_bmad-output/planning-artifacts/spec-day-trader-ai/stories/1-copy-trade-backtest.md`
  summary: Declare httpx and a pytest dev dependency in app/pyproject.toml, and add tests for target ladders, gap fills, lpp.build carry rules and cryptowizard.build.
  evidence: httpx resolves only through openai; those paths have no unit tests yet.
