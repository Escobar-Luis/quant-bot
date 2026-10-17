# Ideas (first pass, Mary)

Unlocks we're building on (from the SDK source and live API, 2026-10-17):
- **PRISM:** the whole observe → root-cause cluster → evaluator v1/v2 → enforce-mode guardrail + block check loop; built-in Knowledge Base retrieval (`kb_upload`, `kb_search`), so no vector DB of our own; trajectory scores (goal adherence, tool compliance, efficiency, safety); live ElevenLabs call tracing with server-side PII scrubbing.
- **Nicrron:** one key, 87 models (Claude 5.x, GPT-5.x, Grok, DeepSeek, Kimi, Mistral) plus embeddings; swap models with zero code; very cheap models (e.g. `anthropic/claude-haiku-5-5`, `openai/gpt-5-nano`) make the 50+ runs PRISM needs nearly free.

## Broad applications

| # | Track | Idea | Sponsor glue |
|---|---|---|---|
| 1 | Intelligence | **Number auditor:** investment memo from 10-K / earnings call where every number cites its source | KB retrieval; evaluator "every number is in the source" |
| 2 | Intelligence | **Backtest claim checker:** reads a strategy pitch ("40%/yr"), reproduces it with data, flags look-ahead and overfitting | tool steps; evaluator "every claimed metric reproduced" |
| 3 | Intelligence | **Portfolio "what changed and why"** morning brief, spoken | KB + ElevenLabs voice |
| 4 | Intelligence | **Risk-factor diff:** year-over-year 10-K risk factor changes, explained | KB; evaluator "every new risk quoted verbatim" |
| 5 | Intelligence | **Personal finance Q&A** over sample statements, with citations | KB |
| 6 | Operations | **Month-end close:** bank vs ledger reconciliation, step by step | 6+ tool steps; alert on failed tool call |
| 7 | Operations | **AP 3-way match:** invoice ↔ PO ↔ receipt, flags only exceptions | steps; alert on cost/latency |
| 8 | Operations | **Scattered-data CFO flash:** SharePoint/CSV/core exports → one weekly report | steps; Ninoo dashboard |
| 9 | Operations | **Expense policy auditor** | steps; alert |
| 10 | Trust & Risk | **Finfluencer / advisor copy reviewer:** blocks "guaranteed returns" and personal advice before publishing | enforce-mode guardrail; block check |
| 11 | Trust & Risk | **Bank voice line screener:** voice agent that never reads out account numbers or SSNs | ElevenLabs + PRISM live voice tracing + guardrail |
| 12 | Trust & Risk | **Quant-bot seatbelt:** guardrail between an LLM trading agent and a paper broker; blocks orders that break risk limits | guardrail; root cause on blocked runs |
| 13 | Cross | **Model risk validation in an afternoon:** run one finance agent across 5 Nicrron models, PRISM scores each, output a model-risk scorecard (SR 11-7 style) | Nicrron model swap × PRISM evaluators |
| 14 | Cross | **Guardrailed research desk:** #1's memos pass #10's compliance guardrail before reaching clients | KB + evaluator + guardrail |

## Mary's strongest 3 (before judging criteria land)

1. **#1 Number auditor** (Intelligence): the track's proofs map 1:1; hallucinated numbers are a vivid failure with an obvious fix and a score that proves it.
2. **#12 Quant-bot seatbelt** (Trust & Risk): fits the repo name; "the run it stopped" is a dramatic demo.
3. **#13 Model risk validation** (cross): uses both sponsors' unlocks most deeply; banks' model-risk teams are a real buyer.

Next: pain evidence for the chosen 3 (who hurts, a number, real complaints), then glue and lock the answer line in `event.md`.
