# Demo run: the 2-minute click path

The exact clicks for the live demo, walked by story 5 so no click lands on a broken screen. The words to say are in `demo/script.md` (story 4); this file is the path under them.

**Walked on:** story 3's build c4408eb (local, phone 390 and desktop 1440, 153/153 numbers match main 28e3f2e). Re-walked on the public URL after each redeploy: see `report.md`.

## Before you walk up (2 minutes)

1. Run the check. Any FAIL: use its numbers, not these.
   ```bash
   ~/dev/quant-bot/app/.venv/bin/python tests/flow/check_numbers.py
   ```
2. **Tab 1 (app):** https://day-trader-ai.vercel.app, signed out (avatar → Sign out). Shows "Did your trading course actually work?"
3. Delay chip on **5m**, time chip on **All** (the app remembers the delay; set it once, signed in, then sign out).
4. **Tab 2 (PRISM, project "bot"):** Root Cause page, the `extract-lpp-v1` cluster.
5. **Tab 3 (PRISM):** the verdict run https://prism.blockconvey.com/trajectories/aaf87897-9169-4c07-81de-83f2d7945192, Steps tab.
6. Window size fixed now. Don't resize on stage: the chart doesn't redraw.
7. Phone signed in on LPP: the backup.

## The path

| Time | Click | Must show |
|---|---|---|
| 0:00 | Tab 1 | "Did your trading course actually **work?**" |
| 0:05 | **Continue** | "Which courses did you buy?", Learn Plan Profit card, 315 trades copied |
| 0:10 | **Next** → **Run the audit** | "You'll get" list, then "Running the audit" (about 3 s), lands on LPP |
| 0:20 | (LPP verdict) | "$10k became **$9,766**. Holding SPY made **$11,964**." · chip **No** · 315 trades |
| 0:35 | Delay chips **1m**, then **15m**, then **5m** | $9,945 · $9,729 · back to $9,766. Word stays **No** |
| 0:45 | Time chip **3M**, then **All** | 3M: $9,994 vs $10,798, **No** |
| 0:50 | (point at the chart) | "Best day to stop: **Jan 10, 2025**, with **$10,416**." |
| 0:55 | **What was traded** → tap **Short the overbought run** | 95 trades, −1.6%, **No**; opens BUY / SELL / STOP / SIZE / TIME and two short quotes. Tap again to close |
| 1:05 | Course tab **Crypto Wizard** | "$10k became **$9,221**. It beat holding Bitcoin." · chip **Yes** |
| 1:12 | Course tab **Learn Plan Profit** → **See the proof** | Proof sheet: −2.3% $9,766 vs +19.6% $11,964 |
| 1:18 | Scroll the sheet: **Knowledge Base** → **Root Cause** → **Evaluator** | KB: searched "Learn Plan Profit entry, exit and sizing rules", 3 hits, **See the run**. Root Cause: 25 failed runs, **See the cluster**. Evaluator (our code): **52% → 66%**; runs failing a code check **29 of 30 → 18 of 30** |
| 1:35 | **See the run** (or Tab 3, PRISM run, Steps) | First step `kb_search`; it found LPP-AVOID-2 ("you don't have to trade every opportunity") |
| 1:50 | Tab 1, close the sheet (**×**) | Back on the LPP verdict, **No**. End: "The model proposes. The code decides. Not advice." |

## Never on stage

1. Real Google sign-in: shows Luis's account picker. If the button opens Google, start signed in on LPP instead.
2. ZipTrader's "By kind of trade": one trade; say "Not enough trades" and move on.
3. A PRISM card that says "pending": skip to the PRISM tab for that beat.
4. Counts: say "29 of 30 runs failed a check; v2: 18" and "PRISM grouped 25 of them". The Root Cause sentence may still say 28 (story 2 fixing); don't read it aloud.
5. The bot suggestion (if its card shows): its change didn't hold on the sealed months (kept: no). Say so, or skip it.

## If something breaks

| Breaks | Do |
|---|---|
| Numbers differ from this file | Read the check's 5-minute table aloud instead |
| App won't load | Phone backup, or the recording |
| Proof sheet won't open | Go to `#proof-lpp` in the address bar |
| Stuck on onboarding | Go to `#verdict-lpp` |
