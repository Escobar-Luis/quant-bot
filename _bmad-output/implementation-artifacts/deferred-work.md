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

## Deferred from: story backend-1-verdict-api (2026-10-17)
- source_spec: `_bmad-output/planning-artifacts/backend/stories/backend-1-verdict-api.md`
  summary: Send `ETag` (the file's sha256) and `Cache-Control` on the results endpoint; answer 304.
  evidence: The files are immutable per snapshot and their hashes are already computed at load; backend-2 (deploy) is where caching headers start to matter.
- source_spec: `_bmad-output/planning-artifacts/backend/stories/backend-1-verdict-api.md`
  summary: Add a supply-chain cooldown (uv `exclude-newer`) so new dependency releases wait about a week.
  evidence: The lock took fastapi 0.143.3 a day after release; a repo-wide setting affects every lane's dependencies.
- source_spec: `_bmad-output/planning-artifacts/backend/stories/backend-1-verdict-api.md`
  summary: List `app/api/` (and later `app/pipeline/`) in AGENTS.md contract 6, "who writes where".
  evidence: AGENTS.md says contracts change there first, by PR; it goes in the backend architecture PR.
- source_spec: `_bmad-output/planning-artifacts/backend/stories/backend-1-verdict-api.md`
  summary: Merge the backend architecture PR before PR #47, so `app/README.md`, the story context and the `snapshot.py` docstring links resolve.
  evidence: The spine lives on the architecture branch; bmad-code-review (Blind Hunter, Acceptance Auditor) on PR #47.
- source_spec: `_bmad-output/planning-artifacts/backend/stories/backend-1-verdict-api.md`
  summary: Typed response models for the API and its shapes written into `contracts.md` (or an OpenAPI file the lanes build against).
  evidence: `/openapi.json` shows untyped bodies; AGENTS.md says lanes build against contracts written there.
- source_spec: `_bmad-output/planning-artifacts/backend/stories/backend-1-verdict-api.md`
  summary: CORS allowlist on the API, from the same origins list as Clerk's `authorized_parties`.
  evidence: A browser client on another origin is blocked today; backend-2 (deploy) owns it.
- source_spec: `_bmad-output/planning-artifacts/backend/stories/backend-1-verdict-api.md`
  summary: Move `fastapi` and `uvicorn` into an `api` dependency group or extra, so collectors and the backtest don't install them.
  evidence: They are in the shared main `dependencies` today; harmless but every lane installs them.
