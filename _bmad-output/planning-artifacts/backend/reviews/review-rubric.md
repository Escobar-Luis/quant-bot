# Rubric review: Day Trader AI backend spine

- **Spine:** `_bmad-output/planning-artifacts/backend/architecture.md` (draft, 2026-10-17), with `.memlog.md`, `research.md`, `stories.yaml`.
- **Checked against:** `main` at `0199dbf` (includes PRs #43–#46), this spike's base `3362e61`, story 1's code at `quant-bot.worktrees/backend-1-verdict-api` (`5901a4d`), `data/` on Luis's Mac (field names only), PyPI on 2026-10-17.
- **Verdict:** **Revise before backend-3.** The paradigm, stack and story 1 hold up. Three blockers remain: what a snapshot's `events/` contain, engine and bar identity, and the PRISM trace budget. The AGENTS.md amendments and the operational envelope are also unplanned.

## Scorecard

| # | Checklist item | Result | Why |
|---|---|---|---|
| 1 | Fixes the real divergence points for the 8 stories, misses none | Partial | Missing: snapshot event shape (3↔6), `engine_version` (3↔6), run response shape (3↔8), allowed-origins list (2↔4↔8), nightly extraction version and window (1↔7) |
| 2 | Every AD's Rule is enforceable and prevents its divergence | Partial | AD-3 can't prevent engine drift without a version check. AD-6's timeout can't be enforced on threads. AD-13's per-IP limit fails behind a proxy. AD-1's id formula is computed twice with no shared code |
| 3 | Nothing in Deferred lets two units diverge | Mostly pass | "Backups" belongs in Open Questions, since `data/` can't be replaced. Everything else is safe to defer |
| 4 | Named tech is verified-current | **Pass** | All 8 PyPI versions match today: fastapi 0.143.3, uvicorn 0.54.0, httpx 0.28.1, pytest 9.1.1, clerk-backend-api 7.0.0, surrealdb 2.0.0, prismtrace-sdk 0.5.3, openai 3.33.0 |
| 5 | Ratifies, not contradicts, the codebase and contracts | **Fail** | Misses the no-video-ID rule (PRs #43–#45). Conflicts with contract 5 and the SPEC's PRISM budget, with Decision 3 and the browser-stored picks, and with rule 6 for LPP. Calls `app/lpp` "existing", but it's PR #18 and still open |
| 6 | Covers the spec's CAPs and B1–B7 | Pass with gaps | Every item is mapped. B3 has no window or sealed-holdout policy. B4's picks contradict the spec |
| 7 | Operational envelope decided, deferred or open | Partial | Has environments, host (open) and bucket (pushed to a story). Missing: rollback, alerting, a secrets list, cache eviction, bucket retention, proxy IPs, a reproducible build |

## Findings (most severe first)

### F1 Blocker: snapshot `events/` would leak private video IDs, and the server can't rebuild what was priced (AD-1, AD-11)
- **Evidence:**
  1. Rows in `data/lpp/events.jsonl` carry `source_id: "yt:<11-char id>"` and `event_id: "lpp:<id>:NNN"`.
  2. Main now forbids these IDs in any public file: `public_json` in `app/backtest/common.py`, and `scrub`/`leaks` in `app/prism/common.py` (PRs #43–#45).
  3. Story 1 already copies that guard (`PRIVATE_URL` in `app/api/snapshot.py`), but the spine never inherits the rule.
  4. AD-11's validator relies on a "derived-event allowlist" that is never defined.
  5. To rebuild LPP v2 positions you need `data/lpp/gold/proof_set.json`, and main's `lpp.build` maps IDs through the private `data/lpp/session_keys.json`. Neither file is in a snapshot.
- **Effect:** backend-6 publishes IDs to the bucket. Or backend-3 builds different positions than the file priced, which fails its own acceptance ("a run at a precomputed delay equals the snapshot numbers").
- **Fix:**
  1. Add an Inherited row: "No unlisted video IDs or YouTube links in any file that leaves `data/` (PRs #43–#45)."
  2. AD-1: `events/<course>/<version>.jsonl` holds exactly the events `mod.build` used for that results file: filtered to the proof set, session keys applied, `event_id`s rewritten.
  3. Pin the field list to what `mod.build` reads.
  4. AD-11's validator runs the `PRIVATE_URL` and `private_video_ids()` check on every snapshot file and every PRISM payload.

### F2 Blocker: engine and bar identity are not pinned, so AD-3's drift is not prevented (AD-3, AD-4, AD-5)
- **Evidence:**
  1. `engine_version` appears nowhere in the code (`git grep` on main: 0 hits). backend-3 (the cache key) and backend-6 (the manifest) will each invent their own.
  2. Nothing requires the API's engine to equal the snapshot's. A container built at another sha computes custom delays with different math than the precomputed delays shown beside them.
  3. Bars sit outside the manifest and outside `snapshot_id`. `bars.py` caches whatever it fetched under a per-day key, which a later upload can overwrite.
  4. Daily closes are cached as `daily/<SYM>_<start>_<end>.json`, so a custom `start`/`end` misses that cache. In offline mode `hold_numbers` then raises `NoBars`; it doesn't price as `no_bars`.
  5. `app/backtest/common.py` runs `git rev-parse` and `load_dotenv` at import. Without git in the image, that raises `FileNotFoundError`. Story 1 avoids importing it for this reason.
- **Fix:**
  1. Define `engine_version` once, as sha256 of the sorted `app/backtest/*.py` sources (one function).
  2. The manifest records it. The API serves on-demand runs only when its own `engine_version` matches; otherwise it returns 409 `engine_mismatch` and serves precomputed delays only.
  3. The manifest lists every bar file with its sha256, and those hashes feed `snapshot_id`.
  4. Ranges slice the window's daily series; they never call `daily_closes` with new bounds.
  5. `app/backtest` has no import-time side effects. It takes the bar root and an offline flag as parameters.

### F3 Blocker: AD-9 and AD-13 spend the whole PRISM budget in a day (AD-9, AD-13, contract 5)
- **Evidence:**
  1. The SPEC caps PRISM at 200 credits total, tracing only the 30-session proof set and verdict runs. AGENTS contract 5 says the same.
  2. AD-9 traces every cache miss. AD-13's `RUNS_PER_DAY` defaults to 200 and "also caps PRISM traces", which uses the whole budget in one day.
  3. backend-5's AGENTS.md PR covers contract 4 only. Contract 5's trace scope and its `conversation_id` formats would change silently.
- **Fix:**
  1. Add a separate `TRACES_PER_DAY` (small, for example 20). Past it, count runs locally and skip the trace.
  2. The AGENTS.md PR amends contracts 4 and 5 together.
  3. Add an open question: the PRISM plan and credits after the hackathon, next to the Nicrron one.

### F4 Major: the AGENTS.md amendments aren't planned as one unit (ratification)
- These changes need an AGENTS.md PR first, per its own header, and no story owns them:
  1. **Contract 1:** results are "written only by story/1", but now the pipeline writes them into snapshots.
  2. **Contract 6:** who writes where now includes `app/api/`, `app/pipeline/`, `snapshots/` and the bucket.
  3. **Contract 5:** see F3.
  4. **Decision 3 and the SPEC non-goal:** "no per-user data on a server". The spec's `architecture.md` keeps picks in browser storage, and main's `web/src/main.js` stores them in `localStorage` (`dta-picks`) today. AD-8 moves them into Clerk. Open question 3 offers only "Clerk or our table" and leaves out the status quo.
  5. **Decision 4:** hosting moves from Ninoo/Vercel to Railway.
  6. **Decision 5:** JSONL stays only on the Mac; snapshots move derived events into a bucket.
- **Fix:**
  1. Add a story, **backend-0: AGENTS.md amendments**, as the first PR, with one Inherited-table row per change.
  2. Rewrite open question 3 with three options: browser storage (status quo, no backend), Clerk `publicMetadata`, or our own table.

### F5 Major: the nightly refresh breaks rule 6 for LPP and has no window policy (AD-11, B3)
- **Evidence:**
  1. The LPP collector (`app/lpp/`, PR #18, open, not on main) finds sessions in `data/discord/youtube_links.jsonl`, which comes from Discord. So "LPP from YouTube automatically" is an unattended Discord read.
  2. Windows are constants: `lpp.WINDOW` ends 2025-09-12 with sealed 2025-06-12; `cryptowizard.WINDOW` ends 2026-10-16. New sessions fall outside the window and drop silently. Moving the window rolls `sealed_from` (contract rule 10, AGENTS rule 4) and turns sealed months into dev months for the improver.
  3. Which extraction version runs nightly is undecided. Running v2 on all sessions clears `same_sessions.proof_set` and flips the AD-3 headline from v1 to v2 on its own.
  4. Tracing for nightly extraction is undecided: rule 1 says trace every run, contract 5 says trace only the proof set, and no `agent_id` is named.
- **Fix:**
  1. AD-11: the nightly LPP stage processes only links a supervised read already added.
  2. Add an AD for windows: the end advances, `sealed_from` stays fixed per course until Luis re-seals, and the improver never re-picks on formerly sealed months.
  3. Pin the nightly extraction version and its trace policy.
  4. Make PR #18's merge a prerequisite of backend-7.

### F6 Major: API shapes are undefined between backend-1/3 and backend-8 (conventions, AD-4)
- **Evidence:**
  1. The verdict shape exists only in story 1's `headline_view`.
  2. The `/v1/runs` response is undefined. AD-3 says "results/1 structure", but RunSpec also takes a `portfolio`.
  3. Canonical RunSpec JSON doesn't say whether defaults are filled before hashing. `{}` and `{start: window.start}` would get different keys and miss the precomputed check.
  4. Story 1 carries `snapshot_id` in the `X-Snapshot-Id` header on raw results, but the convention says "every response carries" it, without saying where.
  5. The token transport is unstated. Clerk SDK issue #243 is about parsing the `Authorization` header.
- **Fix:**
  1. Commit FastAPI's OpenAPI file as the contract backend-8 builds against.
  2. A run response is a results/1 subset: `delays_min: [d]`, `portfolios[*].by_delay[str(d)]` and `series.by_delay[str(d)]`, the trades sample, `unknown`, `snapshot_id` and `run_key`. No `strategies`, `combos` or `suggestion` on custom runs.
  3. Hash the normalized spec with all six fields present.
  4. Every response has `X-Snapshot-Id`, and our own JSON bodies carry it too.
  5. The token goes in `Authorization: Bearer`.

### F7 Major: things two units compute have no single implementation (AD-1, AD-3)
- **Evidence:**
  1. `snapshot_id` is computed by both the pipeline and the API, but the arrow rule stops `app/pipeline` from importing `app/api`.
  2. The joiner, trailing newline and encoding are unstated. Story 1 uses `"\n".join`, no trailing newline, UTF-8 and POSIX paths.
  3. AD-3 puts the headline rule "once in app/api", yet backend-6's "numbers match" check needs it too.
- **Fix:**
  1. Put `snapshot_id()` and `headline()` in one module that both units import (for example `app/snapshot_format/`), and add the arrows.
  2. The API recomputes the id on load and refuses a snapshot whose id differs from its folder name or from `current.json`.

### F8 Major: operational envelope gaps
1. **Rollback:** not stated.
   - Snapshots: point `current.json` back at the previous id, keeping the last N.
   - Code: redeploy the previous image on the host.
   - Name who may do either.
2. **Monitoring:** a failed night keeps the old snapshot live and nobody hears about it.
   - Alert Luis, with a macOS notification or an email.
   - `/health` reports the snapshot's `created_at` and age, trace-queue drops and run-cache size.
3. **Secrets:** no inventory.
   - Server: `CLERK_JWT_KEY` (PEM), `CLERK_SECRET_KEY` (AD-8's picks writes need it, so "networkless" covers verification only), `PRISMTRACE_API_KEY` and `PRISMTRACE_PROJECT_ID`, `USER_HASH_SALT`, bucket read key.
   - Mac: bucket write key.
   - Rule: the server holds no Nicrron or Alpaca key, and startup refuses to run if one is set. That enforces AD-5 and AD-10.
4. **Per-IP limits (AD-13):** uvicorn trusts forwarded headers only from 127.0.0.1 by default, so every caller behind the host's proxy shares one bucket. Set `FORWARDED_ALLOW_IPS` for the proxy.
5. **Origins:**
   - CORS and Clerk `authorized_parties` read one `ALLOWED_ORIGINS` list.
   - Vercel preview URLs change on every deploy, so pin a stable preview alias.
6. **Storage growth:**
   - AD-4's run cache is never invalidated, on a 5 GB volume. Evict runs whose `snapshot_id` is neither current nor previous.
   - Keep only the last N snapshots in the bucket.
7. **Clerk instance:** the preview shares the live demo's Clerk development instance. AD-8's custom session claim and new origins change the instance judges use, which is an AD-12 risk. Use a second dev instance for preview, or declare the change additive and re-run the demo flow test.
8. **Reproducible build:** the container runs `uv sync --frozen` from `app/uv.lock`. `pyproject` uses `>=`, and the research says to pin prismtrace exactly.
9. **Schedule:** the launchd run time is unset. Run it after 20:00 ET, when the UTC crypto day has closed, and handle a Mac that was asleep.
10. **Backups:** `data/` is the one store that can't be replaced: raw content, the session-key map, the ledger and the gold proof set. Move it from Deferred to Open Questions.

### F9 Minor: AD-6's timeout can't be enforced as written
A Python thread can't be stopped. A CPU-bound run past 10 s keeps its slot, and everyone else gets 429. **Fix:** use a process pool that kills and respawns a worker on timeout, or reword the rule: "504 `run_timeout`; the slot frees when the run ends."

### F10 Minor: AD-8 picks go stale after a write
Picks are read from the session claim, which stays stale until the token refreshes (about 60 s). Onboarding saves, then the tabs show the old picks. **Fix:**
1. `PUT` returns the new picks.
2. The client refreshes its token with `getToken({ skipCache: true })`.
3. Reads drop course ids that aren't in the current snapshot.
4. List Clerk's session-token template edit as a Luis step in backend-4.

### F11 Minor: AD-12's wording blocks a safe merge
"Lives on its own branch" reads as never merging. `deploy-vercel.sh` reaches production only with `--prod`. **Fix:** backend-8 may merge once a build without `VITE_API_URL` behaves exactly like main (story 5's flow test passes). Its scripts never pass `--prod`.

### F12 Minor: `stories.yaml` has `governed_by` gaps and no dependencies
1. backend-2 lacks AD-7 (origins) and the secrets convention.
2. backend-3 lacks AD-1 (events).
3. backend-6 lacks AD-3 and AD-12.
4. backend-7 lacks AD-1, AD-9 and AD-12.
5. backend-8 lacks AD-4 and the conventions.
6. No `depends_on`: backend-5 needs 3 and 4; backend-7 needs PR #18 and 6; backend-8 needs 2, 3 and 4.

### F13 Minor: housekeeping
1. The `learn.md` companion is listed but doesn't exist, and `stories/` is empty.
2. The spike is based on `3362e61`, but main is at `0199dbf`. Rebase before the PR.
3. The Stack table lists httpx as "tests" only, but `backtest/bars.py` imports it at runtime (it arrives through openai).
4. A hosted read model (AD-2) would break the SPEC non-goal "any cloud database". Say so in open question 2.

## What holds up
1. Snapshot serving fits a team whose data is on one Mac and whose demo is frozen. Going live by flipping one pointer is simple and rolls back cheaply.
2. AD-4's content-addressed cache, AD-5's offline request path and AD-10's rule of no model call per request all prevent real drift and cost risks.
3. AD-12 protects the judged demo without blocking backend work.
4. Story 1 matches the spine: the AD-1 id formula, the AD-3 headline rule (same as `web/src/data.js` `latest()`) and the error envelope. It goes further with the privacy guard and `X-Snapshot-Id`, which the spine should adopt.
5. Every stack version is current on PyPI. `research.md` cites a live source for each library.

## Coverage

| Item | Mapped | Gap |
|---|---|---|
| B1 verdicts | AD-1, AD-3 | Response shape (F6) |
| B2 on-demand runs | AD-3 to AD-6 | Engine and bar identity (F2), events (F1), timeout (F9) |
| B3 nightly | AD-10, AD-11 | Window and sealed policy, rule 6, extraction version (F5); alerting (F8) |
| B4 sign-in and picks | AD-7, AD-8 | Contradicts Decision 3 (F4); staleness (F10); origins (F8) |
| B5 traces | AD-9 | Budget and contract 5 (F3) |
| B6 cost and limits | AD-4, AD-10, AD-13 | Proxy IPs, eviction (F8) |
| B7 hosting | Seed, open question 1 | Rollback, secrets, build (F8) |
| CAP-1 to 8, 10, 11 | Map table | CAP-7 bars deferred on market-data terms (fine) |
| CAP-9, CAP-12 | Pipeline only | Need the window policy (F5) |
