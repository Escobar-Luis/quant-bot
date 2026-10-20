---
id: SPEC-audit
companions: [audit-baseline.md, architecture-diagrams.md, bankroll-rules.md, ../spec-day-trader-ai/contracts.md]
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Day Trader AI audit

## Why

Pain plus mandate. Luis is about to tell LinkedIn that copying Learn Plan Profit's trades would have lost money, and he has never verified how the data was pulled, how it was digested, or whether the math is right. The baseline (audit-baseline.md) confirms the gaps: LPP extraction code is not on main, the 96%/94% accuracy was graded by an AI-drafted gold set, nothing recomputes P&L independently, and one verdict says "Yes" for a course that lost 7.8%. Before the claim goes public, he needs to audit each step himself, from GitHub.

## Capabilities

- **CAP-1**
  - **intent:** Anyone can read how each course's data was collected and turned into events, from code on main, and Luis can rerun it.
  - **success:** All collection and extraction code is on main; for each course a documented command, run against local `data/`, lists sources, events, passed and in-review counts and priced trades, and they equal the README; ZipTrader's 86 events vs 1 priced trade is explained.
- **CAP-2**
  - **intent:** Luis grades a random sample of extracted events against their source, so digestion accuracy is measured by a human.
  - **success:** A stored, seeded sample per course with Luis's verdict per event (precision), plus a few source sessions where Luis lists trades the extraction missed (recall); both per course appear in the README and the evals view.
- **CAP-3**
  - **intent:** A second, independent calculator recomputes every copied trade and each headline per course and delay, and checks them against results/.
  - **success:** One command covers every results file, delay and portfolio, exits 0 when all trades (all 315 LPP, via the engine's full ledger) and headlines reconcile within tolerance at stored precision, exits non-zero on a deliberately altered result, writes a per-trade diff and records the pass in `proofs/audit.json` with the results `git_sha`; plus a 10-trade hand-check sheet with raw bars that Luis signs off.
- **CAP-4**
  - **intent:** Each course shows copying vs just holding per calendar year and for all time.
  - **success:** results/ carries the per-year and all-time numbers (end value, return, holding return, trades, word); the app shows them; they match the CAP-3 recompute.
- **CAP-5**
  - **intent:** Every check and evaluator is listed in one place with what it measures, its latest score, where it runs, and what is and isn't traced.
  - **success:** The evals view and README list each code check, gold/human metric, PRISM evaluator and the CAP-3 eval with its current score and source file or PRISM link.
- **CAP-6**
  - **intent:** The README lets Luis audit the system: architecture, tech stack, data layout and counts, assumptions and caveats.
  - **success:** Luis answers, from the README alone, how data was pulled, how it was digested, how accurate that was, how the money was computed and how it is observed; the three wrong claims in audit-baseline.md item 7 are fixed.
- **CAP-7**
  - **intent:** Verdict words never read as success when the copy lost money, and versions are compared only on the same sessions.
  - **success:** Crypto Wizard's card says it lost money and lost less than Bitcoin; LPP v2 is never shown against the full-window SPY return.
- **CAP-8**
  - **intent:** The Oct 21 episode video shows how we know the result is right.
  - **success:** The video has a beat naming the second calculator's result; it is rendered only after CAP-3 passes.

- **CAP-9**
  - **intent:** The user picks a starting amount, a start date and a stop date, and sees what one account would have become copying every posted trade in that window, with no money added and gains and losses compounding.
  - **success:** Moving the amount or either date updates the ending balance, the path and the same-money benchmark in the browser; a test fixes the ending balance for a known ledger, start, stop and amount; the second calculator reproduces it.
- **CAP-10**
  - **intent:** Each course says which kinds of trades made money, which lost, and the likely reason, from data.
  - **success:** Per course, the app lists the best and worst setups with their numbers and one plain-words reason tied to measured market conditions in those months, marked "likely reason".
- **CAP-11**
  - **intent:** Comparisons are fair: the benchmark at the same money actually invested, the held-out months' own verdict, the S&P with dividends, and the result with and without assumed trades.
  - **success:** Every course card shows these four numbers; Crypto Wizard's held-out "No" is visible.
- **CAP-12**
  - **intent:** Every copy decision uses only what the host said before that moment.
  - **success:** A test feeds a session where a later statement would change an earlier decision, and the earlier decision does not change.

## Constraints

- Gate: the LinkedIn post and the video render wait until CAP-3 passes (Luis, 2026-10-20).
- The second calculator is written from `contracts.md`, never from or importing `app/backtest/engine.py`; it reads events and cached bars itself (alpaca_1m, then yahoo_1m; binance for crypto), never fetches, and fails with a named missing-bar error.
- The gate opens on CAP-3 exit 0 plus Luis's hand-check sign-off; any later change to `results/` reopens it.
- Changing the verdict words or adding a `results/` key changes the contract: edit `contracts.md` and AGENTS.md decision 1 first, by PR, then message the lanes.
- Raw course content never enters git or the public app; the app reads only `results/` and `proofs/`.
- No redeploy of the live app without Luis's explicit OK.
- The model proposes, the code decides: every number shown comes from `results/`, `proofs/` or the eval output.

- The bankroll simulator runs in the browser from a per-trade ledger published in `results/` (all trades, every delay); no server, no per-user data stored.
- No margin or borrowing: a trade that doesn't fit the cash left is sized down or skipped, and the app says how many. Exact rules: bankroll-rules.md.
- Stories that write `app/backtest/` or `results/` first amend AGENTS.md contracts 1 and 6; each one reruns `app/audit` and refreshes `proofs/audit.json`.
- Any model call (CAP-10 wording) goes through Nicrron and is traced to PRISM under its own agent_id.

## Non-goals

- Re-extracting every session with a new model or prompt.
- Pricing options trades.
- Adding courses or live trading.
- Human-grading every event.
- Changing the copy-trade rules beyond the bankroll model (CAP-9) and the look-ahead fix (CAP-12).

## Success signal

- Luis opens the repo on GitHub, follows the README diagram, runs the audit command and sees it pass, reads LPP by year and all time, and explains in his own words how "No" was computed and how sure it is (human accuracy, second-calculator match, and how the answer moves across delays).

## Assumptions

- Each new trade's first buy is 10% of the account by default (Luis, 2026-10-20), adjustable with a slider.
- The headline becomes the bankroll run at defaults ($10,000, full window, 10% per trade, 5 minutes); today's $1,000-per-trade numbers remain only as an audit column until Luis retires them.
- By year means calendar years inside each course window (LPP 2024 and 2025; Crypto Wizard 2025 and 2026; ZipTrader 2026, equal to all time); all time is the full window.
- A year is a slice of the one all-time run: a trade belongs to its exit year, the year return is realized P&L over equity at the year's start, holding runs from the year's first to last trading day inside the window, and under 30 trades reads "Not enough trades".
- v2 is compared with v1 on the same sessions (`same_sessions`).

## Open Questions

- Sentiment for CAP-10: market data only (VIX, trend, sector moves; free), or also news and social sentiment (paid or rate-limited)?

- Human grading sample size per course (default: 30 LPP, 30 Crypto Wizard, all 86 ZipTrader events)?
- CAP-3 tolerance (default: each trade within 1 cent, each headline within 1 dollar)?
