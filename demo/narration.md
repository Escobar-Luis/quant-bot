# Narration (the short version, under 60 seconds)

Voice-over for the recording and the Devpost video. `python3 demo/narrate.py` sends the block below to ElevenLabs, or to Nicrron (`openai/tts-1-hd`, voice onyx) when the ElevenLabs key is rejected, and writes `demo/narration.mp3`. Edit only the block, then run it again; it prints the length in seconds.

Numbers: `results/lpp/v1.json` (5-minute delay), `results/cryptowizard/v1.json`, `results/ziptrader/v1.json`, `proofs/prism.json`, `proofs/prism.json` `evaluator.failed_runs` and `root_cause`. Re-check them with `python3 demo/check_numbers.py` before generating. Third person on purpose, so any voice fits; with Luis's own voice in `ELEVENLABS_VOICE_ID`, "Luis paid" can become "I paid".

<!-- voiceover:start -->
Luis paid for three day-trading courses. None shows a full record. Would copying every trade they posted have worked?

Day Trader AI copies every trade with ten thousand fake dollars, after costs, against just holding the market.

Learn Plan Profit: no. Ten thousand dollars became nine thousand seven hundred sixty-six. Just holding the S and P five hundred made eleven thousand nine hundred sixty-four. Crypto Wizard: yes, it lost less than Bitcoin. ZipTrader: not enough trades.

An AI, through Nicrron, reads every session, and code checks every number. Version one failed our checks in twenty-eight of thirty runs: it quoted long stretches and lost track of open trades. PRISM grouped twenty-five of them into one cluster. Version two, partly a code fix, cut failures to eighteen. Our numbers check rose from fifty-two to sixty-six percent. Every answer cites the course notes it found in PRISM.

The model proposes. The code decides.
<!-- voiceover:end -->

## Captions (same words, for sound-off viewing)

1. Luis paid for three trading courses.
2. Would copying every trade have worked?
3. $10k fake money, after costs, vs just holding.
4. Learn Plan Profit: No. $10k → $9,766. Holding: $11,964.
5. Crypto Wizard: Yes (lost less than Bitcoin).
6. ZipTrader: not enough trades.
7. v1 failed our checks in 28 of 30 runs; PRISM clustered 25.
8. v2 (prompt + code fixes): 18 failures; our numbers check 52% → 66%.
9. Answers cite course notes in PRISM.
10. The model proposes. The code decides.

Timings get set when the recording is cut (`demo/README.md`).
