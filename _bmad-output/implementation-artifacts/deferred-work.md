# Deferred work

## Deferred from: code review of story extract-lpp, PR #18 (2026-10-17)

- **Held-out gold session.** The v0 → v1 prompt was tuned on the same 5 gold sessions it is scored on; one or two more gold sessions, drafted blind and never used for tuning, would check that the 96%/100% (v2) numbers hold. `app/lpp/gold.py`
- **Call and rule metrics are loose.** A call matches on ticker within 60 s (level and direction not compared); a rule matches any rule within 60 s (wording not compared). Fine as a first bar; compare level, side and wording before quoting call precision or rule recall in the demo. `app/lpp/gold.py` `_match`
- **The 30 `extract-lpp-v1` PRISM runs predate the trace contract.** They carry `conversation_id = lpp-<video_id>-lpp-v1` and no `metadata`. Changing them means re-sending 30 traces (credits, duplicate runs in Root Cause), so they stay; v2 and later sends follow `contracts.md`. `app/lpp/prism.py`
- **Rate-limit back-off has no unit test.** A fake client raising `RateLimitError` N times, then returning JSON, would pin "same model, no fallback". The full runs already passed through it (11 rate limits, all recovered). `app/lpp/extract.py`
- **Caption-split numbers.** "9 60" for $9.60 is not joined, so such a price fails `numbers_ok`. Joining adjacent tokens risks false matches ("500 shares 100"); revisit if `number_not_*` failures show this pattern. `app/lpp/checks.py`
- **Daily-range fallback uses split-adjusted yfinance bars.** Only 3 events fell back to it once Alpaca keys arrived; a split inside the window could misfire there. `app/lpp/checks.py` `_price_ok`
- **Sealed window and per-delay portfolios** for the copy-the-host test belong to story 1 (`app/backtest/`, `contracts.md` rules 2-10); `app/lpp/copytest.py` is the LPP-side design and a first pass.
- **Knowledge Base docs from the extracted rules** (Proof 1) belong to story 2; the 1,123 ok rules in `data/lpp/events.jsonl` are the input.
