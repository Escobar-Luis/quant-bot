# Contracts

The short version lives in `AGENTS.md` (every agent reads it). This file holds the full shapes and the copy-trade rules. `results/_sample.json` is a valid example the web app can use before real results exist.

## Copy-trade rules (code, never the model)

1. **Post time:** the Discord message timestamp, or the video's `release_timestamp` + `t_s` for LPP. Never a time the model reads off an image.
2. **Delay:** `delays_min = [1, 3, 5, 10, 15, 30, 60]`; the slider opens at 5. The delay applies to entries and to exits the course announces.
3. **Entry:** the open of the first 1-minute bar at or after post time + delay. If the post gives a trigger level, entry is when price trades the trigger after post time + delay; if it never does, no trade (counted as `not_triggered`).
4. **Exit**, first that applies: the course's own close or trim (+ delay); stop or target, whichever trades first (both in one bar = stop); the horizon as written; otherwise day trades at 15:55 ET the same session, swing trades after 5 sessions, crypto setups after 24 hours (all three `assumed`, listed in `unknown`).
5. **Costs per side:** 5 bps stocks, 20 bps stocks under $10, 25 bps crypto.
6. **Sizing:** $1,000 per trade. LPP scales the host's share counts so all of a trade's buys together come to $1,000, keeping his add/trim ratios (decided by Luis, 2026-10-17; wording clarified 2026-10-20 after the audit found two readings; superseded by the bankroll model in spec-audit CAP-9); an entry with no share count gets the upper median of his stated counts (with an even count, the higher of the two middle values); total open exposure is capped at cash, and trades that don't fit are sized down or counted as couldn't-copy. Each portfolio starts with $10,000 of fake money; unused cash earns nothing.
7. **Just holding:** $10,000 in SPY (stocks) or BTC (crypto) bought at the window's first trading minute, held to its end.
8. **Portfolios:** `day` (opened and closed the same session, or called intraday or a scalp), `swing` (held overnight, or a horizon in days), `options` (calls, puts, strikes or expiries: counted, `testable: false`), `crypto` (Crypto Wizard setups), and `all` (every testable trade in one account: the course headline).
9. **Answer word, per portfolio and delay:** fewer than 30 trades → `Not enough trades`; else return minus just holding's return ≥ +2 pts → `Yes`; within ±2 pts → `Barely`; ≤ −2 pts → `No`.
10. **Sealed window:** the last 3 months of each course's window (`window.sealed_from`). The as-taught test reports it for information; the later improver must never read it.

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
  "portfolios": [
    {
      "id": "all", "label": "Everything he traded", "testable": true,
      "by_delay": {
        "5": {"end": 9420, "ret_pct": -5.8, "hold_end": 11890, "hold_ret_pct": 18.9,
              "trades": 412, "not_triggered": 9, "won_pct": 44, "worst_drop_pct": -17, "word": "No",
              "sealed": {"ret_pct": -1.2, "hold_ret_pct": 3.1}}
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
