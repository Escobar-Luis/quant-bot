# ZipTrader: what we collected and what we could test (2026-10-17)

Source: the ZipTrader+ Discord, read-only in Luis's signed-in Chrome. Raw posts, images and transcripts stay in gitignored `data/ziptrader/`; this note holds counts, paraphrases and locators only.

## For Luis

**Found**
1. Briefings are news digests.
2. Only 7 real calls.
3. Nutshell is long-term, not day-trading.
4. Real lessons live on ZipTraderU.

**Decide**
1. Collect `#options-ideas` staff calls?
2. Alpaca keys for minute bars?
3. ZipTraderU lessons: separate story?

## 1. Inventory

24 text channels in 6 categories. Counts are Discord search result counts (`in:<channel>`), or exact when the channel's start was visible on one page load ("viewed"). 10 search pages used.

| Channel | Holds | Posts | Collect? |
|---|---|---|---|
| `#strategy-explained` | Strategy Nutshell graphic, staff | 1 (viewed) | Yes |
| `#morning-briefing` | Daily staff briefing screenshot | 4,980; 12 in Oct 1-16 | Yes, October |
| `#education` | Links to 6 ZipTraderU lectures | 2 | No (course is off-Discord) |
| `#ziptrader-25` | Staff long-term 25-stock list, updates | 6 (viewed) | Later |
| `#stock-briefs` | Staff per-ticker news briefs | 1,527 | Later (news, mostly untestable) |
| `#options-ideas` | Staff long-dated call ideas, May-Oct 2026 | not counted | Later (dated calls) |
| `#big-tip` | How-to: notification settings | 1 | No |
| Classrooms: `#momentum-plays`, `#biotech-plays`, `#etf-plays`, `#dividends`, `#crypto-plays` | Member chat | 495, 1,005, 6, 6, 6 | No |
| `#brokers`, `main square` chats, `#reflection`, admin channels | Member chat, admin | not counted | No |
| `#day-trade-ideas` | Member chat; latest 30 messages: 0 staff | not counted | No |

## 2. What was collected (all in `data/ziptrader/`)

| File | Rows | What |
|---|---|---|
| `sources.jsonl` | 13 | 1 Nutshell + 12 October briefings (Oct 1-16, every trading day), all staff, one PNG each |
| `discord/img/` | 13 PNG, 12.7 MB | Downloaded with Luis's OK from the open Discord tab |
| `discord/transcripts/` | 26 | Every image read by two models (Haiku + Sonnet for briefings; Sonnet + GPT-5.4-mini for the Nutshell) |
| `events.jsonl` | 86 | 7 `call`, 65 `setup`, 14 `rule`; 85 `ok`, 1 `needs_review` |
| `strategy_nutshell.spec.json` | 3 specs | One StrategySpec per strategy on the card |

Checks on the 86 events: quote 86/86, numbers 85/86 (a JPM paraphrase says "Q3", which its panel doesn't), ticker 72/72 (rules have none), cross-read 86/86, price not checked (no minute bars).

Cost: under $1 in Nicrron calls (transcription $0.53; extraction and re-runs after review the rest). PRISM: 13 runs of agent `extract-ziptrader-v1` (one per post), inside the free automatic analyses.

## 3. Morning briefings → events

Each briefing is a fixed grid: three macro panels ("what matters today") and six ticker panels ("on the radar today"), each ticker panel ending with a NEWS line and a WATCH line. The WATCH line is almost always a question ("whether X holds or Y"), not a call.

1. 12 of 12 briefings extracted; none skipped.
2. 72 ticker mentions, 43 distinct tickers.
3. **7 calls** (a direction or a level): NKE support 32 (Oct 2), SYNA near the 123 deal price (Oct 2), LEN support near 80 (Oct 6), PENG long (Oct 7), MU support near 950 (Oct 13), CRWV and RKLB holding the prior day's low (Oct 16).
4. **65 setups**: named tickers on the watch list with neither direction nor level. Testable only weakly ("did it beat SPY that session?").
5. `wall_utc` is the Discord message time (posts land 06:44-13:23 UTC, before the open), never a date on the image.

So the briefings can't answer "did ZipTrader's calls work" with any power: n = 7.

## 4. Strategy Nutshell → StrategySpec v0

Posted 2026-01-08 in `#strategy-explained` (`dc:1387103286389243985/1458657028481220719`). The card is a long-term and swing approach with options on top, not a day-trading rule set.

| Spec | Testable? | Rules (paraphrased; item on the card) |
|---|---|---|
| Buy good assets at good prices (main focus) | Runs, on assumptions | Buy dips (A, dip assumed = 14-day RSI below 30); hold to the end of the window (B, assumed); universe and the sell rule are judgement |
| Momentum riding (secondary) | Runs, mostly sourced | Stop 15-20% below entry (C, the one fully sourced number; coded at 15%); entry and "ride" assumed = close above 50-day average; "lock in profits" and "cut losses quickly" assumed = close crosses below the 10-day EMA, in profit or at a loss |
| Options strategy (secondary) | No | Needs options prices and judgement |

**What we couldn't test** (the UI's "what we couldn't test" list)
1. "High conviction stocks": author's judgement; v0 proxy is a fixed list (the staff's `#ziptrader-25` picks once collected, or the October briefing tickers).
2. "Sell when value realized": discretionary.
3. "Rapid business model growth": needs fundamentals.
4. Both options items: no options data.
5. No timeframe or holding period on the card: daily bars assumed.

Every assumption is written into the spec (`assumed`), so v1 proposals can change them and say which. The assumed definitions come from the model and can differ between runs (two runs picked a 50-day average, then RSI below 30, for "dip"); the spec file records which one this v0 uses.

## 5. How it was built (`app/collect/ziptrader/`)

Run in order with `uv run` (each script declares its own dependencies):
1. `sources.py`: DOM listing → `sources.jsonl`.
2. `transcribe.py`: crops each briefing at its two column gutters and sends each column at full resolution (the whole image would be scaled to ~1,568 px); Haiku for briefings, Sonnet for the Nutshell, `--model` for the cross-check read.
3. `extract_calls.py`: one Haiku call per whole briefing; code sets `type` (call vs setup) and runs the checks.
4. `nutshell_spec.py`: Sonnet proposes rules; code validates the vocabulary and numbers, assembles the specs and writes rule events.
5. `checks.py`: every check runs on the event's own span (its ticker's panel, or its card line): `quote_ok` (exact, case kept except a first capital), `numbers_ok`, `ticker_ok` (real symbol per the Nasdaq Trader directory in `data/ref/`, named in the span), `price_ok` (null: no Alpaca keys yet), `xcheck_ok` (the quote is also in the second model's reading).
6. `test_ziptrader.py`: 25 unit tests, no network: `uv run --with pytest --with openai --with python-dotenv --with pillow --with numpy pytest app/collect/ziptrader -q`.
7. `--trace` on the two extract scripts sends one PRISM run per post (locators and derived events only).

**Additions to the shared record shapes** (extra keys; the common loader can ignore them)
1. `events.levels`: every level of a call, `[{value, kind, ref}]`; `entry`, `stop`, `targets`, `level`, `level_kind` are filled from it.
2. `events.level_ref`: a named level without a number (`prev_low`, `premarket_high`, ...).
3. `events.watch`: paraphrase of the WATCH line.
4. `events.checks.xcheck_ok`, `numbers_missing`, `rule_errors`: cross-read result and why a check failed.
5. `sources.image_files`: local image paths under `data/ziptrader/`.
6. Spec: `pct_from_entry`, `const` and `+ - *` in the vocabulary; `hold` rules; `exit.variants` (assumed alternatives); `exit.time.at = "window_end"`; `timeframe.holding = "swing:open"` (no session count stated); items carry `quote_ok`, `xcheck_ok` and `assumed` (a list of the assumptions).

Lessons
1. Exact quotes ran 13-14 words; code trims an exact quote to its first 12 words instead of failing it.
2. One Nicrron stream ended mid-JSON; the spec step retries an unparseable reply instead of patching it.
3. Chrome blocks a page's second automatic download; one ZIP from a fresh tab worked.
4. Discord search ANDs two `in:` filters (0 results), so each channel needs its own search.
5. Checking against the ticker's own panel, not the whole briefing, caught a paraphrase number the whole-text check had passed.

## 6. Deferred (from the code review)
1. KB docs for PRISM proof 1 (`ziptrader-strategy-cards.md` etc.): the `story/extract-rules` loader writes them.
2. `price_ok` from minute bars: the backtest story, once Alpaca keys (or yfinance) are allowed.
3. Posts with several images: only the first is transcribed; none in this set have more than one.
