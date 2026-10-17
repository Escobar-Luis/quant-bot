# Learn Plan Profit: events summary

Window: 2024-08-15 to 2025-09-12. 244 sources, 4196 events (1775 trades, 1645 rules, 776 calls). 3000 passed every code check; 1196 need review.

## Per month

| Month | Trades | Calls | Setups | Rules | Need review |
|---|---|---|---|---|---|
| 2024-08 | 60 | 40 | 0 | 83 | 74 |
| 2024-09 | 88 | 48 | 0 | 112 | 79 |
| 2024-10 | 51 | 59 | 0 | 110 | 73 |
| 2024-11 | 87 | 64 | 0 | 139 | 132 |
| 2024-12 | 104 | 84 | 0 | 144 | 83 |
| 2025-01 | 128 | 67 | 0 | 132 | 111 |
| 2025-02 | 88 | 63 | 0 | 108 | 74 |
| 2025-03 | 160 | 39 | 0 | 109 | 73 |
| 2025-04 | 184 | 54 | 0 | 146 | 80 |
| 2025-05 | 218 | 61 | 0 | 131 | 91 |
| 2025-06 | 129 | 42 | 0 | 94 | 71 |
| 2025-07 | 228 | 76 | 0 | 164 | 113 |
| 2025-08 | 174 | 53 | 0 | 119 | 98 |
| 2025-09 | 76 | 26 | 0 | 54 | 44 |

## What gets traded

- Top tickers (checked events): TSLA 491, NVDA 265, PLTR 234, MSTR 155, HIMS 148, HOOD 129, SOUN 109, SOFI 67, QQQ 51, SMCI 42, RDDT 42, COIN 34.
- Sides: short 1456, long 319.
- Events with an entry, stop or target level: 249.
- Live sessions read: 246 of 247; round trips (open and close both said): 159; positions still open at the end of a session: 206.
- Share of airtime spent on trading: 37.6% on average.

How a trade is tested: entry at the first 1-minute bar at post time + delay; exit at the course's own close + delay, else stop or target, else the stated horizon, else 15:55 ET (day), 5 sessions (swing), 24 h (crypto). Costs per side: 5 bps, 20 bps under $10, 25 bps crypto. Code decides, not the model.
