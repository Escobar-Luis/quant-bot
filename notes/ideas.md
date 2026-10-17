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

## Strongest 3: the pain each solves (evidence 2026-10-17)

| Rank | Application | Who hurts | Evidence | Pain |
|---|---|---|---|---|
| 1 | **#12 Quant-bot seatbelt** (Trust & Risk) | Retail users of agentic brokerage accounts; broker-dealer compliance; people building LLM trading agents | Robinhood: 150k+ agentic accounts, $100M+ assets, trades without per-trade approval ([PYMNTS](https://www.pymnts.com/?p=4264530)). Alpha Arena S1: 4 of 6 LLMs lost real money, GPT-5 -59% ([ForkLog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/)). A Claude paper agent opened 104 positions, ~$1.5M on $100k; a per-trade limit didn't stop it ([r/ai_trading](https://www.reddit.com/r/ai_trading/comments/1w5odv1/robinhood_says_50000_people_opened_accounts_where/)). FINRA 2026 Oversight Report covers AI agents first time ([Debevoise](https://www.debevoise.com/insights/publications/2025/12/finras-2026-regulatory-oversight-report-continued)); House FS members asked SEC who is accountable for agent trades, Jun 2026 ([Orrick](https://infobytes.orrick.com/2026-07-10/democratic-lawmakers-press-sec-on-broker-dealer-and-ai-developer-responsibilities-in-agentic-trading/)). SEC: AI-bot "guaranteed profit" schemes, $15M+ and $12.3M ([WealthManagement](https://www.wealthmanagement.com/regulation-compliance/sec-charges-two-firms-with-15m-crypto-fraud-scheme), [OECD](https://oecd.ai/en/incidents/2026-05-30-0fd1)). | Strong, very timely |
| 2 | **#1 Number auditor** (Intelligence) | Equity/credit analysts, IB associates, retail chatbot users | 5,000 annual reports: AI got figures wrong 18.2% from text, 9.2% from XBRL; mostly wrong line item or scale, invented <2% ([Thomson Reuters](https://tax.thomsonreuters.com/news/xbrl-cuts-ai-errors-in-reading-company-filings-study-finds/)). CAC 40 test: chatbots 0-13% correct without sources, up to 80% with retrieval ([UC Strategies](https://ucstrategies.com/news/dont-ask-ai-for-stock-advice-it-gets-financial-data-wrong-almost-every-time/)). Hebbia survey n=529: 49% say fast verification is essential ([CFOtech](https://cfotech.com.au/story/survey-finds-ai-core-to-wall-street-research-workflows)). Crowded (Hebbia, V7, AlphaSense); stand out by recomputing each number against XBRL. | Strong, crowded |
| 3 | **#13 Model risk validation** (cross) | Bank model validators, heads of model risk | Deloitte EMEA 2025 (87 banks): 76% use GenAI, 13-43% have a validated use case ([Deloitte](https://www.deloitte.com/content/dam/assets-zone2/dk/en/docs/generic/2025/2025-emea-model-risk-management-banks-orig.pdf)). A third of banks keep no GenAI logs ([Risk.net](https://www.risk.net/benchmarking/model-risk/7963835/a-third-of-banks-do-not-maintain-logs-for-genai-models)). SR 11-7 was replaced by SR 26-2 (Apr 2026), which leaves GenAI out of scope ([Fed](https://www.federalreserve.gov/supervisionreg/srletters/sr2602.htm)); reframe as filling that gap. Slow buyers. | Medium |

## Glue for the leader: quant-bot seatbelt (draft)

- **Nicrron:** the trading agent's model calls; run the same agent on several models through one key (the track's own suggestion: "test how different models behave against the same guardrail"). Cheap models make 50+ runs nearly free.
- **Our seatbelt code:** portfolio-level limits a per-trade cap misses: total exposure, position count, concentration, kill switch. Paper broker with fake money only.
- **PRISM guardrail (enforce):** every outgoing client note or order rationale goes through `/api/guardrails/evaluate` first. Regex for "guaranteed / risk-free / can't lose"; PII for account numbers and SSNs. Blocked → no model call, no order, fallback message.
- **PRISM proofs:** the block on a real run; the Enforcement Check showing "honoured"; a Root Cause cluster of 3+ blocked or failed runs (e.g. "agent over-trades after a drawdown").
- **Ninoo Builder:** review UI: positions, blocked actions, why.
- **ElevenLabs (optional):** spoken kill-switch alert.
