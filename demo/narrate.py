"""Turn demo/narration.md's voice-over block into demo/narration.mp3.

    python3 demo/narrate.py                        # ElevenLabs if its key works, else Nicrron
    python3 demo/narrate.py --provider nicrron     # force one: elevenlabs | nicrron
    python3 demo/narrate.py --voices               # list ElevenLabs voices

Keys live in ~/dev/quant-bot/.env and are never printed:
- ElevenLabs: ELEVENLABS_API_KEY, optional ELEVENLABS_VOICE_ID (else the premade default below).
- Nicrron (OpenAI-compatible /audio/speech): NICRRON_API_KEY, optional NICRRON_BASE_URL.
Standard library only.
"""
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ENV = pathlib.Path.home() / "dev/quant-bot/.env"
ELEVEN = "https://api.elevenlabs.io"
ELEVEN_VOICE = "nPczCjzI2devNBz1zQrb"  # Brian, premade: deep, calm American narrator
ELEVEN_MODEL = "eleven_multilingual_v2"
NICRRON = "https://api.nicrron.ai/v1"
NICRRON_MODEL = "openai/tts-1-hd"  # from Nicrron's GET /v1/models
NICRRON_VOICE = "onyx"


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


def fetch(url, headers, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def eleven_ok(key):
    try:
        fetch(f"{ELEVEN}/v1/user", {"xi-api-key": key})
        return True
    except urllib.error.HTTPError:
        return False


def eleven(text, key):
    voice = env("ELEVENLABS_VOICE_ID") or ELEVEN_VOICE
    audio = fetch(f"{ELEVEN}/v1/text-to-speech/{voice}?output_format=mp3_44100_128", {"xi-api-key": key},
                  {"text": text, "model_id": ELEVEN_MODEL,
                   "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2, "use_speaker_boost": True}})
    return audio, f"ElevenLabs, voice {'custom' if voice != ELEVEN_VOICE else 'Brian'}"


def nicrron(text):
    key = env("NICRRON_API_KEY")
    if not key:
        sys.exit("NICRRON_API_KEY missing in ~/dev/quant-bot/.env")
    base = (env("NICRRON_BASE_URL") or NICRRON).rstrip("/")
    audio = fetch(f"{base}/audio/speech", {"Authorization": f"Bearer {key}"},
                  {"model": NICRRON_MODEL, "voice": NICRRON_VOICE, "input": text, "response_format": "mp3"})
    return audio, f"Nicrron {NICRRON_MODEL}, voice {NICRRON_VOICE}"


def seconds(path):
    try:  # macOS
        out = subprocess.run(["afinfo", str(path)], capture_output=True, text=True).stdout
        m = re.search(r"estimated duration:\s*([\d.]+)", out)
        if m:
            return float(m.group(1))
    except FileNotFoundError:
        pass
    return path.stat().st_size / 16000  # rough: 128 kbps


def main():
    provider = sys.argv[sys.argv.index("--provider") + 1] if "--provider" in sys.argv else None
    ekey = env("ELEVENLABS_API_KEY")
    if "--voices" in sys.argv:
        for v in json.loads(fetch(f"{ELEVEN}/v1/voices", {"xi-api-key": ekey or ""}))["voices"]:
            print(v["voice_id"], v["name"], v.get("category"))
        return
    if provider is None:
        provider = "elevenlabs" if ekey and eleven_ok(ekey) else "nicrron"
        if provider == "nicrron":
            print("ElevenLabs key missing or rejected; using Nicrron")
    text = voiceover()
    if provider == "elevenlabs":
        if not ekey:
            sys.exit("ELEVENLABS_API_KEY missing in ~/dev/quant-bot/.env")
        audio, who = eleven(text, ekey)
    elif provider == "nicrron":
        audio, who = nicrron(text)
    else:
        sys.exit("--provider must be elevenlabs or nicrron")
    out = HERE / "narration.mp3"
    out.write_bytes(audio)
    secs = seconds(out)
    print(f"wrote {out.name}: {secs:.0f} s, {len(text.split())} words, {who}")
    if secs > 60:
        print("over 60 s: trim the voiceover block in narration.md")


if __name__ == "__main__":
    main()
