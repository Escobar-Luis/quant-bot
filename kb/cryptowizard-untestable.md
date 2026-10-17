# Crypto Wizard: what we can't test, and why

72 of 670 events failed a code check and are left out of the money result. Each kind, with one example:

| Check failed | Events | Means | Example |
|---|---|---|---|
| rule_words_ok | 46 | Flagged by a code check. | "A Doji should be smaller than them." (dc:855852754392449065/859085107357155339) |
| price_ok | 17 | Flagged by a code check. | "OUR BNB TRADE JUST HIT THE FIRST TAKE PROFIT" (dc:639277011164200960/1436471423618257040) |
| numbers_ok | 5 | Flagged by a code check. | "requires two candles to confirm a breakout" (dc:855852754392449065/1009497577361768549) |
| quote_ok | 4 | Flagged by a code check. | "A price break above the peak (or 'neckline') sandwiched between the two …" (dc:855852754392449065/1136012837039394887) |
| unlinked | 2 | Flagged by a code check. | "Please close the BTC trade" (dc:639277011164200960/1456687073653424355) |
| chart_ok | 1 | Flagged by a code check. | "TP 4: $64,128.00." (dc:639277011164200960/1522174405868916776) |

## Not priced at all

- Options mentioned in 0 trades or calls: counted, not priced (no free options price history).
- Futures (ES, MES, MNQ, NQ, RTY, YM): 0 events; no free 2024-25 futures minute bars.
- Exits he never announced are assumed (15:55 ET for day trades) and listed as assumed in the results.
