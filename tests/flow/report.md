# Full-flow report (story/5-full-flow-test)

Newest run on top. Screenshots in `tests/flow/shots/`.

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
