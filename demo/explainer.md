# Architecture explainer (44 s, animated)

How the services talk and where the data comes from, following one real trade.

- **Video:** https://claude.ai/artifact/L6Tnm9Tv86SwP79MTkPyeE (44 s, private until Luis shares it).
- **Source:** HyperFrames project `~/dev/showcase-videos/day-trader-arch/` on Luis's Mac (its own git; `STORYBOARD.md` has the beats and the real-vs-illustrative list). Made with the architecture-explainer-video skill.
- **Path shown:** the courses (YouTube live sessions, Discord) → Nicrron (reads captions and chart images, writes each trade as data) → code checks → `data/` on Luis's laptop → backtester at Alpaca and Binance minute prices, 5 minutes late, after costs → `results/lpp/v1.json` → the web app on Vercel. PRISM sits underneath: traced extraction, verdict and improver runs; Knowledge Base search (card LPP-AVOID-2); Root Cause, 25 failed runs in one cluster; Evaluator, 28 → 18 failed runs of 30, numbers check 52% → 66%. Ends on Learn Plan Profit: No, $9,766 vs $11,964.
- **The trade:** TSLA short, "Let's do 50 shares short. 22840.", posted 2025-04-09 9:31 ET; in 9:37 at $228.09, out 2025-04-10 at $260.58, −8.2% (`results/lpp/v1.json`, `by_delay.5`).
- **Not shown on purpose:** Whisper and embeddings. They were planned (`notes/strategy-pipeline.md`) but the merged code doesn't use them.
- **Voice:** `voice.py` uses ElevenLabs (`ELEVENLABS_VOICE_ID`) when `ELEVENLABS_API_KEY` works, otherwise Nicrron text-to-speech. This cut is narrated by Nicrron (`openai/tts-1-hd`, onyx): the key in `.env` is the key's ID, not the `sk_…` secret, so ElevenLabs refuses it.
