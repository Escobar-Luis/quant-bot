# Backend research (2026-10-17)

Checked live today through the agent-reach skill (PyPI JSON, GitHub releases and issues via `gh`, Exa, `opencli reddit`, `opencli twitter`; X rate-limited after two searches). Rows marked *unverified* weren't confirmed from a live source.

## Libraries

| Library | Latest stable (date) | Fit / risk | Source |
|---|---|---|---|
| fastapi | 0.143.3 (10-16) | Fine. 0.143.0 made OpenTelemetry exporter setup opt-in | github.com/fastapi/fastapi/releases |
| uvicorn | 0.54.0 (09-25) | Fine. Open #3202 (oversized websocket header) doesn't touch us | github.com/Kludex/uvicorn/releases |
| httpx | 0.28.1 (2024-12-06) | Stable; 1.0.dev6 is a pre-release, so stay `< 1` | pypi.org/pypi/httpx/json |
| pytest | 9.1.1 (06-19) | Fine. Open #15099 (monkeypatch with a custom `__setattr__`) | github.com/pytest-dev/pytest/issues/15099 |
| clerk-backend-api | 7.0.0 (08-11) | `authenticate_request` with `jwt_key` (PEM) + `authorized_parties` is networkless; with only `secret_key` it fetches and caches JWKS. Open #243: case-sensitive `Authorization` parsing can miss a `__session` cookie | github.com/clerk/clerk-sdk-python |
| surrealdb | 2.0.0 (04-23); 3.0.0b10 beta | 2.0.0 added SurrealDB 3.x features; pin `==2.0.0` if the read model stays | github.com/surrealdb/surrealdb.py/releases |
| prismtrace-sdk | 0.5.3 (10-16) | Pre-1.0, weekly releases; pin exactly | pypi.org/pypi/prismtrace-sdk/json |
| pyarrow | 26.0.0 (10-09) | Safe if bars move to Parquet | github.com/apache/arrow/releases |
| polars | 2.0.0 (10-06) | Major release with Parquet breaking changes; avoid for now | github.com/pola-rs/polars/releases |

## Hosts (one always-on Python API, 1–5 GB disk, bursts of seconds)

| Host | Cost | Storage and cron | Risk and sentiment | Source |
|---|---|---|---|---|
| Railway Hobby | $5/mo incl. $5 usage; ≈ $6–8/mo (estimate) | Volume up to 5 GB, daily/weekly backups; built-in cron (UTC) | No cold start, hard spend limit; one X post on a surprise $13 bill | railway.com/pricing, docs.railway.com/reference/backups, reddit.com/r/webdev/comments/1w6f563 |
| Fly.io | ≈ $4.14/mo (512 MB + volume); no free tier | Volume on one Machine; Tigris object storage, first 5 GB free | Platform-wide rolling reboots 10-16, AMS outages 09-26 and 10-03 | fly.io/docs/about/pricing, status.flyio.net |
| Render | ≈ $7.75/mo (Starter + disk) | Cron can't reach a disk; a disk blocks zero-downtime deploys | 0.5 CPU; deploy outage 10-14 | render.com/pricing, render.com/docs/disks |
| Cloud Run | ≈ $0 scaled to zero; ≈ $10/mo kept warm | GCS via FUSE (not POSIX); 3 scheduler jobs free | Cold starts; sentiment *unverified* | cloud.google.com/run/pricing |
| Vercel Functions | Free on Hobby | No disk; Hobby cron once a day | 300 s max on Hobby; sentiment *unverified* | vercel.com/docs/functions/limitations |

Recommendation: **Railway Hobby** (one service + volume). The nightly job runs on Luis's Mac (AD-11), so the host's cron isn't needed.

## Clerk

- Session tokens: verify with the instance's JWKS public key; check `exp`, `nbf`, `azp` (Clerk warns that skipping `azp` opens CSRF); optionally reject `sts=pending`. clerk.com/docs/guides/sessions/manual-jwt-verification
- Metadata: public (frontend reads, backend writes), private (backend only), unsafe (frontend writes; tamperable). 8 KB total; keep custom session claims under 1.2 KB; 10 metadata updates per 10 s per user; Backend API 1000 / 10 s in production, 100 / 10 s in development. clerk.com/docs/guides/how-clerk-works/system-limits

## Nicrron

- Exact-match cache keyed by the whole request, per account; on with `temperature: 0` (or `x-nicrron-cache: true`); a hit returns `X-Nicrron-Cache: HIT` and isn't billed. No published TTL. nicrron.ai/docs
- Rate limits: none published; the gateway fails over on upstream 429/5xx. The extractor saw about 60 requests/min (PR #18).
- Pricing: provider rate + 5% fee; card top-ups +5.5% + $0.35. The hackathon credits expire 2026-10-18 18:00 ET (`notes/sponsors.md`).

## Measured here

- Warm-bar backtest at one delay: LPP v1 315 positions in 0.27 s (build + simulate); Crypto Wizard 126 positions in 0.56 s. `data/bars` is 94 MB.
