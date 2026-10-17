# Demo (story/4-demo-story)

| File | What | Status |
|---|---|---|
| `script.md` | ~2:50 live demo, words on top of story 5's click path (`tests/flow/demo-run.md`) | Ready; only PRISM's own evaluator pass rates pending |
| `narration.md` | ~55 s voice-over text and captions | Ready |
| `narration.mp3` | 57 s voice-over, made by `python3 demo/narrate.py` (Nicrron `openai/tts-1-hd`, voice onyx; ElevenLabs when its key works) | Ready |
| `submission.md` | Devpost answers, ready to paste | Draft; **[fill]** marks PRISM values and the video link |
| `check_numbers.py` | Prints every number the script says, from the files; exit 1 while anything is pending | Works |

## Before you go on stage (or submit)

```bash
git -C ~/dev/quant-bot fetch -q origin && python3 demo/check_numbers.py
```

Compare its output with the "Numbers on screen" table in `script.md`. It finds each file in this checkout, `origin/main`, or the branch that writes it.

## Recording

- **Video:** https://claude.ai/artifact/13kzNaaYG9PjSkgw8ZB5Qi (private until Luis shares it). File: `demo/out/demo.mp4` (gitignored, 4 MB, 1440×810, 58.6 s).
- Recorded 15:27 ET on the live app, the same build story 5 passed at 15:24 (bundle `index-Db3xMx-B.js`). Real clicks on the deployed app, never the mock.
- Made by `node demo/record.mjs`: Playwright drives Google Chrome along `tests/flow/demo-run.md`, timed to `narration.mp3`; frames come from Chrome's screencast with their own timestamps, so voice and picture stay in sync. Captions and a corner label ("Live app · recorded … · AI voice") are an overlay added for the recording.
- Re-record after a redeploy: `node demo/record.mjs` (needs `playwright`, local or global, and ffmpeg), then republish the page with the new `demo/out/demo.mp4`.
- ElevenLabs keys (today's and yesterday's) are rejected, so the narration runs through Nicrron. A fresh ElevenLabs key in `.env` makes `narrate.py` switch back automatically.
