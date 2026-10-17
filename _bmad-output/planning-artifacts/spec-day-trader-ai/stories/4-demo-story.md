---
title: 'story/4-demo-story: script, narration, recording'
type: 'feature'
created: '2026-10-17'
status: 'in-progress'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/event.md'
  - '{project-root}/_bmad-output/planning-artifacts/spec-day-trader-ai/SPEC.md'
  - '{project-root}/_bmad-output/planning-artifacts/spec-day-trader-ai/lanes.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The hackathon is judged on a live demo (no slides) of the Money Intelligence story: the failure, the fix, the score that proves it. Nobody has written what Luis says and clicks, the voice-over, or the Devpost answers.

**Approach:** In `demo/` only: a live-demo script under 3 minutes on the public app (north-star problem → a real verdict → the delay slider → the three PRISM proofs), a 30-60 s ElevenLabs narration of the short version (`demo/narration.mp3`), a recording plan for the real deployed app (never the mock; anything not live is labelled), and `demo/submission.md` with Devpost answers Luis pastes himself. Every number comes from `results/` or `proofs/` and says which file.

</frozen-after-approval>

## Implementation Notes

- 14:50: LPP v1 is already real in the live bundle (`$8,806` at 5 min), so the script leads with LPP, not Crypto Wizard.
- `proofs/prism.json` (PR #15) still has `null` for Knowledge Base, Root Cause and PRISM pass rates; only the code-mirror evaluator (52% → 66%) is real. The script names a fallback for each proof and labels it.
- The bmad spec lives beside stories 1 and 2 (`stories/`); every other file is under `demo/`.
- 15:05: story 1 regenerated results after its code review (LPP $8,806 → $9,766, 287 → 315 trades); the script and submission now cite today's files, and `check_numbers.py` finds them on main or the writing branch.
- ElevenLabs returns 401 "Invalid API key" for the key in `.env`; `narration.mp3` waits on a new key. Recording waits on the 15:30 full-flow test.

## Review Triage Log

Blind Hunter, pass 1 (20 findings):
- high, patched: the root cause we stated wasn't the team's (now `notes/sources/lpp.md` §7, both causes, and the ledger part of the fix).
- high, deferred to story 3: the app picks the highest version, so a rebuild shows LPP v2 (52 sessions) as the headline; `check_numbers.py` now warns.
- high, deferred to story 3: the proof drawer renders `null` PRISM values as "0% → 0%" / "null failed runs"; the script's pre-stage check now avoids those cards.
- medium, patched: 28/30 failed vs 52% passing read as a contradiction (each now names its check); setup vs live Google sign-in; swipe order (LPP → ZipTrader → Crypto Wizard); beats and narration too long (narration 138 words, `narrate.py` prints seconds); Nicrron never named; KB missing from narration; README command printed nothing; checker silently printed `None`; ZipTrader prices are Yahoo; the problem citation (now the FTC's Warrior Trading finding and the Brazil study); "sealed" overclaimed; 29 vs 30 explained; recording fallback and deadline; private repo is Luis's call.
- low, patched: Q&A prep added; "fake money" rule dropped.
- low, rejected: Vercel URL vs AGENTS.md's Ninoo-first (Vercel is the live fallback after 15:00); caption timings (set when the video is cut).
