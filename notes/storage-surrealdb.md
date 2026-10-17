# Storage: SurrealDB, shaped for the agent (2026-10-17)

Luis asked to save the collected course data to a real database, SurrealDB, hosted if possible, and to write down the schema and why it suits an agent. Code: `app/db/schema.surql` (schema and agent functions), `app/db/load.py` (loader). This replaces the SQLite + sqlite-vec plan in `notes/strategy-pipeline.md` section 5.

## Where it runs
1. **Now: embedded SurrealDB on disk**, `surrealkv://~/dev/quant-bot/data/surreal/daytrader` (inside the gitignored `data/`). No account needed.
2. **Surreal Cloud: three lines in `~/dev/quant-bot/.env`**, then re-run the loader:
   ```
   SURREALDB_URL=wss://<instance>.aws-use1.surreal.cloud
   SURREALDB_USER=<system user from the instance's Authentication panel>
   SURREALDB_PASS=<its password>
   ```
   Why not yet: the env files on this Mac only hold SurrealDB **Agent Memory** keys (`SPECTRON_*`, in the hacksprint app), which are a hosted memory API, not a database instance. No `SURREALDB_URL` is set anywhere.
3. Namespace `daytrader`, database `courses` (override with `SURREALDB_NAMESPACE`, `SURREALDB_DATABASE`).
4. Embedded mode is one process at a time (a file lock), so the loader is the only writer. Source agents keep writing JSONL; the loader syncs it.
5. Privacy: caption text (`segment`) is paid course content. It stays in Luis's own database (local or his private Cloud instance), never in git, PRISM or the public demo (`AGENTS.md` rule 5).

## Load
```bash
cd app && uv run python -m db.load --embed
```
Re-runnable: schema is `DEFINE ... OVERWRITE`, records are `UPSERT`ed by fixed ids, edges and segments are deleted and rebuilt per record. `--stats` prints counts and calls each agent function once.

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
   | `fn::similar_rules($vec, $k?)` | rules by meaning (HNSW, cosine, voyage-finance-2 1024-d) |
   | `fn::ticker_activity($ticker)` | per course and type, via the `mentions` graph |
   | `fn::context($source, $t, $window?)` | the caption text around one moment, to check a quote |

2. **Checked data by default.** Functions return `status = "ok"` events unless the caller asks for unchecked ones, so the agent doesn't reason over rows that failed a code check.
3. **Derived first, raw on request.** Events are short typed rows (paraphrase 15 words, quote 12). Raw captions are reachable only through `fn::context`, in a time window: cheap in tokens, and scoped for copyright.
4. **Fixed ids are citations.** `event:⟨lpp:A4929OT4Jls:003⟩` is stable across re-runs, so the agent can cite it, the UI can link it, and PRISM traces can name it.
5. **Indexes match the questions.** Composite `(course, type, ticker, wall)` for "what did the host do in TSLA in March"; BM25 on rule text and captions; HNSW on embeddings; `(source, start_s)` for context windows.
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
