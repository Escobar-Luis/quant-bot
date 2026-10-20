# Backtesting with an LLM in the loop: sources and what to do (2026-10-17)

Tag: **[R]** = I read the paper text or docs; **[A]** = abstract or search summary only. Paper ≠ peer reviewed unless it says journal.

## Bottom line for our build
1. "Pretend it's 2019" prompts don't stop recall; only post-cutoff data or time-partitioned models do (sec 1).
2. Every v1→vN tweak is a trial. Log N, hold out a final window, report a deflated Sharpe (sec 2).
3. LLM trading edges shrink or vanish on longer, wider tests; a flat holdout is a legitimate finding (sec 1).
4. Saturday: Alpaca paper + crypto; keyless public crypto data verified live today (sec 4).

## 1. LLM look-ahead and memorization: the evidence
- Lopez-Lira, Tang, Zhu, 2025, preprint [R]: GPT-4o (cutoff Oct 2023) recalls S&P 500 closes with 0.61% mean error pre-cutoff; post-cutoff 16.9% error, 45.7% direction (coin flip). https://arxiv.org/abs/2504.14765
  - Told to ignore info after a fake cutoff, it still scored 98% on a GDP question (real post-cutoff accuracy 40%). Masking failed: it named the company in 100% of Apple/Meta/Microsoft calls. One model, small post-cutoff n.
- Sarkar & Vafa, 2024, NBER conference paper [R]: direct tests find look-ahead in LLM earnings-call risk prediction; prompting can't fix it; train only on pre-period text. https://conference.nber.org/conf_papers/f205530/f205530.pdf
- Gao, Jiang, Yan, 2025, preprint [R]: "Lookahead Propensity" test. for Llama-3.3-70B, +1 s.d. of recall adds ~32% to the headline signal's predictive effect; the interaction is insignificant after the Dec 2023 cutoff. https://arxiv.org/abs/2512.23847
- Yan et al. (DatedGPT), 2026, preprint [R]: headline-sentiment Sharpe 3.65 with a 2024-trained model on 2014-24 vs 3.20 look-ahead-free (+14%). https://arxiv.org/abs/2603.11838
- Benhenda (Look-Ahead-Bench), 2026, preprint [R]: Llama 3.1 and DeepSeek 3.2 lose 15 to 22 points of alpha moving from 2021 to 2024 windows. Proof of concept, 5 stocks. https://arxiv.org/abs/2601.13770
- Li, Kim, Cucuringu, Ma (FINSABER), KDD 2026 [R]: LLM agent edges "deteriorate significantly" over 2000-2024 and 100+ symbols; FinMem's published TSLA Sharpe 2.68 became 0.93 when re-run with GPT-4o-mini. Authors say look-ahead is not fully removed. https://arxiv.org/abs/2505.07078
- Glasserman & Lin, 2023, preprint [R abstract]: counter-evidence. In-sample, anonymized headlines did *better* (a "distraction" effect); out-of-sample look-ahead "not a concern". https://arxiv.org/abs/2309.17322
- Roy & Roy (MemGuard-Alpha), 2026, preprint [R abstract]: membership-inference filters of contaminated signals did not improve risk-adjusted returns. Don't plan on detecting leakage. https://arxiv.org/abs/2603.26797

## 2. Mitigations and what each costs
- **Post-cutoff only** (best): used by Lopez-Lira & Tang 2023-25, [R abstract] https://arxiv.org/abs/2304.07619; and by 2504.14765 above. Need each model's published cutoff. **Not verified for the Nicrron Claude 5.x models.**
- **Anonymize tickers/dates**: Jeon & Lee, 2026 workshop paper, shuffled-score control drops rank IC 0.015→0.0004; they "do not claim this blocks all leakage" [R]. https://arxiv.org/abs/2603.17692 BTC/ETH can't be masked; treat as weak.
- **Honest holdout**: Arnott, Harvey, Markowitz, 2019, J. Financial Data Science [R]: true out-of-sample exists only live; tuning after peeking at the holdout makes it in-sample; log every trial. https://ssrn.com/abstract=3275654 (DOI 10.3905/jfds.2019.1.064)
- **Trials vs sample length**: Bailey, Borwein, López de Prado, Zhu, 2014, Notices of the AMS [R]: with 5 years of data, >45 independent configs nearly guarantees in-sample Sharpe 1 with out-of-sample 0; 7 configs suffice at 2 years. https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf
- **Deflated Sharpe Ratio**: Bailey & López de Prado, 2014, J. Portfolio Management [R]: inputs are N trials, variance of trial Sharpes, sample length T, skew, kurtosis. https://ssrn.com/abstract=2460551
- **Probability of Backtest Overfitting**: Bailey et al., 2017, J. Computational Finance [R abstract]: plain hold-out is "unreliable" for backtests. https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- **Higher bar**: Harvey, Liu, Zhu, 2016, Rev. Financial Studies [R abstract]: new factors need t > 3.0, not 2.0, after many tries. https://www.nber.org/papers/w20592
- **Purged k-fold, embargo, CPCV**: López de Prado, *Advances in Financial Machine Learning*, Wiley 2018 (ISBN 978-1-119-48208-6; ch. 7 and 12) [A]. https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086
- **Disclosure frame**: SEC Marketing Rule (Dec 2020) treats backtests as "hypothetical performance" needing stated assumptions and limits [A, not read]. https://www.sec.gov/files/rules/final/2020/ia-5653.pdf

## 3. What fits 5 hours (my recommendation)
1. Fixed windows: dev windows (LLM sees metrics) and one locked holdout the LLM never sees until the last version. Never re-tune after the holdout (Arnott 4b).
2. Trial log = the version table: params, dev Sharpe, N so far. About 30 lines of Python give a DSR on the final pick. Use N = number of versions (conservative; versions are correlated).
3. LLM sees metrics and relative labels ("window A"), not tickers or dates. Pick windows after the model's cutoff if the provider publishes one; else label them "contaminated".
4. Include costs: Alpaca live crypto taker fee is 25 bps at the lowest tier (docs, below); paper fees not stated, so assume 25 bps.
5. Skip full CPCV and purged k-fold (overkill). Walk-forward plus a one-bar embargo is enough for next-bar labels.
6. Demo honesty: show dev vs holdout per version, DSR, N, and the cutoff caveat. Flat holdout = real finding. PRISM clusters = the trial history.

## 4. Today (Saturday, US equities closed)
- Alpaca paper supports crypto: "Paper trading simulates crypto trading as well." https://docs.alpaca.markets/docs/paper-trading (2026) [R]
- Crypto is "24 hours everyday" https://docs.alpaca.markets/docs/crypto-trading (2025); the docs never say paper is also 24/7. **Confirm with one paper order once you have keys.**
- Crypto paper limits [R]: market/limit/stop_limit; gtc/ioc only; no shorting or margin; fills simulated from live quotes, no slippage or impact modeled. https://docs.alpaca.markets/docs/crypto-orders
- Free data plan, equities [R]: IEX only, 30 websocket symbols, 200 calls/min, history since 2016. https://docs.alpaca.markets/docs/about-market-data-api (2026)
- **Verified today by me, no keys** (HTTP 200): Alpaca `data.alpaca.markets/v1beta3/crypto/us/bars` returned BTC/USD daily bars from 2021-01-01 (asked from 2015), and latest trade 2026-10-17 $81.3k. Docs only say historical crypto needs no auth; the API reference says keys are needed. Don't rely on keyless in the app.
- Also keyless, live today: Kraken `api.kraken.com/0/public/OHLC`, Binance `data-api.binance.vision/api/v3/klines`, Coinbase `api.exchange.coinbase.com/products/BTC-USD/candles`. Binance Spot Testnet (testnet.binance.vision) returned **HTTP 451** from this Mac: skip.
- CCXT: MIT, one API for 100+ exchanges, `set_sandbox_mode(True)` only where an exchange has a sandbox (you register there for keys); OHLCV history is capped per call (~1000), so paginate. https://docs.ccxt.com/docs/manual [R]
- Kraken CLI: docs say paper trading "without auth or capital" (not tried). https://docs.kraken.com/llms.txt [A]
- yfinance: no key, but "intended for personal use only", not affiliated with Yahoo; fine for a demo, not a product. https://github.com/ranaroussi/yfinance [R]
- **Luis's sign-ups:** (1) Alpaca "Paper Only" account at https://app.alpaca.markets/signup: docs say email only, $100k default; no ID or funding stated. (2) Generate paper API keys in the dashboard sidebar; put key ID and secret in `app/.env` (names in `.env.example`). Base URL `https://paper-api.alpaca.markets`; SDK `alpaca-py`. (3) Nothing else: Kraken, Binance, Coinbase public data need no account. Nicrron and PRISM keys already work.

## 5. Sentiment as a feature
- Tetlock, 2007, J. Finance [A]: WSJ-column pessimism predicts a dip then reversion, but low returns also *cause* pessimism (reverse causality). https://papers.ssrn.com/abstract=685145
- Bollen, Mao, Zeng, 2011, J. Computational Science [R]: reported 87.6% daily DJIA direction from Twitter mood. https://arxiv.org/abs/1010.3003
  - Lachanski & Pav, 2017, Econ Journal Watch [R]: couldn't reproduce it, consistent with data snooping, no out-of-sample value; the fund built on it closed in 2012. https://econjwatch.org/articles/shy-of-the-character-limit-twitter-mood-predicts-the-stock-market-revisited
- Ke, Kelly, Xiu, 2019, NBER w26186 [A]: supervised news-text sentiment; prices adjust with a delay, more so for small, volatile stocks. https://www.nber.org/papers/w26186
- Lopez-Lira & Tang, v6 2025 [R abstract]: GPT-4 scores on post-cutoff headlines predict drift (small stocks, bad news); returns fall as LLM adoption rises. https://arxiv.org/abs/2304.07619
- Leakage is highest here: headline sentiment is the exact task in the Gao, DatedGPT and Glasserman studies above. Only post-cutoff headlines are clean.
- Gap: all of this is equities. I found no crypto-specific sentiment study I'd trust. Verdict: skip for v1; add later only on post-cutoff timestamps.

## Not verified
- Nicrron model training cutoffs; Alpaca paper crypto fees; Loughran & McDonald 2011 and López de Prado's "10 Reasons ML Funds Fail" (SSRN blocked me); AFML chapter contents (secondary only).

## 6. Version log: improver v2, rule changes from LPP's losses (spec-audit story 20, CAP-15, 2026-10-20)

Every variant tried, with dev and sealed numbers (AGENTS.md rule 4). Code: `app/backtest/improvements.py` (`cd app && uv run python -m backtest.improver --v2`); key `improvements` in `results/lpp/v1.json` (shape: `contracts.md`, section `improvements`); recomputed independently by `app/audit/improvements.py` inside `audit.run` (PASS, 0 mismatches).

1. **Basis:** the headline's 342 copied trades (rule 13, `all`, 5 min, cash cap); each change re-prices every position, one full-window run; dev = first buy before 2025-06-12 (2024-08-15 to 2025-06-11, 239 trades as-is), sealed = 2025-06-12 to 2025-09-12 (103 trades as-is). Return = summed copied P&L / $10,000. SPY = total return (dividends reinvested).
2. **As-is:** dev −4.73%, sealed +2.08% (the headline's sealed block). SPY: dev +10.47%, sealed +9.64%.
3. **Model step:** `daytrader-improver-v2` (Claude Sonnet via Nicrron, prompt `improver-v2`), one call, $0.03 of the $3 cap; it saw only the dev-month strategy_profile tables, setups, top 5 dev losing patterns and his rules' wording, never a sealed number. PRISM run: https://prism.blockconvey.com/trajectories/6efa6a02-ea2a-47a2-8d25-5e3d72a7826c (re-run after the PR #68 review, same cached reply; first run 4edf2a7f). Code rejected none of its 6 proposals.
4. **Keep rule (code, fixed before any run):** beats as-is on dev, does not lose on sealed, 30+ trades in each. Nothing re-tuned after the sealed numbers.

| # | Change (model's words) | Code applied | Dev trades | Dev return (vs as-is, pts) | Dev vs SPY | Sealed trades | Sealed return (vs as-is, pts) | Sealed vs SPY | Decision |
|---|---|---|---|---|---|---|---|---|---|
| V1 | In big tech trades, skip adds priced worse than the first buy's fill | `no_add_against` big tech | 239 | +6.94% (+11.67) | −3.53 | 104 | +4.12% (+2.04) | −5.52 | kept |
| V2 | Stop out shorts into resistance when price rises 2.5% against the entry | `stop_pct` 2.5, short-resistance | 239 | −2.68% (+2.05) | −13.15 | 103 | +2.17% (+0.09) | −7.47 | kept (held up, not proven) |
| V3 | Leave big tech trades 60 minutes after the first buy | `max_hold` 60, big tech | 239 | +9.95% (+14.68) | −0.52 | 104 | +3.86% (+1.78) | −5.78 | kept |
| V4 | Leave long trades 45 minutes after the first buy | `max_hold` 45, longs | 239 | −4.67% (+0.06) | −15.14 | 103 | −7.31% (−9.39) | −16.95 | not kept: lost on sealed |
| V5 | Skip PLTR trades | `skip` PLTR | 221 | −1.97% (+2.76) | −12.44 | 86 | −1.73% (−3.81) | −11.37 | not kept: lost on sealed |
| V6 | Skip big tech overbought shorts posted in the 09:30 half hour | `skip` short, big tech, short-overbought, 09:30 | 216 | +0.48% (+5.21) | −9.99 | 102 | +3.46% (+1.38) | −6.18 | kept |

**Also tried, by the engineer (smoke test of the machinery before the model ran; not candidates, not in the key, but their sealed numbers were seen):** skip TSLA shorts: dev 180 trades +10.22% (+14.95), sealed 98 +5.11% (+3.03); no adds against the first buy, big tech: same as V1; leave shorts 60 min after the first buy: dev +0.82% (+5.55), sealed −7.36% (−9.44); 2% stop on every trade: dev −9.76% (−5.03), sealed −7.49% (−9.57); only crypto-linked or hot small and mid caps: dev 100 trades +12.13% (+16.86), sealed 88 +5.28% (+3.20); skip `adds: to_loser` (rejected by code: known only after entry). The model's prompt was fixed before these ran and doesn't contain them.

**Read this as:** 10 distinct changes priced in all (the model's 6, 4 of them kept; 4 more by the engineer, whose 5th equals V1). Every kept change still trails just holding SPY on both dev and sealed months. Cutting time in a trade (V3, V4, the engineer's 60-min shorts) swings sealed results by single trades (V4's −9.39 pts is mostly one PLTR long on 2025-08-20 that gained $700 as-is by 15:55). The big tech changes (V1, V3) partly undo rule 13's assumed 15:55 exit, which story 23/24 may revise. Sealed gains of 0.2 to 2 pts on ~100 trades are within luck with 10 variants tried; no multiple-testing correction yet (story 27).

**Review fix (PR #68, same day, same cached proposals, same keep rule):** `setup` used his reason from any leg, so 35 of 343 positions got a reason he stated after the copy's first buy fill (up to 26 min later). Now only legs posted at or before the first fill count, else `unknown` (engine and audit, the audit from its own copy of the definitions). Only V2 moved: dev −2.27% → −2.68% (+2.46 → +2.05 pts vs as-is), sealed +2.29% → +2.17% (+0.21 → +0.09); still kept. The others are unchanged (V1, V3, V4, V5 don't use `setup`; V6's numbers came out the same). Before the fix V2's numbers were seen with the look-ahead setup: counted as the same variant, not a new one. The key now carries `variants_tried` (10 distinct priced), the disclosure, `kept_label` "held up (not proven)" and the luck test (story 27).

## 7. Trial log: his strategy as code (spec-audit story 21, 2026-10-20)
Pre-registered in `notes/research/strategy-as-code.md` (commit sha in `results/strategy-lab.json` `preregistered_sha`). Every version tried:
1. Universe picker v1, v2, v3 (pre-window data only; v3 kept): spec section 8.
2. Rule runs: S4 and S5 × variants `P`, `no-stop`, `exit-11`, `gap-10` × (a) his stocks and (b) other stocks, plus control C on all four universes: 20 runs, all published in `results/strategy-lab.json`.
3. After the first run: one bug fix (gap compared in floating point missed an exactly-5% gap; spec section 8 item 4), no rule change.
4. Results: spec section 9. Neither S4 nor S5 held up against SPY (+17.68%); S4 beat 2,000 random draws on both universes but earned +6% / +11%; S5 had no edge.

## 8. Trials per claim, and the luck tests (spec-audit story 28, CAP-16, 2026-10-20; absorbs story 27)
Code: `app/backtest/howsure.py` (`cd app && uv run python -m backtest.howsure`), output `results/how-sure.json` (shape: `contracts.md`, section `how-sure`); the luck tests and shuffle percentiles are recomputed by `app/audit/howsure.py` inside `audit.run`. No model call.

**Trials per family** (N in the deflated Sharpe or the Harvey–Liu haircut; every variant priced for that claim's whole window, whatever happened to it):

| Family | N | What was priced |
|---|---|---|
| LPP headline | 4 | rule 11 as taught (whole-trade sizing); rule 11 stitched (`as_taught_stitched`); rule 13 provisional (`no_look_ahead`, no hold intent); rule 13 with hold intent (the headline since story 17). Delays and cost cases are shown side by side, never picked. |
| Crypto Wizard headline | 1 | one copy rule, never changed |
| ZipTrader headline | 1 | one copy rule, never changed (1 priced trade) |
| Improvements (story 20) | 10 | section 6: the model's 6 + the engineer's 4 distinct smoke tests |
| Strategy lab (story 21) | 29 | section 7: 25 runs (S4/S5 × 4 variants × lists, control × 5) + 4 picker versions |

**Run by this story (not selection, so not added to N):** walk-forward over the improvements (11 candidates: as-is + the 10, 3-month train / 1-month test), threshold sensitivity (improvements `stop_pct` 2.5 and `max_hold` 60 / 45 at ×0.5, ×0.8, ×1.2, ×1.5; lab S4/S5 `gap_pct` 5 and `stop_pct` 5 at the same steps, which needed Alpaca 1-minute bars for gap days of 2.5% to 5%), the shuffle tests (seed 28, 1,000 draws) and the up/down month split. Nothing was re-tuned or re-picked from them; a claim that fails any is labelled "not proven".
