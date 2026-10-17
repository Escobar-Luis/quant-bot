# Demo (story/4-demo-story)

| File | What | Status |
|---|---|---|
| `script.md` | ~2:50 live demo on the real app: problem → verdict → slider → failure, fix, score | Ready on today's files; PRISM cluster and pass rates still pending |
| `narration.md` | ~55 s voice-over text and captions | Ready |
| `narration.mp3` | 55 s voice-over, made by `python3 demo/narrate.py` (Nicrron `openai/tts-1-hd`, voice onyx; ElevenLabs when its key works) | Ready |
| `submission.md` | Devpost answers, ready to paste | Draft; **[fill]** marks PRISM values and the video link |
| `check_numbers.py` | Prints every number the script says, from the files; exit 1 while anything is pending | Works |

## Before you go on stage (or submit)

```bash
git -C ~/dev/quant-bot fetch -q origin && python3 demo/check_numbers.py
```

Compare its output with the "Numbers on screen" table in `script.md`. It finds each file in this checkout, `origin/main`, or the branch that writes it.

## Recording

- **Video link:** pending.
- Record the real deployed app (https://day-trader-ai.vercel.app), never the mock. Anything not live gets an on-screen label ("Not live yet").
- Plan: a screen recording of the script's beats (LPP verdict → slider → ZipTrader and Crypto Wizard → proof drawer → PRISM tabs) with `narration.mp3` under it, captions from `narration.md`. Optional: a 30 s how-it-works cut with the architecture-explainer-video skill.
- Upload to YouTube (unlisted) or Loom; don't commit the video file.
- Timing: right after the 15:30 full-flow test. Deadline 16:15 whatever is live, PRISM cards that aren't live labelled "Pending".
- ElevenLabs keys (today's and yesterday's) are rejected, so the narration runs through Nicrron. A fresh ElevenLabs key in `.env` makes `narrate.py` switch back automatically.
