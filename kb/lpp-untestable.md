# Learn Plan Profit: what we can't test, and why

1196 of 4196 events failed a code check and are left out of the money result. Each kind, with one example:

| Check failed | Events | Means | Example |
|---|---|---|---|
| quote_too_long | 701 | The model's quote ran over 12 words. | "there's no confirmation just yet which means that no reason to enter" (yt:A4929OT4Jls t=641s) |
| open_never_closed | 206 | He opened a trade and never said he closed it; the exit is assumed. | "shorting 1,000 shares of Nvidia" (yt:A4929OT4Jls t=1492s) |
| close_without_open | 189 | A close with no matching open earlier in the session. | "just going to buy them to cover which means closing out my" (yt:IWWdGdI6_kQ t=2084s) |
| number_not_near_quote | 61 | The number is in the transcript, but not near the quoted words. | "19 1970 1990 right around $20 per share" (yt:opYYXya051w t=389s) |
| number_not_in_source | 41 | A number the model reported is never said. | "let's see 124 124 30" (yt:Jds31wPEh1U t=945s) |
| qty_exceeds_position | 41 | Sold more shares than the position held. | "reduce it by 600 shares reducing my position size in half" (yt:gHkL5yEdOzw t=355s) |
| price_off_day_range | 20 | The price is outside that day's trading range. | "I'm buying a thousand shares of SQ right around 749 to 750" (yt:YBzTRwygnIM t=755s) |
| quote_not_in_source | 16 | The quote isn't in the source. | "my position size would have to be relatively pretty light" (yt:aGwIY9Lz9x8 t=1750s) |
| ticker_unresolved | 9 | The ticker couldn't be matched to a real symbol. | "constant support here right around 930 940" (yt:i8qXf2qniaQ t=2393s) |
| ticker_unknown | 7 | The ticker isn't a known symbol. | "if we break below this like 214 215 support" (yt:ZWasZSbOBpk t=835s) |

## Not priced at all

- Options mentioned in 5 trades or calls: counted, not priced (no free options price history).
- Futures (ES, MES, MNQ, NQ, RTY, YM): 0 events; no free 2024-25 futures minute bars.
- Sessions with no captions: 1; sessions the extractor failed on: 0.
- Exits he never announced are assumed (15:55 ET for day trades) and listed as assumed in the results.
