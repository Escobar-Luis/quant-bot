---
title: 'story/1-copy-trade-backtest: copy every posted trade, per delay'
type: 'feature'
created: '2026-10-17'
status: 'in-progress'
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
