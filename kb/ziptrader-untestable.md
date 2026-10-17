# ZipTrader: what we can't test, and why

1 of 86 events failed a code check and are left out of the money result. Each kind, with one example:

| Check failed | Events | Means | Example |
|---|---|---|---|
| numbers_ok | 1 | Flagged by a code check. | "NII guidance and credit provisions over headline EPS" (dc:634554429689036830/1559548352948080751) |

## Not priced at all

- Options mentioned in 0 trades or calls: counted, not priced (no free options price history).
- Futures (ES, MES, MNQ, NQ, RTY, YM): 0 events; no free 2024-25 futures minute bars.
- Exits he never announced are assumed (15:55 ET for day trades) and listed as assumed in the results.
