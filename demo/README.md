# Demo (story/4-demo-story)

| File | What | Status |
|---|---|---|
| `script.md` | ~2:50 live demo, words on top of story 5's click path (`tests/flow/demo-run.md`) | Ready (28 → 18 failed runs, PRISM judge 50% → 47% with its caveat) |
| `narration.md` | ~55 s voice-over text and captions | Ready |
| `narration.mp3` | 57 s voice-over, made by `python3 demo/narrate.py` (Nicrron `openai/tts-1-hd`, voice onyx; ElevenLabs when its key works) | Ready |
| `submission.md` | Devpost answers, ready to paste | Draft; **[fill]** marks PRISM values and the video link |
| `explainer.md` | 44 s animated architecture explainer: link, source, what it shows | Ready; Nicrron voice (ElevenLabs key in `.env` is the key ID) |
| `check_numbers.py` | Prints every number the script says, from the files; exit 1 while anything is pending | Works |

## Before you go on stage (or submit)

```bash
git -C ~/dev/quant-bot fetch -q origin && python3 demo/check_numbers.py
```

Compare its output with the "Numbers on screen" table in `script.md`. It finds each file in this checkout, `origin/main`, or the branch that writes it.

## Recording

- **Video:** https://claude.ai/artifact/13kzNaaYG9PjSkgw8ZB5Qi (private until Luis shares it). File: `demo/out/day-trader-ai.mp4` (gitignored; the GitHub release carries it).
- Three parts, one Nicrron voice (`demo/merged/`):
  1. **The problem** (`act1.html`, ~25 s): courses post wins, never a full record; $2.1B (Journal of Finance, 2023); the FTC on Warrior Trading (2022); Luis's three courses; the question.
  2. **The live app** (~45 s): a fresh window on https://day-trader-ai.vercel.app, real clicks: onboarding, LPP verdict, delay chips, Crypto Wizard, ZipTrader, the proof sheet, the agent's change "not kept".
  3. **How it works** (~38 s): the architecture explainer (`demo/explainer.md`) from its map pull-out to "No: $9,766 vs $11,964".
- Make it: `python3 demo/merged/voice.py act1` and `act2` (voice + Whisper times), then `node demo/merged/record.mjs all` (needs `playwright` and ffmpeg). Acts 1 and 2 are recorded from Chrome's screencast with each frame's own timestamp, so voice and picture stay in sync; captions are an overlay added for the recording.
- ElevenLabs refuses the key in `.env` (it's the key's ID), so the voice is Nicrron's (`openai/tts-1-hd`, onyx) throughout. Luis chose to keep it.
