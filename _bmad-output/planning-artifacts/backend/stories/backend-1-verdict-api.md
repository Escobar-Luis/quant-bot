---
title: 'story/backend-1-verdict-api: serve verdicts from a snapshot folder'
type: 'feature'
created: '2026-10-17'
status: 'done'
route: 'oneshot'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/planning-artifacts/backend/architecture.md'
  - '{project-root}/_bmad-output/planning-artifacts/spec-day-trader-ai/contracts.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The verdicts only exist as JSON bundled into the static web app; nothing can serve them to another client, and every later backend story (runs, picks, traces, nightly) needs an API to grow from.

**Approach:** A FastAPI app in `app/api/` that loads one snapshot folder (default: the repo's `results/`, overridable with `SNAPSHOT_DIR`) at startup and serves, read-only and with no network or auth:

1. `GET /health` → `{ok, snapshot_id, courses}`.
2. `GET /v1/courses` → each course's headline file (AD-3 rule) and its headline at the default delay.
3. `GET /v1/courses/{course}/verdict?delay=<min>` → word, end, return, just-holding end and return, trades, window, hold, unknown; delay defaults to the file's `default_delay_min` and must be one of its `delays_min`.
4. `GET /v1/courses/{course}/results/{version}` → the results/1 file as is.

Every response carries `snapshot_id` (AD-1: 12 hex of sha256 over sorted `path:sha256` lines). Errors use the convention envelope.

## Acceptance

1. Every number `/verdict` returns equals the headline file's `portfolios[all].by_delay[delay]` (tested against the real `results/`).
2. LPP's headline is `v1` (v2 is the proof set); an unknown course is 404 `unknown_course`; a delay outside `delays_min` is 422 `delay_not_precomputed`; an unknown version is 404 `unknown_version`.
3. `snapshot_id` is the same for the same files and changes when a file changes.
4. `pytest app/api` passes offline; `uvicorn api.main:app` starts locally; main's `web/`, `results/` and `proofs/` are untouched.

</frozen-after-approval>

## Implementation Notes

- Built `app/api/` (`snapshot.py`: load, contract checks, AD-1 id, AD-3 headline rule; `main.py`: four routes, error envelope, `X-Snapshot-Id` header, one JSON log line per request) and `app/api/tests/test_api.py` (44 tests, offline). Run with `uvicorn --factory api.main:create_app --no-access-log` (no app is built at import).
- Dependencies in their own commit (shared `pyproject.toml`): `fastapi` 0.143.3, `uvicorn` 0.54.0; dev group `pytest` 9.1.1, `httpx` 0.28.1. This also declares pytest and httpx, which `deferred-work.md` asked for.
- The snapshot id hashes every `.json`/`.jsonl` file (no dotfiles) under the snapshot's `results/`, `positions/` and `bars/`, served or skipped, `_sample.json` included, as paths relative to the snapshot folder; the default root (the repo) isn't hashed whole. Each file is read once, so the hashed bytes are the served bytes. `results/_sample.json` is never served.
- Files that break what the API relies on (schema, course/version vs path, whole-minute delays, the six headline numbers at every delay, NaN, privacy) are skipped and listed in `/health.skipped`; a course with any skipped file is withheld whole, so the API can't headline an older file than the web app's `latest()`.
- Privacy (main's #43–#45): a file holding a `yt:` video ID or a YouTube link is never served. The pattern copies `backtest.common.PRIVATE_URL` (a test keeps them equal) instead of importing it, because `backtest.common` runs git and loads `.env` on import.
- Rebased on main after #43–#46 (session keys replaced video IDs in `results/`).
- Aligned with the spine after its review gate (spine v2): the query parameter is `delay_min` (the intent above says `delay`), `/verdict` returns the `verdict/1` shape (`at` = the file's `by_delay` entry verbatim, plus `series`, `rules`, `start`/`end`, `source: "snapshot"`, `run_key: null`, `engine_version: null` until manifests exist), and the hashed folders are `results/`, `positions/` and `bars/`.
- The results endpoint returns the file's bytes unchanged; the snapshot id rides in the `X-Snapshot-Id` header there, so the contract document isn't altered.
- Smoke after the rebase (before the code-review patches): `uvicorn` served `/health` (snapshot `646c7375ef10`, three courses, none skipped, `HEAD` 200) and LPP at 15 min (v1, "No", $9,729.38).

## Review Triage Log

Blind Hunter, 15 findings (14 verified, 1 not a defect):
1. Branch behind main, results still held video IDs: high, patched (rebased on #43–#46).
2. No privacy guard on a public read surface: medium, patched (files with `yt:` IDs or YouTube links are skipped; test).
3. Malformed fields crash startup or 500 (`portfolios: ["x"]`, `same_sessions` list, `default_delay_min: true`): medium, patched (type checks, errors caught as a skip reason; tests).
4. Delay rows checked for presence, not content: medium, patched (six required keys per row; test).
5. 500s lacked `X-Snapshot-Id` and a JSON line; startup warnings weren't JSON: low, patched (envelope stamps the header, 500 handler logs one JSON line with the traceback inside; test).
6. API could headline an older version than the web when the newest is skipped: medium, patched (course withheld whole; test).
7. `/health` said ok on an empty or mistyped snapshot: medium, patched (`ok` false with no course; missing `results/` refuses to start; tests).
8. Snapshot id departed from AD-1 and ignored skipped files: medium, patched (every file under the data folders; known-answer test). AD-1 in the spine says the same.
9. Docs link to `architecture.md`, which lives on the architecture branch: low, deferred to merge order (that PR merges first).
10. AGENTS.md "who writes where" lacks `app/api/`: low, deferred (AGENTS.md edits go in the architecture PR).
11. Story status still `ready-for-dev`: false as a defect (the workflow sets `done` at finalize; done now).
12. Brand-new dependency versions (fastapi 0.143.3, one day old) and API deps installed for every package: low, deferred (supply-chain cooldown is a repo-wide `exclude-newer` call).
13. Acceptance test picked its expected file with the code under test: medium, patched (the rule is written out again in the test).
14. No `ETag`/`Cache-Control`, `HEAD /health` 405: low; HEAD patched, caching headers deferred to backend-2 (deploy).
15. `v01.json` and `v1.json` both accepted: low, patched (`v[1-9]\d*`; test).

### Review Findings (bmad-code-review on PR #47, 2026-10-17)

Layers: Blind Hunter, Edge Case Hunter, Verification Gap, Acceptance Auditor (all reported). 0 decision-needed, 17 patched, 4 deferred, 6 rejected.

Patched:
1. Story note on the snapshot id contradicted the code: low (note fixed above).
2. Stray files (`.DS_Store`, swap files) changed the id across machines: medium (only `.json`/`.jsonl`, no dotfiles; test).
3. Privacy scan missed escaped (`youtu\u002ebe`), mixed-case and non-UTF-8 links: medium (scans decoded raw text and the parsed text, case-insensitive; tests). Bare IDs stay a documented server limit.
4. Building the app at import broke test collection with a bad `SNAPSHOT_DIR`: low (`--factory`, no module-level app).
5. Hash and served bytes came from two reads: low (one read).
6. A 500 still produced uvicorn's multi-line traceback, and the access log doubled every line: low (middleware turns errors into the envelope; `--no-access-log` documented; the 500 test now runs with server exceptions raised).
7. `deferred-work.md` lacked two items: low (added).
8. A `NaN` in a file passed the checks, then 500'd `/v1/courses` for every course: medium (non-finite numbers refused at parse; test).
9. A badly named file (`v02.json`) didn't withhold its course, so the API could headline v1 while the web headlines it: low (any skipped file withholds the course; test).
10. `same_sessions: null` skipped a valid file: low (treated as absent; test).
11. 405 lost its `Allow` header: low (kept; test).
12. `/health` answered 200 with no course: low (503; test).
13. Request log dropped the query string: low (logged).
14. Acceptance 1 could pass with no files: low (module-level assert).
15. The id wasn't checked end to end through `load()`: medium, verification gap (known-answer test with two courses, an events file and ignored stray files).
16. Course/version mismatch, default delay outside `delays_min`, and bad JSON had no skip tests: medium, verification gap (three cases added).
17. `httpx < 1` from the spine's Stack wasn't encoded; unknown course on the results route untested: low (`httpx>=0.28.1,<1`; test).

Deferred (in `deferred-work.md`): the architecture PR must merge first (links and AGENTS.md "who writes where"); typed response models and the API shapes in `contracts.md`; CORS (backend-2, with the origins list); API dependencies in their own group.

Rejected: HEAD on every route (only `/health` is probed; adds surface); a directory or dangling symlink named `v2.json` crashing startup (fails loudly on a state nothing produces); AC1 naming `portfolios[all]` while the code follows `headline_portfolio` (every file says `all`; the fix would edit the spec); the parity test's name (renamed, not a defect); UTF-16 files (covered by the decoded-text scan); triage wording on HEAD (clarified: `/health` only).
