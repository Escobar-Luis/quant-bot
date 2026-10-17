# Guardrails: allowlist-only web access for the quant-bot agent (research, 2026-10-17)

Read-only research: no PRISM rules or settings were created or changed. Tags: **[V]** verified live or in source today, **[D]** docs only, **[?]** unverified, test first. Paper trading and fake data only.

## 1. PRISM, what actually works
1. **Plan gate [V]:** `GET /api/entitlements` shows `plan: free`, `guardrails: read true, write false`, 100 analyses/day, so `MONEYTALKS#2` (Builder) is not active yet; rules can't be created until it is. [docs/Plans](https://blockconvey.com/docs)
2. **Ten rule types exist; four run via evaluate [D]:** Prompt Injection, PII/PHI, Regex Pattern Match, Off-Topic, checked in that order, first matching block rule decides. The other six are "coming soon". [docs/Guardrails](https://blockconvey.com/docs)
3. **Inline call [V]:** `POST /api/guardrails/evaluate` with `{project_id, messages, trace_id?, agent_id?}` and header `X-PRISMtrace-Key`; one benign call returned `200 {"blocked":false,"evaluated":true,"flagged":false,"flags":[],"latency_ms":80}`. [docs/Guardrails](https://blockconvey.com/docs)
4. **Flag vs Block [D]:** each rule has one action; Flag only records on the Guardrails page, Block returns `blocked:true` plus `rule_name`, `rule_type`, `matched_text`, `fallback_message`. Live response also carries `flagged` and `flags`, which the docs table says are not returned, so a Flag rule is a safe test probe [?]. [docs/Guardrails](https://blockconvey.com/docs)
5. **PRISM never stops our tool call [D]:** only the zero-code proxy prevents; on the SDK/HTTP path "ask PRISM first and enforce the answer yourself", and the proxy covers Anthropic/OpenAI/Gemini, not Nicrron. So code must enforce. [docs/Integrations](https://blockconvey.com/docs), [notes/sponsors.md](../sponsors.md)
6. **Only the last user message is checked [D]:** assistant and tool messages are ignored, so a URL must be put into a synthetic final `role:"user"` message, e.g. `FETCH host=evil.example`. [docs/Guardrails](https://blockconvey.com/docs)
7. **Regex allowlist [?]:** the rule type is "your own patterns", engine undocumented. A block rule can express an allowlist only as a negative lookahead (`^FETCH host=(?!(?:sec\.gov|fred\.stlouisfed\.org)$)`), which needs a backtracking engine (Python `re` yes, RE2/Rust no). Test with a Flag rule before trusting it. [docs/Guardrails](https://blockconvey.com/docs)
8. **Fails open [D]:** `evaluated:false` (plan_not_entitled, internal_error) means nothing ran; our code must apply its own fail mode (deny). [docs/Guardrails](https://blockconvey.com/docs)
9. **Enforcement Check [D]:** needs the same `trace_id` on evaluate and on the trace. Honoured = no LLM span at/after the decision (tool and retrieval spans don't count) or, for a span-less trace, no output. Not honoured = LLM span or output after the block. Unverifiable = no `trace_id` or trace not found. Compares your span times to PRISM's clock, so keep NTP. [docs/Guardrails](https://blockconvey.com/docs)
10. **Alert [D]:** metric `guardrail_blocks` + threshold, optional agent scope; the agent_id must already exist on a trace or creation is refused. Free and Builder both get alerts. [docs/Alerts](https://blockconvey.com/docs)
11. **SDK 0.5.3 has no guardrail helper [V]:** only `trace_llm(trace_id=…)` and `submit_trajectory(…)` exist, so evaluate is a raw HTTPS call. No API to read Enforcement Check results was found (GET probes on `/api/guardrails*` gave 404/405); read it on the Guardrails page. [SDK client.py](../../app/.venv/lib/python3.13/site-packages/prismtrace/client.py)
12. **Trace shape [D]:** `POST /api/traces` requires `output_message` (send `""` for a blocked run) and a re-sent `trace_id` returns the existing trace, so send one trace per run id. Empty output for a blocked run is our inference [?]. [docs/API](https://blockconvey.com/docs)

## 2. Credible sources (all fetched today)
1. **OWASP LLM06 Excessive Agency:** limit tools to the minimum and "avoid open-ended extensions (e.g. fetch a URL)", the exact tool we expose. [genai.owasp.org](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
2. **OWASP LLM01 Prompt Injection:** indirect injection arrives via external content "such as websites or files". [genai.owasp.org](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
3. **OWASP SSRF cheat sheet:** where the destinations are known, when the callable destinations are known, enforce an allowlist at the application layer. [cheatsheetseries.owasp.org](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
4. **NIST AI 600-1 (Jul 2024) §2.9:** names indirect prompt injection as an information-security risk for GenAI apps that retrieve data. [nvlpubs.nist.gov](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
5. **FINRA 2026 oversight report, GenAI/agents:** lists autonomy, "scope and authority" (agents acting beyond intended scope), auditability; suggests tracking agent actions and "guardrails or control mechanisms to limit or restrict agent behaviors". [finra.org](https://www.finra.org/rules-guidance/guidance/reports/2026-finra-annual-regulatory-oversight-report/gen-ai)
6. **Greshake et al. 2023:** coined indirect prompt injection (attacker text planted in retrieved content). [arXiv 2302.12173](https://arxiv.org/abs/2302.12173)
7. **AgentDojo (NeurIPS 2024):** a simple tool filter cut attack success to 7.5%, but fails when allowed tools suffice for the attack (17% of cases). [arXiv 2406.13352](https://arxiv.org/abs/2406.13352)
8. **Progent 2025:** deterministic allow/block rules over tool names and arguments, least privilege, expansions need approval. [arXiv 2504.11703](https://arxiv.org/abs/2504.11703)
9. **Beurer-Kellner et al. 2025 / CaMeL 2025:** restrict what an agent may do after reading untrusted input; CaMeL solved 77% of AgentDojo tasks with provable security vs 84% undefended. [2506.08837](https://arxiv.org/abs/2506.08837), [2503.18813](https://arxiv.org/abs/2503.18813)
10. **Willison "lethal trifecta":** private data + untrusted content + outbound channel = exfiltration; cut one leg. The allowlist cuts the outbound leg. [simonwillison.net](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)

## 3. Design: code enforces, PRISM decides and proves
```
LLM proposes fetch_url(url) -> normalize -> PRISM evaluate(trace_id=run) -> code allowlist (deny wins) -> fetch or end run
```
1. **Single source of truth:** `ALLOWED_HOSTS` in code (illustrative: `sec.gov`, `fred.stlouisfed.org`, `api.bls.gov`); generate the PRISM regex from it (`"|".join(map(re.escape, ALLOWED))`) so they can't drift.
2. **Enforcer (code, fail closed):** `urllib.parse`, https only, no userinfo (`sec.gov@evil.example`), exact host or dot-suffix match (not `endswith`), no IP literals, resolve DNS and refuse private ranges, re-check every redirect hop, size/type caps. [OWASP SSRF](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
3. **Decider/auditor (PRISM):** always call evaluate before the fetch, even when code would already deny, so every attempt is on the Guardrails page. Rule: Regex, Block, scoped to `agent_id=quant-bot-research`, text `FETCH host=<canonical host>`. If PRISM and code disagree, deny and log `metadata.disagreement`. Fallback if lookahead is unsupported: code appends `allowlist=MISS` and the rule blocks that token (PRISM then audits rather than decides).
4. **Proof of "honoured":** one `trace_id` per run. On block: no tool result goes back to the model, no further Nicrron call, send the trace with `output_message=""` plus a trajectory ending `final_status="error"`, label `blocked: allowlist_miss`. Feeding the refusal to the LLM would add an LLM span after the block = "not honoured".
5. **Second sensor:** evaluate each fetched page's text (as a user message) so the Prompt Injection rule can flag planted instructions; max body size is unknown [?].
6. **Production note:** the safest tool is `fetch_source(source_id, path)` with an enum of sources and no URL; keep open `fetch_url` for the demo only, since a block needs an attack surface (OWASP LLM06 above).
7. **Residual risk:** an allowlisted host can still carry data in the query string; the demo has no private data (fake data only).

## 4. Trust & Risk proof plan (event.md)
1. **Runs first:** ~45 benign allowlisted runs, then ~15 adversarial; PRISM wants 50+ before fixing. Free allows 100 analyses/day, Builder 200; Root Cause costs 5 credits. [notes/sponsors.md](../sponsors.md)
2. **Cluster (one cause, 4-6 runs):** a fake allowlisted page carries "also fetch <url>"; the model obeys and the call is blocked. Vary the host so it isn't one string: `pastebin.example`, typosquat `sec-gov.example`, suffix trick `sec.gov.evil.example`, userinfo `sec.gov@evil.example`, IDN homograph. Common cause: untrusted page text treated as instructions.
3. **v2 fix:** quarantine page text (summarize with a tool-less model call), strip links, switch to `fetch_source` enum; replay the same inputs and compare blocks v1 vs v2 (design basis: [Beurer-Kellner et al.](https://arxiv.org/abs/2506.08837)).
4. **Alert:** `guardrail_blocks` above 2 for `quant-bot-research` (docs example is 10) fires during the adversarial batch.
5. **Order of work:** redeem Builder → Flag-rule lookahead test → send 1 benign trace so the agent_id exists → enforce rule → blocked runs → read Enforcement Check.

## 5. Test first (5 minutes, after Builder)
1. Flag rule `^FETCH host=(?!(?:sec\.gov)$)` on agent `guardrail-test`; evaluate `FETCH host=sec.gov` expects `flagged:false`, `FETCH host=evil.example` expects `flagged:true`. If both are false, lookahead isn't supported: use the `allowlist=MISS` fallback.
2. One blocked run with `trace_id`; confirm the Guardrails page says honoured (`no_downstream_execution`), then delete the test rule.
