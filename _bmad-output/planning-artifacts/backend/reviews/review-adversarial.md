---
review: adversarial
target: ../architecture.md (spine, draft 2026-10-17) + ../stories.yaml
method: pick two stories built by different agents, have each obey every AD to the letter, find where they still clash
evidence: app/backtest/*.py, web/src/{data,main}.js, results/*, data/bars/ (counts only), contracts.md, AGENTS.md
date: 2026-10-17
---

# Adversarial review: backend spine

## Verdict

**Not build-ready.** 12 pairs of stories can each follow every AD and still build pieces that don't fit. Four of them would make the server's numbers disagree with the nightly numbers on day one:

- H1: engine input
- H2: bar store
- H3: headline version
- H5: ids and hashes

The paradigm is fine (snapshot serving, one engine, content-addressed runs). The holes are in what a snapshot contains and in which module owns each formula.

## Summary

| # | Pair (agent A × agent B) | Clash kind | Severity | AD to change |
|---|---|---|---|---|
| H1 | backend-6 × backend-3 | shared-data shape: what the engine reads on the server | Blocker | add AD-14 |
| H2 | backend-6 × backend-3 | shared-data shape + state mutation: bar store | Blocker | tighten AD-5 |
| H3 | backend-7 × backend-1 (+ backend-8) | headline rule, version ownership | Blocker | tighten AD-3 |
| H4 | backend-3 × backend-8 | range and word rules | Major | tighten AD-4, AD-3 |
| H5 | backend-1 × backend-6, backend-3 × backend-5/6 | id and hash formulas (snapshot_id, engine_version, run key) | Blocker | add AD-15 |
| H6 | backend-6 × backend-3 | state mutation: hot-swap during a run | Major | add AD-16 |
| H7 | backend-4 × backend-5 (+ backend-3) | two owners of one counter | Medium | tighten AD-13 |
| H8 | backend-4 × backend-8 | conflicting write and read paths for picks | Medium | tighten AD-8 |
| H9 | backend-5 × backend-7, backend-3 × backend-5 | trace shape, proof agent_ids | Major | tighten AD-9 |
| H10 | backend-1 × backend-3 (→ backend-8) | response shape | Medium | conventions + AD-3 |
| H11 | backend-7 × backend-3, backend-2 × backend-3 | two writers of git `results/`; import side effects | Major | tighten AD-3, AD-12 |
| H12 | backend-7 × backend-3 | two owners of `window`; snapshot churn | Medium | add AD-17 |

---

## H1 — The server can't rebuild the engine's input (backend-6 × backend-3)

**backend-6 builds this, legally.**

1. It writes `events/<course>/<version>.jsonl`, exactly as AD-1 names it.
2. It keeps the fields on its own allowlist. AD-11 says the validator enforces "no field outside the derived-event allowlist", but the spine never lists those fields.
3. It caps every `quote` at 12 words, as AD-11 requires.

**backend-3 builds this, legally.** On the server it builds positions the only way the engine can, with `mod.build(version)`, pointing `DATA_DIR` at the snapshot.

**What breaks.**

1. **Paths don't match.** No course module reads `events/<course>/<version>.jsonl`.
   - `cryptowizard.build` reads `cryptowizard/events.calls.jsonl` and `events.rules.jsonl`, and ignores `version` (cryptowizard.py:48).
   - `ziptrader.build` reads `ziptrader/events.jsonl`, also ignoring `version`.
   - `lpp.build` reads `lpp/events.jsonl` (v1) or `lpp/v2/events.jsonl`.
2. **Fields the engine needs aren't on any list.**
   - LPP needs `status` and `fail`: ledger-failed events are kept (lpp.py:54).
   - LPP needs `instrument` for the options split (lpp.py:58), plus `wall_utc`, `qty`, `why`, `session_date` and `t_s`.
   - Crypto Wizard needs `links_to`, `extra.close_pcts`, `extra.side_inferred`, `targets`, `stop` and `pair`.
3. **ZipTrader reads the full quote.** It classifies swing trades from the uncapped quote text (ziptrader.py:41). A 12-word cap can turn a swing trade into a day trade. Today only one call is marked swing, and its phrase survives the cap by luck.
4. **LPP v2 needs a file no snapshot carries.** It reads `data/lpp/gold/proof_set.json` (lpp.py:36).
5. **The acceptance test can't catch this.** backend-3's test ("a run at a precomputed delay equals the snapshot numbers") runs on Luis's Mac against `data/`, so it passes there. On the host it either crashes or quietly prices a different set of positions.

**Fix: add AD-14.**

> **AD-14 — The engine's input is published, not rebuilt.** The pipeline runs `mod.build`, de-duplicates `pid`s (the loop now in `backtest.run.main`, moved to `app/backtest/positions.py:build_positions(course, version)`), and writes the result with `positions.py:dump` to `positions/<course>/<version>.jsonl`: one `Position` per line, `Position` and `Leg` dataclass fields only, `quote` ≤ 12 words. The API builds nothing. It loads positions only with `positions.py:load`. It never calls a course module's `build`, `load`, `proof_set` or `unknown`, and never reads `events/`. A run's `rules`, `unknown` and `checks` are copied from the snapshot's results file for that course and version. `positions/` is inside the snapshot_id hash. The derived-field allowlist the validator enforces is the `Position`/`Leg` field list. `events/` is optional and for display only.

---

## H2 — The bar store has no defined layout, isn't offline, and can change (backend-6 × backend-3)

**backend-6 builds this, legally.**

1. It uploads bars to `bars/<source>/<sym>/<day>.json`, the layout in `.memlog.md`'s snapshot-transport decision.
2. It puts them outside `snapshots/<id>/`, as the Structural Seed draws `bars/...` beside `snaps`.
3. It re-uploads a day when it re-fetches one.
4. The API syncs the bucket's `bars/` into one local folder.

**backend-3 builds this, legally.** "Bars offline mode" means running the engine with no Alpaca keys, which is the engine's existing no-key path.

**What breaks.**

1. **Layout.** The engine reads `alpaca_1m/<T>/<date>.json`, `binance/<SYM>/1m/<date>.json` and `daily/<SYM>_<start>_<end>.json` (bars.py:72–240).
   - With backend-6's layout, every session prices as `no_bars`.
   - Off-grid delays then all say "Not enough trades", while 1, 3, 5, … show the real word.
   - `data/bars/` already mixes sources: 935 `alpaca_1m` files, 9 `yahoo_1m`, 50 `yf_1d`.
2. **"No keys" isn't offline.** Every one of these paths reaches the network and writes into the server's bar folder (bars.py:100, 130, 162, 240):
   - `stock_day` falls back to Yahoo for sessions up to 28 days old (bars.py:83–85).
   - `crypto_day` calls Binance keyless.
   - `daily_closes` calls Yahoo or Binance.
3. **Hold.** `daily_closes` is cached by the exact `(start, end)` pair (bars.py:217; today `daily/SPY_2024-08-15_2025-09-12.json`).
   - A new window end, or any range, needs a file that doesn't exist.
   - `hold_numbers` then raises and the whole run fails. AD-5 promised only "a missing session ... counted in `unknown`".
4. **Mutable bars.** Bars aren't covered by `snapshot_id`. A re-fetched day changes the numbers behind an unchanged run key, and AD-4's never-invalidated cache keeps serving the old numbers.
5. **Stale memory after a swap.** The `lru_cache` on `stock_day`, `yahoo_day` and `crypto_day` (bars.py:72, 118, 136) keeps the previous snapshot's bars after a hot-swap.

**Fix: tighten AD-5.**

> **AD-5 — The request path prices only the snapshot's own bars.** `snapshots/<id>/bars/` mirrors `data/bars/` byte for byte, in the engine's layout: `alpaca_1m/<TICKER>/<YYYY-MM-DD>.json`, `binance/<SYMBOL>/1m/<YYYY-MM-DD>.json`, `daily/<SYMBOL>_<start>_<end>.json`. Every bar file is listed in the manifest with its sha256 and is inside the snapshot_id hash; the bucket may store each body once under `blobs/<sha256>`. A night that priced any bar from `yahoo_1m/` or `yf_1d/` fails validation. Offline mode is the env var `BARS_OFFLINE=1`, set by `app/api` before importing `backtest`. With it set, every fetch in `bars.py` raises `NoBars("offline")` before any network call, and no function writes a file. A run's hold comes from the snapshot's `series.hold`, never from `daily_closes`. Bar lookups are cached per bars root path, so a swapped snapshot never reads the previous one's bars.

---

## H3 — The headline version is inferred, so the nightly can flip it (backend-7 × backend-1, plus backend-8)

**backend-7 builds this, legally.**

1. It extracts new LPP sessions with the newest prompt (v2, the fix).
2. It prices them with the documented flag `backtest.run --version v2 --all-sessions`.
3. So `same_sessions.proof_set` is `false`.

AD-10 only says the extraction ledger is keyed by `prompt_version`. Nothing says which prompt the nightly uses.

**backend-1 builds this, legally.** It applies AD-3's rule: the headline is the highest version whose `same_sessions.proof_set` is not true.

**What breaks.**

1. **The public verdict flips overnight.** LPP's verdict switches from v1 to v2 on the first night, with no PR and no decision from Luis. backend-1's own acceptance check ("lpp headline is v1") starts failing.
2. **The other legal choice also fails.** If backend-7 prices v2 with the default (proof set only), new sessions never reach the headline, and B3 refreshes nothing for LPP.
3. **backend-8 picks its own version.** It must send `version` in a `RunSpec`.
   - It picks the version with `latest()` over the bundled, frozen files (web/src/data.js:36), so it gets v1.
   - After the flip, the slider at 5 min shows v2 (from `/verdict`) and at 7 min shows a v1 run.
   - AD-3's "implemented once in `app/api`" doesn't stop a client from choosing a version.

**Fix: tighten AD-3.**

> **AD-3 (headline) — The headline is declared, not inferred.** `manifest.json` carries `headline: {"lpp": "v1", "ziptrader": "v1", "cryptowizard": "v1"}`, copied by the pipeline from `app/pipeline/headline.json`, which changes only by a PR Luis merges. The API reads it from the bound snapshot's manifest and nowhere else; `same_sessions.proof_set` is display-only. The nightly extracts and prices new sources only for each course's headline version; a proof-set version (lpp v2) is never re-run by the nightly. `RunSpec.version` is optional and defaults to the headline. Every verdict and run response returns `version`, and a client sends back the version it was given. Versions compare as `int(v[1:])`.

---

## H4 — Three meanings of "range", two word rules (backend-3 × backend-8)

**backend-3 builds this, legally.** For "any range in the window" (B2):

1. It keeps positions whose first entry falls in `[start, end]`.
2. It starts $10k at `start`.
3. It computes hold with `hold_numbers` over `[start, end]`.
   - That needs `daily_closes(start, end)`, which a range never has (H2).
   - When `end` is before `sealed_from`, `next(d for d in dates if d >= window["sealed_from"])` raises `StopIteration` (run.py:46), so the API returns a 500.

**backend-8 builds this, legally.** It keeps the existing 3M / 6M / 1Y chips:

1. The chips read `ranges[...]` from the file. `extras.ranges` keeps trades whose **exit** is on or before `until`, and holds from the window start (extras.py:101).
2. When the file has no `ranges`, they fall back to `cut()` (main.js:176–187), which:
   - truncates the money curve;
   - computes the word in JS (`wordFor`, main.js:174);
   - decides "Not enough trades" from the **whole-window** trade count;
   - doesn't round the gap.

**What breaks.**

1. **One question, three answers.** The same range at the same delay gives:
   - `ranges.3m` from the file (by exit date);
   - a `/v1/runs` result (by entry date);
   - the curve fallback.
2. **The precomputed shortcut doesn't help.** AD-4's shortcut only covers whole-window specs, so nothing reconciles the three.
3. **Word drift.** `engine.word` rounds the gap to 2 decimals (engine.py:256); `wordFor` doesn't.
   - Return −15.47 against hold −17.47: the engine says **Yes**, the web says **Barely**, because −15.47 − (−17.47) = 1.9999999999999982 in floating point.
   - A small grid search found 53 such pairs.

**Fix: tighten AD-4 and AD-3's word clause.**

> **AD-4 (ranges) — A range has one meaning,** implemented once in `app/backtest/ranges.py:range_stats(results, dates, hold_series, start, end)`, which `extras.ranges` also calls. Price the whole-window positions unchanged. Keep those whose first entry session ≥ `start` and last exit session ≤ `end`. Size them with `fit_to_cash` from $10,000. Just holding is `hold_series[end_idx] / base − 1`, where `base` is 10,000 when `start` = `window.start`, else `hold_series[start_idx − 1]`. `start` and `end` must be dates in `series.dates`. `sealed` covers kept trades with entry ≥ `sealed_from`, and is `null` when `end` < `sealed_from`. The word is `engine.word` on the rounded numbers the response shows. Clients never compute a range, a return or a word: on the API branch, the web's `cut()` curve fallback and `wordFor` are removed.

If arbitrary starts aren't needed yet, a safer first cut is: "`start` must equal `window.start`; arbitrary start is deferred." That matches today's chips exactly.

---

## H5 — `snapshot_id`, `engine_version` and the run key are under-specified (backend-1 × backend-6, backend-3 × backend-5, backend-3 × backend-6)

### 5a. `snapshot_id` (backend-1 × backend-6)

1. **Different files get hashed.**
   - backend-1 hashes the frozen `results/` folder, which holds `results/_sample.json`; AD-1 says "every file under `results/`".
   - backend-6 builds from `results/<course>/<version>.json` only.
   - Same data, different id.
2. **The formula leaves details open.** Line separator, trailing newline, path form (`results/…` or `./results/…`) and hex case aren't specified.
3. **Two copies are forced.** AD-1 says "the pipeline and the API compute it with this one formula", but the import arrows forbid `app/api` from importing `app/pipeline`. Each side writes its own copy.

### 5b. `engine_version` (backend-3 × backend-6)

1. **Nobody defines it.**
   - backend-6 writes the manifest's `engine_version` as the Mac checkout's git sha.
   - backend-3 keys runs with the server image's sha, or a constant.
2. **One slider can mix two engines.** AD-4 answers precomputed delays from the snapshot (the Mac's engine) and every other delay with the server's engine. When the two differ, nothing detects it.

### 5c. Run key (backend-3 × backend-5)

1. **The canonical form is ambiguous.** "sha256 of the canonical JSON of the spec plus `snapshot_id` plus `engine_version`" could mean:
   - JSON concatenated with the other two strings, or one merged object;
   - defaults filled in, or left out (an omitted `start` and an explicit window start then give two keys, and the precomputed check misses the explicit form);
   - `delay_min` as an int or a string.
2. **The trace may recompute it.** backend-5 needs `key[:12]` for `conversation_id` and the full key as `run_key` in metadata. It runs after the response, from a queue. If it recomputes from the request body, it gets a different key.

**Fix: add AD-15.**

> **AD-15 — Ids are computed in one module,** `app/backtest/ids.py`, imported by both pipeline and API; no other module computes them.
> - `snapshot_id(folder)`: take one line `"<relpath>:<sha256 hex lower of the file's bytes>"` for every regular file under `results/`, `positions/`, `events/`, `verdicts/` and `bars/` (POSIX relative path, no `./`; files whose name starts with `_` are never published). Sort the lines by relpath as UTF-8 bytes, join them with `\n` and add a trailing `\n`. The id is the first 12 hex of the sha256 of that text.
> - `ENGINE_VERSION`: the first 12 hex of sha256 over `relpath\0bytes` of every `app/backtest/*.py` except tests, sorted by relpath. The manifest records it. The API computes a run only when its own `ENGINE_VERSION` equals the bound manifest's; otherwise every non-precomputed run answers 503 `engine_mismatch`.
> - `run_key(spec, snapshot_id, engine_version)`: normalize the spec first, so every field is present (`course`; `version` and `portfolio` resolved; `delay_min` an int; `start` and `end` resolved ISO dates). Then take the sha256 hex of `json.dumps({**spec, "snapshot_id": …, "engine_version": …}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()`. The precomputed-spec check runs on the normalized spec. The key travels with the run (cache, response, log line, trace); no unit recomputes it.

---

## H6 — A hot-swap during a run caches a wrong answer forever (backend-6 × backend-3)

**backend-6 builds this, legally.** It adds the pointer poller to `app/api`. On a change, it replaces a module-level `SNAPSHOT` and re-syncs bars into the same local folder.

**backend-3 builds this, legally.**

1. A run reads `SNAPSHOT.positions` at the start.
2. It reads bars while it simulates.
3. At the end it stamps the response and the cache key with `SNAPSHOT.id`.

**What breaks.**

1. **A swap mid-run mixes two snapshots.** Positions come from A, bars partly from B, and the result is cached under B's key. AD-4 never invalidates a cached run, so that wrong entry stays forever.
2. **Errors can be cached too.** AD-6 doesn't say errors are excluded, so backend-3 may legally cache a `run_timeout` and fail that key permanently.

**Fix: add AD-16.**

> **AD-16 — A request binds one snapshot.** `app/api/snapshot.py` alone holds the live reference. Each request takes the reference once at entry: an immutable `Snapshot` (id, manifest, folder). Every read, the run key, the response's `snapshot_id` and the trace use it. A swap works in this order: download every manifest file into `cache/snapshots/<id>/`, check each sha256, recompute `snapshot_id`, and only then replace the reference in one assignment. On any mismatch, it keeps the old snapshot. A snapshot folder is deleted only when it is neither live nor one of the two previous ones. The run cache stores only completed results; a timeout or exception is never cached.

---

## H7 — Two counters for one daily cap (backend-4 × backend-5, plus backend-3)

**backend-4 builds this, legally.** It implements AD-13's buckets at the route. It counts `RUNS_PER_DAY` on every `POST /v1/runs`, including cache hits and precomputed answers, and returns 429 `rate_limited`.

**backend-5 builds this, legally.** AD-13 says `RUNS_PER_DAY` "also caps PRISM traces", so it keeps its own counter in the trace queue and drops traces past 200.

**What breaks.**

1. **Cache hits use up the cap.** 200 of them exhaust it while no run was computed.
2. **Computed runs go untraced.** The trace counter resets on its own schedule (per process, a different day boundary), so it drops traces of runs that were computed. That breaks AD-9's "every API-triggered run is traced".
3. **A third error code appears.** backend-3's pool-busy 429 needs its own code. The web (backend-8) can only special-case the one it knows.

**Fix: tighten AD-13.**

> **AD-13 (counters) — All counters live in `app/api/limits.py`.** `RUNS_PER_DAY` counts cache-miss computations only: UTC day, checked and consumed just before compute; cache hits and precomputed answers never consume it. It is the only cap on traces: every computed run enqueues exactly one trajectory, and the queue drops only on overflow, which it logs. Per-user buckets key on the Clerk user id; per-IP buckets on the first `X-Forwarded-For` hop the host sets. The 429 codes are exactly `rate_limited` (bucket), `runs_busy` (pool full) and `daily_cap` (`RUNS_PER_DAY`), each with `Retry-After` in seconds.

---

## H8 — Picks have one write path but two read paths (backend-4 × backend-8)

**backend-4 builds this, legally.** `GET /v1/me/picks` returns the session token's `picks` claim; AD-8 says reads come "from a custom session-token claim, so reads cost no Clerk call". `PUT` returns 204.

**backend-8 builds this, legally.**

1. Onboarding sends `PUT`, then routes to the verdict screen.
2. That screen sends `GET` with the cached token. Clerk tokens live about 60 s, so it gets old or empty picks, and onboarding shows again.
3. The other legal option is reading `user.publicMetadata` in the browser; AD-8 forbids only browser writes. That adds a third read path, which can see course ids the API's snapshot doesn't list.

**Fix: tighten AD-8.**

> **AD-8 (paths) — One write path, one read path.** `PUT /v1/me/picks` takes `{"picks": [...]}`: unique course ids from the bound snapshot's `/v1/courses`, 0–3 items, order kept. It writes `publicMetadata.course_picks` and returns 200 `{"picks": [...], "snapshot_id": ...}`. `GET /v1/me/picks` returns the token claim intersected with the bound snapshot's courses. After a `PUT`, the client uses the `PUT` response and fetches a fresh token (`getToken({ skipCache: true })`) before its next API call. The client never reads `publicMetadata` itself.

---

## H9 — Nightly traces can change the live PRISM proofs; API trace steps have no source (backend-5 × backend-7, backend-3 × backend-5)

### 9a. Which runs get traced, under which ids (backend-5 × backend-7)

**backend-5 builds this, legally.** Its AGENTS.md PR adds `daytrader-api-backtest-v1` to contract 4 and nothing else, as the story says. Contract 5 still reads "Trace only the 30-session LPP proof set and verdict runs."

**backend-7 builds this, legally.** AGENTS rule 1 says every run is traced, and contract 4 already lists `extract-lpp-v1` for "events from one LPP session". So it traces nightly extraction under `extract-lpp-v1`, with `proof_set: false`.

**What breaks.**

1. **The live proofs drift.** The PRISM population behind the proof agent_ids grows every night. The Root Cause cluster count the demo cites (28 → 18 failed runs, commit 3362e61) and the evaluator's v1/v2 pass rates move behind the links in `proofs/prism.json`.
2. **AD-12 doesn't cover this.** It freezes the file, not what the file's links show.
3. **The other legal choice also fails.** If backend-7 follows contract 5 and doesn't trace, it breaks rule 1. Either way, the two stories obey different lines of AGENTS.md.

### 9b. Where the trace steps come from (backend-3 × backend-5)

1. **The steps have no source.** backend-5 needs the four `tool_call` steps with counts and statuses. backend-3's shared function returns only the results structure ("add nothing", AD-3). backend-5 must either re-run the steps (double compute, with different inputs if a swap happened in between) or make the outputs up.
2. **Metadata has no defined values.** Contract 5's `prompt_version`, `agent_version`, `git_sha` and `proof_set` have no defined value for a code-only run.
3. **The user hash has no single formula.** backend-4's logs and backend-5's trace can each pick their own salted-hash formula, or log the raw id.

**Fix: tighten AD-9.**

> **AD-9 (who traces what) — The AGENTS.md PR that adds `daytrader-api-backtest-v1` also adds `extract-<course>-nightly-v<n>`, and amends contract 5's "trace only" line to: the 30-session proof set, verdict runs, API cache-miss runs, and nightly extraction.** Nightly runs never use a proof agent_id (`extract-lpp-v1`, `extract-lpp-v2`, `daytrader-verdict-v1`, `daytrader-verdict-v2`). `backtest.compute` returns `(result, steps)`, where `steps` are the four AD-9 `tool_call` steps it actually ran, each with `tool_name`, a locator `input`, a counts `output`, `status` and `ms`. `app/api/trace.py` only appends `final_answer` and metadata; it never re-runs a step. API-run metadata is exactly `{agent_version: "v1", course, prompt_version: null, git_sha: <image sha>, proof_set: false, snapshot_id, engine_version, run_key, user}`. `user` = `hmac_sha256(USER_HASH_SALT, clerk_user_id)[:16]`, from `app/api/auth.py:user_hash`. That is also the only user value a log line may carry.

---

## H10 — Two response shapes for the same number (backend-1 × backend-3, read by backend-8)

**backend-1 builds this, legally.** `/verdict?delay=` returns a shape backend-1 makes up, such as `{course, version, delay, at, snapshot_id}`. Off-grid delays get 422 `delay_not_precomputed`.

**backend-3 builds this, legally.** AD-3 says the shared function returns "the results/1 structure", so `POST /v1/runs` returns a full results/1 document with `delays_min: [7]` and `by_delay: {"7": …}`.

**What breaks.**

1. **The run document breaks results/1.** It violates rule 1 of results/1 ("every delay present"), and backend-6's validator would reject it.
2. **The parameter has two names.** It is `delay` in one route and `delay_min` in the other.
3. **The same number arrives in two shapes.** AD-4's precomputed shortcut means delay 5 can come back through either endpoint, in two different shapes. backend-8's slider has to handle both.

**Fix: add a responses row to the conventions table and adjust AD-3.**

> **Responses — `/v1/courses/{course}/verdict` and `/v1/runs/*` both return `verdict/1`:** `{schema: "verdict/1", snapshot_id, engine_version, course, version, portfolio, delay_min, start, end, source: "snapshot" | "run", run_key: str | null, at: <the results/1 by_delay entry, verbatim, including word and sealed>, series: {dates, hold, money}, rules, unknown}`. The parameter is `delay_min` in every query and body. `/verdict` accepts only `delays_min` values (else 422 `delay_not_precomputed`); `/v1/runs` accepts 1–60. A run is never labelled `results/1`. `compute` returns the entries per portfolio and per delay, and the API assembles `verdict/1`.

---

## H11 — The CLI writes the frozen demo's files, and importing the engine runs `git` (backend-7 × backend-3, backend-2 × backend-3)

**backend-3 builds this, legally.**

1. It extracts the compute function and keeps the CLI's output byte-identical, as its story requires.
2. So the CLI still writes `REPO/results/<course>/<version>.json` by default (run.py:217).
3. It still rewrites `data/improver/<course>-<version>.json` through `decide()` (run.py:212).
4. Importing `backtest.common` still runs `git rev-parse` and `load_dotenv` (common.py:12–21).

**backend-7 builds this, legally.** AD-3 says "the CLI and the API both call it", so the nightly runs the CLI from Luis's main checkout.

**What breaks.**

1. **The frozen demo can change.**
   - The CLI dirties git `results/` in main's working tree.
   - The next agent that runs `git add -A` on a branch from there ships new numbers to the frozen Vercel demo.
   - AD-12 says "the pipeline never writes them". The pipeline didn't; the CLI did.
2. **The container can't import the engine.** backend-2's slim image (`python:3.13-slim`) has no `git`, so `import backtest.common` raises `FileNotFoundError` at API startup.

**Fix: tighten AD-3 and AD-12.**

> **AD-3 (purity) — `backtest.compute` is pure:** it reads only its arguments and the bars root it is given, writes nothing, starts no subprocess, and reads no `.env`. `git_sha()`, `_main_checkout()` and `load_dotenv` run only inside the CLI's `main()`.
> **AD-12 (nightly) — The pipeline imports `backtest.compute` and never shells out to `backtest.run`.** It runs from its own clone (`~/dev/quant-bot-nightly`), never from the main checkout or a worktree, and writes only under `$SNAPSHOT_BUILD_DIR`. The improver's write-back stays a manual CLI step.

---

## H12 — Two owners of `window`; snapshots that change every night (backend-7 × backend-3)

**backend-7 builds this, legally.**

1. New sessions fall after `window.end` (LPP's ends 2025-09-12; Crypto Wizard's 2026-10-16).
2. The window is a code constant (`lpp.WINDOW` etc.), and contract rule 10 says the sealed part is the last 3 months.
3. So the nightly moves both `end` and `sealed_from` by overriding `mod.WINDOW`.

**backend-3 builds this, legally.**

1. It validates `start` and `end` against the snapshot file's `window`, as AD-4 says.
2. The compute, lifted from the CLI, prices hold with `mod.WINDOW` from the server's code (run.py:126).

**What breaks.**

1. **Two windows.** Whenever the deployed code and the night's build disagree, the server prices with one window and validates against another.
2. **The holdout slides.** When `sealed_from` moves, yesterday's sealed months become dev months. `combos` and `suggestion` ("picked on dev, reported on sealed"; AGENTS rule 4) then get picked on data that used to be the holdout.
3. **A new id every night.** `generated_at` and `git_sha` sit inside hashed files (run.py:188). A night with no new source still gets a new `snapshot_id`: the pointer flips, and every cached run is invalidated daily.

**Fix: add AD-17.** Moving `sealed_from` rules is a contract change, so it needs an AGENTS.md PR first.

> **AD-17 — The window is snapshot data.** `compute` takes `window` from the results file being extended; `mod.WINDOW` is only the CLI default. Each course's `sealed_from` is fixed in `app/pipeline/windows.json` and moves only by an AGENTS.md PR; the nightly may extend `end` only. Dev-month picks (`combos`, `suggestion`) use only dates before `sealed_from`. The pipeline publishes nothing when the night's inputs (positions, bars, `engine_version`) hash the same as the live snapshot's.

---

## Smaller findings (not pairs, still worth a line)

1. **AD-6:** a thread pool can't kill a run that times out. Two stuck runs make every later request get 429 `runs_busy`. Either use a process pool (and accept cold `lru_cache`s), or write down that the thread keeps running after the 10 s answer.
2. **AD-9 vs AD-10:** "A model call made by any API path is traced" contradicts "The API never calls a model". Delete the AD-9 sentence.
3. **Verdict text has two owners.** AD-1 hashes `verdicts/` into the snapshot. The Deferred list says serving it comes later. AD-10 says custom-run text is code-templated. Pick one source until the verdict story; otherwise delay 5 shows model text and delay 7 shows template text.
4. **Run cache size:** "never invalidated" also means never evicted, on a ≤ 5 GB volume. Add size-bounded LRU eviction. Eviction isn't invalidation: an evicted key just recomputes to the same result.
5. **`_sample.json`:** say whether the API ever serves it. The web falls back to it for a missing course (data.js:28).

## Held up under attack

1. **AD-7 token check:** backend-4 vs backend-8. It names the library, the PEM key, `azp`, `sts` and which routes are public or private, leaving nothing to disagree on.
2. **AD-10 extraction ledger:** backend-7 alone. One owner, one key.
3. **AD-2 read model:** no story builds against it yet, so there's no pair to break.
4. **AD-11's stop-on-failure rule:** one owner, one pointer.

## Suggested order of edits

1. AD-15 (ids) and AD-14 (positions), because every other fix refers to `snapshot_id`, `ENGINE_VERSION` and the positions file.
2. AD-5 (bars) and AD-16 (request-bound snapshot): the server's numbers are wrong without them.
3. AD-3 (headline, purity, word) and AD-4 (ranges).
4. AD-9, AD-13, AD-8, AD-17, the response conventions, and AD-12 (nightly). AD-9 and AD-17 need the AGENTS.md PR first.
