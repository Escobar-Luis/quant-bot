# Demo (story/4-demo-story)

| File | What | Status |
|---|---|---|
| `script.md` | 2:45 live demo on the real app: problem → verdict → slider → failure, fix, score | Draft on real LPP, Crypto Wizard, ZipTrader results; PRISM lines wait on `proofs/prism.json` |
| `narration.md` | ~55 s voice-over text and captions | Ready |
| `narration.mp3` | ElevenLabs voice-over, made by `python3 demo/narrate.py` | Blocked: the key in `.env` is rejected ("Invalid API key") |
| `submission.md` | Devpost answers, ready to paste | Draft; **[fill]** marks PRISM values |
| `check_numbers.py` | Prints every number the script says, from the files | Works |

## Recording

- **Video link:** pending.
- Record the real deployed app (https://day-trader-ai.vercel.app), never the mock. Anything not live gets an on-screen label ("Not live yet").
- Plan: screen recording of the script's beats (sign-in → LPP verdict → slider → Crypto Wizard and ZipTrader → proof drawer → PRISM tabs) with `narration.mp3` under it; or the architecture-explainer-video skill for a 30 s how-it-works cut.
- Starts after the 15:30 full-flow test, once PRISM's three proofs show on screen.

## Before you go on stage

```bash
python3 demo/check_numbers.py --ref origin/main
```

Compare its output with the "Numbers on screen" table in `script.md`.
