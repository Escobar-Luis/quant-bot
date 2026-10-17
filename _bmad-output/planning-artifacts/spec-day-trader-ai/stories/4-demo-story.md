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
