# MONEY TALKS 2: AI x Finance Hackathon

- **When / where:** Saturday 2026-10-17, Nomad Works, 1216 Broadway, New York
- **Page:** https://luma.com/aq51ak1d (hosts: Block Convey, localhost:nyc). 445 registered.
- **Build window:** 10:00-18:00 ET per Luma; hacking/freeze/demo times not published (last event by the same hosts: hacking 11:15-16:30, Devpost due 16:30, demos 16:30-18:00). Money Talks 1 attendee: "promised 8 hours, got 4.5".   **Demo length:** not published
- **Hand-in:** via Discord and Builderbase (links not public); a private Devpost page likely exists (money-talks-2-nyc.devpost.com). Last event required: video demo link, GitHub repo, track, how it handles uncertainty, tools, team roles. Track sponsors bring specific challenges, shared on the day.
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
Not published. Luma: "No slide decks… real demos"; prove the PRISM connection in the final demo. Best stand-in, same hosts and sponsors (Get Hired Hack, Oct 10), each /5:
1. Technical execution: accuracy beats feature count.
2. Trust & explainability: flag what it doesn't know.
3. Design: a domain user can use it without a walkthrough.
4. Uniqueness of idea.

Judges (announced): Harish Nanjala (Beyond Alpha Ventures), Madhav Goenka (Celestral AI, voice), Aniket Soni (Cognizant), Allen M. C. (YC Club of HK, voice AI). Panel spans AI, fintech, investing, banking.

Money Talks 1 pattern (Sep 5): teams that posted all stressed citations, "unknown stays unknown", "the model proposes; the code decides", and PRISM trace evidence (one cited a 98.89 trajectory score). MT1 briefs: vendor security questionnaires (Trust & Risk), flux analysis (Money Operations).

## Sponsors, and what each prize rewards
Prizes: "cash prizes + partner credits", amounts not published. MT1: 1st $1,000 + $1,000+ credits; two runners-up $500 + $500 credits; interview chats with track sponsors. Agora is sponsoring tracks.
- **PRISM by Block Convey** (required): observe, root-cause, evaluate, guardrail. Code `MONEYTALKS#2` at Settings → Billing. One workspace per team. SDK `prismtrace-sdk` or OpenTelemetry exporter.
- **NicrronNinoo** (required, technology sponsor): Nicrron API (OpenAI-compatible, `https://api.nicrron.ai/v1`, 80+ models, `nicrron/auto`), Ninoo Builder (plain-English app → `*.ninoo.app`), Ninoo Code (terminal agent). $260/participant via code `FINTECH-LPBMK`. Credits expire 2026-10-18 18:00 ET.
- **ElevenLabs** (optional): voice/chat agents, TTS, transcription. Free Creator month via their Discord #coupon-codes. Showcase submission for merch.

## The question
Sponsor tech (Track A): do we understand PRISM + Nicrron well enough to apply them creatively? The track proofs make PRISM's observe → fix → prove loop the centre of the demo.

## Winning here means
A live demo (no slides) of a finance agent a domain user could run cold, where the code decides and the model proposes, it says what it doesn't know, and PRISM evidence proves the risk it stopped or the fix it made. Unique versus MT1's citation-and-questionnaire builds.

## Answer
X for [user] who [pain]; on screen they see Z; [sponsors] do Y.
