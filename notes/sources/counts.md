# Counts per course (audit story 1, CAP-1)

How many sources each course has on disk, how many events extraction produced, how many passed every code check, and how many trades the backtest priced. Regenerate with:

```
cd app && uv run python -m audit.counts          # or --json
```

It reads the gitignored `data/` in the main checkout and the committed `results/`. Output on 2026-10-20 (main 4c196aa + story/extract-lpp):

```
== lpp
  sources: links (urls_12mo.txt) 247, captions on disk 246, no captions 1, not fetched 0, other folders (2018 seed) 23, sources.jsonl 247
  v1 events 4196 (call 776, rule 1645, trade 1775); passed every check 2883, in review 1313; posted 2024-08-15 to 2025-09-12
  v1 priced (results/lpp/v1.json): 315 trades at 5 min [1m 315, 3m 315, 5m 315, 10m 315, 15m 315, 30m 315, 60m 315]; by portfolio {'all': 315, 'day': 272, 'swing': 43}; 200 trade rows in file
  v1 window 2024-08-15 to 2025-09-12, sealed from 2025-06-12
  v2 events 4128 (call 771, rule 1589, trade 1768); passed every check 3773, in review 355; posted 2024-08-15 to 2025-09-12
  v2 priced (results/lpp/v2.json): 51 trades at 5 min [1m 51, 3m 51, 5m 51, 10m 51, 15m 51, 30m 51, 60m 51]; by portfolio {'all': 51, 'day': 50, 'swing': 1}; 51 trade rows in file
  v2 window 2024-08-15 to 2025-09-12, sealed from 2025-06-12
== ziptrader
  sources: sources.jsonl 13, #morning-briefing 12, #strategy-explained 1
  v1 events 86 (call 7, rule 14, setup 65); passed every check 85, in review 1; posted 2026-01-08 to 2026-10-16
  v1 priced (results/ziptrader/v1.json): 1 trades at 5 min [1m 1, 3m 1, 5m 1, 10m 1, 15m 1, 30m 1, 60m 1]; by portfolio {'all': 1, 'day': 0, 'swing': 1}; 1 trade rows in file
  v1 window 2026-10-01 to 2026-10-16, sealed from 2026-10-01
== cryptowizard
  sources: sources.jsonl 595, #wzrd-chat-crypto 440, #wzrd-lessons 155, skipped posts 42
  v1 events 670 (call 126, rule 272, trade 272); passed every check 598, in review 72; posted 2021-06-28 to 2026-10-16
  v1 priced (results/cryptowizard/v1.json): 122 trades at 5 min [1m 122, 3m 122, 5m 122, 10m 122, 15m 122, 30m 122, 60m 122]; by portfolio {'all': 122, 'crypto': 122}; 122 trade rows in file
  v1 window 2025-10-17 to 2026-10-16, sealed from 2026-07-16
```

Reading it:
1. **LPP sources.** 247 Discord links to morning live streams (2024-08-15 to 2025-09-12); 246 have English captions, 1 (`41ixdD2nUp0`) has none. The 23 extra folders are the Apr-May 2018 early sample, not in the year. Fetch: `uv run python -m lpp.fetch_captions --dry-run` (see that module).
2. **LPP events vs trades.** Events are trade legs (entries, trims, exits), calls and rules. The backtest pairs ok trade legs into 315 round trips; `results/lpp/v1.json` keeps a 200-row sample of them, so trades can't be summed from the file (story 2 writes the full ledger).
3. **LPP v2** prices only the 30-session PRISM proof set (51 trades), though its events cover all 247 sessions.
4. **Crypto Wizard** posts reach back to 2021 (lessons); only setups inside the window 2025-10-17 to 2026-10-16 are priced.
5. Trade counts are the same at every delay: a delay moves the fill, it doesn't drop the trade.

## ZipTrader: 86 events, 1 priced trade

Traced through `app/collect/ziptrader/extract_calls.py` (event types) and `app/backtest/ziptrader.py` `build()` (what gets priced). The briefings are a watch list, not trade calls, and the copier only copies an item that says which way to trade.

| Step | Dropped | Left | Why |
|---|---|---|---|
| All events | | 86 | 12 morning briefings (2026-10-01 to 10-16) + 1 strategy card |
| Not a trade item | 14 rules | 72 | The "Strategy Nutshell" card (2026-01-08, `#strategy-explained`): rules, never priced. Up to 12 short ones are shown as cited rules. |
| Failed a check | 1 setup | 71 | JPM: the paraphrase says "Q3", which its panel doesn't (`numbers_ok` false, `needs_review`). |
| No direction | 70 | 1 | 64 setups (ticker on the watch list, no side, no level) + 6 calls with a level but no side (NKE $32, SYNA $123, LEN $80, MU $950 support/resistance; CRWV, RKLB "previous low"). Counted as `watch_only`, not traded. |
| Priced | | **1** | PENG long, 2026-10-07 briefing; its quote says "more than one session", so it is a swing trade with the 5-session exit assumed. |

So the 1 is by design, not a loss in the pipeline: the collector types side-less tickers as `setup` (its docstring keeps them for a weak "beat SPY that session?" test, which isn't built), and the loader requires `side` long or short. Turning a support level into a long would invent a trade the course never posted.

Two things found on the way:
1. `results/ziptrader/v1.json` `unknown` says "Only 13 briefings"; there are 12 briefings. `build()` counts distinct `source_id`s, which includes the strategy card.
2. Only 12 briefings (two weeks) were collected, so even if every call had a side, the count would stay under the 30-trade bar for a verdict.
