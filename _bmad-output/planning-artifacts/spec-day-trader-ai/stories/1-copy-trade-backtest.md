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
</content>
</invoke>
