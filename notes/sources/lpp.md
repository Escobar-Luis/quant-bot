# Learn Plan Profit: Morning Live Trading → checked events (story `extract-lpp`, 2026-10-17)

Code: `app/lpp/`. Data (gitignored, never in git or PRISM): `~/dev/quant-bot/data/lpp/`. Design: `notes/strategy-pipeline.md` section 4 (branch `spike/strategy-pipeline`). Rules from `AGENTS.md`: the model proposes, code decides; quotes 12 words max; no transcript text leaves the Mac except in the Nicrron call.

## For Luis

**Numbers**
1. 246 of 247 sessions extracted.
2. 4,196 events; 1,775 trades.
3. Trade recall 100% (draft gold).
4. Trade precision 97% (draft gold).
5. Trading is 38% of airtime.
6. PRISM v1: 28 of 30 failed.
7. v2, same 30: 16 failed.

**Your call**
1. Review 5 gold checklists.
2. Alpaca keys for minute bars?
3. Trace other 217 sessions? (No.)
4. Send v2 after Root Cause?

## 1. Source
1. Discord `#morning-live-trading` (LPP server), one YouTube link per trading day; 247 sessions, 2024-08-15 to 2025-09-12 (collected by the strategy-pipeline session).
2. Unlisted live streams, ~45 min from ~09:29:50 ET (`release_timestamp`), so `wall_utc = release_timestamp + t_s` is the real market minute.
3. English auto-captions (`json3`, word timings) on 246 of 247. One session (`41ixdD2nUp0`, 2024-09-18) has no captions on YouTube at all: skipped (Whisper would cost ~$0.26; pipeline decision 2).

## 2. Keep and drop
**Keep** (one record per event, shared shape from the pipeline hand-over, plus `session_date`, `instrument`, `fail`):
1. **Trade**: an order the host places during the stream (open, add, trim, close): ticker, side, qty, price.
2. **Call**: a US ticker with a direction and a price level (entry, stop, target, support, resistance).
3. **Rule**: a general rule someone could code, paraphrased (15 words max).
4. Every event: `t_s` (from the quote's first caption word, found by code), `wall_utc`, `why` (15 words), an exact quote (12 words max).

**Drop**: narration, news read-outs, viewer Q&A without a rule, chit-chat, promos, disclaimers. Only their airtime share is kept (section 6).

## 3. Pipeline (`app/lpp/`)
| Step | Module | What it does |
|---|---|---|
| Captions → words | `transcript.py` | json3 → timed words; prompt lines tagged `[t=s]` every 20 s; normalized text for checks |
| Extract | `extract.py` | one streamed call per whole session, `anthropic/claude-sonnet-5-5`, temperature 0, fallback `sonnet-5` then `gpt-5.4`; reply cached in `data/lpp/extract/<id>.json` |
| Check | `checks.py` | quote exact (and ≤12 words), numbers said near the quote, ticker real, price plausible, position ledger; any failure → `needs_review` with the check name in `fail` |
| Bars | `bars.py` | yfinance daily bars (cached); Alpaca 1-min bars when keys exist |
| Write | `run.py` | `sources.jsonl`, `events.jsonl`, `sessions.jsonl` |
| Gold | `gold.py` | metrics vs gold; review checklists |
| PRISM | `prism.py` | one agent run per proof-set session |
| Evaluator | `evaluate.py` | local "numbers grounded" score, v1 vs v2 |
| Test design | `copytest.py` | host round trips, copy the host vs SPY, calls |

**Why the whole-session call failed before** (prototype: 502, then an empty stream): Sonnet 5.5 on Nicrron thinks for 20-60 s on a 9k-token session before its first token, and the hidden thinking counts against `max_tokens` (a 6-8k budget ended with `finish=length` and almost no JSON). Nicrron drops non-streamed calls at ~30 s. Fix: stream, `max_tokens` 24000. Median call 34 s.

**Checks in detail**
1. `quote_ok`: the quote (≤12 words) is consecutive caption words; its first word's time becomes `t_s`.
2. `numbers_ok`: every qty, price and level is said within 3 min before / 1 min after the quote. Captions drop decimal points ("5874" for $58.74), so that form counts too.
3. `ticker_ok`: the symbol has 2024-25 daily bars on yfinance (catches misheard tickers that aren't symbols).
4. `price_ok`: no Alpaca keys yet, so daily range: a fill must sit inside that day's high-low (1% slack), a level within 25%; a x10/x100 match is flagged `price_decimal_shift`. With keys it checks the 1-min bars at `wall_utc` ±2 min.
5. `ledger_ok`: trades reconcile into round trips per (ticker, side); a close with nothing open, a trim past the position, or an open never closed fails.

## 4. Counts (v1, all sessions)
Sessions: 247 linked, 246 extracted with `anthropic/claude-sonnet-5-5` (no fallback model used), 1 without captions. 2024-08-15 to 2025-09-12, median 58 min, 1.35 M caption words. Tokens in 2.68 M, out 1.39 M (thinking included), about **$20** at list + 5%. 10 calls needed a retry (11 rate limits, 2 bad JSON), all recovered.

| Type | Events | ok | needs_review | Per session (median) |
|---|---|---|---|---|
| trade | 1,775 | 1,227 | 548 | 6 |
| call | 776 | 633 | 143 | 3 |
| rule | 1,645 | 1,140 | 505 | 7 |
| all | 4,196 | 3,000 | 1,196 | |

1. 40 sessions have no trade by the host.
2. 159 round trips open and close on air; 206 positions are still open when the stream ends.
3. He mostly shorts: 240 short opens vs 66 long.
4. Most traded: TSLA 443, NVDA 245, PLTR 236, HIMS 154, MSTR 126, HOOD 125, SOUN 98, SOFI 76.
5. Trades per month rise from 60 (2024-08) to 228 (2025-07).

## 5. Metrics vs gold (5 sessions spread over the year)
Gold = drafted by this session from the captions before seeing the extractor's output; unsure items marked for Luis. Luis's review is pending, so these are **provisional**. Matching: trade = same ticker and action group (entry or exit) within 30 s; call = same ticker within 60 s; rule = any rule within 60 s. Unsure gold counts neither way.

| Version | Trade recall | Trade recall, exact action | Trade precision | Call precision | Rule recall |
|---|---|---|---|---|---|
| `lpp-v0` (first prompt) | 96.4% (27/28) | 85.7% | 86.5% (32/37) | 73.3% | 76.1% |
| **`lpp-v1`** (all 247 sessions) | **100% (28/28)** | 96.4% | **97.1% (33/34)** | 80.0% (12/15) | 65.2% (30/46) |
| `lpp-v2` (proof set) | 96.4% (27/28) | 96.4% | 100% (27/27) | 78.9% | 67.4% |

Gold: 36 trades (28 sure, 8 unsure), 28 calls (16 sure), 62 rules (46 sure), 126 events in 5 sessions (2024-09-24, 2024-12-04, 2025-02-18, 2025-05-13, 2025-07-29). Two sessions have no host trades at all, which tests precision on "viewer's trade read out loud". What v0 got wrong and v1 fixed: a trade he recounted from the week before, one cover emitted twice, two unresolved tickers ("another 500 shares" while building a SOFI short). Rule recall is the weakest number; the gold rules are generous, and recurring rules (3+ sessions) are what the strategy step needs.

Bar before running all 247: trade recall ≥ 90%, precision ≥ 95%: **met by v1 on the draft gold**. Prompt versions tried (all logged in `data/lpp/extract/`): `lpp-v0` (first draft), `lpp-v1` (only trades placed on air, one event per order, resolve tickers from context, decimal-dropped prices), `lpp-v2` (quotes must carry the event's numbers; ledger carries positions across sessions).

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
| `open_never_closed` | 206 | 160 |
| `close_without_open` | 189 | 86 |
| `number_not_near_quote` | 61 | 52 |
| `number_not_in_source` | 41 | 33 |
| `qty_exceeds_position` | 41 | 25 |
| `price_off_day_range` | 20 | 16 |
| `quote_not_in_source` | 16 | 16 |
| `ticker_unresolved` | 9 | 9 |
| `ticker_unknown` | 7 | 1 |

1. 229 of 246 sessions have at least one `needs_review` event; 17 are fully clean.
2. Carried positions explain part of the ledger failures: 49 of 189 `close_without_open` close a position that was open at the end of the previous session, and 71 of 206 `open_never_closed` are trimmed or closed the next session. The rest are positions opened pre-market or closed after the stream, plus missed trades.
3. The prototype's feared failures were rare with whole-session extraction: P&L read as a price shows up as `price_off_day_range` (20 events), misheard tickers as `ticker_unknown`/`unresolved` (16).

**Our one sentence:** the model can't count to 12, so its evidence quotes run long and often leave out the number they should prove; and the host holds positions past the 45-minute stream and across days, so a one-session ledger sees opens with no close and closes with no open.

## 8. PRISM
1. `extract-lpp-v1`: one agent run per session for the **30-session proof set** (gold 5 + 25 spread over the year, `data/lpp/gold/proof_set.json`), per the 200-credit budget in `notes/strategy-pipeline.md` section 7. The other 217 sessions are not traced.
2. Steps: `load_captions` (locator, word count) → `llm_extract` (model, tokens, seconds, airtime) → `check_events` (ok vs needs_review, failure kinds) → final answer (events JSON: tickers, levels, quotes ≤12 words, failed checks). No transcript text.
3. `final_status="error"` when any event is `needs_review`: 28 of the 30 v1 runs (sent 14:36 ET; trajectory ids in `data/lpp/prism_runs.jsonl`). Next: "Analyze now" on the Intelligence page (5 credits).
4. Evaluator "numbers grounded" (every qty, price and level appears in the quote the event cites), run locally on the same sessions: 

| Same 30 sessions | Error runs | needs_review events | Events grounded | Runs grounded |
|---|---|---|---|---|
| `extract-lpp-v1` | 28 | 147 | 89.0% (210/236) | 51.7% (15/29) |
| `extract-lpp-v2` | 16 | 32 | 94.4% (236/250) | 65.5% (19/29) |

v2 = v1 plus three fixes aimed at the clusters: (a) the prompt asks for the quote to include the event's numbers; (b) code trims a verified quote to the 12-word window that holds those numbers (the prompt alone made quotes longer: 84 → 100 too-long quotes); (c) the ledger takes in positions open at the end of the previous session and reports a position still open at stream end instead of failing it. 29 of 30 sessions have events.
5. `extract-lpp-v2` is ready locally on the proof set; send it to PRISM after Root Cause has clustered v1, so the clusters stay v1-only.

## 9. Test design (`copytest.py`; no engine yet)
1. **Host's round trips**: legs priced at the 1-min bar at each `wall_utc` (his stated fill when it sits inside that bar).
2. **Copy the host**: enter 60 s after he announces, exit 60 s after he says he trimmed or closed, same share counts, costs 5 bps per side (20 under $10); compare with SPY over the same minutes.
3. **Calls**: did the level trade after the call that session (1-min bars), else the day's range (weak: it may have traded before the call).
4. Status now: 349 round trips found in v1 (134 closed on air, waiting for minute bars; 215 still open at stream end). Calls: 632 levels judged on the daily range only (weak evidence), 439 traded that day (69%): support 235/294, resistance 87/109, entry 25/35, target 86/184, stop 6/10. Written to `data/lpp/tests/`.
5. Blocker: 2024-25 minute bars need Alpaca keys (`APCA_API_KEY_ID`, `APCA_API_SECRET_KEY` in `~/dev/quant-bot/.env`); the code picks them up with no change.

## 10. Not verified
1. Gold is a draft until Luis reviews it.
2. The `share` of airtime is the model's labelling, not timed by a human.
3. Daily-range price checks can't catch a wrong price inside the day's range.
4. Alpaca's free-plan `feed=sip` history (pipeline doc, unverified).
