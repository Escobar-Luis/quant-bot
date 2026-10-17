# Code review: PR #17 (web app) and PR #15 (PRISM proofs)

2026-10-17, 15:25 to 15:45 ET. `bmad-code-review`: edge-case hunter and acceptance auditor on each PR, plus direct checks of the live bundle at https://day-trader-ai.vercel.app. Checked against `AGENTS.md`, `contracts.md` and `SPEC.md`.

## Verdict

**PR #17:** safe to merge once the 2 demo-blocking fixes below land and the app is redeployed.
**PR #15:** already merged. Nothing demo-blocking: its count gaps are already explained in `demo/script.md`.

## Clean (checked, nothing to fix)

1. **Secrets:** no `.env` secret value is in the live bundle or in git. The Clerk key isn't set, so sign-in is a plain "Continue" (labelled honestly, not a fake Google button).
2. **Copyright:** every quote in `results/`, `kb/` and `proofs/` is 12 words or fewer. Rules are paraphrases.
3. **Sample data:** `results/_sample.json` (course `lpp`) is never shown, because the real `results/lpp/v1.json` exists. A file with `sample: true` shows a "Sample data" pill.
4. **Live = repo:** the deployed bundle holds the current results (`9765.86`, `9221.2`) and the post-#30 Root Cause sentence.
5. **Headline:** LPP's headline is v1 (full year). `lpp/v2` is marked `same_sessions.proof_set` and only feeds the proof-set line.
6. **PRISM ids:** all six `agent_id`s match contract 4, and the metadata keys match contract 5.

## Demo-blocking (sent to the UI lane at 15:38)

| # | Where | What's wrong | Fix |
|---|---|---|---|
| B1 | `web/src/main.js:335` (+`:186`) | On chip **3M** (demo beat 1:00) the meta still says "315 trades", the full-window count. `ranges.3m.by_delay.5.trades` is 44. Crypto Wizard at 3M shows "Not enough trades" beside "122 trades", where the file says 27. | `cut()` returns `trades: fileR?.trades ?? v.s.trades`; line 335 uses `nTrades(k.trades)`. |
| B2 | `web/src/main.js:308` | LPP's "Best mix" card says "Looked good on past months" beside a **No** chip: +1.46% against +9.44% for holding. | Compare with holding: `Beat holding` / `Trailed holding` / `Lost money`. |

## Later: PR #17 (web, owner: UI lane)

1. **Range cut stays full-window in places** (`main.js:240`, `:189-193`). Strategy meta "holding SPY +19.6%" and the strategy rows stay full-window on 3M/6M/1Y. Best stop is computed from the curve when the range isn't "All".
2. **Client-side verdict word** (`main.js:174,186`). When a range has no `ranges` entry (ZipTrader), `wordFor()` recomputes the word with the full-window trade count. That's harmless today, since ZipTrader has 1 trade, but the code is deciding the word instead of the file.
3. **Range persists to a course without `ranges`** (`main.js:330`). The guard needs `!v.r.ranges?.[range]`. Today the result is the same numbers as "All", with the chips hidden.
4. **`keptOf` can override the file** (`main.js:277-285`). Without `kept_reason`, a code threshold can turn the file's `kept: true` into "Not kept". The current file has `kept_reason`, so there's no effect today.
5. **Hardcoded "$10k" / "$10,000" copy** (`index.html:40,85,106,147`; `main.js:90` falls back with `|| 10000`). It matches every file today, but it isn't read from `money_start`.
6. **Assumed PRISM routes** (`main.js:292`, `:295`). The suggestion link falls back to a built `/trajectories/<id>` URL, and "PRISM-traced" shows even with no link. The file has `prism_url`, so there's no effect today.
7. **Root Cause link is the generic `/root-cause` page** (`proofs/prism.json:78`, rendered at `main.js:530`). "See the cluster" opens the landing page. Use the cluster deep link if PRISM has one.
8. **Sample fallback still bundled** (`web/src/data.js:26-27`). If LPP's file ever failed the schema check, sample numbers would show, and the onboarding cards and proof sheet carry no pill. Drop the fallback for production.
9. **Nearest-delay snap** (`main.js:73-78`). A missing delay key silently shows another delay's numbers under "entered N min late". All files have all 7 delays today.
10. **Crash on missing optional keys** (`main.js:230,310,313,505,554`). `month()` / `longDay()` throw `RangeError` on a missing date, and so do `m.ids` and `p.label`. Guard with `if (!d) return ''` and `|| []`.
11. **Onboarding "run" is theatre** (`index.html:82-87`, `main.js:654-663`). The steps animate as if computing live, but the results were computed earlier. Consider wording such as "Loaded: …".
12. **Accessibility at 390px** (`ui.css`). Tap targets are under 44px: avatar 30, pill 30, delay chips 34, `.d-stops` 28. Text is 10-11px in `.sec` / `.meta`, and `--ink3` #8a8882 on `--card` #232222 is about 4.5:1, which is borderline for that size.
13. **KB hit snippets show internal notes** (`main.js:500,519-523`). 2 of LPP's 3 hits render doc headers such as "_Copy assigned to daytrader-verdict-v2._ … 1196 need review". Strip the heading line, or prefer card hits.
14. **No Google sign-in on the live app** (`auth.js:7,14-18`; `deploy-vercel.sh:8,13`). AGENTS Decision 4 wants Clerk. `~/dev/quant-bot/.env` has no `CLERK_PUBLISHABLE_KEY`, and `--prebuilt` never reads Vercel's env. The 2.9 MB Clerk library still ships, unused. This is known (the lane's note, 15:20).
15. **The Yes headline hides the holding value** (`main.js:197-200`). Crypto Wizard reads "$10k became $9,221. It beat holding Bitcoin.", without Bitcoin's $7,543. CAP-5 wants "Just holding made $Y" on every word.
16. **Fine print and proof word stay full-window on 3M/6M/1Y** (`main.js:336`, `:506`). This is the same family as B1.
17. **Bot suggests / Best mix ignore the delay chips** (`main.js:286-316`). They were computed at `delay_min: 5` but show unchanged and unlabelled from 1m to 60m. Label them "at 5 min".
18. **The Crypto Wizard and ZipTrader proof sheets say "pending in PRISM"** (`main.js:114`). `proofFor` is LPP-only, but `knowledge_base.v1_run_per_course` has run links for both.
19. **The trade chart never has minute bars** (`tradeChart.js:56,78`). No trade has `bars`, so CAP-7's chart is a line through the entry prices. At 1m, "Posted" and "In" sit on the same point.
20. **A saved delay overrides "opens at 5"** (`main.js:71`). The demo browser should start in a fresh profile or use `?still=1`.
21. **Keyboard** (`main.js:735-742`). Left and right arrows switch course even while focus is on a chip. The course tabs lack `aria-controls`.

## Later: PR #15 (PRISM, owner: PRISM lane)

1. **Two failed-run counts, unlabelled** (`proofs/prism.json:73` vs `:97-100`). Root Cause says 25 (PRISM's cluster) and Evaluator says 29 of 30 (code checks). The script explains this, but the fields should say what they count. In the UI, `main.js:529` could read "25 runs in PRISM's cluster".
2. **29 vs 30 denominators** (`app/prism/evaluators.py:103`; `proofs.py:113-116`). The mirror scores the 29 sessions both versions extracted, which drops `xW7zeI3tVFA`, v1's only success. `failed_runs.of` counts v1 traces only (30). `proofs/README.md:44-45` tells Luis to score 30 in PRISM, so PRISM's score and the mirror won't share inputs.
3. **PRISM's evaluator score and links are null, yet `proofs check` passes** (`proofs/prism.json:86,90,113,121,125,132`; `proofs.py:213-217`). Track proof 3 still depends on the PRISM UI. `check()` should flag null `pass_pct` / `url`.
4. **The verdict evaluator's 0% → 100% is mostly a prompt artifact** (`app/prism/verdict.py:84-86,95,165-168`). v1's prompt never asks for "Not advice", but `check_language` fails v1 without it. 3 of the 4 v1 runs pass `check_numbers` and fail only on that phrase. Don't quote this score. Give both versions the same instruction, or score without `check_language`.
5. **`check_numbers` is too loose** (`verdict.py:120,131`). It uses `abs()` on both sides, so +2.34% passes when the result is −2.34%. The allowed set is every number in the whole results JSON (dates, delays, trade prices). Compare signed values against the headline numbers only.
6. **Stale verdict runs** (`proofs.py:43-51`). `latest_runs()` never compares a row's `results_sha` with the current results `git_sha`: the runs are on 8fd8d78 / 5cd9d36, while the results are now a65b16a / 25e5847.
7. **Hardcoded framing** (`proofs.py:141-142`). The "fewer failed runs, within a few dollars" sentence is a literal string, not derived from `failed_runs` and `money_same_sessions`. It's true today.
8. **`conversation_id` drifts from contract 5** (`verdict.py:171`). The id appends the results sha (`verdict-lpp-v1-8fd8d78`). Extract traces use `lpp-<vid>-lpp-v1`. Update the contract or move the sha into metadata.
9. **Verdict runs have 7 steps, not the specified 5** (`verdict.py:7,189-197`). The added steps are `check_cites` and `check_language`, with no spec change-log entry. That's fine for the bonus "6+ tool steps", but record it.
10. **Extraction re-traced; failures only in metadata** (`extract_traces.py:1-9,58,82-83`). The story said not to re-trace. `trace_llm` sets no `final_status="error"`, so PRISM sees the failures only through its detectors.
11. **PRISM spend not logged** (`proofs/README.md:20`, `prism.json:160`). Root Cause "Analyze now" cost 5 credits, but the log shows 0 and `credits.jsonl` is missing.
12. **Our Root Cause sentence restates our checks, not PRISM's cause** (`prism.json:76-77`). PRISM names `failed_tool_call` and `unsupported_answer`. Our sentence names quote length and open positions. Tie the two together in one clause.
13. **KB top hit is our card's text, not PRISM's snippet** (`proofs.py:72-75`; `kb.py:92`). Card ids are positional, so a kb rebuild could show a rule the run never retrieved.
14. **Crash paths in offline scripts** (`extract_traces.py:44,59,80`; `evaluators.py:94,99`; `common.py:57`). Possible crashes: `review_reasons` is None, zero records, `proof_set.json` missing, a `source_id` with no colon, a blank JSONL line.
15. **PR description said "Draft: spec only so far"** but the PR shipped code and generated proofs. That's why it merged without a review.
