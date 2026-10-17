# Crypto Wizard (CRYPTOWZRD Discord): how setups are given, what we indexed

Collected 2026-10-17, read-only, in Luis's signed-in Chrome, through Discord's own search (no scrolling, no clicks inside messages). Raw posts, charts and every JSONL file live in gitignored `data/cryptowizard/`; this note holds paraphrases and quotes of 12 words or fewer only.

## For Luis

**Indexed (Oct 2025 – Oct 2026)**
1. 126 crypto trade calls
2. 190 "TP hit" follow-ups
3. 82 "please close" exits
4. 272 rules from 64 lessons
5. 42 posts skipped, reasons listed

**First look (sketch, 5-min delay)**
1. Calls lose 0.58% per trade
2. Holding the coin: −0.64%
3. Costs eat 0.50% per trade
4. Zero stop-outs ever announced
5. 16 stops our bars found

**Decide**
1. Allow Chrome downloads for discord.com?
2. Collect Intraday Setups channel too?
3. Sample chart-only "WZRD ALPHA" posts?

## 1. Where the setups are

Full table: `data/cryptowizard/inventory.md` (copy in the session notes folder). The short version:

| Channel | Holds | Count | Collected |
|---|---|---|---|
| `#wzrd-chat-crypto` | Staff-only feed: trade calls, TP-hit and close follow-ups, market updates, ~15 chart-only "WZRD ALPHA" posts a day | 56,801 all time; 12,071 in 12 months | Yes: search `SL` (354) + `please close` (293), last 12 months |
| `#wzrd-crypto-setups` | Daily "<PAIR>USDT Intraday Setup": support and resistance lists, two conditional scenarios | 8,566; 1,464 in 12 months | No (decision 2) |
| `#wzrd-lessons` | "WZRD Lesson N" text lessons, 1 to 115 | 155 posts | Yes, all |
| `#wzrd-bible`, `#wzrd-risk-management`, `#wzrd-trends` | The method as PDFs (7.6, 6.6, 2.5 MB) | 3 PDFs | Approved, blocked (decision 1) |
| `#wzrd-spot-setups`, `#wzrd-macro-dca`, `#wzrd-chat-hodl` | Older spot, DCA and long-term holds (2021–2023) | 19, 33, 98 | No: old, not scalps |
| `#wzrd-forex-setups` | FX and indices (FOREXWZRD) | 5,360 | No: not crypto |

Pages read: 15 (`SL`) + 12 (`please close`) + 7 (lessons) = 34 search pages, plus one look at each info channel.

## 2. How a setup is given

### Trade call (the test set), in `#wzrd-chat-crypto`
A fixed template, staff only, roughly 10 a month:

| Field | How it appears | Notes |
|---|---|---|
| Pair | `<COIN> Trade Update: (Risky-Scalp)`; `2ND`/`3RD` marks a second trade on the same coin | Coin only; their charts say `BINANCE:<COIN>USDT`, so we test Binance spot USDT pairs |
| Side | `LONG Entry` / `SHORT Entry`, or a custom emoji (not in the page text) | 78 of 126 sides inferred from the stop (stop below entry = long) |
| Entry | "Now or as close to $X" | Market at post time; 9 calls sit 2–3% below the market (a pullback limit) |
| Stop | `SL: $Y` | Always present; median 3.86% from entry (p10 2.2%, p90 7.2%) |
| Breakeven | "B/E Move: When it moves close to TP2" | Identical in all 126 |
| Targets | `TP 1..4: $T (Close 25% / 30% / another 25% / remaining 20%)` | 124 of 126 use this ladder; median 0.53R, 0.99R, 1.52R, 2.38R |
| Timeframe | Not in the text; every chart (125 of 125) is 1h | From Sonnet vision on the attached chart |
| Reasoning | One to three sentences after the TPs | Mostly "bullish breakout / reversal", always with a Bitcoin caveat |
| Boilerplate | Risk disclaimer, "patience is needed" | Dropped from the stored reasoning |
| Chart | TradingView snapshot with a long/short position box | 124 of 125 charts show the post's own levels |

### Follow-ups (linked to their call by coin and trade number)
1. **TP hit:** a joke banner, then "OUR XRP TRADE JUST HIT THE FIRST TAKE PROFIT", the claimed pips and "% raw gain", and "Please close 25% of the trade". Seen for TP1 (84), TP2 (63), TP3 (43) on crypto calls; never TP4.
2. **Close:** "Please close the LINK trade." plus a reason: Bitcoin weakness, macro or Trump news, lost momentum. 17 of 82 closes come after TP1.
3. **Never a loss post.** No "stop hit" message exists in 12 months of follow-ups. Losers end in silence or in a discretionary close.
4. Close posts restate the entry rule (29 times): "entered upon strong bullish breakouts on both the H1 & H4 timeframes".

### Not collected (other formats)
1. **Intraday Setup** (`#wzrd-crypto-setups`): support and resistance lists and two "if-then" scenarios: below a level means short ("Red WZRD Projection"), above another means long ("Blue"). No stop, no targets, ~4 a day. Testable as conditional breakouts with assumed exits.
2. **WZRD ALPHA** (`#wzrd-chat-crypto`): "The chart explains all, breakout points, criteria and targets." The levels exist only in the image, ~15 a day.

## 3. What became events

`data/cryptowizard/events.jsonl` (shared record shape from the hand-over), 670 events:

| Type | Count | ok | needs_review | Why review |
|---|---|---|---|---|
| `call` (open) | 126 | 116 | 10 | 9 entries 2–3% off the market minute; 1 chart that doesn't show the post's levels |
| `trade` trim (TP hit) | 190 | 182 | 8 | the claimed TP never traded on Binance spot between call and claim |
| `trade` close | 82 | 80 | 2 | no matching call in the window |
| `rule` (lessons) | 272 | 220 | 52 | paraphrase over 15 words (43), quote or number not found in the lesson (9) |

Skipped, each listed in `skipped.jsonl` with its reason: 30 non-crypto posts (S&P, Nasdaq, Russell, Dow, oil, USDCAD calls in the same channel), 10 giveaway promos, 2 commentary posts. Lessons: 64 of 115 extracted; 51 macro essays skipped by title (inflation, gold, the Fed), listed in `lessons_index.jsonl`.

Numbers come from code (regex on the template), never from the model. Two typos fixed in code and flagged: `$111, 928` and `$0.0.06390`.

## 4. Code checks

| Check | Rule | Result |
|---|---|---|
| `quote_ok` | Quote is an exact substring of the post, 12 words max | all calls and follow-ups |
| `numbers_ok` | Entry, stop and every target appear in the post | 126 of 126 |
| `ticker_ok` | Pair listed on Binance spot | 16 of 16 coins |
| `price_ok` (call) | Entry within 2% of the 1-minute close at the post minute | 113 of 122 with bars |
| `price_ok` (TP hit) | The claimed target traded between call and claim | 172 of 180 |
| `chart_ok` | The chart shows at least 3 of the post's levels | 124 of 125 |
| `why_ok` | Paraphrase ≤ 15 words, no number the post lacks | 208 of 208 (v2) |

## 5. Test sketch (story 1 owns the real engine)

`app/collect/cryptowizard/score_calls.py` follows AGENTS.md contract 2: entry at the first 1-minute open at or after post + delay; stop or target, stop first when both trade in one bar; their own close + delay; else 24 hours; 25 bps per side; baseline = holding the same coin over the same minutes. Binance spot 1-minute bars, cached under `data/bars/binance/`.

122 calls scored (4 HYPE calls predate HYPE's Binance bars). Average net return per trade:

| Delay | TP1 only | Ladder as posted | Managed (their closes) | Hold same coin |
|---|---|---|---|---|
| 1 min | −0.61% (64% hit TP1) | −0.62% | −0.62% | −0.69% |
| 5 min | −0.60% (63%) | −0.60% | −0.58% | −0.64% |
| 60 min | −0.61% (51%) | −0.55% | −0.58% | −0.53% |

Reading:
1. Before costs the ladder is about flat (−0.10% per trade); the 0.50% round-trip cost makes it negative.
2. TP1 sits at about half the risk (0.53R), so "TP1 hit" is frequent (63%) while the average R stays negative (−0.15R).
3. Their posts claim an average 3.2% "raw gain" per TP post; our bars confirm the levels traded (172 of 180) but not the money, because the losers are never posted.
4. The calls track the coin: they beat holding it in 59 of 122 trades, about a coin flip. The year was a falling market (BTC calls went from $107k to $80k).
5. Small sample, one year, one regime. Not a verdict.

Open question for story 1: "Now or as close to $X" with X 2–3% under the market reads like a limit order. The contract's trigger rule would then fill at X or not at all.

## 6. Strategy as rules (`data/cryptowizard/strategy.spec.json`, draft v0)

1. **Universe:** BTC, XRP, ETH, LINK, BNB, plus 11 altcoins they called (Binance USDT pairs).
2. **Entry:** breakout of a hand-drawn "WZRD line", confirmed on both H1 and H4; enter at the post.
3. **Stop:** fixed price in the post, median 3.9% away.
4. **Targets:** four TPs at about 0.5R, 1R, 1.5R and 2.4R, closing 25/30/25/20%.
5. **Breakeven:** stop to entry near TP2 (coded: after TP2 trades).
6. **Exit early:** when Bitcoin weakens or macro news hits (discretionary, 82 times).
7. **Lessons add:** breakouts need two candles to confirm a horizontal line, one close for a trendline; wait for a retest to avoid fakeouts; trade UK 10:00–17:00 (the only time rule with numbers); don't over-leverage; risk a fixed amount per margin trade.

Only 2 of 220 checked lesson rules are codeable in the closed vocabulary (inside bar, session window); the rest need chart-pattern recognition or judgment.

## 7. What can't be tested

1. Where the WZRD lines are drawn: hand-made, published only inside their charts.
2. "Unless Bitcoin crashes": discretionary, no threshold.
3. Macro and Trump-news calls: no point-in-time news data.
4. Chart patterns as triggers (triangles, H&S, wedges): needs a pattern detector.
5. Their real fills: they trade on Bybit (partner links); we price on Binance spot. Bybit's API is geo-blocked from here.
6. Losing trades they never followed up on: we only know them from the bars.

## 8. PRISM material (story 2 decides what to show)

1. **Failure:** extractor v1 (20 posts per call, plain JSON parse) broke JSON in 4 of 11 batches and wrote paraphrases up to 19 words: 10 of 11 runs failed. Our sentence: asking for 20 paraphrases in one reply makes the model drop the JSON shape and overrun the word cap.
2. **Fix:** v2 (10 per call, a 12-word target under the 15-word cap, JSON cut from any prose, one repair call).
3. **Score:** our evaluator (`evaluate.py`: present, ≤ 15 words, no new numbers, valid tags) on the same 208 posts: v1 44%, v2 100%.
4. These runs were traced to PRISM before the contract limited tracing to the LPP proof set, under agent ids `cw-extractor-v1`, `cw-extractor-v2`, `cw-rules-v1`, `cw-chart-reader-v1` (not the contract id `extract-cryptowizard-v1`). Tracing is now off unless `CW_TRACE=1`.

## 9. Files and rerun

Scripts in `app/collect/cryptowizard/` (run with `~/dev/quant-bot/app/.venv/bin/python`, in this order): `parse_posts.py` → `fetch_charts.py` → `bars.py` → `enrich_why.py v2` → `charts_vision.py` → `extract_rules.py` → `score_calls.py 5` → `build_events.py` → `strategy_spec.py` → `evaluate.py`.

Raw collection: `data/cryptowizard/raw/cw_posts_2026-10-17_{sl12,close12,lessons}.json`, saved from the Discord tab by browser download (Luis approved), 802 search hits, 595 unique posts.
