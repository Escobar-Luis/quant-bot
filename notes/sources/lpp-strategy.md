# Learn Plan Profit: his strategy, from the corrected record (spec-audit story 19, CAP-14, 2026-10-20)

Code: `app/backtest/strategy.py` (`cd app && uv run python -m backtest.strategy`). Key: `strategy_profile` in `results/lpp/v1.json` (shape: `contracts.md`, section `strategy_profile`). Recomputed independently by `app/audit/strategy.py` inside `audit.run` (PASS, 0 mismatches). Quotes are 12 words or fewer (AGENTS.md shared rule 5); "the host" is the course's host.

## For Luis

**His strategy**
1. Shorts, mostly: 80% of trades.
2. First half hour: 71%.
3. Tesla: shorted 78% of the time.
4. Adds often, losers more than winners.
5. Rarely closes on air: 55% assumed.

**Where the losses come from**
1. Big tech, added to losers.
2. Shorts left open past 3 h.
3. Big tech shorts into resistance.

## 1. What was measured

1. Trades: the headline's 342 copied trades (rule 13, no look-ahead; portfolio `all`; entered 5 min after each post; after the cash cap). 187 sessions, 2024-08-15 to 2025-09-12. Copied P&L −$264.55 (the headline's $9,735.45), 50% won.
2. Features per trade, by code: ticker and its group, long or short, the ET time he posted the first leg, his stated reason (the keyword setups from `app/backtest/lpp.py`), adds (to a loser: any add at a worse price than his average so far), how it ended (stated on the stream, or assumed at 15:55 ET), hold time, his size on the first buy, and his trades that day.
3. Model step (`daytrader-strategy-v1`, Claude Sonnet via Nicrron): given only the tables and 40 short rule quotes, it proposed 8 rules, each with a checkable `when` (situation) and `does` (what he does). Code kept a rule only with 15+ trades and followed 60%+ of the time, and drops a rule whose `does` repeats its `when` or allows every value: all 8 passed. Hedge words ("usually", "almost always") are replaced by the measured share. PRISM run: https://prism.blockconvey.com/trajectories/678d0b05-4e5a-45d8-9bd7-08e9b22ef604. Spend: $0.08 of the $3 cap (two calls: prompt strategy-v1, then strategy-v1.1 asking for specific rules and quotes that agree; replies cached in `data/lpp/strategy/`).

## 2. The rules (code-checked; P&L is the copied P&L of the trades that follow the rule)

| # | Rule (model's wording, hedges replaced by the measured share) | Situation | Follows | Trades | Won | P&L |
|---|---|---|---|---|---|---|
| S1 | He trades the short side, betting stocks will fall (80% of the time).  | all 342 | 80.1% | 274 | 51% | −$610.85 |
| S2 | He opens trades in the first half hour after the market opens (71% of the time).  | all 342 | 70.5% | 241 | 52% | −$334.64 |
| S3 | When he trades Tesla, he is betting it will fall (78% of the time).  | 83 TSLA | 78.3% | 65 | 45% | −$1,613.39 |
| S4 | He shorts hot small and mid caps after a big run-up, in the first hour of trading (93% of the time).  | 45 | 93.3% | 42 | 57% | +$568.72 |
| S5 | His crypto-linked trades, such as Coinbase and MicroStrategy, are shorts (85% of the time).  | 61 | 85.2% | 52 | 54% | +$569.49 |
| S6 | When he buys a dip, he enters in the opening half hour (61% of the time).  | 49 | 61.2% | 30 | 43% | +$16.85 |
| S7 | When he adds to a losing trade, he ends up holding it for three hours or more (66% of the time).  | 133 | 66.2% | 88 | 38% | −$1,942.65 |
| S8 | He keeps his first buy under $50,000, $10,000 to $50,000 (65% of the time).  | all 342 | 64.9% | 222 | 54% | −$104.96 |

Quotes the model attached (his own words): "I want to wait for those overbought levels" (2025-01-21, S4); "remember if you enter early watch that position size" (2025-02-14, S2). Review of PR #67: S1's quote (a reversal setup) and S8's (mind your size) don't say what their rule says, so both show no quote (`quote_hidden`); story 25 checks every pair.

## 3. The tables (342 trades)

1. **Side:** short 274 (51% won, −$610.85, avg win $45.96, avg loss −$51.85); long 68 (46%, +$346.30).
2. **Group:** big tech 141 (44%, −$1,975.49); hot small and mid caps 126 (54%, +$957.55); crypto-linked 61 (52%, +$533.44); index funds 6; other 8.
3. **Tickers:** TSLA 83 (24%; 42% won, −$1,929.83), NVDA 51 (+$67.08), PLTR 35 (+$133.91), MSTR 34 (62%, +$868.23), HIMS 30 (−$48.53), SOUN 23 (65%, +$696.91), HOOD 18, then SMCI, SOFI 9 each, COIN 8 (12% won, −$469.27).
4. **Time he posts the first leg (ET):** 09:30-09:45 155 (45%, −$109.46); 09:45 85 (−$270.21); 10:00 59 (+$414.07); 10:15 31; after 10:30 only 11 (2 won). Streams end about 10:30.
5. **His stated reason:** overbought run 97 (−$441.66); resistance 52 (58% won but avg loss −$75.38 vs avg win $28.42: −$805.79); breakdown 52 (+$613.99); dip buys 49 (41%, −$224.01); no repeatable reason, shorts 73 (+$22.61), longs 19 (+$570.31).
6. **Adds:** he posted 671 adds on 263 trades and 366 trims on 177. Of the 226 copies with 2+ buys, 133 added to a loser (43% won, −$1,479.68, avg loss −$78.10) and 93 to a winner (61%, +$1,413.37). No adds: 116 (−$198.24).
7. **How it ended:** he said he closed on the stream on 153 (54% won, +$1,331.11); 189 (55%) had no stated close and left at 15:55 ET by rule 13 (46%, −$1,595.66; avg loss −$71.18).
8. **Hold:** under 15 min 92 (+$245.41); 15-60 min 59 (64% won, +$1,034.82); 3 h or more 186 (−$1,952.81, nearly all the assumed 15:55 exits); overnight 4.
9. **Size (his first buy):** median 100 shares, about $21,093 (90th percentile $58,785; stated on 255 of 342). $50k+ first buys won 33%.
10. **Trades per session:** median 2, max 5. Sessions with one trade: 93 trades, 43% won, −$967.30.

## 4. Where his losses come from (feeds story 20)

Picked by code from every one-feature condition and every pair of what he traded with how he traded it (15+ trades), by total P&L, skipping a pattern that mostly repeats an earlier pick. "Share of losses" = its losing trades' dollars over all losing trades' dollars ($8,141.74 gross); patterns overlap, so shares don't add up.

| # | Pattern | Trades | Won | P&L | Avg win / loss | Share of losses |
|---|---|---|---|---|---|---|
| 1 | Big tech, added to a loser | 51 | 31% | −$2,270.68 | $21.40 / −$74.66 | 32.1% |
| 2 | Shorts held 3 h or more | 159 | 47% | −$2,233.42 | $56.12 / −$76.70 | 79.1% |
| 3 | Big tech, short into resistance | 27 | 52% | −$878.22 | $28.67 / −$98.43 | 15.7% |

1. Adding to a losing big-tech position is the single worst habit: wins are small, losses three times bigger.
2. Pattern 2 is mostly rule 13's assumed exit: he didn't say he closed on the stream, so the copy holds to 15:55 ET. His chat says he closes during the day, often after the stream (notes/sources/lpp-discord-exits.md), so part of this loss may be the copy's, not his (stories 23, 24).
3. Short-into-resistance wins more often than not (52%) but loses big when it's wrong.
4. **Worst 10 days:** every one has a trade with an assumed exit and 9 of 10 an add to a loser; 14 trades, 13 of them shorts. The worst, 2025-04-09 (TSLA and DJT shorts), lost $784.40.

## 5. Caveats

1. Setups come from keyword rules on his stated reason (one-line paraphrases), not from charts.
2. "Added to a loser" compares the copy's fill prices at 5 min, not his own fills.
3. Ticker groups are by what the company is, set in code (`TICKER_GROUPS`); PLTR, SOUN and HIMS count as hot small and mid caps.
4. Trades he made off the stream (afternoons, premarket) are not in the record (story 24).
