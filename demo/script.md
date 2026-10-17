# Live demo script (about 2:50, no slides)

App: https://day-trader-ai.vercel.app · Track: Money Intelligence · Story: the failure → the fix → the score.

Numbers move while the lanes finish. Every number below comes from a file (see "Numbers on screen"). Before going on stage, run `python3 demo/check_numbers.py` and fix any line that differs.

## Before you walk up (3 minutes)

1. Tab 1, private window: the app's sign-in screen.
2. Tab 2: the app, signed in, on `#verdict-lpp`, slider at 5 min.
3. Tab 3: PRISM, Root Cause cluster for `extract-lpp-v1`.
4. Tab 4: PRISM, Evaluator "Numbers grounded", v1 vs v2.
5. Tab 5: PRISM, the verdict run from `proofs/prism.json` → `knowledge_base.run_url`, Steps tab.
6. Phone: app signed in (backup).
7. Check tab 2: the LPP line must say **$9,766** and **315 trades**. Anything else means the app shows a different file; read the check script's output and use its numbers.
8. Open **See the proof** on tab 2. If a PRISM card shows "null", "0% → 0%" or an empty search, don't scroll to it on stage; use the PRISM tabs instead.

No real Google sign-in on the projector: it shows Luis's account picker. Tab 1 is for the opening line only.

## The script

| Time | On screen (click) | Say |
|---|---|---|
| **0:00** | Tab 1: "Did your trading course actually WORK?" | "I paid for three day-trading courses. Each one shows its wins. None shows a full record. When the FTC looked at one day-trading course, it found 'the vast majority of customer accounts actually lost money.' So: if I'd copied every trade my courses posted, would it have worked?" |
| **0:20** | Switch to tab 2 (signed in). | "You sign in with Google and pick the courses you bought. It copies every posted trade with ten thousand dollars of fake money, after costs, and compares it with just holding the market." |
| **0:32** | Verdict: Learn Plan Profit, stamp **No**. | "Learn Plan Profit. A year of live sessions, 315 trades copied. The answer is no. Ten thousand dollars became **$9,766**. Just holding the S&P 500 made **$11,964**." |
| **0:50** | Drag the slider 5 → 1 → 15. Money: **$9,945** at 1, **$9,729** at 15. | "People aren't bots. This is how late you got in after each post. One minute late, fifteen minutes late: it never catches up with just holding." |
| **1:02** | Swipe right: ZipTrader, **Not enough trades**. Swipe right again: Crypto Wizard, **Yes**, **$9,221** vs **$7,543**. | "ZipTrader: not enough trades. Twelve briefings, mostly watch-lists, so it says so instead of guessing. Crypto Wizard: yes, but read the line. It lost money, just less than holding Bitcoin. And in the newest three months it fell behind." |
| **1:20** | Swipe back to LPP. Tap **See the proof**. Scroll to **What we don't know**. | "Every verdict says what we don't know: 137 exits we had to assume, share counts he never said. So how do you trust an AI that read a year of videos?" |
| **1:35** | **The failure.** Tab 3: PRISM Root Cause cluster. | "An AI, through Nicrron, reads each session and writes down the trades. Code checks every one: the quote must be real, and its numbers must be in it. Version 1 failed a check in 28 of 30 runs. PRISM grouped the failures: [cluster name, `proofs/prism.json` → `root_cause.cluster`]." |
| **1:55** | **The fix.** Stay on tab 3. | "Two causes. The AI couldn't keep a quote to twelve words, so quotes ran long and missed their numbers. And the host holds trades overnight, so reading one session at a time saw closes with no open. Version 2: quotes carry their number, code trims them, and positions carry across days." |
| **2:15** | **The score.** Tab 4: Evaluator, v1 vs v2. | "Our evaluator, 'numbers grounded', scored both versions on the same 29 sessions. Runs passing: **52%**, now **66%**. Failed runs: 28 down to 16. And the verdict didn't move: still no." |
| **2:30** | **The knowledge.** Tab 5: verdict run, Steps tab, first step `kb_search`. | "When the agent explains a verdict, its first step searches the course notes we put in PRISM. It found the course's own rule: you don't have to take every trade. So the verdict says that too." |
| **2:45** | Back to tab 2, the stamp. | "The model proposes. The code decides. Not advice. Thank you." |

## Fallbacks (say it, don't hide it)

| Beat | If it isn't in PRISM yet | Say |
|---|---|---|
| Root Cause | Show the `extract-lpp-v1` runs list in PRISM (28 marked error, each naming its failed check). | "PRISM's Root Cause runs on these 28 failures; each one names the check it failed." |
| Evaluator | Say the numbers; don't show the drawer's card if it reads "0% → 0%". | "These pass rates are our code running the same rule; PRISM's own scores land next." |
| Knowledge Base | The run link is in `proofs/prism.json`; open it in PRISM. | (no change) |
| Wifi | Phone on hotspot, or play the recording (`demo/README.md`). | "Here's the same flow, recorded an hour ago." |

## Numbers on screen (source of truth)

| Shown | Value now | File, field |
|---|---|---|
| LPP, 5 min | $9,766 vs $11,964, No, 315 trades | `results/lpp/v1.json` portfolio `all`, `by_delay.5` |
| LPP, 1 / 15 min | $9,945 / $9,729 | same, `by_delay.1` / `.15` |
| LPP assumed exits | 137 day trades | same, `unknown[0]` |
| Crypto Wizard, 5 min | $9,221 vs $7,543, Yes | `results/cryptowizard/v1.json` `all` |
| Crypto Wizard, newest 3 months | -0.8% vs Bitcoin +26.0% | same, `by_delay.5.sealed` |
| ZipTrader | 1 trade copied of 12 briefings, Not enough trades | `results/ziptrader/v1.json` |
| Failed runs, v1 → v2 | 28 → 16 of the same 30 sessions | `notes/sources/lpp.md`, extract-lpp PR #18 |
| Numbers grounded, runs passing | 52% → 66% (our code); PRISM's own: pending | `proofs/prism.json` `evaluator` |
| The two causes | quotes too long; one-session ledger | `notes/sources/lpp.md` §7, "Our one sentence" |
| Knowledge Base | query "Learn Plan Profit entry, exit and sizing rules", card LPP-AVOID-2 | `proofs/prism.json` `knowledge_base` |
| FTC quote | Warrior Trading, 2022 | `notes/research/us-evidence.md` §2 |

Why 29 and 30: the proof set is 30 sessions; the evaluator scores the 29 that both versions extracted.

## If a judge asks

1. **Why "Yes" if Crypto Wizard lost money?** "Worked" means beating just holding. Bitcoin fell 25% in that year.
2. **Day trades vs everything?** LPP day trades about broke even ($10,046 at 5 min); swing trades lost.
3. **Why $1,000 a trade?** The host trades $40k+ positions; we scale each to $1,000 so $10,000 can copy them.
4. **Options?** Counted, not priced: no free options price history.
5. **Does the model grade the course?** No. Code prices every trade on 1-minute bars. The model has no outcome field.
6. **v2 on the full year?** v2 re-read 52 sessions so far; we only compare it with v1 on those same sessions.

## Plain-word rules for the talk

1. Say "just holding", never "baseline".
2. Say "got in late", never "latency" or "slippage".
3. Never call a course a scam. The numbers speak.
4. No course content on screen beyond short quotes.
