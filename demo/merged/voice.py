"""Voice one act: demo/merged/<act>.txt -> demo/out/<act>.mp3 + demo/out/<act>.json (Whisper word times).
   python3 demo/merged/voice.py act1 [elevenlabs|nicrron]"""
import importlib.util, json, pathlib, sys, urllib.request, uuid
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "out"; OUT.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location("n", str(HERE.parent / "narrate.py"))
n = importlib.util.module_from_spec(spec); spec.loader.exec_module(n)
act = sys.argv[1]
text = " ".join((HERE / f"{act}.txt").read_text().split())
ekey = n.env("ELEVENLABS_API_KEY")
provider = sys.argv[2] if len(sys.argv) > 2 else ("elevenlabs" if ekey and n.eleven_ok(ekey) else "nicrron")
audio, who = n.eleven(text, ekey) if provider == "elevenlabs" else n.nicrron(text)
mp3 = OUT / f"{act}.mp3"; mp3.write_bytes(audio)
key = n.env("NICRRON_API_KEY"); b = uuid.uuid4().hex
part = lambda k, v: f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
body = (part("model", "openai/whisper-1") + part("response_format", "verbose_json") + part("timestamp_granularities[]", "word") + part("timestamp_granularities[]", "segment")
        + f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="a.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n').encode() + audio + f"\r\n--{b}--\r\n".encode()
d = json.loads(urllib.request.urlopen(urllib.request.Request("https://api.nicrron.ai/v1/audio/transcriptions", data=body,
    headers={"Authorization": "Bearer " + key, "Content-Type": f"multipart/form-data; boundary={b}"}), timeout=180).read())
(OUT / f"{act}.json").write_text(json.dumps({"who": who, "duration": n.seconds(mp3), "segments": d.get("segments"), "words": d.get("words")}))
print(f"{act}: {who}, {n.seconds(mp3):.1f} s, {len(text.split())} words")
for s in d.get("segments", []): print(f"  {s['start']:6.2f} {s['end']:6.2f} {s['text']}")
