# Live demo script (2:45, no slides)

App: https://day-trader-ai.vercel.app · Track: Money Intelligence · Story: the failure → the fix → the score.

Every number below is from a committed file (`results/<course>/v1.json` at the 5-minute delay unless the line says otherwise, or `proofs/prism.json`). If a file changes, re-check this script before going on stage: `demo/check_numbers.py` prints the live values.

## Before you walk up (2 minutes)

1. Laptop: app signed in, on `#verdict-lpp`, slider at 5 min.
2. Tab 2: PRISM, Root Cause cluster for `extract-lpp-v1`.
3. Tab 3: PRISM, Evaluator "Numbers grounded", v1 vs v2.
4. Tab 4: PRISM, a `daytrader-verdict-v1` run, Steps tab.
5. Phone: app signed in (backup screen).
6. If wifi dies: play `demo/recording.mp4` (when it exists).

Tabs 2-4 only if PRISM has them by then. If one is missing, use the fallback line in that beat and say it out loud; never show the mock.

## The script

| Time | On screen (click) | Say |
|---|---|---|
| **0:00** | Sign-in screen: "Did your trading course actually WORK?" | "I paid for three day-trading courses. Every one shows you its wins. None shows a full record. And in the US, retail options traders lost 2.1 billion dollars in 20 months. So I asked one question: if I had copied every trade they posted, would it have worked?" |
| **0:20** | Click **Continue with Google** (real sign-in). Onboarding: tick all three courses, tap through. | "Sign in with Google. Pick the courses you bought. It copies every trade they posted, with ten thousand dollars of fake money, after costs, and compares it with just holding the market." |
| **0:35** | Verdict: Learn Plan Profit, stamp **No**. | "Learn Plan Profit. A year of live trading sessions, 287 trades copied. The answer is no. Ten thousand dollars became **$8,806**. Just holding the S&P 500 made **$11,964**." |
| **0:55** | Drag the slider 5 → 1 → 15 min. Money changes: **$8,653** at 1, **$8,232** at 15. | "People aren't bots. This is how late you got in after each post. One minute late, fifteen minutes late: it never catches up with just holding." |
| **1:10** | Swipe to Crypto Wizard, stamp **Yes**: **$9,221** vs **$7,543**. Then ZipTrader, **Not enough trades**. | "Crypto Wizard: yes, but read the line. It lost money, just less than holding Bitcoin. ZipTrader: not enough trades. Twelve briefings, mostly watch-lists. It says so instead of guessing." |
| **1:30** | Back to LPP. Tap **See the proof**. Scroll to **What we don't know**. | "Every verdict lists what we don't know: exits we had to assume, trades we couldn't copy. Now, how do you trust the AI that read a year of videos?" |
| **1:45** | **The failure.** Tab 2: PRISM Root Cause cluster. | "The model reads each session and writes down the trades. Code checks every one: the quote must be real, and every number must be in it. Version 1 failed 28 of 30 runs. PRISM grouped the failures and named the cause: [cluster name from `proofs/prism.json`]." |
| **2:05** | **The fix.** Stay on PRISM, or back to the drawer. | "Our one-line reason: it wrote down prices it heard nearby, not the ones in the words it quoted. Version 2: the quote must carry the number, and code trims it to the 12 words that hold it." |
| **2:15** | **The score.** Tab 3: Evaluator, v1 vs v2. | "Our evaluator, 'numbers grounded', scores both versions on the same 29 sessions. Runs that pass: **52% → 66%**. Failed runs: **28 → 16**. And the answer didn't change: still no. The fix made the evidence cleaner, not the verdict rosier." |
| **2:30** | **The knowledge.** Tab 4: verdict run, Steps tab, first step `kb_search`. | "When the agent explains a verdict, its first step searches the course notes we uploaded to PRISM, and it cites the card it used." |
| **2:40** | Back to the app's stamp. | "The model proposes. The code decides. Fake money, not advice. Thank you." |

## Fallbacks (say it, don't hide it)

| Beat | If it isn't in PRISM yet | Say |
|---|---|---|
| Root Cause | Show the 28 error runs of `extract-lpp-v1` in PRISM's run list (each names the failed check). | "PRISM's Root Cause analysis runs on these; here are the 28 failures and the check each one failed." |
| Evaluator | Show the drawer's Evaluator card (code mirror, 52% → 66%). | "This is our code running the same rule; PRISM's own scores land here next." |
| Knowledge Base | Show `kb/lpp-strategy-cards.md` cards in the proof drawer, if listed. | "These are the cards we uploaded; the retrieval run lands next." |
| Sign-in fails | Phone backup, already signed in. | "Here's one I signed in earlier." |

## Numbers on screen (source of truth)

| Shown | Value | File, field |
|---|---|---|
| LPP, 5 min | $8,806 vs $11,964, No, 287 trades | `results/lpp/v1.json` portfolio `all`, `by_delay.5` |
| LPP, 1 min / 15 min | $8,653 / $8,232 | same, `by_delay.1` / `by_delay.15` |
| LPP day trades, 5 min | $10,708 (+7.1%) vs +19.6%, No | portfolio `day` |
| Crypto Wizard, 5 min | $9,221 vs $7,543, Yes | `results/cryptowizard/v1.json` `all` |
| Crypto Wizard, newest 3 months (sealed) | −0.8% vs BTC +26.0% | same, `by_delay.5.sealed` |
| ZipTrader | 1 trade copied, Not enough trades | `results/ziptrader/v1.json` |
| v1 vs v2, same 29 sessions, 5 min | $11,009 vs $10,899, both No | `results/lpp/v2.json` `same_sessions` |
| Evaluator, runs passing | 52% → 66% (our code); PRISM's own: pending | `proofs/prism.json` `evaluator.code_mirror` |
| Failed runs | 28 of 30 → 16 of 30 | `extract-lpp` PR #18 |
| US options losses | $2.1B in 20 months (2019-21) | north-star deck; Bryzgalova, Pavlova & Sikorskaya, J. of Finance, 2023 |

## Plain-word rules for the talk

1. Say "just holding", never "baseline".
2. Say "got in late", never "latency" or "slippage".
3. Say "fake money" once, "not advice" once.
4. Never call a course a scam. The numbers speak.
5. No course content on screen beyond short quotes.
