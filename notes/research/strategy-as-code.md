# His strategy as code, on new prices and other stocks (spec-audit story 21, CAP-15)

Pre-registration. Everything below is fixed and committed **before** the first test-window price is read (AGENTS.md
rule 4). Anything changed after the first run is a new variant, logged in section 8 and in
`notes/research/backtesting.md`, never a quiet edit.

Luis's question: "can we backtest that new strategy we create, or just reuse his old strategy, on current prices, on
different stocks, and then see what works and what doesn't."

No model anywhere: the rules are code, the prices are Alpaca's, the verdict is arithmetic (AGENTS.md rule 3).
Code: `app/backtest/lab.py` (`cd app && uv run python -m backtest.lab`), universe picker `app/backtest/lab_universe.py`,
independent recompute `app/audit/lab.py` (inside `audit.run`). Output: `results/strategy-lab.json` (shape:
`contracts.md`, section `strategy-lab`).

## 1. Where the rules come from

Two of his eight code-checked rules (`results/lpp/v1.json` `strategy_profile`, `notes/sources/lpp-strategy.md`) made
money in his own record, copied at 5 min:

| His rule | His trades | Won | Copied P&L |
|---|---|---|---|
| S4 He shorts hot small and mid caps after a big run-up, in the first hour | 42 | 57% | +$568.72 |
| S5 His crypto-linked trades are shorts | 52 | 54% | +$569.49 |

Both need his post to say *which* stock and *when*. Here code decides both, so the rule runs with no post from him.

## 2. The rules, as code

Every price below is an Alpaca bar (SIP feed). "Daily" bars are split-adjusted (`adjustment=split`), used only for
the signal (ratios); trades fill on raw 1-minute bars of that same session.

**Gap** on session d = daily open(d) / daily close(previous session) − 1. Known at 09:30 ET, before every entry
below: no look-ahead.

- **S4, "Short the run-up"** (his S4). Universe: a hot list (section 3). On every session where a stock's gap is
  **+5% or more** (it ran up into the open; his words: "I want to wait for those overbought levels"), short it at the
  open of the first 1-minute bar at or after **09:45 ET** (inside his first hour).
- **S5, "Short crypto stocks that open up"** (his S5). Universe: a crypto-linked list (section 3). Same gap trigger
  (**+5%** or more), short at the open of the first 1-minute bar at or after **09:35 ET** (inside his first half
  hour).
- **Stop** (both): **5% above the entry**. Covered at the first 1-minute bar, from the entry bar on, whose high
  reaches the stop; fill = the larger of that bar's open and the stop (a gap through the stop fills at the open).
- **Exit** (both): his day-trader policy, rule 13: cover at the open of the first 1-minute bar at or after
  **15:55 ET**; if the session has no bar then, at the last bar's close (contracts rule 12i).
- **C, "Short at the open" (as-is control).** The same universes, every session, no signal and no stop: short at
  the daily open, cover at the daily close. Daily bars, because 1-minute bars for every session of every stock would
  cost ~13,000 ticker-days; the daily close is 16:00, five minutes after 15:55 (stated on the card).
- **SPY, buy and hold.** $10,000 in SPY at the close of the session before the window, held to the last close,
  dividends reinvested (Alpaca daily, `adjustment=all`).

## 3. Universes (pre-registered)

**(a) His stocks** = the names in his record (`data/lpp/events.jsonl`, v1 and v2) that the code's ticker groups
(`TICKER_GROUPS`, `app/backtest/strategy.py`) put in each group:
- `his-hot` (13): AFRM, AI, CVNA, DJT, GME, HIMS, OPEN, PLTR, RDDT, SMCI, SOFI, SOUN, TEM.
- `his-crypto` (4): COIN, HOOD, MARA, MSTR.

**(b) Other stocks** (30), chosen by `app/backtest/lab_universe.py` from data up to 2025-09-12 only (the last session
of his window), run 2026-10-20 before any test-window price was read:
1. Start: every active, tradable US-listed common stock in Alpaca's asset list (5,526), dropping names that match
   ETF / ETN / Trust / Fund / leveraged / warrant / unit / right / preferred / note wording, and dropping every
   ticker in his record or in the code's ticker groups (70).
2. `new-crypto` (10): 20-session average dollar volume ≥ $20M and close ≥ $1 on 2025-09-12; one year of daily
   returns to 2025-09-12 (a later listing: 60+ sessions); correlation with IBIT (the spot-bitcoin ETF, bitcoin on
   the stock market's clock; a reference, never traded) ≥ 0.4 **and** beta to IBIT ≥ 1; top 10 by correlation:
   **HUT, KEEL, HIVE, BTBT, BTDR, IREN, CIFR, GLXY, WULF, LUNR**.
3. `new-hot` (20): not in `new-crypto`; 20-session average dollar volume ≥ $100M and close ≥ $5 on 2025-09-12; top
   20 by average daily range ((high − low) / open, 20 sessions): **SOGP, IPDN, ORBS, OPAD, NEGG, CWD, WLDS, ONDS,
   BMNR, AAOI, RUN, SEDG, BLSH, UUUU, SBET, APLD, CRCL, SMR, PL, PGY**.

The picker's rule went through three versions, all on pre-window data, before this file was committed (section 8):
v1 and v2 ranked by short correlation alone and picked banks and industrials as "crypto-linked".
Caveats: the asset list is today's, so a stock delisted between 2025-09-12 and today is missing (survivorship);
LUNR (a space company) passes the crypto rule by its numbers.

S4 runs on `his-hot` and `new-hot`; S5 on `his-crypto` and `new-crypto`; C on all four.

## 4. Windows (pre-registered)

- **Test window:** 2025-09-15 (the first session after his window ends, 2025-09-12) to **2026-10-16** (the last
  session closed when this story began, a Friday).
- **Post-cutoff slice:** 2026-07-01 to 2026-10-16, reported beside the full window for information. The rules are
  code and no model sees these prices, so the model's training cutoff matters little; the slice is there for
  anyone who wants months no model could have read about.

## 5. Money, costs, scoring

- $10,000 start. Each trade $1,000 at its entry price (fractional shares). All trades close the same session, so a
  session's trades share the cash: when a session has n trades and n × $1,000 is more than the account (the lesser
  of $10,000 and $10,000 + realized P&L so far), each is sized to that amount / n (counted as `sized_down`). Shorts
  are cash-secured; no margin.
- Costs per side on every fill (contracts.md rule 5): 5 bps, 20 bps when the fill price is under $10.
- P&L of a short = shares × (entry − exit) − costs. Won = P&L > 0.
- Return = (end − $10,000) / $10,000. Max drawdown = the deepest drop of end-of-session equity from its running peak
  (every session in the window). The SPY numbers use the same dates.
- **Word** (contracts.md rule 9, vs SPY): under 30 trades → `Not enough trades`; return below 0 → `No`; return −
  SPY return ≥ +2 pts → `Yes` ("worked"); within ±2 → `Barely`; ≤ −2 → `No`.
- Caveat on the comparison: SPY is fully invested, a rule holds $1,000 per trade for part of a day. The brief asks
  for exactly this bar ("beats SPY by 2+ pts"), so it stands; the card says so.

## 5b. Stress and realism (added before the first run, from the coordinator's quant-practice notes, 2026-10-20)

- **One look:** this file is committed before the first run; `results/strategy-lab.json` records that commit
  (`preregistered_sha`) and the number of variants tried (`variants_tried`).
- **Costs, three ways** per run: `base` (above); `x2` (every per-side cost doubled); `small_cap` (a wider spread for
  small, thin stocks: per side 50 bps under $5, 30 bps under $10, else 5 bps, plus 10 bps when the stock's
  20-session average dollar volume before that session is under $50M). Return and word are given for each; the word
  shown first is `base`.
- **Borrow:** each stock's `easy_to_borrow` flag from Alpaca's asset list (today's flag, not the flag on the trade
  date: a caveat). A hard-to-borrow short may not be possible at all; the run reports how many trades were on such
  names, and a `borrow_high` return that charges each of those trades one day of a 100%-a-year fee (0.4% of
  notional); easy-to-borrow intraday shorts pay no fee (no position at the close).
- **Gaps through the stop** fill at the bar's open (section 2).
- **Versus random:** for every rule run, its daily-bar twin (short at the daily open, cover at the daily close, on
  the same trigger sessions, base costs) is compared with 2,000 draws of the same number of sessions picked at
  random from the same stocks' sessions in the window (seed 21). Reported: the twin's P&L, the random 2.5th and
  97.5th percentiles and its percentile rank. Daily bars, because random sessions would need 1-minute bars the data
  budget doesn't allow; the twin has no stop and exits 5 minutes later than the rule.
- **Risk next to return:** max drawdown, longest losing streak (consecutive losing trades in time order) and worst
  session (P&L and date).
- **30+ trades** per claim (the word rule).

## 6. Variants (pre-registered; every one reported, changed one at a time from the primary)

| id | Gap | Stop | Exit | Why |
|---|---|---|---|---|
| `P` (primary) | +5% | 5% | 15:55 | the rule as above |
| `no-stop` | +5% | none | 15:55 | his record shows few stops |
| `exit-11` | +5% | 5% | 11:00 ET | his streams end ~10:30 and he says he closes during the day |
| `gap-10` | +10% | 5% | 15:55 | a bigger run-up only |

Plus C (control) and SPY. 4 variants × 4 rule-universe pairs + 4 controls = 20 runs, each on the full window and the
slice. With 16 rule runs, one "worked" by luck is likely (Bailey et al. 2014, `backtesting.md` sec 2): a rule
counts as holding up only if its **primary** run says `Yes` on **both** (a) and (b).

## 7. Data budget

1-minute bars only for a stock's trigger sessions (gap ≥ +5%), fetched through `backtest.bars.stock_day` into
`data/bars/alpaca_1m/` (cached; never fetched twice), at most **200 new ticker-days per run** (`--fetch-cap`); the
run stops with a list of what is still missing, and the next run continues. Daily bars: one request per stock per
adjustment for the window. No other network. `gap-10` sessions are a subset of `P`'s.

## 8. Log (every version tried; also in `backtesting.md`)

1. 2026-10-20, picker v1 (pre-window data): crypto-linked = top 10 by 60-session correlation with BTC/USD daily
   closes (UTC midnight). Picked CSW, AZZ, TTEK, EVR, MC, PIPR, DAL, JEF, ETSY, CPA: clocks don't line up. Dropped.
2. Picker v2 (pre-window): correlation with IBIT, 60 sessions. Picked BTDR, SBET, GLXY, HUT but also WT, TTEK, SNX,
   DLB, IMVT, AMC (noise at 60 points across 1,780 stocks). Dropped.
3. Picker v3 (pre-window): one year, correlation ≥ 0.4 and beta ≥ 1. Kept (section 3).
4. 2026-10-20, after the first run: a bug fix, not a rule change. The gap test compared `open >= close × 1.05`;
   for WULF on 2025-10-09 (12.915 vs 12.30, exactly +5.00%) floating point made 12.30 × 1.05 = 12.915000000000001,
   so an exactly-5% gap was missed, against the spec's "+5% or more". The audit's independent recompute caught it
   (a missing-bar error on that session). Fixed by comparing the rounded gap (9 decimals): one trade added
   (S5 `new-crypto`: 214 → 215 trades, +0.35% → −0.16%). No threshold, list or window changed.

## 9. Results (2026-10-20; `results/strategy-lab.json`, audit 0 mismatches)

SPY total return 2025-09-12 close → 2026-10-16 close: **+17.68%** (worst drop −8.88%). Primary runs (`P`), $10,000,
$1,000 a trade, base costs:

| Rule | Stocks | Trades | Won | Return | Worst drop | vs SPY | Word | ×2 costs | Small-cap costs | vs random (pct rank) |
|---|---|---|---|---|---|---|---|---|---|---|
| S4 short the run-up | (a) his 13 | 62 | 60% | +6.34% | −2.48% | −11.34 | No | +5.40% | +6.03% | 100 (outside the band) |
| S4 | (b) other 20 | 283 | 51% | +11.01% | −5.09% | −6.68 | No | +4.82% | +3.33% | 99.9 (outside) |
| S5 short crypto stocks that open up | (a) his 4 | 44 | 41% | −1.77% | −3.08% | −19.45 | No | −2.36% | −1.87% | 1.7 (inside, low) |
| S5 | (b) other 10 | 215 | 49% | −0.16% | −9.77% | −17.85 | No | −4.47% | −4.17% | 19.8 (inside) |
| C short every open | his hot | 3,575 | 51% | −6.36% | −39.66% | −24.04 | No | −40.62% | −23.19% | – |
| C | his crypto | 1,100 | 54% | +5.24% | −25.29% | −12.44 | No | −7.92% | +3.80% | – |
| C | other hot | 5,500 | 54% | +55.20% | −18.16% | +37.51 | Yes | −3.48% | −13.10% | – |
| C | other crypto | 2,750 | 51% | −40.43% | −68.03% | −58.11 | No | −65.85% | −65.69% | – |

1. **Neither rule held up** by the pre-registered bar (primary `Yes` on both (a) and (b)).
2. **S4 has a real edge, but a small one.** Gap-ups of 5%+ in hot stocks fell from the open to the close far more
   than random sessions of the same stocks (the daily twin sits at the 99.9th-100th percentile of 2,000 random
   draws, on his stocks and on new ones), and it stays positive at 2× costs. At $1,000 a trade it earned +6% and
   +11% against SPY's +18%, so it's "No" by the bar. The post-cutoff slice (from 2026-07-01) is flat to negative.
   The stop cost money: no stop earned more (+8.0% / +16.6%, `Barely` on (b)) with deeper drops. Exiting at 11:00
   earned less than holding to 15:55.
3. **S5 doesn't work.** Shorting crypto stocks after a 5%+ gap lost money on his names and broke even on new ones,
   inside the random band: no edge.
4. **Shorting every open is noise or worse,** except the "other hot" list (+55%), a list of pump-and-dump names
   that fell most days. That result dies under realistic costs (−3% at 2×, −13% with small-cap spreads) and 45%
   of its trades are on hard-to-borrow names, so it isn't tradeable as shown.
5. Caveats: SPY is fully invested, a rule holds $1,000 for hours; borrow flags are today's, not the trade date's;
   the "other" lists come from today's asset list (survivorship); 16 rule runs were tried (23 counting the picker
   versions), so one lucky "Yes" would have been likely.
