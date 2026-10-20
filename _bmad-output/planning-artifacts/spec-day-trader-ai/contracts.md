# Contracts

The short version lives in `AGENTS.md` (every agent reads it). This file holds the full shapes and the copy-trade rules. `results/_sample.json` is a valid example the web app can use before real results exist.

## Copy-trade rules (code, never the model)

1. **Post time:** the Discord message timestamp, or the video's `release_timestamp` + `t_s` for LPP. Never a time the model reads off an image.
2. **Delay:** `delays_min = [1, 3, 5, 10, 15, 30, 60]`; the slider opens at 5. The delay applies to entries and to exits the course announces.
3. **Entry:** the open of the first 1-minute bar at or after post time + delay. If the post gives a trigger level, entry is when price trades the trigger after post time + delay; if it never does, no trade (counted as `not_triggered`).
4. **Exit**, first that applies: the course's own close or trim (+ delay); stop or target, whichever trades first (both in one bar = stop); the horizon as written; otherwise day trades at 15:55 ET the same session, swing trades after 5 sessions, crypto setups after 24 hours (all three `assumed`, listed in `unknown`).
5. **Costs per side:** 5 bps stocks, 20 bps stocks under $10, 25 bps crypto.
6. **Sizing:** $1,000 per trade. LPP scales the host's share counts so all of a trade's buys together come to $1,000, keeping his add/trim ratios (decided by Luis, 2026-10-17; wording clarified 2026-10-20 after the audit found two readings; superseded by the bankroll model in spec-audit CAP-9; whole-trade scaling reads his later adds, see rule 13); an entry with no share count gets the upper median of his stated counts (with an even count, the higher of the two middle values). Cash cap, per buy (2026-10-20, audit-9): every fill is copied in time order; each buy takes its own money as it fills, never money for a later add; a buy that doesn't fit is sized down to the cash, or skipped at $1 or less (a first buy skipped = the trade couldn't be copied, and its later buys go with it); each sell returns the money in what it sold plus its gain, and a trade's costs leave cash at its last sell. At one moment sells go before buys, then by trade id, except that a trade's own fills keep their order. `sized_down` counts buys sized down or skipped. Measured peak money in positions (`all`, 5 min): LPP v1 as taught $3,584 (was $4,715 under the old whole-trade reservation), LPP v1 no_look_ahead $10,005, LPP v2 no_look_ahead $10,547 (before this per-buy cap, rule 13 reserved up to $10,811); above $10,000 only when realized gains have grown the cash. Each portfolio starts with $10,000 of fake money; unused cash earns nothing.
7. **Just holding:** $10,000 in SPY (stocks) or BTC (crypto) bought at the window's first trading minute, held to its end.
8. **Portfolios:** `day` (opened and closed the same session, or called intraday or a scalp), `swing` (held overnight, or a horizon in days), `options` (calls, puts, strikes or expiries: counted, `testable: false`), `crypto` (Crypto Wizard setups), and `all` (every testable trade in one account: the course headline).
9. **Answer word, per portfolio and delay** (amended 2026-10-20, spec-audit CAP-7: a word never reads as success when the copy lost money): fewer than 30 trades → `Not enough trades`; else a return below 0 → `No`; else return minus the benchmark's return ≥ +2 pts → `Yes`; within ±2 pts → `Barely`; ≤ −2 pts → `No`. The benchmark is just holding (rule 7), except in a proof-set file (one with `same_sessions`, LPP v2): its `all` portfolio is compared only with v1 on the same sessions (`same_sessions.by_delay`), its other portfolios carry no comparison (`word`, `vs` null), and it has no `strategies`, `ranges`, `combos` or `best_stop`. Each by_delay row also carries:
   - `outcome`: `Made money` (return > 0), `Lost money` (< 0), `Broke even` (0), `No trades` (0 trades).
   - `vs`: the comparison in plain words, gap = return − benchmark return: ≥ +2 → `beat <B>` (`less than <B>` when the copy lost money); within ±2 → `about the same as <B>`; ≤ −2 → `<B> did better` (`more than <B>` when the benchmark also lost). `<B>` is `compare_with.name`: `the S&P` (SPY), `Bitcoin` (BTC), `v1` (proof set). Null with 0 trades.
   - `sealed.word`, `sealed.outcome`, `sealed.vs`: the same three on the sealed months alone (rule 10), with the sealed trade count and the sealed benchmark return.
   The card reads outcome, then vs, then the sealed months' word: "Lost money, less than Bitcoin. Held-out months: No." Top-level `compare_with`: `{"kind": "hold" | "same_sessions", "name": "the S&P" | "Bitcoin" | "v1"}`.
10. **Sealed window:** the last 3 months of each course's window (`window.sealed_from`). The as-taught test reports it for information; the later improver must never read it.
11. **LPP ledger as taught** (documented from lpp.py 2026-10-20; the headline; uses later statements, see rule 13): his `trade` events are copied when every check passed, or when the only failed checks are the ledger checks `open_never_closed`, `close_without_open` or `qty_exceeds_position` (those are kept and resolved by this ledger); options are counted, not priced. Positions are kept per ticker and side; an exit that names no side belongs to his one open position on that ticker, else it is skipped; a buy (open or add) that names no side is skipped and counted. A position he still holds at the end of a session carries to a later session only when his next word on it within 7 days is an add, trim or close; otherwise it leaves at 15:55 ET of its session (assumed), and a later `open` starts a new position. An exit with no open position is skipped. A position whose legs span sessions is a swing trade (rule 8).
12. **Edge rules (adopted by Luis 2026-10-20 from the audit, notes/audit/findings-story-2.md):** (a) a horizon said only in the quote counts as written (rule 4) and belongs in the extraction's horizon field; (b) rule 11's look-ahead carry stays for the as-taught headline; rule 13 is its provisional no-look-ahead version; (c) a take-profit post after the copier's own target order filled sells nothing more; (d) a trigger crossed by a gap between bars fills at the gap bar's open; (e) a moved break-even stop hit in the same bar fills at the stop level; (f) rule 6 scales at the first fill's price (superseded by the bankroll model, spec-audit CAP-9); (g) a trim with no size sells half the position; (h) just holding ends at the official daily close, the last 1-minute close reported as an alternative. Added with PR #58: (i) when price data ends before the exit, the trade closes at the last bar's close; (j) a take-profit post for target n also sells the shares of earlier targets that never filled; (k) cash of $1 or less skips the trade (counted).
13. **No look-ahead, provisional** (spec-audit CAP-12, 2026-10-20; reported as the LPP `no_look_ahead` key, labelled provisional; not the headline until (i) his hold intent is extracted with timestamps into the `horizon` field (spec-audit story 17) and (ii) sizing and cash are look-ahead-free, which the bankroll model, story 8, delivers by replacing rule 6's sizing and cash rules; the headline stays rules 6 and 11 as taught): every copy decision uses only what he said before that moment. (a) Which events are copied, positions per ticker and side, side-less exits and exits with no open position: as rule 11. (b) A position leaves at 15:55 ET of the session its first leg was posted in, unless one of its legs, posted before that moment, states a horizon past the session (the extraction's `horizon` field, rule 12a): then it stays open to 15:55 ET of that horizon's last session, counted in weekdays from the session of the leg that said it (a horizon with no count is rule 4's 5 sessions; the latest end wins). (c) A word posted at or after the moment a position left starts afresh: an open or add opens a new position, a trim or close finds nothing open and is skipped. (d) A position held past its first session is a swing trade leaving at that moment; every other position is a day trade (rules 4, 8). (e) Sizing: the first buy is $1,000 at its fill price; each later add buys the first buy's shares × (his count for the add ÷ his count for the first buy), where a count he didn't state is the upper median of the counts he had stated on this position's buys posted up to that add (the two are equal when he has stated none); an add never takes the position past $10,000 held at the add's price; a trim sells the share of his stated holding so far that he trimmed (no size: half). ASSUMPTION: a holiday counts as a weekday session. Cash: rule 6's per-buy cap.

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

LPP files also carry `no_look_ahead` (rule 13, provisional): the same events through rule 13's ledger and sizing, shown beside the as-taught headline. Same row fields as `portfolios[].by_delay`, no series; in a proof-set file its rows carry no comparison (word and vs null, rule 9):

```json
"no_look_ahead": {"provisional": true, "label": "Provisional: no look-ahead", "rules": "contracts.md rule 13: ...",
                  "why_provisional": "...", "positions": 346,
                  "portfolios": [{"id": "all", "by_delay": {"5": {"end": 9313.42, "word": "No", "...": "..."}}},
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
