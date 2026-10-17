---
id: SPEC-day-trader-ai
companions:
  - architecture.md
  - contracts.md
  - lanes.md
  - ../../../AGENTS.md
  - ../../../event.md
  - ../../../notes/strategy-pipeline.md
sources:
  - ../../../notes/sponsors.md
  - ../../../notes/research/backtesting.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete contract for what to build, test and demo today. Sources are for traceability only.

# Day Trader AI (MONEY TALKS 2, Money Intelligence track)

## Why

A pain to solve, for one person first. Luis paid for three day-trading courses (Learn Plan Profit, ZipTrader, Crypto Wizard) and never learned whether following them verbatim would have made money. Course sellers show wins, not a full record; research says almost all day traders lose after fees (north-star deck). Today's hackathon requires the answer to be proven on PRISM (Knowledge Base, Root Cause, Evaluator) with model calls through Nicrron, demoed live by 16:30 on 2026-10-17.

## Capabilities

- **CAP-1** Delay slider
  - **intent:** The user sets how many minutes after each post they would have entered (1, 3, 5, 10, 15, 30, 60) and sees the money result change, because a person reading Discord is not a bot.
  - **success:** Moving the slider changes "$10k became $X" to that delay's value in the results file, instantly, with no network call.
- **CAP-2** Day lookup (stretch)
  - **intent:** The user picks a date and sees what each course posted that day: LPP's live trades, ZipTrader's morning brief, Crypto Wizard's setups.
  - **success:** A date with LPP data lists its trades with times and quotes of 12 words or fewer; a date with nothing says "No posts that day".
- **CAP-3** Sign in and out
  - **intent:** The user signs in with Google and can sign out.
  - **success:** On the public URL, a judge's phone completes Google sign-in and reaches onboarding; sign-out returns to the sign-in screen.
- **CAP-4** Onboarding
  - **intent:** The user picks the courses they bought, sees what they'll get, and watches the audit run (stamp-v2's three steps).
  - **success:** The picked courses become the verdict tabs.
- **CAP-5** Verdict per course
  - **intent:** The user sees, for each course, whether copying every trade it posted beat just holding: one word (Yes, Barely, No, Not enough trades), one line ("$10k became $X. Just holding made $Y."), and what we don't know.
  - **success:** Every number on the screen equals the results file; the word follows the code rule in `contracts.md`.
- **CAP-6** Portfolios (the learning view)
  - **intent:** The user sees each kind of trade the course posted (day, swing, options, crypto) as its own $10k portfolio, side by side against just holding, so they learn which parts worked.
  - **success:** Each portfolio in the file shows its end value, trade count and word; options show "Can't test yet" with a count and the reason.
- **CAP-7** Check any trade
  - **intent:** The user opens a trade and sees when it was posted, when they would have entered at the chosen delay, and the price in between, with the course's own words cited.
  - **success:** A TradingView-style chart shows a post marker and an entry marker the chosen delay apart on minute bars; the citation shows channel and date, or video and timestamp.
- **CAP-8** The proof
  - **intent:** A judge opens the proof behind a verdict: the course rules the agent retrieved (Knowledge Base), the failure cluster and its cause (Root Cause), and the score from our evaluator on v1 and v2 (Evaluator), each linked to PRISM.
  - **success:** Each value comes from `proofs/prism.json`, and each link opens the PRISM run or cluster.
- **CAP-9** Bot suggests a better version (if time)
  - **intent:** The agent proposes one change to a strategy; code backtests it on months it never saw and keeps it only if it beats the parent.
  - **success:** The answer screen shows the change with before and after on dev and sealed months, linked to its `daytrader-improver-v1` PRISM run.
- **CAP-10** What was traded
  - **intent:** The user sees each course's strategies by name and, for one, what it entailed (buy, sell, stop, size, time) with cited quotes.
  - **success:** Every strategy in `results.strategies` shows its name, trade count and result vs just holding; tapping it lists its rules with citations.
- **CAP-11** Time range and best day to stop
  - **intent:** The user picks how long they followed the course (3M, 6M, 1Y) and sees the day stopping would have made the most.
  - **success:** The chips switch to `results.ranges` values; the chart marks `results.best_stop` with its date and value.
- **CAP-12** Best mix (if time)
  - **intent:** The user sees the best pair of strategies in one account, within a course or across courses, on dates both cover.
  - **success:** `results.combos` shows the pair, its window and its sealed-month result vs just holding. Today it is within one course only: LPP (2024-08 to 2025-09) and Crypto Wizard (2025-10 to 2026-10) share no dates.

## Constraints

- The model proposes, the code decides: the model only extracts events and writes plain-language text; code prices every trade on bars after post time + delay, and no schema has an outcome field for the model.
- Course content is copyrighted: raw files stay in gitignored `data/`; git, PRISM and the app get paraphrased rules, locators and quotes of 12 words or fewer.
- The public app is static: it reads only committed JSON (`results/`, `proofs/`); no backend, no secret in the browser (the Clerk publishable key is public by design).
- Contracts in `AGENTS.md` are fixed for today; changing one is a PR to `AGENTS.md` first, then a message to every lane.
- PRISM credits: 200 total. Trace only the 30-session LPP proof set plus verdict runs; one `agent_id` per version, never renamed.
- All model calls go through Nicrron; long calls stream.
- Plain words for a non-trader: no "baseline", "drawdown", "Sharpe" or "in-sample" on first view; fake money; "Not advice" on every verdict.
- Costs are always on: 5 bps per side for stocks, 20 bps under $10, 25 bps for crypto.
- Freeze at 16:00; the full-flow test starts at 15:30.
- The look is Mission Control (artifact GMm4UgLyFG3jLqXCSizu3y, X1 Night city), replacing stamp-v2.

## Non-goals

- A fully custom trading algorithm beyond one tested change (CAP-9) and pairs (CAP-12).
- Pricing options (no free options price history).
- Real brokerage, live trading or trade alerts.
- User accounts beyond sign-in: no saved portfolios, payments or per-user data on a server.
- Supabase or any cloud database.
- Showing transcripts, screenshots or member chat.

## Success signal

On the public Ninoo URL a judge signs in with Google on their phone, picks Learn Plan Profit, reads the word and "$10k became $X. Just holding made $Y.", drags the delay from 1 to 15 minutes and watches the money change, then opens the proof and sees the `kb_search` step of a `daytrader-verdict` run, a Root Cause cluster of 3+ failed `extract-lpp-v1` runs, and the evaluator's pass rate rising from v1 to v2 on the same 30 sessions.

## Assumptions

- Options posts are counted and shown as "Can't test yet", not priced through the underlying stock.
- Sizing: LPP copies the host's share counts when stated; otherwise $1,000 per trade.
- The slider opens at 5 minutes.
- Each course is tested on the dates we have: LPP 2024-08-15 to 2025-09-12 (247 sessions); ZipTrader 2026-10-01 to 10-16 (12 briefings, mostly watch-lists, weak evidence); Crypto Wizard the window Luis picked for its collector. Dates barely overlap, so CAP-2 stays a stretch.
- Anyone who signs in sees the same three verdicts; the product answers Luis's own question.
- Clerk's development instance works on a `*.ninoo.app` domain, and Ninoo can import the private repo's `web/` folder; the hello-world test checks both.

## Open Questions

- What did each course cost Luis? With it the verdict can say "worth the investment" in dollars (`course_fee_usd`).
- Widen ZipTrader beyond 12 October briefings (12 months of images Luis saves by hand)? Not today by default.
</content>
</invoke>
