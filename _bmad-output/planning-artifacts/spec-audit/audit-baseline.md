# Audit baseline (2026-10-20, main 387f8c4 + gitignored data/)

What exists today, before the audit stories. Each story starts from here.

Key findings
1. LPP extraction code (app/lpp/) is NOT on main: only on unmerged branch story/extract-lpp (.claude/worktrees/extract-lpp-aa4bcf). LPP collection (Discord links via Chrome, yt-dlp captions) has no committed code; method only in notes/strategy-pipeline.md §4.
2. LPP source = YouTube auto-captions of 246 daily live streams (2024-08-15 → 2025-09-12), not transcription. One model call per session (Sonnet via Nicrron, temp 0).
3. Digestion accuracy: code checks on every event (quote/number in source, ticker, price within 1% of minute bar, ledger). v1 2,883 pass / 1,313 review; v2 3,773 / 355. Gold set = 5 LPP sessions, 126 events, drafted by the agent, NOT human-reviewed (v1 recall 96.4%, precision 94.1%; v2 96.4% / 100%). No human sample for Crypto Wizard or ZipTrader.
4. Math: engine has 17 unit tests; handcheck.py checks one entry price only. No independent P&L recompute. Crypto Wizard trades sum reconciles to $9,221.20; LPP v1 file keeps 200 of 315 trades so it can't be reconciled from the file.
5. By year (5-min delay, from series): LPP 2024 +3.85% vs SPY +6.66%; 2025 −5.97% vs SPY +12.17%. Crypto Wizard 2025 −2.35% vs BTC −18.99%; 2026 −5.57% vs BTC −6.88%. Realized-only.
6. Misleading: Crypto Wizard "Yes" = lost 7.79%, less than BTC (−24.57%); sealed months −0.82% vs BTC +26.04%. LPP v2 (29 sessions) compared with 13-month SPY. "1y" range ≠ full window. Hold ignores dividends.
7. README errors: run command missing --course; "every run traced" (only proof sets); "transcribed" (captions); no data layout, checks, gold caveats, exit/sizing assumptions.
8. PRISM: only the 30-session LPP proof set + verdict runs traced. Numbers-grounded code score 52%→66% vs notes 53.3/66.7 (denominator mismatch).
