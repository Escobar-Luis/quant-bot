"""YouTube json3 auto-captions -> timed words, prompt lines and a normalized text for code checks."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .common import YT

_PUNCT = re.compile(r"[^\w\s.$%]")


def norm(s: str) -> str:
    """Lowercase, drop punctuation (keep digits, '.', '$', '%'), collapse spaces. Used on both sides of every check."""
    s = s.lower().replace(",", "").replace("’", "'").replace("'", "")
    s = _PUNCT.sub(" ", s)
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)  # keep decimal points only
    return " ".join(s.split())


@dataclass
class Transcript:
    video_id: str
    words: list            # [(t_s, word)] in caption order
    release_ts: int | None  # live start, unix seconds
    duration: int | None
    title: str
    time_source: str = "release_timestamp"  # "timestamp" (upload time) makes wall_utc approximate

    @property
    def text(self) -> str:
        return " ".join(w for _, w in self.words)

    @property
    def ntext(self) -> str:
        return norm(self.text)

    def lines(self, every_s: int = 20) -> list[str]:
        """Prompt lines, each tagged with the time of its first word."""
        out, cur, t0 = [], [], None
        for t, w in self.words:
            if t0 is None:
                t0 = t
            if t - t0 >= every_s and cur:
                out.append(f"[t={int(t0)}] {' '.join(cur)}")
                cur, t0 = [], t
            cur.append(w)
        if cur:
            out.append(f"[t={int(t0)}] {' '.join(cur)}")
        return out

    def window(self, t_from: float, t_to: float) -> str:
        return norm(" ".join(w for t, w in self.words if t_from <= t <= t_to))

    def find(self, quote: str, near: float | None = None) -> float | None:
        """Time of the first word of `quote` in the captions (closest match to `near`), else None."""
        q = norm(quote).split()
        if not q:
            return None
        toks = [(t, norm(w)) for t, w in self.words]
        flat, at = [], []
        for t, w in toks:
            for p in w.split():
                flat.append(p)
                at.append(t)
        hits = [at[i] for i in range(len(flat) - len(q) + 1) if flat[i:i + len(q)] == q]
        if not hits:
            return None
        return min(hits, key=lambda h: abs(h - near)) if near is not None else hits[0]


def load(video_id: str) -> Transcript | None:
    d = YT / video_id
    caps = sorted(d.glob("*.en-orig.json3")) or sorted(d.glob("*.en.json3"))
    info_p = d / f"{video_id}.info.json"
    if not caps or not info_p.exists():
        return None
    info = json.loads(info_p.read_text())
    words = []
    for e in json.loads(caps[0].read_text()).get("events", []):
        if "segs" not in e or "tStartMs" not in e:
            continue
        for s in e["segs"]:
            for w in s.get("utf8", "").split():
                if w.startswith("[") and w.endswith("]"):  # [Music], [Applause]
                    continue
                words.append(((e["tStartMs"] + s.get("tOffsetMs", 0)) / 1000, w))
    rel = info.get("release_timestamp")
    return Transcript(video_id, words, rel or info.get("timestamp"), info.get("duration"), info.get("title", ""),
                      "release_timestamp" if rel else "timestamp")


def available() -> list[str]:
    return sorted(p.name for p in YT.iterdir() if p.is_dir() and load_ok(p))


def load_ok(d: Path) -> bool:
    return bool(list(d.glob("*.en-orig.json3")) or list(d.glob("*.en.json3"))) and (d / f"{d.name}.info.json").exists()
