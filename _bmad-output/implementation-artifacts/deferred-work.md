- source_spec: `_bmad-output/planning-artifacts/spec-day-trader-ai/stories/1-copy-trade-backtest.md`
  summary: Include SPY dividends in just holding (dividend-adjusted daily bars for the hold line).
  evidence: Raw closes leave out about 1.3 points over LPP's window, most of the ±2-point "Barely" band; disclosed in `unknown` for now.
- source_spec: `_bmad-output/planning-artifacts/spec-day-trader-ai/stories/1-copy-trade-backtest.md`
  summary: Drop or flag positions whose legs fall outside the course window.
  evidence: maybe-false today (data fits the windows); a wider re-extraction would clamp out-of-window exits onto the first or last date.
- source_spec: `_bmad-output/planning-artifacts/spec-day-trader-ai/stories/1-copy-trade-backtest.md`
  summary: Declare httpx and a pytest dev dependency in app/pyproject.toml, and add tests for target ladders, gap fills, lpp.build carry rules and cryptowizard.build.
  evidence: httpx resolves only through openai; those paths have no unit tests yet.

## Deferred from: code review of 1-copy-trade-backtest (2026-10-17)
- Trade-row pnl not scaled by the cash-fit factor (0 trades sized down today).
- Exits reaching today's unclosed bars turn a setup into no_bars (4 HYPEUSDT setups).
- v2's word compares its sessions with a full year of holding; same_sessions has the fair numbers.
- Log every version tried in notes/research/backtesting.md (AGENTS.md rule 4).
- Worst drop uses closed trades only.
- Window filter on positions (maybe-false today).
- Tests for trigger fills and lpp.build ledger rules.
- Bar cache robustness: empty weekday answers cached forever, non-atomic writes.
- handcheck: check exits and P&L, clear errors.
