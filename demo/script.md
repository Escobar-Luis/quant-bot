# Live demo script (about 2:50, no slides)

App: https://day-trader-ai.vercel.app · Track: Money Intelligence · Story: the failure → the fix → the score.

The clicks follow story 5's walked path, `tests/flow/demo-run.md` (new UI, 15:15); this file adds the words. Every number comes from a file (see "Numbers on screen"). Right before going on stage, run both checks and use their numbers if anything differs:

```bash
git -C ~/dev/quant-bot fetch -q origin && python3 demo/check_numbers.py
~/dev/quant-bot/app/.venv/bin/python tests/flow/check_numbers.py
```

## Before you walk up (2 minutes)

1. **Tab 1 (app):** a **fresh private window** (onboarding shows only on a browser's first visit; a fresh window opens on 5m and All). Shows "Did your trading course actually **work?**"
2. Used this browser before? Avatar → **Change courses** reopens onboarding; set the delay chip back to **5m**.
3. **Tab 2 (PRISM, project "bot"):** Root Cause page, the `extract-lpp-v1` cluster.
4. **Tab 3 (PRISM):** the verdict run from `proofs/prism.json` → `knowledge_base.run_url`, Steps tab.
5. Window size fixed. Don't resize on stage: the chart doesn't redraw.
6. Phone signed in on LPP: the backup.
7. If **Continue** opens Google's account picker, don't sign in on the projector: start signed in on LPP and skip to 0:35.

## The script

| Time | Click | Say |
|---|---|---|
| **0:00** | Tab 1: "Did your trading course actually **work?**" | "I paid for three day-trading courses. Each one shows its wins. None shows a full record. When the FTC looked at one day-trading course, it found 'the vast majority of customer accounts actually lost money.' So: if I'd copied every trade my courses posted, would it have worked?" |
| **0:20** | **Continue** → "Which courses did you buy?" → **Next** → **Run the audit** (about 3 s). | "Pick the courses you bought. It copies every trade they posted with ten thousand dollars of fake money, after costs, and compares it with just holding the market." |
| **0:35** | LPP verdict: chip **No**, 315 trades. | "Learn Plan Profit. A year of live sessions, 315 trades copied. The answer is no. Ten thousand dollars became **$9,766**. Just holding the S&P 500 made **$11,964**." |
| **0:50** | Delay chips **1m** → **15m** → **5m**: $9,945 · $9,729 · $9,766. | "People aren't bots. This is how late you got in after each post. One minute late, fifteen minutes late: still no." |
| **1:00** | Time chip **3M** ($9,994 vs $10,798, No), then **All**. Point at the chart. | "Quit after three months? Still behind. Even on the best day to stop, **January 10, 2025**, it had **$10,416**, and just holding had more." |
| **1:10** | **What was traded** → tap **Short the overbought run** (95 trades, −1.6%, No). Tap again to close. | "Each kind of trade is its own portfolio, so you learn which part worked. Here's the rule, in his own words." |
| **1:20** | Course tab **Crypto Wizard**: "$10k became **$9,221**. It beat holding Bitcoin." chip **Yes**. | "Crypto Wizard: yes, but read the line. It lost money, just less than holding Bitcoin. ZipTrader: not enough trades. It says so instead of guessing." |
| **1:30** | Course tab **Learn Plan Profit** → **See the proof**. **Knowledge Base** card. | "So how do you trust an AI that read a year of videos? Every verdict starts by looking up the course's own rules, from notes we put in PRISM's Knowledge Base." |
| **1:40** | **The failure.** Scroll to **Root Cause** (25 failed runs, our sentence). Optional: Tab 2. | "An AI, through Nicrron, reads each session and writes down the trades. Code checks every one. Version 1 failed our checks in 28 of 30 runs, as PRISM's Agent Runs page counts them. PRISM grouped 25 of them into one cluster. Our reading: it quoted long stretches of captions and lost track of open trades." |
| **2:00** | **The fix.** Stay on the sheet. | "Version 2: each quote must carry its number. And part of the fix is code, not the prompt: code trims each quote to twelve words, and a ledger rule carries open trades across days." |
| **2:10** | **The score.** Scroll to **Evaluator** ("our code" 52% → 66%). | "Our code check, 'numbers grounded', reads every run in full. Runs passing: **52%**, now **66%**. Failed runs: **28 down to 18**. PRISM's own judge scored them 50 and 47, but it saw cut-off output in 24 of 30 runs, so it can't tell them apart. And the money barely moved: the fix made the evidence cleaner, not the answer rosier." |
| **2:30** | Tab 3: PRISM verdict run, Steps tab, first step `kb_search`. | "In PRISM, the verdict agent's first step is that search. It found the course's own rule: you don't have to trade every opportunity. So the verdict says that copying every post isn't how the course says to trade." |
| **2:45** | Tab 1, close the sheet (**×**). Back on LPP, **No**. | "The model proposes. The code decides. Not advice. Thank you." |

## Never on stage (from `tests/flow/demo-run.md`)

1. Real Google sign-in on the projector.
2. ZipTrader's "By kind of trade": one trade. Say "not enough trades" and move on.
3. A PRISM card that says "pending": go to the PRISM tab for that beat.
4. "28 of 30" vs "25": 28 runs failed a code check, as PRISM's Agent Runs page counts them; PRISM's cluster holds 25 of them. Say both, as above.
5. The bot suggestion card: its change didn't hold on the newest months (kept: no). Say so, or skip it.

## If something breaks

| Breaks | Do |
|---|---|
| Numbers differ from this file | Read the check's 5-minute numbers aloud instead |
| App won't load | Phone backup, or the recording (https://claude.ai/artifact/13kzNaaYG9PjSkgw8ZB5Qi) |
| Proof sheet won't open | `#proof-lpp` in the address bar |
| Stuck on onboarding | `#verdict-lpp` in the address bar |

## Numbers on screen (source of truth)

| Shown | Value now | File, field |
|---|---|---|
| LPP, 5 min | $9,766 vs $11,964, No, 315 trades | `results/lpp/v1.json` portfolio `all`, `by_delay.5` |
| LPP, 1 / 15 min | $9,945 / $9,729 | same, `by_delay.1` / `.15` |
| LPP, first 3 months (chip 3M) | $9,994 vs $10,798, No | same, `ranges.3m.by_delay.5` (until 2024-11-14) |
| Best day to stop | Jan 10, 2025, $10,416 vs holding $10,564 | same, `best_stop.by_delay.5` |
| Short the overbought run | 95 trades, −1.6%, No | same, `strategies` |
| Crypto Wizard, 5 min | $9,221 vs $7,543, Yes | `results/cryptowizard/v1.json` `all` |
| ZipTrader | 1 trade, Not enough trades | `results/ziptrader/v1.json` |
| Failed runs, v1 → v2 | 28 → 18 of the same 30 sessions (PRISM Agent Runs) | `proofs/prism.json` `evaluator.failed_runs` |
| Root Cause cluster | 25 failed runs, tier "Needs review" | `proofs/prism.json` `root_cause` |
| Numbers grounded, runs passing | 52% → 66% (our code, full output); PRISM's judge 50% → 47% (saw cut-off output in 24 of 30 runs) | `proofs/prism.json` `evaluator.code_mirror`, `.v1`, `.v2`, `.caveat` |
| Money, same 30 sessions, 5 min | v1 $10,291 vs v2 $10,303 | `proofs/prism.json` `evaluator.money_same_sessions` |
| Knowledge Base | query "Learn Plan Profit entry, exit and sizing rules", card LPP-AVOID-2 | `proofs/prism.json` `knowledge_base` |
| FTC quote | Warrior Trading, 2022 | `notes/research/us-evidence.md` §2 |

Why 28, not 29: failed runs now come from PRISM's Agent Runs page (PR #35); our earlier count was 29. Part of v2's gain is code (quote trimming, a ledger rule), not only the prompt (`evaluator.framing`).

## If a judge asks

1. **Why "Yes" if Crypto Wizard lost money?** "Worked" means beating just holding. Bitcoin fell 25% in that year.
2. **Why $1,000 a trade?** The host trades $40k+ positions; each copy is scaled to $1,000 so $10,000 can follow them.
3. **Options?** Counted, not priced: no free options price history.
4. **Does the model grade the course?** No. Code prices every trade on 1-minute bars. The model has no outcome field.
5. **Can the agent make it better?** It tried: "skip short-breakdown entries from 10:00 ET" helped on older months (−1.3% → +0.5%) but not on the newest ones (−0.1% both), so we didn't keep it.

## Plain-word rules for the talk

1. Say "just holding", never "baseline".
2. Say "got in late", never "latency" or "slippage".
3. Never call a course a scam. The numbers speak.
4. No course content on screen beyond short quotes.
