# Full-flow report (story/5-full-flow-test)

Newest run on top. Screenshots in `tests/flow/shots/`.

## 15:24 · LIVE https://day-trader-ai.vercel.app (bundle index-Db3xMx-B.js, deployed 15:21), main 256018a

**Call: PASS. Demo-ready.**

| Check | Phone 390 | Desktop 1440 | Notes |
|---|---|---|---|
| Live build carries main's numbers + 5 PRISM links | PASS | PASS | `check_numbers.py`: 19 pass, 0 fail |
| Verdict numbers: 3 courses × 1/5/15 min × 3M/6M/1Y/All, strategies, best stop | PASS 150/150 | PASS 150/150 | Desktop run with motion on |
| Fresh visit: Continue → onboarding 1–3 → LPP at 5m, $9,766 | PASS | | Onboarding shows once per browser (localStorage) |
| Sign out → sign in | PASS | | Stand-in sign-in, no Clerk key |
| "1 trade", no best stop on ZipTrader | PASS | | |
| Bot suggestion card + PRISM link | PASS | | Improver run 692218c0, "Not kept" |
| Proof: KB run link, Root Cause cluster link, Evaluator 52% → 66%, 29 → 18 of 30 | PASS | PASS | Root Cause sentence no longer carries a count |
| No horizontal overflow | PASS | PASS | |
| Load | 0.56 s, 2.9 MB | | One console error: a blocked third-party request (ERR_BLOCKED_BY_CLIENT), harmless |

Screenshots: shots/live-phone-verdict-lpp-1524.jpg, shots/live-desktop-proof-lpp-1524.jpg.

## 15:18 · story 3 build c4408eb (local preview), main 28e3f2e

**Call: files PASS · new build PASS · live still old build (deploy waits on Luis's OK)**

| Check | Phone 390 | Desktop 1440 | Notes |
|---|---|---|---|
| Files vs contract, PRISM links | PASS | PASS | KB, improver run open in "bot"; Root Cause is a page link |
| Verdict numbers (3 courses × 1/5/15 × ranges) | PASS 153/153 | PASS 153/153 (2a3eee8) | |
| "1 trade", no best stop when too few | PASS | | Fixed |
| Learning view, trade sheet, sign-out | PASS | | |
| Proof: KB search + run link, Root Cause + cluster link, Evaluator 52% → 66% | PASS | | PRISM's own score: pending (credits) |
| Proof counts agree | FAIL | | Root Cause says 28 of 30, Evaluator says 29 of 30 (shots/phone-proof-28-vs-29.jpg). Sent to story 2; story 4 told |

## 15:15 · story 3 build 7a2f242 (local preview) + live URL

**Call: files PASS · live FAIL (stale deploy) · new build PASS**

| Check | Phone 390 | Desktop 1440 | Notes |
|---|---|---|---|
| Files vs contract (4 results, proofs) | PASS | PASS | `check_numbers.py`, 0 FAIL on main 6e78e4a |
| PRISM links open the right run in "bot" | PASS | PASS | KB verdict v2, 3 v1 verdicts, improver |
| Live build carries main's numbers | FAIL | FAIL | Stale: LPP $8,677 at 10m vs main $9,791; no v2 keys, no proof links. Sent to story 3 |
| Sign in (stand-in) → onboarding 1–3 → LPP | PASS | PASS | No Clerk key: "Continue" signs in locally |
| Verdict numbers, 3 courses × 1/5/15 min × 3M/6M/1Y | PASS | PASS (153/153) | `dom_check.js` |
| Strategies, entails, best day to stop | PASS | PASS | |
| Best mix | PASS | PASS | LPP and Crypto Wizard |
| Proof sheet (KB, Root Cause, Evaluator, newest months, unknowns) | PASS | – | Showed "pending" for PRISM, never "null" |
| No horizontal overflow | PASS | PASS | |
| Load | 0.58 s, 2.5 MB | | Live, old build |

**Bugs sent**
1. Story 3: live deploy stale (shots/phone-verdict-lpp-stale-1511.jpg). Open until redeploy.
2. Story 3: "1 trades" (shots/phone-onboard-1trades.jpg). Fixed in 2a3eee8.
3. Story 3: best day to stop shown for "Not enough trades". Fixed in 2a3eee8.
4. Story 2: proofs/prism.json not on main. Now on main (6e78e4a); Evaluator PRISM pass rates still null.

**Not checked yet:** real Google sign-in (no Clerk key on the build), trade sheet, learning view on desktop.
