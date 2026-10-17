# Learn Plan Profit: Morning Live Trading → checked events (story `extract-lpp`, 2026-10-17)

Code: `app/lpp/`. Data (gitignored): `~/dev/quant-bot/data/lpp/`. Design: `notes/strategy-pipeline.md` section 4; shapes and copy-trade rules: `_bmad-output/planning-artifacts/spec-day-trader-ai/contracts.md`. Rules from `AGENTS.md`: the model proposes, code decides. Raw transcripts never leave the Mac except in the Nicrron call; git, PRISM and the demo get events, locators and quotes of 12 words or fewer.

## For Luis

**Numbers**
1. 246 of 247 sessions extracted.
2. 4,196 events; 1,775 trades.
3. v2 meets the gold bar.
4. v1 misses precision by one.
5. Trading is 38% of airtime.
6. PRISM v1: 28 of 30 failed.
7. v2, same 30: 18 fail.

**Your call**
1. Review 5 gold checklists.
2. Send v2 runs to PRISM?
3. Story 1 prices v2?

## 1. Source
1. Discord `#morning-live-trading` (LPP server), one YouTube link per trading day; 247 sessions, 2024-08-15 to 2025-09-12 (collected by the strategy-pipeline session).
2. Unlisted live streams starting ~09:29:50 ET (`release_timestamp`), median 58 min, so `wall_utc = release_timestamp + t_s` is the real market minute. If a video lacked `release_timestamp`, the upload time would be used and the session row says `time_source: "timestamp"`; none of the 246 needed it.
3. English auto-captions (`json3`, word timings) on 246 of 247. One session (`41ixdD2nUp0`, 2024-09-18) has no captions on YouTube at all: skipped (Whisper would cost ~$0.26; pipeline decision 2).

## 2. Keep and drop
**Keep** (one record per event, shared shape from the pipeline hand-over, plus `session_date`, `instrument`, `fail`, and extra `checks` fields):
1. **Trade**: an order the host places during the stream (open, add, trim, close): ticker, side, qty, price.
2. **Call**: a US ticker with a direction and a price level (entry, stop, target, support, resistance).
3. **Rule**: a general rule someone could code, paraphrased (15 words max; longer ones are flagged `paraphrase_ok: false`).
4. Every event: `t_s` (time of the quote's first caption word, found by code), `wall_utc`, `why` (15 words), an exact quote (12 words max).

**Drop**: narration, news read-outs, viewer Q&A without a rule, chit-chat, promos, disclaimers. Only their airtime share is kept (section 6).

## 3. Pipeline (`app/lpp/`)
| Step | Module | What it does |
|---|---|---|
| Captions → words | `transcript.py` | json3 → timed words; prompt lines tagged `[t=s]` every 20 s; normalized text for checks |
| Extract | `extract.py` | one streamed call per whole session, `anthropic/claude-sonnet-5-5`, temperature 0; waits out Nicrron's 60 requests/min; reply cached in `data/lpp/extract/` (v1) and `extract/lpp-v2/` |
| Check | `checks.py` | quote, numbers, ticker, price, required fields, position ledger; any failure → `needs_review`, check name in `fail` |
| Bars | `bars.py` | Alpaca 1-min bars (as traded) and yfinance daily bars, cached in `data/bars/` |
| Write | `run.py` | `sources.jsonl`, `events.jsonl`, `sessions.jsonl` (v1 in `data/lpp/`, v2 in `data/lpp/v2/`) |
| Gold | `gold.py` | metrics vs gold; review checklists |
| PRISM | `prism.py` | one agent run per proof-set session, per `contracts.md` trace conventions |
| Evaluator | `evaluate.py` | local "numbers grounded" score |
| Test design | `copytest.py` | host round trips, copy the host vs SPY, calls |
| Tests | `test_lpp.py` | 9 unit tests: `cd app && uv run --with pytest pytest lpp -q` |

**Why the whole-session call failed before** (prototype: a 502, then an empty stream): Sonnet 5.5 on Nicrron thinks for 20-60 s on a 9k-token session before its first token, and that hidden thinking counts against `max_tokens`. A 6-8k budget ended with `finish=length` and almost no JSON. Nicrron also drops non-streamed calls at ~30 s. Fix: stream, `max_tokens` 24000. Median call 34 s.

**Checks**
1. `quote_ok`: the quote is 12 words or fewer of consecutive caption words; its first word's time becomes `t_s`.
2. `numbers_ok`: every qty, price and level is said within 3 min before / 1 min after the quote. Captions drop decimal points ("5874" for $58.74), so that form counts for prices and levels, never for share counts. Numbers inside a rule paraphrase must be said too (`rule_number_not_in_source`).
3. `ticker_ok`: the symbol has 2024-25 daily bars (catches misheard tickers that aren't symbols, and delisted ones like SAVE).
4. `price_ok`: the as-traded 1-min bars within 2 min of `wall_utc` (Alpaca keys arrived at 14:44 ET): a fill within 1%, a call level within 25%. With no minute bars it falls back to the day's range; `checks.price_check` says which ran (1,018 minute, 3 daily).
5. Required fields: a trade needs an action and a side; a call needs a side and a level.
6. `ledger_ok`: trades reconcile into round trips per (ticker, side, instrument). v1 fails a close with nothing open, a trim past the position, and an open never closed. v2 takes in positions still open from earlier sessions and reports a position open at stream end instead of failing it.

## 4. Counts (v1, all sessions, after the review fixes)
Sessions: 247 linked, 246 extracted (all `anthropic/claude-sonnet-5-5`, no fallback model), 1 without captions. 1.35 M caption words. Tokens in 2.68 M, out 1.39 M (thinking included), about **$20** at list + 5%; v2 about the same again. 10 calls needed a retry (11 rate limits, 2 bad JSON), all recovered.

| Type | Events | ok | needs_review | Per session (median) |
|---|---|---|---|---|
| trade | 1,775 | 1,219 | 556 | 6 |
| call | 776 | 541 | 235 | 3 |
| rule | 1,645 | 1,123 | 522 | 7 |
| all | 4,196 | 2,883 | 1,313 | |

1. 40 sessions have no trade by the host.
2. 169 round trips open and close on air; 201 positions are still open when the stream ends.
3. He mostly shorts: 240 short opens vs 66 long.
4. Most traded: TSLA 443, NVDA 245, PLTR 236, HIMS 154, MSTR 126, HOOD 125, SOUN 98, SOFI 76.
5. Trades per month rise from 60 (2024-08) to 228 (2025-07).

**v2 on all 246 sessions** (`data/lpp/v2/`, same check code): 4,128 events (1,768 trades, 771 calls, 1,589 rules); `needs_review` 355 (v1: 1,313); 93 sessions fully clean (v1: 12). Remaining v2 failures: `close_without_open` 107, `call_without_side` 78, `number_not_near_quote` 63, `number_not_in_source` 42, `rule_number_not_in_source` 22, `qty_exceeds_position` 19, `quote_not_in_source` 19, `trade_without_side` 16, `price_off_minute_bar` 16, `ticker_unresolved` 9, `quote_too_long` 8, `ticker_unknown` 7. 193 round trips close on air; 218 positions are open at stream end.

## 5. Metrics vs gold (5 sessions spread over the year)
Gold was drafted by this session from the captions before it saw the extractor's output: 36 trades (28 sure, 8 unsure), 28 calls (16 sure), 62 rules (46 sure), 126 events in 5 sessions (2024-09-24, 2024-12-04, 2025-02-18, 2025-05-13, 2025-07-29). Two sessions have no host trades at all, which tests "a viewer's trade read out loud". Luis's review is pending, so every number here is **provisional**.

Matching (the spec's): a trade = same ticker **and same action** within 30 s; call = same ticker within 60 s (level and direction not compared); rule = any rule within 60 s (wording not compared). Unsure gold counts neither way.

| Version | Trade recall | Trade precision | Same, entry/exit only | Call precision | Rule recall |
|---|---|---|---|---|---|
| `lpp-v0` (first prompt) | 85.7% | n/a | 96.4% / 86.5% | 73.3% | 76.1% |
| `lpp-v1` (all 247) | 96.4% (27/28) | **94.1% (32/34)** | 100% / 97.1% | 80.0% | 65.2% |
| `lpp-v2` | 96.4% (27/28) | **100% (27/27)** | 96.4% / 100% | 78.9% | 67.4% |

1. **Bar (recall ≥ 90%, precision ≥ 95%):** v2 meets it; v1 misses precision by one event. v1's two misses: a cover emitted twice, and a HIMS short logged as "open" when he was adding to 1,000 shares carried from the day before (he only says so 38 minutes later). All 247 sessions were first run with v1 because the first scoring used the looser entry/exit match (97.1%); the code review moved the headline to the spec's strict match.
2. **In-sample:** v0 → v1 was tuned on these same 5 sessions (e.g. resolving an unnamed "another 500 shares" while he builds a SOFI short, and spoken names like "sofi"). Luis's review is the check on the gold itself; a held-out gold session would be the check on the tuning.
3. Rule recall is the weakest number; the gold rules are generous, and the strategy step needs recurring rules (3+ sessions), not every one.

## 6. Airtime (share of each stream; the model marks stretches, code adds them up)
| Category | Mean % | Median % |
|---|---|---|
| trading (trades, calls, setups, rules) | 37.6 | 36.6 |
| narration (price moves, no action) | 28.5 | 27.8 |
| chit-chat | 12.7 | 10.4 |
| viewer Q&A | 11.2 | 10.1 |
| news read-outs | 6.0 | 4.0 |
| promo | 2.3 | 1.3 |
| silence | 1.6 | 0.0 |
| disclaimer | 0.1 | 0.0 |

## 7. Failure kinds (PRISM Root Cause input)
v1, all 246 sessions (an event can fail more than one check):

| Check failed | Events | Sessions |
|---|---|---|
| `quote_too_long` | 701 | 211 |
| `close_without_open` | 216 | 94 |
| `open_never_closed` | 201 | 158 |
| `call_without_side` | 108 | 41 |
| `number_not_near_quote` | 70 | 57 |
| `number_not_in_source` | 44 | 36 |
| `qty_exceeds_position` | 26 | 25 |
| `rule_number_not_in_source` | 26 | 24 |
| `trade_without_side` | 17 | 16 |
| `price_off_minute_bar` | 17 | 15 |
| `quote_not_in_source` | 16 | 16 |
| `ticker_unresolved` | 9 | 9 |
| `ticker_unknown` | 7 | 1 (SAVE, delisted) |
| `call_without_level` | 1 | 1 |

1. 234 of 246 sessions have at least one `needs_review` event; 12 are fully clean.
2. Carried positions explain part of the ledger failures: 57 of 216 `close_without_open` close a position that was open at the end of the previous session, and 69 of 201 `open_never_closed` are trimmed or closed the next session. The rest are positions opened pre-market or closed after the stream, plus missed trades.
3. The prototype's feared failures were rare with whole-session extraction: a P&L read as a price shows up as `price_off_minute_bar` (17 events); misheard tickers as `ticker_unknown`/`ticker_unresolved` (16).

**Our one sentence:** the model can't count to 12, so its evidence quotes run long and often leave out the number they should prove; and the host holds positions past the stream and across days, so a one-session ledger sees opens with no close and closes with no open.

## 8. PRISM
1. `extract-lpp-v1`: one agent run per session of the **30-session proof set** (gold 5 + 25 spread over the year, `data/lpp/gold/proof_set.json`), sent 14:36 ET, 28 `final_status="error"`; trajectory ids in `data/lpp/prism_runs.jsonl`. The other 217 sessions are not traced (budget, `contracts.md`).
2. Steps: `load_captions` (locator, word count) → `llm_extract` (model, tokens, seconds, airtime) → `check_events` (ok vs needs_review, failure kinds) → final answer (events JSON: tickers, levels, quotes of 12 words or fewer, failed check names).
3. Those 30 v1 runs went out before the contract fix: their `conversation_id` is `lpp-<video_id>-lpp-v1` and they carry no `metadata`. `prism.py` now sends `lpp-<video_id>` with `metadata {agent_version, course, prompt_version, git_sha, proof_set}`, logs every send, and won't send the same agent and session twice.
4. Evaluator "numbers grounded": every qty, price and level appears in the quote the same event cites (PRISM sees quotes, not transcripts, so the quote is the evidence). Same 30 sessions, same check code:

| | Error runs | needs_review events | Events grounded | Runs grounded |
|---|---|---|---|---|
| `extract-lpp-v1` | 29 | 163 | 89.0% (210/236) | 53.3% (16/30) |
| `extract-lpp-v2` | 18 | 30 | 94.4% (236/250) | 66.7% (20/30) |

5. What v2 changes, and how much of the gain is code: (a) the prompt asks the quote to include the event's numbers; (b) **code** trims a verified quote to its 12-word window holding the most of those numbers, because the prompt alone made quotes longer (84 → 100 too-long quotes); (c) the v2 **ledger rules** carry positions across sessions and stop failing a position still open at stream end. (b) and (c) are code, not a better model, and (c) is a rule change; the demo should say so. The local re-check of v1 counts 29 error runs vs the 28 traced because the review added checks (side, level).
6. v2 is not in PRISM yet. Root Cause should cluster the v1 runs first (story 2), then `LPP_VERSION=v2 uv run python -m lpp.prism --proof-set`.

## 9. Test design (`copytest.py`; the full engine is story 1)
1. **Host's round trips**: the shared ledger over trades that pass the validity checks; legs priced at the 1-min bar at each `wall_utc` (his stated fill when it sits inside that bar).
2. **Copy the host** (`contracts.md` rules 2-5): each entry and each announced trim or close copied 60 s later at the open of the first 1-min bar at or after announce + delay; same share counts; costs 5 bps per side (20 under $10); SPY over the same minutes.
3. **Calls**: did the level trade after the call, before 16:00 ET that session (1-min bars).
4. **First pass** (`data/lpp/tests/`, `data/lpp/v2/tests/`): 362 round trips in each version; 50 can be priced end to end (closed on air with every share count stated).

| | Host, gross | Copy 60 s later, net | Copy positive | Copy ahead of SPY, same minutes |
|---|---|---|---|---|
| v1 | +$9,620 | +$4,499 | 33 of 50 | 32 of 50 |
| v2 | +$10,963 | +$7,002 | 35 of 50 | 35 of 50 |

   The rest: ~90 trips lack a share count, ~200 are open at stream end, ~20 have counts that don't add up. 50 hand-picked-by-completeness trips is a small, selected sample: story 1's verdict decides.
5. Calls (minute bars after the call): v1 372 of 636 levels traded that session (58%; support 190/260, resistance 67/96, entry 29/45, stop 10/15, target 76/220); v2 394 of 664 (59%).
6. Not here: the sealed window (`contracts.md` rule 10) and the per-delay portfolios; both are story 1's.

## 10. Not verified
1. Gold is a draft until Luis reviews it; v1 was tuned on it.
2. Airtime is the model's labelling, not timed by a human.
3. The call and rule metrics don't compare levels, directions or wording.
4. The daily-range fallback uses split-adjusted yfinance bars; only 3 events used it.
