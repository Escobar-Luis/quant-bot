# Sponsors

| Sponsor | Unlock (what only it can do) | What we have access to | Prize rewards |
|---|---|---|---|
| PRISM by Block Convey (required) | Observe → root-cause cluster → evaluator v1/v2 → enforce-mode guardrail + block check, on one platform; built-in Knowledge Base retrieval; live ElevenLabs call tracing | Code `MONEYTALKS#2`; one workspace; 200 analysed runs/day | (pending) |
| NicrronNinoo (required) | One key, 87 models, fallback lists, routing slugs, free exact cache, finance embeddings | $260/person (`FINTECH-LPBMK`), expires 2026-10-18 18:00 ET | (pending) |
| ElevenLabs (optional) | Voice agents in 32 languages; PRISM traces calls live | Free Creator month via Discord | Showcase merch |

## PRISM by Block Convey
- **What it is:** agent observability plus evaluation plus guardrails. Every run is a trace; a session groups runs; the platform clusters failures and scores runs.
- **Unlock:** one loop from "it failed" to "here's proof the fix works": Root Cause clusters, custom Evaluators scoring v1 vs v2, enforce-mode Guardrails with a block check (honoured / not honoured / unverifiable). Built-in Knowledge Base (`kb_upload`, `kb_search`) means retrieval without our own vector DB. Trajectory scores: goal adherence, tool compliance, efficiency, safety.
- **Access:** sign up at prism.blockconvey.com, redeem `MONEYTALKS#2` (Settings → Billing), key at Settings → API Keys. 200 runs/day analysed. Organizers: get 50+ runs in before fixing.
- **Smallest working call:** `PRISMtrace(api_key, host, project_id).trace_llm(model=..., input_messages=..., output=..., latency_ms=..., agent_id=..., session_id=...)`; check with `python -m prismtrace.verify` (prints `CREDENTIAL OK`, `LIVE CONNECTED`). Env: `PRISMTRACE_API_KEY`, `PRISMTRACE_PROJECT_ID`, `PRISMTRACE_HOST` (default `https://api.prism.blockconvey.com`).
- **Skills / SDK:** `prismtrace-sdk` 0.5.3 (in `app/`). Integrations: manual traces and `@pt.trace` decorator, `submit_trajectory` (ordered steps: reasoning, tool_call, final_answer), OpenAI Agents SDK processor (preview), LangChain, LangGraph, Google ADK, LiteLLM callback, Claude tool-use tracer, OpenTelemetry exporter, ElevenLabs live voice (PII scrubbed server-side). `agent_id` is what guardrail and alert rules scope to: mint once, never change.
- **Prize rewards:** (pending event research)

## NicrronNinoo
- **What it is:** Nicrron API, an OpenAI-compatible gateway (`https://api.nicrron.ai/v1`, `NICRRON_API_KEY`); Ninoo Builder, plain-English app builder that publishes to `<app>.ninoo.app`; Ninoo Code, a terminal coding agent. One credit balance.
- **Unlock:**
  - one key, 87 models (66 chat, 10 embedding, audio, image, video); swap by model string;
  - routing slugs `nicrron/auto`, `nicrron/reasoning`, `nicrron/coding`, `nicrron/fastest`;
  - fallback array `models: [...]` on 429/5xx (cast past OpenAI SDK types);
  - free exact cache at `temperature: 0` (`X-Nicrron-Cache: HIT`; opt out with `x-nicrron-cache: false`, watch for stale live data);
  - Model Arena in the dashboard; zero retention for chat, embeddings and audio.
- **Access:** $260/person (`FINTECH-LPBMK` = $250 + $10 sign-up), expires 2026-10-18 18:00 ET. Price = provider list + 5% fee. Errors: 400, 402 (no credits, nothing charged), 404 (unknown model). Rate limits undocumented.
- **Smallest working call:** `OpenAI(base_url="https://api.nicrron.ai/v1", api_key=...).chat.completions.create(model="nicrron/auto", messages=[...])` (in `app/smoke.py`).
- **Endpoints:** `/chat/completions` (tools unified across providers, SSE streaming), `/embeddings` (`voyage/voyage-finance-2` $0.12/M finance-tuned; `openai/text-embedding-3-small` $0.02/M), `/audio/speech`, `/audio/transcriptions`, `/images/generations`, `/videos/generations`, public `GET /v1/models`. Structured output and PDF input: not documented.
- **Models (per 1M in/out):** `anthropic/claude-sonnet-5-5` $2/$10; `anthropic/claude-opus-5-5` $4/$20; `anthropic/claude-haiku-5-5` $0.10/$0.50 (100k ctx); `openai/gpt-5-nano` $0.05/$0.40; `deepseek/deepseek-flash` $0.30/$1.20. Which model `nicrron/auto` picked: dashboard logs only.
- **Ninoo Builder:** one-click publish; GitHub import only (no sync); Vite + React works best; calling our backend or holding secrets not documented, so keep keys server-side.
- **Ninoo Code:** `curl -fsSL https://ninoo.ai/install.sh | sh`, `ninoo login`; needs Node 20+. Optional for us.
- **Prize rewards:** (pending event research)

## ElevenLabs (optional)
- **Unlock for us:** PRISM's SDK traces ElevenLabs Agents calls live, turn by turn, with PII scrubbed server-side. A voice front end gets PRISM evidence for free.
- **Access:** Creator month via Discord #coupon-codes; key in `ELEVENLABS_API_KEY`.
