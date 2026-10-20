---
id: SPEC-audit
companions: [audit-baseline.md, architecture-diagrams.md, ../spec-day-trader-ai/contracts.md]
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Day Trader AI audit

## Why

Pain plus mandate. Luis is about to tell LinkedIn that copying Learn Plan Profit's trades would have lost money, and he has never verified how the data was pulled, how it was digested, or whether the math is right. The baseline (audit-baseline.md) confirms the gaps: LPP extraction code is not on main, the 96%/94% accuracy was graded by an AI-drafted gold set, nothing recomputes P&L independently, and one verdict says "Yes" for a course that lost 7.8%. Before the claim goes public, he needs to audit each step himself, from GitHub.

## Capabilities

- **CAP-1**
  - **intent:** Anyone can see and rerun how each course's data was collected and turned into events, from code on main.
  - **success:** For each course, a documented command on main lists its sources and event counts, and they equal the counts in the README.
- **CAP-2**
  - **intent:** Luis grades a random sample of extracted events against their source, so digestion accuracy is measured by a human.
  - **success:** A stored sample per course with Luis's verdict per event; human precision and recall per course appear in the README and the evals view.
- **CAP-3**
  - **intent:** A second, independent calculator recomputes every copied trade and each headline per course and delay, and checks them against results/.
  - **success:** One command exits 0 when all trades and headlines reconcile within tolerance, exits non-zero on a deliberately altered result, and writes a per-trade diff; plus a 10-trade hand-check sheet with the raw bars for Luis.
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

## Constraints

- Gate: the LinkedIn post and the video render wait until CAP-3 passes (Luis, 2026-10-20).
- The second calculator must not import `app/backtest/engine.py`; it reads events and raw bars itself, so a shared bug cannot hide.
- Raw course content never enters git or the public app; the app reads only `results/` and `proofs/`.
- No redeploy of the live app without Luis's explicit OK.
- The model proposes, the code decides: every number shown comes from `results/`, `proofs/` or the eval output.

## Non-goals

- Re-extracting every session with a new model or prompt.
- Pricing options trades.
- Adding courses or live trading.
- Human-grading every event.
- Changing the copy-trade rules, unless CAP-3 exposes a bug.

## Success signal

- Luis opens the repo on GitHub, follows the README diagram, runs the audit command and sees it pass, reads LPP by year and all time, and explains in his own words how "No" was computed and how sure it is.

## Assumptions

- By year means calendar years inside each course window (LPP 2024 and 2025; Crypto Wizard 2025 and 2026); all time is the full window.
- Yearly numbers use realized P&L (closed trades), like the existing series.

## Open Questions

- Human grading sample size per course (default: 30 LPP, 30 Crypto Wizard, all 86 ZipTrader events)?
- Should "just holding SPY" include dividends, or stay price-only with the caveat shown?
- CAP-3 tolerance (default: each trade within 1 cent, each headline within 1 dollar)?
