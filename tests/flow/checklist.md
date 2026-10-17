# Full-flow checklist (story/5-full-flow-test)

Run on https://day-trader-ai.vercel.app after each lane redeploys. Two sizes: phone 390 × 844, desktop 1440 × 900. Failures: a screenshot in `tests/flow/shots/<size>-<screen>.png`, one line to the owning lane, a row in `report.md`.

## 0. Before the browser
1. `~/dev/quant-bot/app/.venv/bin/python tests/flow/check_numbers.py --expect <scratch>/expected.json`
2. Zero FAIL. A "live build stale" FAIL means story 3 must redeploy.
3. Keep the printed 5-minute table open: it is what the screen must say.

## 1. Load
1. First paint under 3 s (script prints it).
2. No console errors.
3. No horizontal scroll: `document.documentElement.scrollWidth <= innerWidth`.

## 2. Sign in (if present)
1. Google sign-in button shows.
2. Sign-in lands on onboarding or verdict.
3. Sign out returns to sign-in.

## 3. Onboarding
1. Each screen: one idea, few words.
2. Next / skip both work.
3. Ends on the first verdict.

## 4. Verdict per course (LPP, ZipTrader, Crypto Wizard)
1. Word matches the table (No / Not enough trades / Yes).
2. Money: $10k → end, vs holding.
3. Trade count matches.
4. Fine print: sizing, couldn't copy, sized down.
5. "Not advice" is on the screen.
6. Word colour: Yes green, Barely amber, No red.

## 5. Delay slider / chips
1. At 1, 5 and 15 minutes: end, word and trades follow the table.
2. Choice survives a course switch.

## 6. v2 cards (hide when the key is missing)
1. Strategies: name, trades, result, word.
2. Tap a strategy: buy / sell / stop / size / time, quotes ≤ 12 words.
3. Time range chips 3M / 6M / 1Y: end, holding and word follow.
4. Best day to stop: date and money match `best_stop`.
5. Bot suggestion and best mix: only if present.

## 7. PRISM proof drawer
1. Opens from LPP.
2. Knowledge Base: query, hits, run link opens `daytrader-verdict-v2` in project "bot".
3. Root Cause / Evaluator: real numbers, or "lands here soon". Never "null" or "0% → 0%".
4. Every link opens a PRISM run (script checks ids, agent and project).

## 8. Learning view and trades
1. Each kind as its own portfolio.
2. Options: counted, "can't test yet".
3. A trade sheet opens and closes.

## 9. Phone only
1. Tap targets ≥ 44 px.
2. Drawer and sheets scroll, nothing cut off.
3. Chart fits the width.
