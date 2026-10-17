# Day Trader AI

**Did the trading courses I paid for actually work?**

Day Trader AI copies every trade a paid trading course posted, with $10,000 of fake money and real trading costs, and compares the result with just holding the market. Then an agent proposes a better version, which is kept only if a sealed test agrees.

- **Live app:** https://day-trader-ai.vercel.app (open in a private window to see onboarding)
- **Demo video (58 s):** [watch the demo](https://claude.ai/artifact/13kzNaaYG9PjSkgw8ZB5Qi)
- Built at MONEY TALKS 2 (AI × Finance hackathon, NYC, 2026-10-17), Money Intelligence track.

## The answer

Every posted trade copied at $1,000 a trade, entering 5 minutes after each post, after costs:

| Course | Verdict | $10k became | Just holding |
|---|---|---|---|
| Learn Plan Profit (a year of live sessions, 315 trades) | **No** | $9,766 | $11,964 (S&P 500) |
| Crypto Wizard | **Yes**, it lost less than holding | $9,221 | $7,543 (Bitcoin) |
| ZipTrader | **Not enough trades** to judge | $10,007 (1 trade) | n/a |

Every number in the app is read from [`results/`](results/). The delay slider (1 minute to 1 hour) and the time ranges recompute from the same files.

## Why it matters

- US retail options traders lost about **$2.1B** in 20 months (Bryzgalova, Pavlova & Sikorskaya, *Journal of Finance*, 2023).
- The FTC alleges one "trading education" company took **$1.2B+** from consumers since 2018.
- **26%** of US investors act on social-media personalities' tips (FINRA Foundation, 2025).

Sources and more: [`notes/research/us-evidence.md`](notes/research/us-evidence.md).

## How it works

1. **Collect:** course posts and live sessions (Discord and YouTube) are read with Luis's own access. Raw content stays on his machine and is never committed.
2. **Extract:** Nicrron models read screenshots, transcribe sessions and pull out each trade and rule, with a citation.
3. **Backtest:** each trade is priced on real 1-minute bars (Alpaca for stocks, Binance for crypto), with costs and a $10k exposure cap.
4. **Verdict:** results are written as JSON, and the web app reads only those files.
5. **Prove:** every run is traced to PRISM, which holds the Knowledge Base, the Root Cause clusters and the evaluator scores.

Architecture and contracts: [`_bmad-output/planning-artifacts/spec-day-trader-ai/`](_bmad-output/planning-artifacts/spec-day-trader-ai/), rules for every agent in [`AGENTS.md`](AGENTS.md).

## Proof it's honest (PRISM)

- **Knowledge Base:** verdict runs retrieve and cite course strategy cards (paraphrased, quotes of 12 words or fewer).
- **Root Cause:** PRISM clustered 25 failed runs of the LPP extractor v1 into one cause.
- **Evaluator:** failed runs dropped from 28 of 30 (v1) to 18 of 30 (v2), and our "numbers grounded" check rose from 52% to 66%. PRISM's own judge scored 50% vs 47%, because it saw cut-off outputs; we show that caveat rather than hide it.
- **Improver:** the agent proposed "skip short-breakdown entries from 10:00 ET". It helped on the tuning months (−1.34% → +0.50%) but not on the sealed months (−0.09% → −0.09%), so it is **not kept**.
- **Honest backtests:** a sealed holdout the model never saw, every version logged, and trade sizes scaled to $1,000 so a $10k follower could actually copy them.

## Sponsors

- **Nicrron:** every model call: extraction, vision, transcription, embeddings, the improver and the demo voice-over.
- **PRISM by Block Convey:** tracing, Knowledge Base, Root Cause, evaluators.

## Run it

```bash
cd app && uv sync && uv run python -m backtest.run
```

```bash
cd web && npm install && npm run dev
```

Keys go in a local `.env` (see `app/.env.example`); never commit it.

## Not financial advice

This is a research tool. It uses fake money and published trades, and says nothing about what anyone should buy. Course content belongs to its creators: the repo holds only derived rules and short citations.
