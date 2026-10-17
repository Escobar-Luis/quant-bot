---
title: 'story/1-copy-trade-backtest: copy every posted trade, per delay'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/planning-artifacts/spec-day-trader-ai/contracts.md'
  - '{project-root}/_bmad-output/planning-artifacts/spec-day-trader-ai/lanes.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nobody knows whether copying each course's posted trades verbatim would have made money; the web app and the PRISM verdict agent need real numbers in `results/<course>/<version>.json`, per kind of trade and per delay, after costs, against just holding.

**Approach:** Code only (no model): turn each course's checked events (`data/<course>/events.jsonl`) into copyable positions, price every position on cached 1-minute bars at post time + delay (1, 3, 5, 10, 15, 30, 60 min) with the copy-trade rules, costs and sizing in `contracts.md`, split into `day` / `swing` / `options` / `crypto` / `all`, compare with just holding SPY or BTC, and write the results file exactly per the contract. Acceptance is lanes.md story 1 (1-5); LPP v1 first, then v2, Crypto Wizard, ZipTrader.

</frozen-after-approval>

## Implementation Notes

- Spec and acceptance are pre-approved in `stories.yaml`, `lanes.md` and `contracts.md` (orchestrator brief: "work the story exactly as written"), so this runs the one-shot route.
- No model calls in the backtest, so nothing to trace for it; per contracts the only story-1 `agent_id` is `daytrader-improver-v1` (stretch).
- Built: `app/backtest/` (bars, engine, lpp, cryptowizard, ziptrader, run, handcheck, tests). Results: `results/cryptowizard/v1.json`, `results/ziptrader/v1.json`; LPP waits on Alpaca keys.
- Entry fills at the first bar whose open time is at or after post + delay (rounds up; the contract example agrees, the sample file rounded down).
- Sizing: LPP's raw share counts peak at ~$42k median per position, so his counts are scaled to $1,000 per trade by default (`--literal` opts out), agreed with the orchestrator pending Luis. Open exposure is capped at the cash (orchestrator request): overflow is sized down or skipped and counted as `couldnt_copy`.
- ZipTrader's October briefings hold one directional call; the rest are watch-list notes, counted not traded. Its bars come from Yahoo's keyless 1-minute feed (last 28 days only).
- Extra per-delay fields beyond the contract: `couldnt_copy`, `sized_down`, `peak_invested_usd`, `sealed.trades`; trade rows add `pnl`, `legs`, `exit_kind`, `assumed_exit`; checks add counts.

## Review Triage Log

Blind Hunter, 19 findings:
1. Unbounded `sessions:5` loop: medium, patched (15-day bound).
2. Alpaca caches a not-yet-closed day: low, patched (guard). Feed missing from the cache path: low, rejected (always sip).
3. Crypto Wizard trim posts dropped: false as a pricing bug (the copier's own target orders reproduce them); patched the `unknown` text to say so.
4. Side-less LPP exits dropped: medium, patched (matched to his one open position, else counted).
5. Raw share counts on $10k: high, patched (scaled default plus the exposure cap).
6. No capital-deployed measure ("Yes" while losing): medium, patched (`peak_invested_usd`, cash line in `unknown`).
7. Day trades rolling overnight: medium, patched (`too_late`, counted in `couldnt_copy`).
8. Positions outside the window: maybe-false, deferred (today's data fits the windows).
9. pid collisions: medium, patched (suffixed).
10. Word on unrounded return: low, patched.
11. SPY dividends left out of holding: medium, deferred (disclosed in `unknown`).
12. Break-even stop not re-checked on its bar: low, patched.
13. `unknown` filtered by the substring "scaled": low, rejected (one line, one module).
14. Options counted per event: low, patched (opens only).
15. Empty `fail` list passes the ledger filter: low, patched.
16. httpx and pytest not declared: low, deferred (shared pyproject; transitive today).
17. Test gaps: medium, partly patched (results contract test, too-late, scaled, exposure cap); rest deferred.
18. handcheck crashes and checks entry only: low, rejected (dev tool; MATCH output is the acceptance check).
19. Citation label past an hour: low, patched (h:mm:ss).

### Review Findings (bmad-code-review, 2026-10-17)

Layers: Blind Hunter, Edge Case Hunter, Verification Gap, Acceptance Auditor (all reported). 1 decision-needed, 16 patched, 9 deferred, 4 rejected.

- [x] [Review][Decision] (resolved 2026-10-17: Luis kept $1,000 per trade; contracts.md rule 6 updated in #27) LPP sizing departs from contracts.md rule 6: his share counts are scaled so each trade is $1,000 (`--literal` keeps raw counts); the orchestrator agreed, Luis has not, and the contract text still says "the host's share counts". Needs Luis's yes and an AGENTS.md/contracts.md PR.
- [x] [Review][Patch] `peak_invested_usd` was overwritten by the account high [app/backtest/engine.py:portfolio_stats]
- [x] [Review][Patch] Scaled trades grew with his adds past $1,000 (one SOFI trade ~$111k) [app/backtest/engine.py:_simulate]
- [x] [Review][Patch] A full trim ended the copy; later adds were dropped [app/backtest/engine.py:_simulate]
- [x] [Review][Patch] Day-trade legs after 15:55 rolled to the next morning [app/backtest/engine.py:_simulate]
- [x] [Review][Patch] Word gap float error at exactly 2.00 points [app/backtest/engine.py:word]
- [x] [Review][Patch] Network errors aborted the whole run [app/backtest/bars.py]
- [x] [Review][Patch] Alpaca daily request reached today (403 on the free plan) [app/backtest/bars.py:daily_closes]
- [x] [Review][Patch] same_sessions ran for courses without versions [app/backtest/run.py]
- [x] [Review][Patch] `days` published ~1,600 course quotes; now time, ticker, action only [app/backtest/lpp.py]
- [x] [Review][Patch] LPP calls (watched levels) not copied and not disclosed [app/backtest/lpp.py:unknown]
- [x] [Review][Patch] Crypto Wizard side not normalized; inferred sides undisclosed [app/backtest/cryptowizard.py]
- [x] [Review][Patch] ZipTrader price source, briefing count and swing test hard-coded [app/backtest/ziptrader.py]
- [x] [Review][Patch] Hold symbol shown as BTCUSDT [app/backtest/cryptowizard.py]
- [x] [Review][Patch] Results files carried a git_sha older than their code (regenerated after commit 8fd8d78)
- [x] [Review][Patch] Contract test missed required keys, word consistency, headline [app/backtest/tests/test_results_contract.py]
- [x] [Review][Patch] No tests for target ladder, break-even, re-entry, 15:55 cutoff, portfolio_stats [app/backtest/tests/test_engine.py]
- [x] [Review][Defer] Trade-row `pnl` is not scaled by the cash-fit factor [app/backtest/run.py:trade_row] — deferred: no trade is sized down in today's files (couldnt_copy and sized_down are 0)
- [x] [Review][Defer] Exits that reach today's unclosed bars make the setup no_bars (4 HYPEUSDT setups) [app/backtest/bars.py] — deferred: disclosed in unknown
- [x] [Review][Defer] v2's word compares 52 sessions with a full year of holding [app/backtest/run.py] — deferred: same_sessions holds the like-for-like v1 numbers; how the UI shows it is story 3's call
- [x] [Review][Defer] Every version tried is not appended to notes/research/backtesting.md — deferred: file outside this lane
- [x] [Review][Defer] Worst drop counts closed trades only — deferred: disclosed in unknown
- [x] [Review][Defer] No window filter on positions — deferred: maybe-false, today's data fits
- [x] [Review][Defer] Trigger-fill and lpp.build ledger tests — deferred: no committed result uses triggers
- [x] [Review][Defer] Cache robustness: empty weekday answers cached, non-atomic writes — deferred: no failure seen
- [x] [Review][Defer] handcheck checks entry only and crashes on no match — deferred: dev tool; MATCH is the acceptance check

Rejected:
- Crypto Wizard trim posts ignored: false as a pricing bug; the setup's targets fill the same shares by standing orders, disclosed in unknown.
- sealed_from before the model cutoff: false for this story; contracts.md rule 10 defines the sealed window as the last 3 months.
- Dead helpers (`sessions`, `last_close_on`, an unreachable cash check, copied `words()`): low, no user harm.
- `--limit 0` prices everything: low, never used.
