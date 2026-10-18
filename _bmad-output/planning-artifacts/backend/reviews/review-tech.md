# Tech review: backend architecture spine

- **Reviewed:** `../architecture.md` (draft, 2026-10-17), evidence in `../research.md`, the built story's lock `~/dev/quant-bot.worktrees/backend-1-verdict-api/app/uv.lock` (+ its `pyproject.toml`), and main's `app/uv.lock`.
- **Lenses:** (1) was every committed technology claim checked against the web or the project, not asserted from memory? (2) did each named technology and version get agent-reach confirmation (GitHub releases plus recent X or Reddit signal)?
- **Re-checked today (2026-10-17, ~16:00 ET):** `gh release list` and `gh api` on the GitHub repos, PyPI JSON, Jina Reader on vendor docs, Exa (`~/.agent-reach/bin/exa-search`, served by free), `opencli reddit search`. X: `opencli twitter search` returned HTTP 429 (session quota), the same wall `research.md` hit after two searches.

## Verdict

**Mostly sound, with fixes needed.** Every pinned library version in the Stack table is the current stable release, and the built lock matches it. But one row is already out of date (httpx: the TestClient now runs on httpx2). The Clerk rule leaves out three SDK behaviours. R2, launchd and the hosting volume trade-off were never researched. Only Railway got any X or Reddit signal.

## Findings (most load-bearing first)

### High

1. **The httpx row is out of date. The TestClient already runs on httpx2.** Starlette 1.2.0 added "Support httpx2 in the test client" ([Kludex/starlette#3291](https://github.com/Kludex/starlette/pull/3291)). The locked Starlette 1.8.0 `testclient.py` tries `import httpx2 as httpx` first. It falls back to `httpx` only with a `StarletteDeprecationWarning` ("install `httpx2` instead"). [pydantic/httpx2](https://github.com/pydantic/httpx2) has been stable since 2.0.0 (2026-05-12), and 2.13.1 (2026-09-23) is already in both locks, pulled in by `openai` 3.33.0. So `fastapi.testclient.TestClient` in `app/api/tests/test_api.py` runs on httpx2 2.13.1, not httpx 0.28.1. The row "httpx (tests, TestClient) 0.28.1 (< 1; 1.0 is pre-release)" is training-era framing, and `research.md` never mentions httpx2. httpx 0.28.1 stays in the lock only because `prismtrace-sdk` requires `httpx>=0.24.0`, plus our dev group.
   - **Fix:** Stack row → `httpx2 2.13.1 (TestClient; via openai)`. Either drop `httpx` from the dev group, or keep it and note it is only prismtrace-sdk's transport. Tests should import nothing from `httpx` directly, so types don't mix.

2. **The Clerk rule (AD-7) leaves out three facts about `clerk-backend-api` 7.0.0.** I read the v7.0.0 source: `src/clerk_backend_api/security/{authenticaterequest,verifytoken,types}.py`.
   - **`sts` is not checked by the SDK.** No `sts` or `pending` appears anywhere in the security module. AD-7's "it checks exp, nbf and azp, and rejects `sts=pending`" must make the last check our own code (`payload.get("sts") == "pending"` → 401). Clerk documents `sts` as relevant only when Organizations are required ([manual JWT verification](https://clerk.com/docs/guides/sessions/manual-jwt-verification)). It is harmless for us, but the check has to live somewhere.
   - **`accepts_token` defaults to `['any']`.** AD-8 means the API holds the secret key (it writes picks). Once that key is passed in, Clerk API keys (`ak_`), M2M tokens (`mt_`/`m2m_`) and OAuth tokens (`oat_`) go through network verification and come back `SIGNED_IN`. Pass `accepts_token=['session_token']`. Or pass only `jwt_key`, without `secret_key`, to `authenticate_request`.
   - **`authorized_parties` is an exact-match list.** `verifytoken.py`: `azp not in options.authorized_parties` → error. It also rejects a token that has no `azp` at all, which is stricter than Clerk's docs ("If the azp claim doesn't exist, you can skip this step"). Vercel per-commit preview URLs (`<project>-<hash>-<scope>.vercel.app`) change on every push. The env var must list the stable **branch** URL (`<project>-git-<branch>-<scope>.vercel.app`, per [Vercel generated URLs](https://vercel.com/docs/deployments/generated-urls)) plus localhost. Name this in AD-7 and the Config convention.
   - Issue [#243](https://github.com/clerk/clerk-sdk-python/issues/243) (open since 2026-07-27) is confirmed. Any `Authorization` header wins over the `__session` cookie. Starlette headers are case-insensitive, and the preview client sends `Bearer` cross-origin, so it doesn't bite us.

### Medium

3. **The AD-8 session-token claim goes stale after a write.** Clerk says metadata changes "won't appear in the session token until the next refresh", and tokens refresh every 60 s ([extending](https://clerk.com/docs/guides/users/extending), [customize session tokens](https://clerk.com/docs/guides/sessions/customize-session-tokens)). After `PUT /v1/me/picks`, either the client forces a refresh (`getToken({ skipCache: true })`), or the UI uses the PUT response body. The limits are confirmed: 8 KB metadata max (stated on the users/extending page, not the system-limits page `research.md` cites), 1.2 KB of custom claims, 10 metadata updates per 10 s per user, and Backend API 100 per 10 s on development instances ([system limits](https://clerk.com/docs/guides/how-clerk-works/system-limits)). The preview environment runs on a dev instance, so the 100/10 s figure applies.

4. **The hosting comparison is lopsided, and the volume isn't needed.** `research.md` counts "a disk blocks zero-downtime deploys" against Render. Railway's volume docs list the same caveat ([volumes, Caveats](https://docs.railway.com/reference/volumes#caveats)): a small downtime on every redeploy with a volume attached, even with a healthcheck. They also say replicas cannot be used with volumes, and each service gets one volume. Under AD-1, though, the host disk is only a cache that can be rebuilt from the bucket (bars are 94 MB). Railway **without** a volume fills ephemeral disk on boot and keeps zero-downtime deploys.
   - Confirmed: Hobby is $5/mo with $5 of usage included, volume up to 5 GB, daily/weekly/monthly backups, and a hard spend limit. Hitting that limit takes workloads offline, which is worth a line.
   - New: Railway now sells S3-compatible Object Storage ($0.015/GB-month, free egress; [pricing](https://railway.com/pricing)), so "the host's" bucket option is real.
   - Not measured: RAM. Holding 94 MB of JSON bars as Python objects may need 1 GB, which is about $10/mo and outside the $6–8 estimate. Measure RSS in backend-2.

5. **Cloudflare R2 was never researched.** It appears nowhere in `research.md`. I spot-checked it ([R2 pricing](https://developers.cloudflare.com/r2/pricing/)):
   - Free tier: 10 GB-month storage, 1M Class A ops, 10M Class B ops, free egress.
   - Reddit r/CloudFlare, 2026-10-10: R2 is the only free-tier Cloudflare product that needs a card on file ([post](https://www.reddit.com/r/CloudFlare/comments/1x2rszj/why_is_r2_the_only_freetier_product_that_needs_a/)). Another post the same day reports Class A spikes from upload tools ([post](https://www.reddit.com/r/CloudFlare/comments/1x2rtw1/r2_class_a_operations_spiking_100300_when/)), because `ListObjects` is Class A.
   - **Fit:** good. A 5-minute poll of `current.json` is about 8.6k Class B ops a month. Poll with HEAD or `If-None-Match` (Class B), never `ListObjects` (Class A). Keep the pipeline's "skip if the key exists" check on HEAD, not on list.

6. **Nicrron's cache is only partly confirmed.** [nicrron.ai/docs](https://nicrron.ai/docs) confirms that `temperature: 0` gets an automatic Redis exact cache: <5 ms, $0, `X-Nicrron-Cache: HIT`. Not confirmed:
   - whether **streamed** calls are cached. AD-10 says "Long calls stream", and `app/collect/cryptowizard/common.py:143` and `app/collect/ziptrader/common.py:64` already stream at `temperature=0`;
   - the TTL and per-account scope;
   - the header's meaning. `research.md` says opt-in `x-nicrron-cache: true`; `notes/sponsors.md` says opt-out `x-nicrron-cache: false`;
   - whether cache entries survive the credit expiry (2026-10-18 18:00 ET) or a key change.
   - **Fix:** AD-10's ledger-first rule is the right defence. Add "the Nicrron cache is a best-effort bonus; never count it in `NIGHTLY_BUDGET_USD` until a streamed call has been seen returning HIT."

7. **The launchd fit was never researched.** Per [Apple's archive doc](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html), a `StartCalendarInterval` job missed during sleep runs on wake, and one missed while the Mac is off is skipped. An [Apple dev forum thread](https://developer.apple.com/forums/thread/815034) reports that with the lid open, DarkWake starts the job and then suspends it mid-run until a full wake. AD-11 should add:
   - a wake schedule (`pmset repeat wake …`) or a run time when the Mac is awake;
   - `caffeinate -i` around the run;
   - absolute paths and an explicit env file, because launchd doesn't read the shell profile;
   - a LaunchAgent, not a LaunchDaemon, because the Discord step needs Luis's logged-in Chrome.

   "Flip `current.json` last" already makes a suspended or half-done night safe.

### Low

8. **The pin policy isn't stated, and the built story floats.** `research.md` says to pin `prismtrace-sdk` exactly and `surrealdb ==2.0.0`. prismtrace-sdk is pre-1.0 with no public repo; releases went 0.4.0 (08-26) → 0.5.0 (09-17) → 0.5.3 (10-16), and 0.5.2 is absent from PyPI. Yet `app/pyproject.toml` uses `>=` for every dependency. `uv.lock` pins for now, but the next `uv lock --upgrade` or `uv add` floats to 0.6. Put the operator in the Stack table: `==` for prismtrace-sdk and surrealdb, `<1` for httpx.
9. **"surrealdb 2.0.0 (3.0 is beta)" is true only for the Python SDK.** The SurrealDB server is 3.3.0 GA, with 2.7.0 also maintained ([releases](https://github.com/surrealdb/surrealdb/releases)). PR #11's schema targets server 2.x and carries a 3.x dialect shim. Name the server major the read model targets.
10. **The AD-6 timeout is soft.** A thread pool can't stop a timed-out run (the thread keeps its slot), and the pure-Python engine holds the GIL, so "10 s timeout" bounds the response, not the work. Use `ProcessPoolExecutor(2)` and recycle a worker on timeout, or call it a soft timeout. This comes from training knowledge; I didn't web-check it.
11. **The `openai ≥ 3.33.0` floor is a release from today** (PyPI upload 2026-10-17 00:30 UTC). That's fine, because main's lock already has it. It isn't in `research.md`, so add a row.

## Lens 2: agent-reach coverage per named technology

"GitHub" means checked via `gh` against releases or issues. "Social" means a recent X or Reddit signal.

| Technology (spine) | Version claim correct today? | GitHub (research.md) | Social (research.md) | My re-check | Status |
|---|---|---|---|---|---|
| Python 3.13 | Yes (3.13.16; 3.15.0 out 10-09; `.python-version` = 3.13) | No (existing project) | No | endoflife.date | OK (existing project) |
| FastAPI 0.143.3 | Yes (Latest, 2026-10-16) | Yes | **No** | `gh release list`; Reddit r/FastAPI last month: active, no 0.143 breakage reports | Social filled by me |
| Uvicorn 0.54.0 | Yes (Latest, 2026-09-25) | Yes (Kludex/uvicorn) | **No** | `gh release list` | **No social signal** |
| httpx 0.28.1 | Latest httpx, but **the wrong library for TestClient** (Finding 1) | No (PyPI only) | **No** | Starlette source, PyPI | **Stale** |
| pytest 9.1.1 | Yes (Latest, 2026-06-19) | Yes (issue #15099) | **No** | `gh release list` | **No social signal** |
| clerk-backend-api 7.0.0 | Yes (Latest, 2026-08-11) | Yes (issue #243) | **No** | release notes + source read | **No social signal**; fit gaps (Finding 2) |
| surrealdb 2.0.0 | Yes (SDK; 3.0.0b10 pre-release) | Yes | **No** | `gh release list` SDK + server | Ambiguous (Finding 9) |
| prismtrace-sdk 0.5.3 | Yes (2026-10-16) | **No** (no public repo) | **No** | PyPI release history | Only PyPI is possible; pin it |
| openai ≥ 3.33.0 | Yes (released today) | **No** | **No** | PyPI | Not researched (existing lock) |
| Railway Hobby | Yes (pricing, volumes, backups, limits) | n/a | **Yes** (Reddit r/webdev; one X post) | docs re-read; Reddit r/flask (2026-05) | Only host with a social signal; volume caveat missed (Finding 4) |
| Fly.io | Yes ($3.69 for 512 MB + $0.15/GB volume) | n/a | **No** (status page only) | [status.flyio.net](https://status.flyio.net/history): rolling host reboots and AMS outages confirmed; r/flydotio search empty | Status page only |
| Render | Yes ($7 Starter, 0.5 CPU, disks $0.25/GB) | n/a | **No** | [render.com/pricing](https://render.com/pricing) | **No social signal** |
| Cloudflare R2 / S3 bucket | Not stated in spine; my check: free tier as above | n/a | **Not researched** | docs + Reddit (Finding 5) | Filled by me |
| Clerk session-token claims and metadata limits | Yes (8 KB, 1.2 KB, 10 per 10 s) | n/a | **No** | Clerk docs via Jina + Exa | Staleness rule missing (Finding 3) |
| Nicrron exact cache | Partly (Finding 6) | n/a | **No** | nicrron.ai/docs | Streaming and TTL unverified |
| launchd | Exists (macOS built-in) | n/a | **Not researched** | Apple doc + dev forum | Fit gaps (Finding 7) |
| Vercel preview + `VITE_API_URL` | Existing project | n/a | No | Vercel URL docs | Exact `azp` match caveat (Finding 2) |

**Bottom line for lens 2:** every library has a GitHub or PyPI release confirmation, and every version is exact. Only Railway had any X or Reddit signal, and X was rate-limited (HTTP 429) both for the original research and for this review. Cloudflare R2, launchd and httpx2 had no agent-reach coverage at all before this review.

## Spot-checks run for this review

1. `gh release list -R fastapi/fastapi`: 0.143.3 Latest, 2026-10-16 ([release](https://github.com/fastapi/fastapi/releases/tag/0.143.3)). Matches the spine and the lock.
2. `gh release list -R clerk/clerk-sdk-python`: v7.0.0 Latest, 2026-08-11 ([release](https://github.com/clerk/clerk-sdk-python/releases/tag/v7.0.0)); its breaking changes are in error types and response models, not the `security/` module. #243 is still open.
3. Also checked: `Kludex/uvicorn` 0.54.0, `pytest-dev/pytest` 9.1.1, and `surrealdb/surrealdb.py` (top releases are v3.0.0-beta.x pre-releases; PyPI stable is 2.0.0). PyPI JSON confirms every Stack version is the latest stable and none is yanked.
4. Cloudflare R2 free tier: 10 GB-month, 1M Class A, 10M Class B, free egress ([developers.cloudflare.com/r2/pricing](https://developers.cloudflare.com/r2/pricing/)). Reddit: card required on file; Class A surprises from `ListObjects`.
5. Starlette and httpx2: [Starlette 1.2.0 notes](https://github.com/Kludex/starlette/releases/tag/1.2.0), `starlette/testclient.py` at tag 1.8.0, PyPI `httpx2` 2.13.1, and the locked dependency graph (openai → httpx2; prismtrace-sdk → httpx).

## Suggested spine edits

1. Stack table: replace the httpx row with httpx2 (Finding 1); add the pin operators (Finding 8); name the SurrealDB server major (Finding 9); add a row for the R2 free tier and card requirement once backend-6 picks the bucket.
2. AD-7: "the API checks `sts` itself; `accepts_token=['session_token']`; `AUTHORIZED_PARTIES` = branch preview URL + localhost (exact match)".
3. AD-8: "after a picks write, the client forces a token refresh or uses the PUT response; the claim may lag up to 60 s".
4. AD-10: "the Nicrron cache is best-effort; streamed-call caching unverified".
5. AD-11: wake schedule, `caffeinate`, LaunchAgent, explicit env.
6. AD-6: process pool, or call the timeout soft.
7. Open Question 1 (hosting): add "Railway without a volume (cache filled from the bucket) keeps zero-downtime deploys", and the RAM caveat.
