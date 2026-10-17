# Lanes: one story per lane

One story = one branch = one worktree = one agent. No two stories write the same file. `app/pyproject.toml` and `app/uv.lock` are shared: add a dependency in its own small commit and expect to rebase. Collectors keep their own folders (`app/lpp/`, `app/collect/*`, `data/<course>/`); nobody else writes there.

## story/1-copy-trade-backtest — Data & strategy

**Owns:** `app/backtest/**`, `results/**`.
**Reads:** `data/<course>/events.jsonl` and `sources.jsonl` (collector shapes in the pipeline hand-over note), `data/bars/` (reuse `app/lpp/bars.py` by import once `story/extract-lpp` merges; until then a loader in `app/backtest/` writing the same cache), `AGENTS.md` contracts.
**Acceptance:**
1. `uv run python -m backtest.run --course lpp --version v1` writes `results/lpp/v1.json` that matches `contracts.md`, for every delay in `[1, 3, 5, 10, 15, 30, 60]`.
2. Trades are split into `day`, `swing`, `options` (counted, untestable), `crypto`, plus `all`; the answer word follows rule 9.
3. One trade per course is hand-checked: entry equals the open of the 1-minute bar at post time + delay.
4. Costs and just holding (SPY or BTC) are applied as in `contracts.md`; every `assumed` choice is in `unknown`.
5. `results/lpp/v1.json` lands by 15:00 even if partial; then `v2` (when `extract-lpp-v2` events exist), `cryptowizard/v1`, `ziptrader/v1`.
6. Stretch, only after 5: the improver (CAP-9) as `daytrader-improver-v1`, never reading the sealed window.

## story/2-prism-proofs — PRISM proofs

**Owns:** `app/prism/**`, `kb/**`, `proofs/**`.
**Reads:** `results/<course>/<version>.json`, `data/<course>/events.jsonl`, the `extract-lpp-v1/v2` runs already in PRISM (it does not re-run extraction; `extract-lpp` does).
**Acceptance:**
1. **Knowledge Base:** `kb/<course>-strategy-cards.md`, `-events-summary.md`, `-untestable.md` (paraphrase, locators, quotes ≤ 12 words) uploaded and assigned to `daytrader-verdict-v1`, then `-v2`.
2. A `daytrader-verdict-v1` run per course whose Steps tab shows a `kb_search` `tool_call` with the query and returned snippets; its answer cites a card.
3. **Root Cause:** "Analyze now" on 3+ failed `extract-lpp-v1` runs; the cluster name, tier, PRISM's cause and our one sentence go in `proofs/prism.json`.
4. **Evaluator:** "Numbers grounded" scores `extract-lpp-v1` and `-v2` on the same 30 sessions; pass rates and links in `proofs/prism.json`. Second evaluator ("every number in the verdict is in the results file") on verdict v1 vs v2 if credits allow.
5. Credits stay under 150 of 200; the spend is logged in `proofs/README.md`.
6. Bonus only after 1-4: `evaluation_failed` alert, Regex guardrail on "guaranteed" or "risk-free".

## story/3-web-app — UI & deploy

**Owns:** `web/**`.
**Reads:** stamp-v2 (`app/mock/variants/stamp-v2/index.html` on `spike/ui-variations`, PR #8), `results/_sample.json` now and `results/<course>/<version>.json` later, `proofs/prism.json`, `CLERK_PUBLISHABLE_KEY` from `.env`.
**Acceptance:**
1. Hello world first: `web/` (Vite) with stamp-v2's look live on the Ninoo URL, reading `results/_sample.json`; Vercel fallback if Ninoo or Clerk fails by 15:00.
2. Real Google sign-in and sign-out via Clerk (CAP-3); the Apple button removed.
3. Onboarding (CAP-4), verdict per course (CAP-5) with the delay slider (CAP-1), portfolios as the learning view (CAP-6), a trade chart with post and entry markers using TradingView Lightweight Charts (CAP-7), the proof drawer (CAP-8).
4. Every number comes from the JSON files; nothing hard-coded; `sample: true` files show the "Sample data" badge.
5. Works at 375 px and desktop widths; `?still=1` skips motion.
6. Stretch: the day view (CAP-2) from `results.days`.

## story/4-demo-story — Demo

**Owns:** `demo/**`.
**Reads:** the public URL, `results/`, `proofs/prism.json`, `event.md` (hand-in needs: video link, repo, track, how it handles uncertainty, tools, team roles).
**Acceptance:**
1. `demo/script.md`: under 3 minutes, the failure → the fix → the score, on the real app, with the PRISM screens to show.
2. ElevenLabs narration of the script (`demo/narration.mp3`), key from `.env`.
3. A screen recording of the real deployed app with the narration; the link in `demo/README.md`.
4. `demo/submission.md`: Devpost answers, ready to paste.
5. Script draft by 15:15 on sample data; final pass after the 15:30 test.

## story/5-full-flow-test — Full-flow test (from ~15:30)

**Owns:** `tests/flow/**`.
**Reads:** everything; writes nowhere else.
**Acceptance:**
1. On the public URL, phone and desktop: sign in, onboarding, each course verdict, slider at 1, 5 and 15, proof drawer, sign out; results in `tests/flow/report.md` with screenshots.
2. A script checks that every number shown for LPP equals `results/lpp/<version>.json` and that `proofs/prism.json` links open.
3. Each bug goes to the owning lane through the orchestrator; this story fixes nothing outside `tests/flow/`.
4. A pass/fail call by 15:55, before the 16:00 freeze.
</content>
</invoke>
