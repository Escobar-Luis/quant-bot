# ZipTrader: events summary

Window: 2026-01-08 to 2026-10-16. 13 sources, 86 events (65 setups, 14 rules, 7 calls). 85 passed every code check; 1 need review.

## Per month

| Month | Trades | Calls | Setups | Rules | Need review |
|---|---|---|---|---|---|
| 2026-01 | 0 | 0 | 0 | 14 | 0 |
| 2026-10 | 0 | 7 | 65 | 0 | 1 |

## What gets traded

- Top tickers (checked events): MU 5, NVDA 5, NKE 3, TSLA 3, APLD 3, CRWV 3, TSM 3, ACN 2, STX 2, STZ 2, PEP 2, DAL 2.
- Sides: long 1.
- Events with an entry, stop or target level: 0.

How a trade is tested: entry at the first 1-minute bar at post time + delay; exit at the course's own close + delay, else stop or target, else the stated horizon, else 15:55 ET (day), 5 sessions (swing), 24 h (crypto). Costs per side: 5 bps, 20 bps under $10, 25 bps crypto. Code decides, not the model.
