# MONEY TALKS 2: AI x Finance Hackathon

- **When / where:** Saturday 2026-10-17, Nomad Works, 1216 Broadway, New York
- **Page:** (pending research)
- **Build window:** (pending)   **Demo length:** (pending)
- **Hand-in:** (pending)
- **Public link (hello-world live):** (pending)

## Brief

Three tracks, themes not assignments. Build anything inside one: an agent, a tool, a product, a workflow.

Only two things are required:
1. Build on **PRISM by Block Convey** and show the three PRISM proofs for the chosen track.
2. Build with **NicrronNinoo**: model calls through the Nicrron API, or the app through Ninoo.

Safety: made-up or sample data only. No real card numbers, bank logins or personal financial details.

### Tracks and required PRISM proofs

**Money Intelligence** (investing, research, portfolio, personal finance)
1. Knowledge Base: upload filings/statements, assign to the agent, show a run whose retrieval step used them.
2. Root Cause: an Intelligence cluster of 3+ failed runs and its cause, plus one sentence on why.
3. Evaluator: our own evaluator (e.g. "every number is in the source") scoring v1 and v2 on the same inputs.
- Demo: the failure, the fix, the score that proves it.

**Money Operations** (payments, expenses, invoices, budgeting, CFO workflows)
1. Sessions: one run on the Steps tab showing every tool call (6+ steps).
2. Alert: on failed tool call, cost or latency, shown firing on a real run.
3. Root Cause: a cluster of 3+ failed runs and its cause, then v2 on the same inputs no longer failing.
- Demo: the failure, the fix, the alert that would have caught it.

**Trust & Risk** (fraud, compliance, risk, security)
1. Guardrail: our own finance-risk guardrail (account/card numbers, SSNs, "guaranteed returns", unlicensed advice) in enforce mode, blocking a real run.
2. Block check: on the Guardrails page, whether the block was honoured / not honoured / unverifiable, and whether PRISM got it right.
3. Root Cause: a cluster of 3+ failed or blocked runs and its cause.
- Demo: the risk, the guardrail, the run it stopped.

PRISM tip from organizers: get 50+ runs into PRISM before fixing anything; clusters and evaluator scores need real runs. 200 runs/day analysed per workspace.

## Judging criteria (with weights)
(pending research; the PRISM proofs are explicitly part of judging)

## Sponsors, and what each prize rewards
- **PRISM by Block Convey** (required): observe, root-cause, evaluate, guardrail. Code `MONEYTALKS#2` at Settings → Billing. One workspace per team. SDK `prismtrace-sdk` or OpenTelemetry exporter.
- **NicrronNinoo** (required, technology sponsor): Nicrron API (OpenAI-compatible, `https://api.nicrron.ai/v1`, 80+ models, `nicrron/auto`), Ninoo Builder (plain-English app → `*.ninoo.app`), Ninoo Code (terminal agent). $260/participant via code `FINTECH-LPBMK`. Credits expire 2026-10-18 18:00 ET.
- **ElevenLabs** (optional): voice/chat agents, TTS, transcription. Free Creator month via their Discord #coupon-codes. Showcase submission for merch.

## The question
Sponsor tech (Track A): do we understand PRISM + Nicrron well enough to apply them creatively? The track proofs make PRISM's observe → fix → prove loop the centre of the demo.

## Winning here means
(draft) A finance agent whose demo visibly fails, gets fixed, and is proven better with PRISM evidence, running on Nicrron, solving a pain a real finance user has.

## Answer
X for [user] who [pain]; on screen they see Z; [sponsors] do Y.
