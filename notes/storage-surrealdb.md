# Storage: SurrealDB, shaped for the agent (2026-10-17)

Luis asked to save the collected course data to a real database, SurrealDB, hosted if possible, and to write down the schema and why it suits an agent. Code: `app/db/schema.surql` (schema and agent functions), `app/db/load.py` (loader). This replaces the SQLite + sqlite-vec plan in `notes/strategy-pipeline.md` section 5.

## Where it runs
1. **Live on Surreal Cloud since 2026-10-17:** free instance `daytrader-ai` (org `hacksprint`, AWS US East, SurrealDB 3.3), endpoint in `~/dev/quant-bot/.env` as `SURREALDB_URL`, a root system user in `SURREALDB_USER` / `SURREALDB_PASS`. First load: 2 min 41 s for 855 sources, 4,952 events, 26,434 caption segments and 1,931 rule embeddings; **55.6 MB of the 1 GB** free storage. `uv run python -m db.verify` matched every count against the JSONL files.
   Without those three lines the loader falls back to embedded on disk (`surrealkv://~/dev/quant-bot/data/surreal/daytrader`).
2. Namespace `daytrader`, database `courses` (override with `SURREALDB_NAMESPACE`, `SURREALDB_DATABASE`). Studio opens on `main/main`; switch to `daytrader/courses` in its database menu to browse.
3. The loader is the only writer. Source agents keep writing JSONL; the loader syncs it.
4. Privacy: caption text (`segment`) is paid course content. It lives only in Luis's own private instance, never in git, PRISM or the public demo (`AGENTS.md` rule 5).
5. The SurrealDB MCP server (`https://mcp.surrealdb.com`) manages instances and runs ad-hoc queries; the bulk load goes through the Python SDK.

## Free tier fit (estimate, 2026-10-17)
Free instance: 1 GB storage (read-only above it), 0.25 vCPU, 1 GB memory, 1 GB egress a month, pauses after 7 idle days ([pricing](https://surrealdb.com/pricing)).

| Item | Rows (12 months of LPP + other courses) | Size |
|---|---|---|
| Caption text (`segment`, 30 s windows) | ~29k | ~7.5 MB (measured: 1.45 M words) |
| Full-text index on rule text (none on captions) | | ~1-2 MB |
| Events | ~4.4k LPP (17.6 per session so far) + a few thousand from the other courses | ~5 MB |
| Rule embeddings, 1024-d, plus HNSW | ~1.7k | ~30 MB |
| Sources, tickers, edges, view | | < 2 MB |
| **Total** | | **~50-90 MB of data, ~100-200 MB with storage overhead** |

Kept out of the database: raw caption JSON (170 MB), video metadata (142 MB), duplicate captions (29 MB), images. All seven years of LPP (~1,700 sessions) would be ~1-1.5 GB: over the free tier.

Compute, measured: the first version took 590 s to load in memory, 582 s of it building a full-text index over captions that no agent function used. Without it, and with writes batched 250 rows at a time and the remaining indexes built last (`indexes.surql`), the full load (4,952 events, 26,434 caption segments, 855 sources) takes **18 s** in memory. Expect a few minutes on a 0.25 vCPU instance over the network. Agent queries are indexed lookups returning short rows.

## Prices: a cache, not a database (Luis's Tiger Data question)
1. **Don't fetch live per backtest.** One LPP backtest touches ~1,000 ticker-days. At Alpaca's free 200 calls a minute that's 5+ minutes per run, repeated for every v1/v2 trial, and a provider revision would silently change past verdicts.
2. **Fetch once, keep it, reuse it.** Market data is public and re-downloadable, so it needs a cache, not a system of record.
3. **Size is small:** ~1,000 ticker-days × 390 regular-session minutes + SPY ≈ 0.5 M one-minute bars for LPP, ~20 MB as Parquet. Crypto Wizard setups at 1-min over days could reach a few million rows; 5-min bars cut that by 5.
4. **Where:** Parquet files per symbol and month under `data/bars/`, read straight into the pandas backtester. Not SurrealDB: a million bar rows would use much of the 1 GB free instance and scan slower than a columnar file.
5. **Tiger Data (TimescaleDB):** the right tool once prices reach tens of millions of rows or need SQL time buckets and compression. But no free tier (30-day trial, then from $30/month, [pricing](https://www.tigerdata.com/pricing)), and a third system to wire up today. Luis's existing Tiger service belongs to another project (`what-are-the-counts`), so don't reuse it. Revisit after the hackathon.

## Load and check
```bash
cd app && uv run python -m db.load --embed && uv run python -m db.verify
```
Re-runnable: schema is `DEFINE ... OVERWRITE`, records are `UPSERT`ed by fixed ids in batches, edges and segments are deleted and rebuilt, heavy indexes (`indexes.surql`) are built last. `--stats` prints counts and calls each agent function once.

## Tables

| Table | One row is | Id (fixed, so re-runs update instead of duplicating) | Key fields |
|---|---|---|---|
| `course` | a course | `course:lpp`, `course:ziptrader`, `course:cryptowizard` | name, market |
| `source` | a Discord post or a video | `source:⟨yt:A4929OT4Jls⟩`, `source:⟨dc:<channel>/<message>⟩` | course, kind, posted_at, live_start (wall clock of t = 0), duration_s, url, stats (airtime, counts, failure kinds) |
| `segment` | 30 s of caption text (private) | `segment:⟨yt:<video>:00120⟩` | source, start_s, end_s, text |
| `event` | one kept item: trade, call, setup or rule | `event:⟨lpp:<video>:003⟩` (the extractor's `event_id`) | course, source, type, wall, ticker, side, action, qty, price, entry, stop, targets, level, why, rule, quote, checks, fail, status, embedding |
| `ticker` | a symbol | `ticker:TSLA` | market |
| `mentions` | edge event → ticker | auto | |
| `closes` | edge close → open (position ledger, later) | auto | |
| `strategy` | a `StrategySpec` version | auto | course, version, parent, proposer, spec |
| `part_of` | edge rule event → strategy | auto | |
| `backtest_run` | one backtest of one version on one window | auto | strategy, window, metrics, trial_n, verdict, prism_trace_id |
| `daily_activity` | view: events per course, day, type | managed by SurrealDB | n |

## Why this shape suits an agent
1. **Functions are the tool surface.** The agent calls six functions instead of writing SurrealQL: fewer tokens, no query mistakes, and each call maps one-to-one to a PRISM `tool_call` step.

   | Function | Answers |
   |---|---|
   | `fn::course_summary($course)` | sources, date range, events by type and status, top tickers |
   | `fn::events($course, $type?, $ticker?, $from?, $to?, $include_unchecked?, $limit?)` | compact event rows in time order |
   | `fn::search_rules($q, $limit?)` | rules by keyword (BM25, English stemming) |
   | `fn::similar_rules($vec, $k?)` | rules by meaning (HNSW, cosine, voyage-finance-2 1024-d, rules only) |
   | `fn::ticker_activity($ticker)` | per course and type, via the `mentions` graph |
   | `fn::context($source, $t, $window?)` | the caption text around one moment, to check a quote |

2. **Checked data by default.** Functions return `status = "ok"` events unless the caller asks for unchecked ones, so the agent doesn't reason over rows that failed a code check.
3. **Derived first, raw on request.** Events are short typed rows (paraphrase 15 words, quote 12). Raw captions are reachable only through `fn::context`, in a time window: cheap in tokens, and scoped for copyright.
4. **Fixed ids are citations.** `event:⟨lpp:A4929OT4Jls:003⟩` is stable across re-runs, so the agent can cite it, the UI can link it, and PRISM traces can name it.
5. **Indexes match the questions.** Composite `(course, type, ticker, wall)` for "what did the host do in TSLA in March"; BM25 on rule text; HNSW on rule embeddings; `(source, start_s)` for caption windows. No full-text index on captions: it cost 97% of load time and nothing queried it.
6. **Graph for cross-course questions.** `event->mentions->ticker` answers "which courses traded NVDA, and how" in one hop.
7. **Pre-aggregated view.** `daily_activity` keeps counts current on every write, so summaries never scan all events.
8. **Strict schema.** `SCHEMAFULL` with typed fields and `ASSERT`ed enums: a bad extractor row fails at load time instead of reaching the agent.
9. **Room for the next stories.** `strategy`, `part_of`, `backtest_run` and `closes` are defined now, so the backtest engine and the verdict agent write into the same database.
10. **On Cloud: a read-only user for the agent.** `DEFINE USER agent ON DATABASE PASSWORD '…' ROLES VIEWER;` lets the agent query but never write; only the loader writes.

## Example queries
```sql
RETURN fn::course_summary("lpp");
RETURN fn::events("lpp", "trade", "TSLA", d"2025-03-01", d"2025-03-31");
RETURN fn::search_rules("stop loss");
RETURN fn::context("yt:A4929OT4Jls", 641, 30);
SELECT * FROM daily_activity WHERE course = course:lpp ORDER BY session_date DESC LIMIT 10;
```

## Gotchas found today
1. SurrealDB 2.x won't cast ISO strings into `datetime` fields; the loader converts them in Python.
2. The `surrealdb` Python SDK 2.0 runs the engine embedded (`mem://`, `surrealkv://`); no server or CLI needed.
3. JSONL files are still growing while agents run; the loader skips a half-written last line.
4. SurrealDB 3.x renamed things: `SEARCH ANALYZER` → `FULLTEXT ANALYZER`, `type::thing` → `type::record`, and `FLEXIBLE` now comes after `TYPE`. Surreal Cloud's data tools need 3.1+, so `load.py` reads the server version and translates the 2.x schema (tested on engines 2.0.0 and 3.2.4).
5. The SDK's embedded `surrealkv://` mode wrote a 460 MB commit log for this data before compaction; another reason to host it.
