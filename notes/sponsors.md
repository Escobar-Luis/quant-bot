# Sponsors

**Verified live 2026-10-17:** `smoke.py` got a Nicrron reply (`nicrron/auto` picked `anthropic/claude-haiku-5-5`; `response.model` shows the pick) and PRISM stored the trace and agent run. `prismtrace.verify`: CREDENTIAL OK, LIVE CONNECTED. The key in `.env` can read the Knowledge Base and call `/api/guardrails/evaluate` (both 200).

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
- **Skills / SDK:** `prismtrace-sdk` 0.5.3 (in `app/`). Integrations: manual traces and `@pt.trace` decorator, `submit_trajectory` (ordered steps: reasoning, tool_call, final_answer), OpenAI Agents SDK processor (preview), LangChain, LangGraph, Google ADK, LiteLLM callback, Claude tool-use tracer, OpenTelemetry exporter, ElevenLabs live voice (PII scrubbed server-side). `agent_id` is what guardrail and alert rules scope to: mint once, never change. The zero-code proxy doesn't cover Nicrron, so we trace by hand.
- **Prize rewards:** (pending event research)

### How each proof works (docs + SDK source, 2026-10-17)
- **Agent run + Steps:** `submit_trajectory(agent_id, conversation_id, steps=[...], final_status="success"|"error")`. `final_status="error"` is what the "Failed" filter shows. Tool calls are `step_type: "tool_call"` with `tool_name`. Each run is judged on 15 rules (safety 35, correctness 30, efficiency 17.5, robustness 17.5).
- **Versions:** no version field. Use one `agent_id` per version (`quant-bot-v1`, `quant-bot-v2`) plus `metadata.agent_version`.
- **Knowledge Base:** upload .txt/.md/.pdf (text layer) in the UI or `kb_upload`; assign each doc to one agent (agents appear only after their first trace). `kb_search` records no step: log retrieval ourselves as a `tool_call` step. Retrieved text becomes `{context}` for evaluators. v2 needs docs reassigned.
- **Root Cause:** "Analyze now" clusters failing traces (5 credits). Tiers: Corroborated, Likely, Tentative, Needs review. With a GitHub repo connected, it drafts a prompt patch, replays failing traces, opens a draft PR only if 80%+ pass. Minimum run count not documented.
- **Evaluators (Builder plan):** LLM-judge rubric over `{input}`, `{output}`, `{context}`, labels + pass threshold, 1 credit per trace. Experiments/datasets are off, so v1 vs v2 = replay the same inputs through both agents and run the evaluator per agent.
- **Alerts:** metric (latency, satisfaction_score, error_rate, traces_per_hour, guardrail_blocks, evaluation_failed) + threshold + optional agent + email. Error rate = traces with empty output.
- **Guardrails (Builder plan):** Flag or Block. Only 4 rule types run: Prompt Injection, PII/PHI, Regex, Off-Topic ("guaranteed returns" → Regex). Inline: POST `/api/guardrails/evaluate` `{project_id, messages, trace_id, agent_id}` before the model call; `blocked: true` → skip the model, return `fallback_message`; `evaluated: false` → fails open. Block check: send the trace under the same `trace_id` with no LLM call after the block → honoured (`enforced_inline`); an LLM call after → not honoured; no trace id → unverifiable. Clock-sensitive.
- **Free automatic scoring:** satisfaction, quality, intent, flagged; finance conversations get extra checks for rate promises and regulated activity.

### Budget (Free / Builder)
- 100 / 200 automatic analyses a day; 2,000 ingest requests a minute.
- Credits: 100 / 400 per cycle plus 100 welcome. Intelligence costs 1 credit per unanalysed trace, evaluators 1 per trace, Root Cause 5. Plan runs so 50+ traces, two evaluator passes and a few re-clusters fit.
- Host: the SDK defaults to `https://api.prism.blockconvey.com`; the docs also name `https://prism.blockconvey.com`. If `verify` fails, try the other. OTLP: `https://prism.blockconvey.com/api/otlp`, `http/protobuf`, header `X-PRISMtrace-Key`.

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
