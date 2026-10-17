"""Turn demo/narration.md's voice-over block into demo/narration.mp3 with ElevenLabs.

    python3 demo/narrate.py            # writes demo/narration.mp3
    python3 demo/narrate.py --voices   # lists voices you can pick

Key: ELEVENLABS_API_KEY in ~/dev/quant-bot/.env (never printed). Voice: ELEVENLABS_VOICE_ID there if set,
else the premade default below. Standard library only.
"""
import json
import pathlib
import re
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ENV = pathlib.Path.home() / "dev/quant-bot/.env"
DEFAULT_VOICE = "nPczCjzI2devNBz1zQrb"  # Brian, premade: deep, calm American narrator
MODEL = "eleven_multilingual_v2"


def env(name):
    for line in ENV.read_text().splitlines():
        m = re.match(rf"\s*(?:export\s+)?{name}\s*=\s*(.*)$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'") or None
    return None


def voiceover():
    text = (HERE / "narration.md").read_text()
    m = re.search(r"<!-- voiceover:start -->(.*?)<!-- voiceover:end -->", text, re.S)
    if not m:
        sys.exit("narration.md has no voiceover block")
    return " ".join(m.group(1).split())


def call(path, body=None, key=None):
    req = urllib.request.Request(
        "https://api.elevenlabs.io" + path,
        data=json.dumps(body).encode() if body else None,
        headers={"xi-api-key": key or "", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    key = env("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY missing in ~/dev/quant-bot/.env")
    if "--voices" in sys.argv:
        for v in json.loads(call("/v1/voices", key=key))["voices"]:
            print(v["voice_id"], v["name"], v.get("category"))
        return
    voice = env("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    text = voiceover()
    words = len(text.split())
    audio = call(
        f"/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        {"text": text, "model_id": MODEL,
         "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2, "use_speaker_boost": True}},
        key,
    )
    out = HERE / "narration.mp3"
    out.write_bytes(audio)
    print(f"wrote {out.name}: {len(audio) // 1024} KB, {words} words, voice {'custom' if voice != DEFAULT_VOICE else 'Brian (default)'}")


if __name__ == "__main__":
    main()
