# Architecture, data, sponsors, deploy

## Six boxes

```
 Luis's Mac (private, gitignored data/)                    git (derived only)            public
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│ 1 Collectors         │──▶│ 3 Copy-trade         │──▶│ results/<course>/    │──▶│ 5 Web app (web/)     │
│ Discord + YouTube →  │   │   backtester         │   │   <version>.json     │   │ stamp-v2 + Clerk +   │
│ events.jsonl         │   │ portfolios × delays, │   └──────────────────────┘   │ Lightweight Charts   │
│ (Nicrron extracts)   │   │ costs, vs holding    │   ┌──────────────────────┐   │ on Ninoo             │
└──────────┬───────────┘   └──────────▲───────────┘   │ proofs/prism.json    │──▶│                      │
           │                          │               └──────────▲───────────┘   └──────────────────────┘
           │               ┌──────────┴───────────┐   ┌──────────┴───────────┐
           │               │ 2 Price bars         │   │ 4 Verdict agent      │
           │               │ data/bars/ cache     │   │ kb_search → results  │
           │               │ Alpaca, Binance,     │   │ → plain verdict      │
           │               │ yfinance             │   │ (Nicrron)            │
           │               └──────────────────────┘   └──────────┬───────────┘
           │                                                     │
           └───────────────────────▶ 6 PRISM ◀───────────────────┘
               extract-*-v1/v2 traces     Knowledge Base · Root Cause · Evaluator
```

1. **Collectors** (running: `extract-lpp`, `collect-ziptrader`, `collect-cryptowizard`): read Discord and YouTube read-only, extract trades, calls and rules with Nicrron, code-check every event, write `data/<course>/{sources,events}.jsonl`.
2. **Price bars**: one cache under `data/bars/`; stocks 1-minute from Alpaca, crypto 1-minute from Binance or Coinbase (keyless), daily from yfinance.
3. **Copy-trade backtester** (code, no model): copies every event at each delay, after costs, per portfolio, against just holding; writes `results/`.
4. **Verdict agent** (`daytrader-verdict-v1/v2`): retrieves the course cards from the PRISM Knowledge Base (logged as a `kb_search` step), reads the results file, writes the plain-language verdict; code checks every number against the file.
5. **Web app**: static; reads `results/` and `proofs/` only.
6. **PRISM**: traces from 1 and 4; Knowledge Base, Root Cause and Evaluator; summarized into `proofs/prism.json`.

## Data

| What | Where | In git? |
|---|---|---|
| Raw Discord posts, images, captions, transcripts | `~/dev/quant-bot/data/<course>/` | No (gitignored, Luis's Mac) |
| Extracted events and sources (JSONL, quotes ≤ 12 words) | `data/<course>/{sources,events}.jsonl` | No |
| Price bars | `data/bars/<source>/` | No |
| Optional local SQLite (`data/daytrader.db`) | Built later from the JSONL by one loader | No |
| Results per course and version | `results/<course>/<version>.json` | Yes (derived) |
| PRISM proof summary | `proofs/prism.json` | Yes |
| Knowledge Base docs (course cards, events summary, untestable) | `kb/<course>-*.md`, uploaded to PRISM | Yes (paraphrase, locators, quotes ≤ 12 words) |
| User identity | Clerk | n/a |
| Onboarding picks, chosen delay | The user's browser storage | n/a |

No Supabase: paid content stays on Luis's Mac, and the public app needs only derived JSON.

## Each sponsor's job

| Sponsor | Job | Where |
|---|---|---|
| Nicrron (required) | Event extraction (`anthropic/claude-sonnet-5-5` per whole source; `claude-haiku-5-5` for bulk images); the verdict agent; embeddings (`voyage/voyage-finance-2`) if the loader groups rules; later the improver | Collectors, `app/prism/` |
| PRISM (required) | Knowledge Base (course cards assigned to `daytrader-verdict-v1`, then `-v2`); Root Cause (cluster of failed `extract-lpp-v1` runs); Evaluator ("numbers grounded", v1 vs v2 on the same 30 sessions; second: "every number in the verdict is in the results file"). Bonus only: verdict runs with 6+ steps, an `evaluation_failed` alert, a Regex guardrail blocking "guaranteed" or "risk-free" | `app/prism/`, `proofs/` |
| ElevenLabs (optional) | Demo narration voice track only | `demo/` |
| Clerk | Google sign-in and sign-out (development instance) | `web/` |
| TradingView Lightweight Charts (free, open source) | The TradingView look for money-over-time and per-trade charts. TradingView's free plan has no data API, so data comes from Alpaca, Binance and yfinance | `web/` |

## Deploy

1. **Host: Ninoo Builder** (`*.ninoo.app`, Luis's pick). Ninoo imports from GitHub and works best with Vite; `web/` is a Vite app.
2. **Hello world first:** stamp-v2 inside `web/`, Clerk sign-in, reading `results/_sample.json`, live on the Ninoo URL before any real data.
3. **Fallback:** if the Ninoo import or Clerk on `ninoo.app` fails by 15:00, deploy `web/` to Vercel (`vercel --prod`; the CLI is installed here).
4. The public URL goes into `event.md` ("Public link").

## Luis's steps (accounts only he creates)

1. **Now, blocking LPP:** Alpaca "Paper Only" account (email only), paper API keys into `~/dev/quant-bot/.env` as `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`. Without them LPP has no 2024-25 minute bars.
2. Clerk app with Google on; publishable key into `.env` as `CLERK_PUBLISHABLE_KEY`.
3. Ninoo Builder account, with GitHub access to `Escobar-Luis/quant-bot`.
4. Optional: what each course cost (`course_fee_usd`).

## First test (the thin slice, by ~15:00)

On the public URL, on a phone: Google sign-in → onboarding → the LPP verdict screen showing the word and "$10k became $X" read from a **real** `results/lpp/v1.json` (even if only part of the sessions are priced) → the delay slider at 1, 5 and 15 minutes shows three different numbers → sign-out works. Behind it, one LPP trade hand-checked: its entry price equals the open of the 1-minute bar at post time + delay.
</content>
</invoke>
