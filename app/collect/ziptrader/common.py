"""Shared bits for the ZipTrader collectors: data paths, the Nicrron client, text normalizing.

Raw course content lives only under DATA_DIR/ziptrader (gitignored), never in git.
Keys come from ~/dev/quant-bot/.env and are never printed.
"""
import base64
import io
import json
import os
import re
import subprocess
import time
from pathlib import Path

from dotenv import dotenv_values
from openai import OpenAI

HERE = Path(__file__).resolve().parent
SERVER_ID = "634553688605851658"
COURSE = "ziptrader"
PROMPT_VERSION = "zt-v1"
VISION_STRATEGY_MODEL = "anthropic/claude-sonnet-5-5"
VISION_BRIEFING_MODEL = "anthropic/claude-haiku-5-5"
XCHECK_MODEL = "openai/gpt-5.4-mini"


def main_checkout() -> Path:
    """The main checkout holds the shared .env and data/; every worktree points at it."""
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    return (HERE / common).resolve().parent if common else Path.home() / "dev/quant-bot"


ROOT = main_checkout()
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data")) / COURSE
DISCORD = DATA / "discord"
IMG = DISCORD / "img"
TRANSCRIPTS = DISCORD / "transcripts"


def env() -> dict:
    return {**dotenv_values(ROOT / ".env"), **{k: v for k, v in os.environ.items() if k.startswith(("NICRRON_", "ALPACA_"))}}


def client() -> OpenAI:
    e = env()
    return OpenAI(base_url=e.get("NICRRON_BASE_URL") or "https://api.nicrron.ai/v1", api_key=e["NICRRON_API_KEY"])


def chat(model: str, system: str, content, max_tokens: int = 4000, retries: int = 2) -> tuple[str, dict]:
    """One streamed call (long non-streamed calls can hit a 502 upstream timeout)."""
    c = client()
    for attempt in range(retries + 1):
        try:
            t = time.time()
            stream = c.chat.completions.create(
                model=model, temperature=0, max_tokens=max_tokens, stream=True,
                stream_options={"include_usage": True},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": content}])
            parts, usage = [], None
            for ev in stream:
                if ev.choices and ev.choices[0].delta and ev.choices[0].delta.content:
                    parts.append(ev.choices[0].delta.content)
                if getattr(ev, "usage", None):
                    usage = ev.usage
            meta = {"model": model, "secs": round(time.time() - t, 1),
                    "tokens_in": getattr(usage, "prompt_tokens", None), "tokens_out": getattr(usage, "completion_tokens", None)}
            return "".join(parts), meta
        except Exception:  # retry transient upstream errors, then give up loudly
            if attempt == retries:
                raise
            time.sleep(3 * (attempt + 1))


def png_data_url(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def parse_json(txt: str):
    txt = re.sub(r"^\s*```(?:json)?|```\s*$", "", txt.strip()).strip()
    return json.loads(txt)


_TRANS = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                        "→": "->", " ": " "})


def norm(s: str) -> str:
    """Lowercase, unify quotes and dashes, collapse whitespace: what the substring checks compare."""
    return re.sub(r"\s+", " ", (s or "").translate(_TRANS).lower()).strip()


def numbers_in(s: str) -> set[str]:
    """Numbers as written, without thousands separators: '52,177.69' -> '52177.69'."""
    return {n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", (s or "").replace(",", ""))}


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def write_jsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
