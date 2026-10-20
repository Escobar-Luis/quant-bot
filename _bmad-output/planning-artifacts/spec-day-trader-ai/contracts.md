# Contracts

The short version lives in `AGENTS.md` (every agent reads it). This file holds the full shapes and the copy-trade rules. `results/_sample.json` is a valid example the web app can use before real results exist.

## Copy-trade rules (code, never the model)

1. **Post time:** the Discord message timestamp, or the video's `release_timestamp` + `t_s` for LPP. Never a time the model reads off an image.
2. **Delay:** `delays_min = [1, 3, 5, 10, 15, 30, 60]`; the slider opens at 5. The delay applies to entries and to exits the course announces.
3. **Entry:** the open of the first 1-minute bar at or after post time + delay. If the post gives a trigger level, entry is when price trades the trigger after post time + delay; if it never does, no trade (counted as `not_triggered`).
4. **Exit**, first that applies: the course's own close or trim (+ delay); stop or target, whichever trades first (both in one bar = stop); the horizon as written; otherwise day trades at 15:55 ET the same session, swing trades after 5 sessions, crypto setups after 24 hours (all three `assumed`, listed in `unknown`).
5. **Costs per side:** 5 bps stocks, 20 bps stocks under $10 (judged on each fill's price), 25 bps crypto. This is the `simple` case: every key of a results file uses it unless it says otherwise. Since spec-audit CAP-17 (story 29, 2026-10-20) each headline is also priced under two more cases, published in `cost_cases` (section below); one cost module, `app/backtest/costs.py`, serves the engine and the strategy lab, and `app/audit` recomputes it on its own:
   - `realistic`, spread plus slippage per side by price and volume: crypto 25 bps; stocks 5 bps at $10 or more, 30 bps from $5 to $10, 50 bps under $5 (each fill's price), plus 10 bps when the ticker's average daily dollar volume (raw close × volume) over the 20 sessions before the fill's session is under $50M (no prior session = under). Daily volumes: Alpaca 1Day raw bars cached in `data/bars/daily_dv/<T>.json` (a failed fetch is cached as `{"_unknown": why}`, counts as thin, and is retried next run); the lab reads its own `data/bars/lab_daily/` raw bars, same rule. A short also pays a borrow fee on each cover: the entry value of the shares covered (average entry price × shares) × the annual rate ÷ 360 × days held, days held = calendar days from the position's first entry to the cover, at least 1 (an intraday short pays one day). Annual rates: easy to borrow 0.5%, hard to borrow 30%, unknown 30% (a failed lookup is never assumed easy), crypto shorts 10% (margin interest or perpetual funding; no flag source). Flags: Alpaca's `easy_to_borrow` for every shorted stock, cached in `data/lab/assets.json` (`null` = the lookup failed, retried next run) with the date of the lookup that set it in `data/lab/assets_checked.json` (a cached flag is never re-dated); the flag is today's, not the trade date's (spec-audit story 32).
   - `x2` ("2× realistic" everywhere it is shown): realistic with every per-side cost and every borrow rate doubled. The strategy lab's older `costs.x2` is 2× simple and is labelled so. A verdict that only holds under `simple` costs is not one the app leads with.
   Each case is its own account: rule 6's cash cap runs again with that case's costs (costs and borrow leave cash at the trade's last sell), so trade counts can differ by a sized-down buy.
6. **Sizing:** $1,000 per trade. LPP scales the host's share counts so all of a trade's buys together come to $1,000, keeping his add/trim ratios (decided by Luis, 2026-10-17; wording clarified 2026-10-20 after the audit found two readings; superseded by the bankroll model in spec-audit CAP-9; whole-trade scaling reads his later adds, so since spec-audit story 18 (2026-10-20) LPP's headline sizes by rule 13(e) and whole-trade scaling survives only in the `as_taught_stitched` key); an entry with no share count gets the upper median of his stated counts (with an even count, the higher of the two middle values). Cash cap, per buy (2026-10-20, audit-9): every fill is copied in time order; each buy takes its own money as it fills, never money for a later add; a buy that doesn't fit is sized down to the cash, or skipped at $1 or less (a first buy skipped = the trade couldn't be copied, and its later buys go with it); each sell returns the money in what it sold plus its gain, and a trade's costs leave cash at its last sell. At one moment sells go before buys, then by trade id, except that a trade's own fills keep their order. `sized_down` counts buys sized down or skipped. Measured peak money in positions (`all`, 5 min): LPP v1 as_taught_stitched $3,584 (was $4,715 under the old whole-trade reservation), LPP v1 rule 13 (the headline since story 18) $10,173, LPP v2 rule 13 $10,547 (before this per-buy cap, rule 13 reserved up to $10,811); above $10,000 only when realized gains have grown the cash. Each portfolio starts with $10,000 of fake money; unused cash earns nothing.
7. **Just holding:** $10,000 in SPY (stocks) or BTC (crypto) bought at the window's first trading minute, held to its end.
8. **Portfolios:** `day` (opened and closed the same session, or called intraday or a scalp), `swing` (held overnight, or a horizon in days), `options` (calls, puts, strikes or expiries: counted, `testable: false`), `crypto` (Crypto Wizard setups), and `all` (every testable trade in one account: the course headline).
9. **Answer word, per portfolio and delay** (amended 2026-10-20, spec-audit CAP-7: a word never reads as success when the copy lost money): fewer than 30 trades → `Not enough trades`; else a return below 0 → `No`; else return minus the benchmark's return ≥ +2 pts → `Yes`; within ±2 pts → `Barely`; ≤ −2 pts → `No`. The benchmark is just holding (rule 7), except in a proof-set file (one with `same_sessions`, LPP v2): its `all` portfolio is compared only with v1 on the same sessions (`same_sessions.by_delay`), its other portfolios carry no comparison (`word`, `vs` null), and it has no `strategies`, `ranges`, `combos` or `best_stop`. Each by_delay row also carries:
   - `outcome`: `Made money` (return > 0), `Lost money` (< 0), `Broke even` (0), `No trades` (0 trades).
   - `vs`: the comparison in plain words, gap = return − benchmark return: ≥ +2 → `beat <B>` (`less than <B>` when the copy lost money); within ±2 → `about the same as <B>`; ≤ −2 → `<B> did better` (`more than <B>` when the benchmark also lost). `<B>` is `compare_with.name`: `the S&P` (SPY), `Bitcoin` (BTC), `v1` (proof set). Null with 0 trades.
   - `sealed.word`, `sealed.outcome`, `sealed.vs`: the same three on the sealed months alone (rule 10), with the sealed trade count and the sealed benchmark return.
   The card reads outcome, then vs, then the sealed months' word: "Lost money, less than Bitcoin. Held-out months: No." Top-level `compare_with`: `{"kind": "hold" | "same_sessions", "name": "the S&P" | "Bitcoin" | "v1"}`.
10. **Sealed window:** the last 3 months of each course's window (`window.sealed_from`). The as-taught test reports it for information; the later improver must never read it.
11. **LPP ledger as taught, stitched** (documented from lpp.py 2026-10-20; the headline until spec-audit story 18, now the `as_taught_stitched` key; uses later statements, see rule 13): his `trade` events are copied when every check passed, or when the only failed checks are the ledger checks `open_never_closed`, `close_without_open` or `qty_exceeds_position` (those are kept and resolved by this ledger); options are counted, not priced. Positions are kept per ticker and side; an exit that names no side belongs to his one open position on that ticker, else it is skipped; a buy (open or add) that names no side is skipped and counted. A position he still holds at the end of a session carries to a later session only when his next word on it within 7 days is an add, trim or close; otherwise it leaves at 15:55 ET of its session (assumed), and a later `open` starts a new position. An exit with no open position is skipped. A position whose legs span sessions is a swing trade (rule 8).
12. **Edge rules (adopted by Luis 2026-10-20 from the audit, notes/audit/findings-story-2.md):** (a) a horizon said only in the quote counts as written (rule 4) and belongs in the extraction's horizon field; (b) rule 11's look-ahead carry stays for the `as_taught_stitched` key; rule 13 is its no-look-ahead version (the LPP headline since spec-audit story 18); (c) a take-profit post after the copier's own target order filled sells nothing more; (d) a trigger crossed by a gap between bars fills at the gap bar's open; (e) a moved break-even stop hit in the same bar fills at the stop level; (f) rule 6 scales at the first fill's price (superseded by the bankroll model, spec-audit CAP-9); (g) a trim with no size sells half the position; (h) just holding ends at the official daily close, the last 1-minute close reported as an alternative. Added with PR #58: (i) when price data ends before the exit, the trade closes at the last bar's close; (j) a take-profit post for target n also sells the shares of earlier targets that never filled; (k) cash of $1 or less skips the trade (counted). Added with spec-audit story 20 (PR #68 review): (l) flat after his own trim or close is not the end of a position: a later add posted before the position leaves (rules 4, 13b) re-enters at its post + delay and is sized as any add (rule 13e); a stop or target that empties the position ends it. This is how his re-adds are copied, with or without a stated stop or target. Added with spec-audit story 29 (CAP-17): (m) a stop crossed by a gap (the bar opens past the stop: above it for a short, below it for a long, including the first bar of a later session) fills at that bar's open, never at the stop level; a stop that trades inside the bar fills at its level; (e) still covers a stop moved to break-even in the same bar.
13. **No look-ahead, LPP's headline** (spec-audit CAP-12, 2026-10-20; the headline since spec-audit story 18, 2026-10-20, replacing rule 11, whose numbers move to the `as_taught_stitched` key). Why: the host states he closes every day ("I have closed my mstr short as I do every day!", his Discord chat, 2025-02-03; notes/sources/lpp-discord-exits.md), so a position carries overnight only on intent stated before 15:55 ET; his hold intent is extracted from the streams with timestamps into the `horizon` field (LPP v1, spec-audit story 17: `app/lpp/hold_intent.py` writes `horizon` with `horizon_source: "hold_intent_v1"`, its ≤12-word quote and t_s, only for statements found in the captions, made while the position was open and before 15:55 ET; v2 events carry none yet, story 22); and the cash cap is per buy, never reserving money for later adds (rule 6, audit-9). Of the 43 overnight trades rule 11 stitched, 29 had an exit he stated on a later stream and 14 an assumed one; his chat closes one of those 14 (SOUN, a later day) and story 17 found no stated hold in any of the 43. The bankroll model (story 8) will still replace rule 6's sizing and cash rules. The rule: every copy decision uses only what he said before that moment. (a) Which events are copied, positions per ticker and side, side-less exits and exits with no open position: as rule 11. (b) A position leaves at 15:55 ET of the session its first leg was posted in, unless one of its legs, posted before that moment, states a horizon past the session (the extraction's `horizon` field, rule 12a): then it stays open to 15:55 ET of that horizon's last session, counted in weekdays from the session of the leg that said it (a horizon with no count is rule 4's 5 sessions; the latest end wins). (c) A word posted at or after the moment a position left starts afresh: an open or add opens a new position, a trim or close finds nothing open and is skipped. (d) A position held past its first session is a swing trade leaving at that moment; every other position is a day trade (rules 4, 8). (e) Sizing: the first buy is $1,000 at its fill price; each later add buys the first buy's shares × (his count for the add ÷ his count for the first buy), where a count he didn't state is the upper median of the counts he had stated on this position's buys posted up to that add (the two are equal when he has stated none); an add never takes the position past $10,000 held at the add's price; a trim sells the share of his stated holding so far that he trimmed (no size: half). ASSUMPTION: a holiday counts as a weekday session. Cash: rule 6's per-buy cap.

## `results/<course>/<version>.json` (written by story 1)

`course`: `lpp` | `ziptrader` | `cryptowizard`. `version`: the extraction version whose events were priced (`v1`, `v2`), so the failure and the fix both show in money.

```json
{
  "schema": "results/1",
  "course": "lpp",
  "course_name": "Learn Plan Profit",
  "version": "v1",
  "source_agent_id": "extract-lpp-v1",
  "sample": false,
  "generated_at": "2026-10-17T19:10:00Z",
  "git_sha": "abc1234",
  "window": {"start": "2024-08-15", "end": "2025-09-12", "sealed_from": "2025-06-12"},
  "money_start": 10000,
  "course_fee_usd": null,
  "delays_min": [1, 3, 5, 10, 15, 30, 60],
  "default_delay_min": 5,
  "costs_bps_per_side": {"stocks": 5, "stocks_under_10": 20, "crypto": 25},
  "sizing": "His share counts, scaled to $1,000 per trade",
  "hold": {"symbol": "SPY", "label": "Just holding", "what": "Buy and keep the S&P 500 (SPY)"},
  "headline_portfolio": "all",
  "compare_with": {"kind": "hold", "name": "the S&P"},
  "portfolios": [
    {
      "id": "all", "label": "Everything he traded", "testable": true,
      "by_delay": {
        "5": {"end": 9420, "ret_pct": -5.8, "hold_end": 11890, "hold_ret_pct": 18.9,
              "trades": 412, "not_triggered": 9, "won_pct": 44, "worst_drop_pct": -17, "word": "No",
              "outcome": "Lost money", "vs": "the S&P did better",
              "sealed": {"ret_pct": -1.2, "hold_ret_pct": 3.1, "trades": 93, "word": "No", "outcome": "Lost money", "vs": "the S&P did better"}}
      },
      "series": {"dates": ["2024-08-15", "2024-09-02"], "hold": [10000, 10180],
                 "by_delay": {"5": [10000, 9960]}}
    },
    {"id": "options", "label": "Options", "testable": false, "count": 37,
     "why": "No free options price history"}
  ],
  "rules": [
    {"id": "R1", "text": "Buy the first break of the morning high", "quote": "first candle to break the high",
     "testable": true,
     "cite": {"source_id": "lpp:2024-08-15", "locator": "t=754s", "label": "Live session, 2024-08-15, 12:34"}}
  ],
  "trades": [
    {"trade_id": "lpp-2024-08-15-3", "portfolio": "day", "ticker": "NVDA", "side": "long",
     "posted_at": "2024-08-15T13:41:12Z", "quote": "I'm in NVDA here at one twenty",
     "cite": {"source_id": "lpp:2024-08-15", "locator": "t=702s", "label": "Live session, 2024-08-15, 11:42"},
     "by_delay": {"5": {"entry_at": "2024-08-15T13:47:00Z", "entry": 120.4, "exit_at": "2024-08-15T14:20:00Z",
                        "exit": 121.9, "ret_pct": 1.15}}}
  ],
  "days": {"2024-08-15": [{"time_et": "09:41", "course": "lpp", "ticker": "NVDA", "action": "open",
                           "quote": "I'm in NVDA here"}]},
  "unknown": ["Exit time assumed at 15:55 when he didn't say he closed.", "Costs are estimates."],
  "checks": {"events_total": 1200, "events_ok": 1100, "needs_review": 100}
}
```

LPP's headline `portfolios` follow rule 13 (no look-ahead) since spec-audit story 18. LPP files also carry `as_taught_stitched` (rule 11 with rule 6's whole-trade sizing; until 2026-10-20 this was the headline and rule 13 sat in a provisional `no_look_ahead` key, now removed): the same events, sessions stitched by his later words, shown beside the headline. Same row fields as `portfolios[].by_delay`, no series; in a proof-set file its rows carry no comparison (word and vs null, rule 9):

```json
"as_taught_stitched": {"label": "As taught, stitched across sessions", "rules": "contracts.md rule 11: ...",
                       "why_not_headline": "...", "positions": 315,
                       "portfolios": [{"id": "all", "by_delay": {"5": {"end": 9763.83, "word": "No", "...": "..."}}},
                                      {"id": "day", "by_delay": {}}, {"id": "swing", "by_delay": {}}]}
```

Rules for the file:
1. Every key in `by_delay` is a string of a `delays_min` value; every delay is present for every testable portfolio.
2. `trades` may be a sample (up to 200, the demo-worthy ones) to keep the file small; counts always cover all trades.
3. Quotes are 12 words or fewer; rule `text` is a paraphrase of 15 words or fewer. No transcript or post text.
4. `days` is optional (CAP-2).
5. A breaking change bumps `schema` and goes through an `AGENTS.md` PR first.

## `proofs/prism.json` (written by story 2)

```json
{
  "schema": "proofs/1",
  "updated_at": "2026-10-17T19:40:00Z",
  "knowledge_base": {
    "agent_id": "daytrader-verdict-v2", "run_url": "https://prism.blockconvey.com/...",
    "docs": ["lpp-strategy-cards.md", "lpp-events-summary.md", "lpp-untestable.md"],
    "query": "lpp entry, exit and sizing rules",
    "hits": [{"doc": "lpp-strategy-cards.md", "snippet": "Buy the first break of the morning high"}]
  },
  "root_cause": {
    "agent_id": "extract-lpp-v1", "failed_runs": 7, "cluster": "<PRISM cluster name>", "tier": "Likely",
    "prism_cause": "<as PRISM states it>",
    "our_sentence": "Live-stream captions mix P&L talk with prices, so a dollar gain was read as an entry price.",
    "url": "https://prism.blockconvey.com/..."
  },
  "evaluator": {
    "name": "Numbers grounded", "checks": "Every price, level and quantity appears in the quote it cites",
    "inputs": "The same 30 LPP sessions",
    "v1": {"agent_id": "extract-lpp-v1", "pass_pct": 63}, "v2": {"agent_id": "extract-lpp-v2", "pass_pct": 93},
    "url": "https://prism.blockconvey.com/..."
  },
  "evaluator_verdict": null,
  "bonus": {"alert": null, "guardrail": null}
}
```

## PRISM `agent_id`s (stable; a new version is a new id)

| `agent_id` | One run is | Owner |
|---|---|---|
| `extract-lpp-v1`, `extract-lpp-v2` | Events from one LPP session | `extract-lpp` (`app/lpp/`) |
| `extract-ziptrader-v1` | Calls from one morning briefing | `collect-ziptrader` |
| `extract-cryptowizard-v1` | One setup or lesson | `collect-cryptowizard` |
| `daytrader-verdict-v1`, `daytrader-verdict-v2` | The verdict for one course and results version | story 2 |
| `daytrader-improver-v1` | One proposed change (later, CAP-9) | story 1 |
| `daytrader-strategy-v1` | LPP's strategy as rules from the copied trades (spec-audit CAP-14); `conversation_id` `strategy-lpp-<version>` | spec-audit story 19 (`app/backtest/strategy.py`) |
| `daytrader-improver-v2` | Up to 6 rule changes from LPP's losses, as code filters on his trades (spec-audit CAP-15); `conversation_id` `improve-lpp-<version>` | spec-audit story 20 (`app/backtest/improvements.py`, `python -m backtest.improver --v2`) |

## Trace and step conventions

1. `submit_trajectory(steps, agent_id=..., agent_name=..., conversation_id=..., final_status=..., metadata=...)`.
2. `conversation_id`: `<course>-<source key>` for extraction (as `app/lpp/` does: `lpp-<video_id>`); `verdict-<course>-<results version>` for verdict runs.
3. Steps in order: `tool_call` steps with snake_case `tool_name` (`load_captions`, `check_events`, `kb_search`, `load_results`, `check_numbers`); `reasoning` steps for model calls (`llm_extract`, `llm_verdict`); one `final_answer` last.
4. Verdict runs: `kb_search` (query, doc ids, snippets) → `load_results` → `llm_verdict` → `check_numbers` → `final_answer`. That is the Knowledge Base proof's retrieval step.
5. `final_status="error"` whenever a code check fails; the output names the failing check and its quote (12 words or fewer), so Root Cause has something to read.
6. Inputs are locators, never raw transcript or post text.
7. `metadata`: `{agent_version, course, prompt_version, git_sha, proof_set}`; `proof_set: true` only for the 30 traced LPP sessions.
</content>
</invoke>

## v2 keys (additive, optional; Luis 2026-10-17 15:00)

Written by story 1, read by story 3; a missing key hides its card. Strategy = trades grouped by setup (the event's `why` plus recurring rules), not by trade type; `portfolio` stays a facet. `series.dates` is shared by every curve. Ranges run from the window start. `combos` and `suggestion` are picked on dev months and reported on the sealed months; cross-course combos only where dates overlap.

```json
{
"strategies": [{"id": "vwap-pullback", "name": "Pullback to VWAP", "portfolio": "day", "testable": true,
  "sessions": 31,
  "entails": {"buy": "Dip to the day's average price, then a bounce", "sell": "2x the risk, or back under VWAP",
              "stop": "Just under the bounce low", "size": "His share count, scaled to $1,000", "time": "Mostly 9:30-11:00"},
  "quotes": [{"text": "wait for it to come back to VWAP", "cite": {"source_id": "yt:…", "locator": "t=850s", "label": "Live session, 2024-10-03, 14:10"}}],
  "untestable": ["Feel the tape"],
  "by_delay": {"5": {"end": 10900, "ret_pct": 9.0, "hold_ret_pct": 6.0, "trades": 98, "won_pct": 58, "word": "Yes"}},
  "series": {"by_delay": {"5": [10000, 10120]}}}],
"ranges": {"3m": {"by_delay": {"5": {"end": 9820, "hold_end": 10350, "word": "No"}}},
           "6m": {"by_delay": {"5": {"end": 11240, "hold_end": 10900, "word": "Yes"}}},
           "1y": {"by_delay": {"5": {"end": 10660, "hold_end": 11890, "word": "No"}}}},
"best_stop": {"by_delay": {"5": {"date": "2025-03-03", "end": 12400, "hold_end": 10950}}},
"combos": [{"ids": ["lpp:vwap-pullback", "cryptowizard:btc-setups"], "window": {"start": "2025-08-01", "end": "2025-09-12"},
            "picked_on": "dev", "sealed": {"ret_pct": 14.0, "hold_ret_pct": 6.0}, "word": "Yes"}],
"suggestion": {"agent_id": "daytrader-improver-v1", "applies_to": "vwap-pullback", "change": "Skip 9:30-9:45",
               "dev": {"before_pct": 9.0, "after_pct": 13.0}, "sealed": {"before_pct": 4.0, "after_pct": 7.0},
               "kept": true, "prism_url": null}
}
```

## `by_year` (additive, optional; spec-audit CAP-4, story audit-3-by-year)

Written by `app/backtest` (`extras.by_year`), reconciled by `app/audit`, shown by `web/` as a small table per course (year rows plus All time); a missing key hides the table. `schema` stays `results/1`. Rules (spec-audit SPEC.md Assumptions):

1. **Periods:** each calendar year inside the window (`from`/`to` = its first and last trading day there), plus `all` (the full window). A year is a slice of the one all-time run: the same copied trades, sizes and cash cap (rule 6) as the headline; nothing is re-run per year.
2. **A trade belongs to the calendar year of its exit day** (its last exit: ET date for stocks, UTC date for crypto), clamped to the window's first and last years (an exit after the window's last trading day counts in the last year). Engine and audit use this one rule.
3. **Copying:** `start` = money at the year's start ($10,000 plus every earlier year's realized P&L); `end` = `start` + the year's realized P&L; `ret_pct` = the year's realized P&L / `start`. `all` equals the headline `end`, `ret_pct` and `trades` exactly.
4. **Just holding** is also one all-time run: $10,000 bought at the window's first trading minute (rule 7), valued at each trading day's official close. `hold_start` = its value at the previous year's last close ($10,000 for the first year), `hold_end` = at the year's last close, `hold_ret_pct` = `hold_end / hold_start − 1`. Stocks use SPY **total return**: each dividend (Yahoo Finance's published SPY dividends, cached in `data/bars/dividends/`) is reinvested at its ex-date's official close; an ex-date on the buy day earns nothing. `hold_price_ret_pct` is the same without dividends (price only, the basis of the headline `hold_ret_pct`). Crypto holds BTC (no dividends: both are equal).
5. **Words:** rule 9 (CAP-7) on the period's `trades`, `ret_pct` and `hold_ret_pct` (total return): `word`, `outcome` and `vs` (`<B>` = `compare_with.name`); under 30 trades is `Not enough trades`, a loss is never `Yes` or `Barely`. `all`'s `outcome` equals the headline's; its `word` and `vs` can differ from the headline's (price-only holding) by the dividends.
7. A proof-set file (`same_sessions`, LPP v2) has no `by_year` (rule 9: no full-window comparison).
6. Every testable portfolio and every delay; money to the cent, returns to 0.01 pt.

```json
"by_year": {
  "hold": {"symbol": "SPY", "basis": "total_return",
           "source": "Yahoo Finance SPY dividends, reinvested at the ex-date close", "dividends": 2},
  "periods": [{"id": "2024", "from": "2024-08-15", "to": "2024-12-31"},
              {"id": "2025", "from": "2025-01-02", "to": "2025-09-12"},
              {"id": "all", "from": "2024-08-15", "to": "2025-09-12"}],
  "portfolios": {"all": {"by_delay": {"5": {
    "2024": {"start": 10000, "end": 9850.1, "ret_pct": -1.5, "hold_start": 10000, "hold_end": 10910.4,
             "hold_ret_pct": 9.1, "hold_price_ret_pct": 8.6, "trades": 120, "word": "No",
             "outcome": "Lost money", "vs": "the S&P did better"},
    "2025": {"start": 9850.1, "end": 9763.83, "ret_pct": -0.88, "hold_start": 10910.4, "hold_end": 12100.2,
             "hold_ret_pct": 10.9, "hold_price_ret_pct": 10.2, "trades": 195, "word": "No"},
    "all":  {"start": 10000, "end": 9763.83, "ret_pct": -2.36, "hold_start": 10000, "hold_end": 12100.2,
             "hold_ret_pct": 21.0, "hold_price_ret_pct": 19.64, "trades": 315, "word": "No"}}}}}
}
```

## `strategy_profile` (additive, optional; spec-audit CAP-14, story audit-19-strategy)

LPP v1 only (a proof-set file has none, rule 9). Written by `app/backtest/strategy.py` (`python -m backtest.strategy`; `backtest.run` re-attaches it from the cached model reply in `data/lpp/strategy/`), reconciled by `app/audit` (`audit.strategy`, from the audit's own trades), shown by `web/` as the "His strategy" card; a missing key hides the card. `schema` stays `results/1`.

1. **Trades:** the headline's copied trades (rule 13, portfolio `all`, `delay_min` 5, after the cash cap): the same trades, count and copied P&L as `portfolios[all].by_delay["5"]` (`summary.trades`, `summary.pnl_usd` = `end − 10,000`).
2. **Features per trade** (what he did; `definitions` holds every list and bucket, so the audit evaluates them without the engine's code): `side`; `group` (`definitions.ticker_groups`, by what the company is, else `other`); `ticker`; `time15` / `time30` (ET time he posted the first leg, bucket start; `before 09:30`; `time30`'s last is `11:00 or later`); `setup` (his stated reason: the first leg's `why` with one, matched to `definitions.setups` in order, first match wins, else `other-longs` / `other-shorts`); `adds` (`none` when the copy has one buy; else `to_loser` when any later buy fills at a worse price than the average of the buys before it, higher for a short, lower for a long; else `to_winner`); `exit` (`assumed` when the copy left by rule 4's default, else `stated`); `hold` (`overnight` for a swing trade, else the copy's minutes from first buy to last sell in `definitions.hold_buckets_min`); `size` (his first buy's share count × the copy's first buy price, `definitions.size_buckets_usd`; `not stated` with no count); `day_trades` (copied trades whose first leg was posted that ET day, `definitions.day_buckets`); `portfolio`. A bucket `[top, label]` holds values below `top` (`null`: the rest).
3. **Group stats** (every table row, setup, rule and pattern): `trades`, `won_pct` (copied P&L > 0, rounded), `pnl_usd` (sum, cents), `avg_win_usd`, `avg_loss_usd` (P&L ≤ 0; null when none), `share_pct` (of all trades, 0.1 pt).
4. **Conditions:** `when` / `does` = `{feature: [allowed values]}`; a trade matches when every listed feature's value is in its list; `{}` matches every trade.
5. **Rules** (≤ 8): the model proposes the wording and the conditions; code keeps a rule only when `situation_trades` (trades matching `when`) ≥ 15, its trades (matching `when` and `does`) ≥ 15 and `follows_pct` = their share of the situation ≥ 60 (0.1 pt). Stats are those of the following trades. `quote`: one of his rule quotes (≤ 12 words) given to the model, with its cite, or null. Rules code dropped are listed in `dropped` with the reason. Also dropped: a `does` that repeats a value of its `when` (`does_repeats_when`) or allows every value its feature takes (`does_covers_every_value`), and a malformed proposal. `text` is the model's wording (`proposed_text`) with its hedge words ("usually", "almost always", "four of every five") replaced by code with the measured `follows_pct`. A quote found not to say what its rule says is null, with `quote_hidden` giving why (spec-audit story 25 checks every pair). A malformed cached reply leaves the key out, with a logged reason.
6. **Losing patterns** (3): every one-feature condition, and every pair of what he traded (`side`, `group`, `ticker`, `setup`) with another of those or with `time30`, `adds`, `exit`, `hold`, with 15+ trades, ranked by `pnl_usd` (then fewer features); a pattern sharing more than half its trades with one already picked is skipped. `share_of_losses_pct` = its losing trades' dollars / all losing trades' dollars; `label` = the condition in plain words, by code.
7. **Worst days** (10): ET days of the first leg, by summed P&L; with shorts, adds to losers, assumed exits and the top 3 tickers.

```json
"strategy_profile": {
  "agent_id": "daytrader-strategy-v1", "prompt_version": "strategy-v1.1", "model": "anthropic/claude-sonnet-5-5",
  "trajectory_id": "…", "prism_url": "https://prism.blockconvey.com/trajectories/…",
  "version": "v1", "portfolio": "all", "delay_min": 5, "basis": "…",
  "summary": {"trades": 342, "sessions": 187, "pnl_usd": -264.55, "won_pct": 50,
              "trades_per_session": {"median": 2, "max": 5},
              "his_size": {"stated_on": 255, "median_shares": 100, "median_usd": 21093, "p90_usd": 58785},
              "adds": {"his_add_posts": 0, "trades_he_added_to": 0, "copied_with_adds": 226, "to_loser": 133, "to_winner": 93},
              "trims": {"his_trim_posts": 0, "trades_he_trimmed": 0}},
  "tables": [{"id": "side", "label": "Long or short", "by": "side",
              "rows": [{"key": "short", "trades": 274, "share_pct": 80.1, "won_pct": 51, "pnl_usd": -611.0,
                        "avg_win_usd": 50.1, "avg_loss_usd": -57.2}]}],
  "setups": [{"when": {"side": ["short"], "group": ["big tech"], "time30": ["09:30"], "setup": ["short-resistance"]},
              "trades": 22, "won_pct": 55, "pnl_usd": -854.79, "share_pct": 6.4}],
  "worst_days": [{"day": "2025-04-07", "trades": 3, "pnl_usd": -300.1, "shorts": 3, "adds_to_loser": 2,
                  "exits_assumed": 2, "tickers": ["TSLA"]}],
  "rules": [{"id": "S1", "text": "He trades the short side (80% of the time).", "proposed_text": "He mostly trades the short side…", "when": {}, "does": {"side": ["short"]},
             "situation_trades": 342, "follows_pct": 80.1, "trades": 274, "won_pct": 51, "pnl_usd": -611.0,
             "share_pct": 80.1, "quote": {"text": "…", "cite": {"source_id": "lpp:2024-08-15", "locator": "t=754s", "label": "…"}}}],
  "dropped": [{"text": "…", "why": "followed 41.0% of the time (under 60%)"}],
  "losing_patterns": [{"id": "group:big_tech-adds:to_loser", "when": {"group": ["big tech"], "adds": ["to_loser"]},
                       "label": "Big tech, added to a loser", "trades": 51, "won_pct": 31, "pnl_usd": -2270.68, "share_of_losses_pct": 32.1}],
  "definitions": {"ticker_groups": {"big tech": ["TSLA", "NVDA"]}, "other_group": "other",
                  "setups": [{"id": "short-overbought", "name": "…", "side": "short", "words": ["overbought"]}],
                  "hold_buckets_min": [[15, "under 15 min"], [null, "3 h or more"]],
                  "size_buckets_usd": [[10000, "under $10k"]], "day_buckets": [[2, "1"]],
                  "kept_if": {"min_trades": 15, "min_follows_pct": 60}, "pattern_min_trades": 15}
}
```

## `improvements` (additive, optional; spec-audit CAP-15, story audit-20-improve)

LPP v1 only (a proof-set file has none, rule 9). Written by `app/backtest/improvements.py` (`python -m backtest.improver --v2`; `backtest.run` re-attaches it from the cached model reply in `data/improver/v2/`, recomputing every number), reconciled by `app/audit` (`audit.improvements`, from the audit's own positions and calculator), shown by `web/` as the "What would have helped" card; a missing key hides the card. `schema` stays `results/1`.

1. **Proposals (model, `daytrader-improver-v2`):** given only the `strategy_profile` tables, setups and losing patterns recomputed on the **dev months** (first buy before `window.sealed_from`), and his rules' wording, the model proposes up to 6 changes: `text` (≤ 20 words), `kind`, `when` (a condition as in `strategy_profile` rule 4), `value`, `why` (≤ 15 words). It never sees a sealed-month number.
2. **Code checks and applies each change** to every headline position (rule 13, portfolio `all`, `delay_min` 5). `when` may use only features known when the first buy fills: `side`, `group`, `ticker`, `time15`, `time30` (as in `strategy_profile`), and `setup` = his stated reason from the first leg, among those posted **at or before the copy's first buy fill** (a position not priced as-is: its first buy's post + delay), that has one, matched to the setups below in order (first keyword match on his side wins, else `other-longs` / `other-shorts`); no reason stated by then = `unknown` (a reason said after the first fill is never used: no look-ahead). Definitions (the audit keeps its own copy and checks the file's `strategy_profile.definitions` against it): `{"ticker_groups": {"big tech": ["TSLA", "NVDA", "AMD", "AVGO", "AMZN", "AAPL", "META", "MSFT", "GOOGL", "GOOG", "NFLX"], "crypto-linked": ["MSTR", "COIN", "HOOD", "MARA", "RIOT", "CLSK"], "hot small and mid caps": ["PLTR", "SOUN", "HIMS", "SOFI", "SMCI", "TEM", "RDDT", "DJT", "OPEN", "GME", "AI", "CVNA", "IONQ", "RKLB", "RGTI", "QBTS", "OKLO", "APP", "UPST", "AFRM"], "index funds": ["SPY", "QQQ", "TQQQ", "SQQQ", "IWM", "SPXS", "SPXL"]}, "setups": [{"id": "short-overbought", "side": "short", "words": ["overbought", "ran up", "run up", "pump", "extended", "rise", "rally", "pop", "rip", "spike", "squeeze"]}, {"id": "short-resistance", "side": "short", "words": ["resistance", "reject", "highs", "high of", "lower high", "double top", "ceiling"]}, {"id": "short-breakdown", "side": "short", "words": ["break", "support", "weak", "downside", "drop", "gap down", "lower", "dump", "bearish", "sell-off"]}, {"id": "buy-the-dip", "side": "long", "words": ["oversold", "dip", "bounce", "support", "recovery", "reversal", "bottom", "flush"]}, {"id": "other-shorts", "side": "short", "words": []}, {"id": "other-longs", "side": "long", "words": []}]}`, other tickers = `other`. Anything else is rejected (`look_ahead_or_unknown_feature`), as are kinds off the menu, values out of range, text over 20 words, `skip`/`only` with an empty `when`, and every proposal after the 6th (`over_6_proposals`). Rejected proposals are listed in `rejected` with the check. Kinds:
   - `skip`: positions matching `when` are not copied. `only`: only positions matching `when` are copied.
   - `no_add_against`: in a matching position, every `add` leg after the first buy whose fill (the open of the first 1-minute bar at or after its post + delay) is worse than the copy's first buy fill (higher for a short, lower for a long; equal is not worse) is removed; the position is then re-priced as usual (rules 1–6, 13).
   - `max_hold` (`value` minutes, 5–390): a matching position's default exit becomes the earlier of its own (rule 13b; 15:55 ET of the first post's session for a day trade) and the copy's first buy fill time + `value` minutes; stated exits before it still apply.
   - `stop_pct` (`value` %, 0.5–10): a matching position gets a stop `value` % against the copy's first buy fill price (long: × (1 − v/100), short: × (1 + v/100)); a stated stop that is tighter stays. Rule 4's stop handling applies.
   A position that doesn't match, or wasn't priced as-is, keeps its as-is result. Re-pricing never changes the first buy (the change is decided from it).
3. **Numbers:** one full-window run of the changed positions through the cash cap (rule 6); a trade is **dev** when its first buy's ET day is before `sealed_from`, else **sealed**. `ret_pct` = the part's summed copied P&L / $10,000 (0.01 pt; as the headline's sealed block). `as_is` is the same with no change (dev + sealed = the headline's `end − 10,000`; sealed = `portfolios[all].by_delay["5"].sealed.ret_pct`). `spy`: SPY total return from by_year's holding run (rule 4 of by_year): `dev_ret_pct` = value at `dev_to` (the last close before `sealed_from`) / $10,000 − 1; `sealed_ret_pct` = value at the window's last close / value at `dev_to` − 1. Per part: `trades`, `ret_pct`, `as_is_ret_pct`, `vs_as_is_pts`, `spy_ret_pct`, `vs_spy_pts` (gaps 0.01 pt).
4. **Kept** (code): only when dev `vs_as_is_pts` > 0 (it beats the as-is copy where it was picked) AND sealed `vs_as_is_pts` ≥ 0 (it does not lose on the held-out months) AND `trades` ≥ `min_trades` (30) in dev and in sealed. `kept_reason` says which test failed: "fewer than 30 trades left …", "no gain on the months it was picked on (dev)", "gained on dev, lost on the held-out (sealed) months", or "gained on dev and did not lose on the held-out (sealed) months". Nothing is re-tuned after the sealed numbers are read; every variant tried is logged in `notes/research/backtesting.md`.
5. `rule` is the change in plain words, by code (what was tested); `text` and `why` are the model's.
6. **Honesty fields:** `variants_tried` (`distinct_priced` = the model's priced variants plus the engineer's smoke tests that priced and aren't the same change, ≥ the variants listed; `model_priced`, `model_rejected`, `smoke_tests_run`, `smoke_tests_priced`, `smoke_tests` [{`rule`, `priced`, `same_as`?, `why`?}], `log`); `disclosure` (sentences: smoke tests whose held-out numbers were seen; the model's rule wording and definitions come from the full-window strategy profile; kept = held up, not proven); `kept_label` = "held up (not proven)", the UI's word for kept; `luck_test` = `{story: "27", status}`; `kept_all_trail_spy` = every kept variant is behind SPY in dev and in sealed. The UI shows the disclosure, the count tried, the luck caveat and story 27, and never calls a kept change proven.

```json
"improvements": {
  "agent_id": "daytrader-improver-v2", "prompt_version": "improver-v2", "model": "anthropic/claude-sonnet-5-5",
  "trajectory_id": "…", "prism_url": "https://prism.blockconvey.com/trajectories/…",
  "version": "v1", "portfolio": "all", "delay_min": 5,
  "window": {"dev_from": "2024-08-15", "sealed_from": "2025-06-12", "sealed_to": "2025-09-12"},
  "basis": "…", "picked_on": "dev", "keep_rule": "…", "min_trades": 30,
  "kept_label": "held up (not proven)", "variants_tried": {"distinct_priced": 10, "model_priced": 6, "model_rejected": 0,
  "smoke_tests_run": 6, "smoke_tests_priced": 5, "smoke_tests": [{"rule": "Skip TSLA shorts", "priced": true}], "log": "…"},
  "disclosure": ["…"], "luck_test": {"story": "27", "status": "not run"}, "kept_all_trail_spy": true,
  "as_is": {"dev": {"trades": 239, "ret_pct": -4.73}, "sealed": {"trades": 103, "ret_pct": 2.08}},
  "spy": {"symbol": "SPY", "basis": "total_return", "dev_to": "2025-06-11", "dev_ret_pct": 10.47, "sealed_ret_pct": 9.64},
  "variants": [{"id": "V1", "text": "In big tech trades, skip adds priced worse than the first buy's fill",
                "rule": "No adds below the first buy (above it for shorts): big tech",
                "kind": "no_add_against", "when": {"group": ["big tech"]}, "why": "…",
                "dev": {"trades": 239, "ret_pct": 6.94, "as_is_ret_pct": -4.73, "vs_as_is_pts": 11.67,
                        "spy_ret_pct": 10.47, "vs_spy_pts": -3.53},
                "sealed": {"trades": 104, "ret_pct": 4.12, "as_is_ret_pct": 2.08, "vs_as_is_pts": 2.04,
                           "spy_ret_pct": 9.64, "vs_spy_pts": -5.52},
                "kept": true, "kept_reason": "gained on dev and did not lose on the held-out (sealed) months"}],
  "rejected": [{"text": "…", "why": "look_ahead_or_unknown_feature:adds"}]
}
```

## `strategy-lab` (`results/strategy-lab.json`, new file; spec-audit CAP-15, story audit-21-new-stocks)

His profitable rules (S4, S5 of `strategy_profile`) run as code, with no post from him, on prices after his window and on stocks he never traded. Rules, universes, windows, costs and variants: `notes/research/strategy-as-code.md`, committed before the first run (`preregistered_sha`). Written only by `app/backtest/lab.py`; recomputed by `app/audit/lab.py` inside `audit.run`; shown by `web/` as the "His strategy on new data" card (a missing file hides it). Not a course file: `audit.run`'s course glob (`results/*/*.json`) never reads it.

1. **Top level:** `schema` `"strategy-lab/1"`, `generated_at`, `git_sha`, `preregistered_sha`, `spec` (the path), `window` `{from, to, slice_from}`, `money_start` 10000, `per_trade_usd` 1000, `costs` (the three cost models, in words and numbers), `variants_tried` (every run in `runs` plus the picker versions logged in the spec), `fetch` `{minute_ticker_days, runs, cap_per_run, note}`.
2. **`benchmark`:** `{symbol: "SPY", basis, from_close, to_close, ret_pct, max_drawdown_pct, slice: {ret_pct}}` (total return, Alpaca daily `adjustment=all`).
3. **`universes`:** `[{id, which: "a" | "b", label, tickers, rule, deviation?}]`; ids `his-hot`, `his-crypto`, `new-hot`, `new-crypto`, and `new-hot-raw` (the disclosed correction after the PR #71 review, with its `deviation` text; top-level `deviations` lists them). The pre-registered `verdict` reads only the pre-registered lists; `verdict.S4.corrected_list` reads `his-hot` and `new-hot-raw`.
4. **`rules`:** `[{id: "S4" | "S5" | "C", label, text, entry_et, universes}]`.
5. **`variants`:** `[{id: "P" | "no-stop" | "exit-11" | "gap-10", gap_pct, stop_pct (null = none), exit_et}]`.
6. **`runs`:** one row per rule × variant × universe (C has variant `"control"`): `{rule, variant, universe, primary, trades, won_pct, pnl_usd, end, ret_pct, max_drawdown_pct, longest_losing_streak, worst_day: {day, pnl_usd}, spy_ret_pct, vs_spy_pts, word, outcome, sized_down, skipped: {no_bars}, costs: {x2: {ret_pct, word}, small_cap: {ret_pct, word}}, borrow: {htb_trades, unknown_trades, borrow_high_ret_pct}, vs_random: {twin_pnl_usd, p2_5, p97_5, pct_rank, draws} | null, slice: {trades, ret_pct, spy_ret_pct, word}}, cost_cases: {simple | realistic | x2: {pnl_usd, ret_pct, word, outcome, borrow_usd}}}` (`cost_cases` since spec-audit story 29: rule 5's three cases; `simple` equals the run's own numbers; `realistic` per side is the old `small_cap` model, plus the borrow fee for one day by flag; the older `costs` and `borrow` keys stay as they were). Money in dollars to the cent, percents to 0.01 pt; `word` and `outcome` per contracts rule 9 against SPY.
7. **`verdict`:** per rule (S4, S5): `{held_up: bool, why}`: held up only when the primary run says `Yes` on both its (a) and (b) universes.

```json
{"schema": "strategy-lab/1", "preregistered_sha": "abc1234", "window": {"from": "2025-09-15", "to": "2026-10-16", "slice_from": "2026-07-01"},
 "benchmark": {"symbol": "SPY", "ret_pct": 14.2, "max_drawdown_pct": -8.1, "slice": {"ret_pct": 3.1}},
 "runs": [{"rule": "S4", "variant": "P", "universe": "new-hot", "primary": true, "trades": 212, "won_pct": 51, "pnl_usd": -123.45,
           "end": 9876.55, "ret_pct": -1.23, "max_drawdown_pct": -4.5, "longest_losing_streak": 7, "worst_day": {"day": "2026-01-05", "pnl_usd": -210.0},
           "spy_ret_pct": 14.2, "vs_spy_pts": -15.43, "word": "No", "outcome": "Lost money", "sized_down": 3, "skipped": {"no_bars": 0},
           "costs": {"x2": {"ret_pct": -1.6, "word": "No"}, "small_cap": {"ret_pct": -2.9, "word": "No"}},
           "borrow": {"htb_trades": 40, "borrow_high_ret_pct": -1.39},
           "vs_random": {"twin_pnl_usd": -80.1, "p2_5": -400.2, "p97_5": 310.5, "pct_rank": 41.0, "draws": 2000},
           "slice": {"trades": 50, "ret_pct": 0.4, "spy_ret_pct": 3.1, "word": "No"}}],
 "verdict": {"S4": {"held_up": false, "why": "…"}}}
```

## `paper` (`results/paper/`, new folder; spec-audit CAP-18, story audit-30-paper)

The forward paper test: the frozen rules in `app/paper/rules-v1.json` (S4 and S5 of `strategy-lab`, variant `P`, S4 on `his-hot` + `new-hot-raw`, S5 on `his-crypto` + `new-crypto`, the realistic cost model) traded with fake money, one completed session at a time, from the first session that opens after the freeze commit (tag `paper-rules-v1`, `0e79dd8`, 2026-10-20T21:38:43Z). Fills are computed from Alpaca market data; no order goes to any broker (AGENTS.md rule 7). Written only by `app/paper/run.py` (`cd app && uv run python -m paper.run`, run daily by hand); recomputed by `app/audit/paper.py` inside `audit.run`; shown by `web/` as the "Paper test since <date>: N days" card (a missing file hides it). Not a course file: `audit.run`'s course glob skips `results/paper/`.

1. **Rules never change in place.** `rules-v1.json` is hashed (`rules_sha256`); the run refuses a file that differs from the one at tag `paper-rules-v1` (`git show paper-rules-v1:app/paper/rules-v1.json`; the freeze sha and time also come from the tag), and every ledger line carries the hash. A rule change is `rules-v2.json` with its own freeze and its own ledger; past sessions are never re-simulated.
2. **`ledger.jsonl`:** append-only, one line per counted session, in order, none skipped: `{day, rules, rules_sha256, spy_factor, rules_out: {S4|S5: {trades, skipped, notional, equity}}}`. `spy_factor` = SPY close(day) / close(previous session), Alpaca daily `adjustment=all` (a one-day ratio, so later dividend back-adjustment can't change it). `trades`: `[{ticker, list, gap, entry_ts, entry, exit_ts, exit, kind: "time" | "stop" | "last", adv_usd, easy_to_borrow: bool | null, pnl: {realistic, x2, base}}]` (times unix seconds, bar open; prices raw); `skipped`: `[{ticker, why: "no_bars"}]`; `notional` and `equity` per cost model (`equity` = the account's end of session, starting at 10000).
3. **Cost models** (frozen in the rules file): `realistic` per side 50 bps under $5, 30 under $10, else 5, plus 10 when the 20-session average dollar volume is under $50M, plus one day of a 100%-a-year borrow fee (0.4% of notional) on names not flagged easy to borrow (flag read when the session is simulated; unknown pays); `x2` all of that doubled; `base` contracts rule 5, no fee.
4. **`summary.json`:** `{schema: "paper/1", generated_at, rules_file, rules_version, rules_sha256, freeze: {sha, tag, at}, status: "waiting" | "running", first_session, last_session, days, money_start, per_trade_usd, cost_models, benchmark: {symbol: "SPY", ret_pct, basis}, rules: [{id, label, text, lists, trades, won_pct, stops, skipped_no_bars, sized_down_days, hard_to_borrow_trades, unknown_borrow_trades, costs: {realistic|x2|base: {end, ret_pct, max_drawdown_pct}}, vs_spy_pts, word, vs_random}]}`. `days` = sessions counted; `benchmark.ret_pct` = the product of the ledger's `spy_factor`s. `word` per contracts rule 9 on the realistic return vs SPY. `vs_random` is null under 30 trades, then `{twin_pnl_usd, p2_5, p97_5, pct_rank, draws}` (the daily twin vs 2,000 seeded draws of as many ticker-sessions from the same lists since the freeze). Rewritten when a session is added or when its `last_session` / `days` disagree with the ledger (a run that died between the two writes).
5. **Cache (gitignored):** `data/paper/daily/<day>.json` (the daily bars and borrow flags a session used, fetched once; an empty Alpaca answer is never cached, the session waits and the next run retries it) and the shared `data/bars/alpaca_1m/`. The audit reads only these.

```json
{"schema": "paper/1", "freeze": {"sha": "0e79dd8…", "tag": "paper-rules-v1", "at": "2026-10-20T21:38:43Z"},
 "status": "running", "first_session": "2026-10-21", "last_session": "2026-10-23", "days": 3,
 "benchmark": {"symbol": "SPY", "ret_pct": 0.42},
 "rules": [{"id": "S4", "trades": 4, "won_pct": 75, "stops": 1, "hard_to_borrow_trades": 1,
            "costs": {"realistic": {"end": 10031.2, "ret_pct": 0.31, "max_drawdown_pct": -0.2}, "x2": {"end": 10012.0, "ret_pct": 0.12, "max_drawdown_pct": -0.3}, "base": {"end": 10045.9, "ret_pct": 0.46, "max_drawdown_pct": -0.1}},
            "vs_spy_pts": -0.11, "word": "Not enough trades", "vs_random": null}]}
```
## `cost_cases` (additive; spec-audit CAP-17, story audit-29-costs)

Every course file (`results/<course>/<version>.json`) carries it. Each headline (every testable portfolio, every delay) priced under rule 5's three cost cases. Written by `app/backtest/run.py` from `app/backtest/costs.py`; recomputed by `app/audit` (its own cost code, its own trades) inside `audit.run`; the web card leads with `default` and shows the other two on a toggle. `portfolios` keep the `simple` numbers (unchanged); `cost_cases.portfolios[].by_delay[d].simple` must equal them.

1. **Top level:** `cases` `["simple", "realistic", "x2"]`, `default` `"realistic"`, `models` `{case: plain words}`, `bps_per_side` (the numbers of rule 5), `borrow` `{source, checked: {from, to}, rates_pct_per_year: {easy, hard, unknown, crypto}, flags: {ticker: "easy" | "hard" | "unknown" | "crypto"}, shorted_tickers, hard, unknown}` (`flags` lists every ticker the file's priced positions short, headline and `same_sessions` together).
2. **`portfolios`:** `[{id, by_delay: {"<delay>": {simple | realistic | x2: row}}}]`, same ids as the file's testable `portfolios`. A row: `end`, `ret_pct`, `hold_ret_pct`, `trades`, `won_pct`, `sized_down`, `couldnt_copy`, `costs_usd` (spread, slippage and borrow of the copied trades), `borrow_usd`, `word`, `outcome`, `vs` and `sealed {ret_pct, hold_ret_pct, trades, word, outcome, vs}` (rule 9, against the same benchmark as the file's headline).
3. **`same_sessions`** (proof-set files only): `{by_delay: {"<delay>": {case: row}}}`, v1 on the same sessions under each case, not judged (`word`, `vs` null); the proof-set headline's row under a case is judged against this row under the same case (rule 9).
4. Money to the cent, percents to 0.01 pt; tolerance in the audit as for the headline ($1, 0.01 pt; counts and words exact).

```json
"cost_cases": {"cases": ["simple", "realistic", "x2"], "default": "realistic",
  "models": {"simple": "5 bps a side, 20 under $10, 25 crypto; no borrow fee", "realistic": "…", "x2": "…"},
  "borrow": {"source": "Alpaca easy_to_borrow, as of the lookup", "checked": {"from": "2026-10-20", "to": "2026-10-20"},
             "rates_pct_per_year": {"easy": 0.5, "hard": 30, "unknown": 30, "crypto": 10},
             "flags": {"TSLA": "easy", "XYZ": "hard"}, "shorted_tickers": 2, "hard": 1, "unknown": 0},
  "portfolios": [{"id": "all", "by_delay": {"5": {
      "simple": {"end": 9735.45, "ret_pct": -2.65, "trades": 342, "costs_usd": 410.2, "borrow_usd": 0, "word": "No", "...": "..."},
      "realistic": {"end": 9500.1, "ret_pct": -5.0, "trades": 342, "costs_usd": 640.9, "borrow_usd": 21.3, "word": "No", "...": "..."},
      "x2": {"...": "..."}}}}]}
```

