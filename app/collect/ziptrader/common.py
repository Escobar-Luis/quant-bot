"""Shared bits for the ZipTrader collectors: data paths, the Nicrron client, text and number normalizing.

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
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
SERVER_ID = "634553688605851658"
COURSE = "ziptrader"
VISION_STRATEGY_MODEL = "anthropic/claude-sonnet-5-5"
VISION_BRIEFING_MODEL = "anthropic/claude-haiku-5-5"
BRIEFING_XCHECK_MODEL = "anthropic/claude-sonnet-5-5"  # second reading of every briefing
CARD_XCHECK_MODEL = "openai/gpt-5.4-mini"              # second vendor for the strategy graphic


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
    return {**dotenv_values(ROOT / ".env"),
            **{k: v for k, v in os.environ.items() if k.startswith(("NICRRON_", "ALPACA_", "PRISMTRACE_"))}}


def client():
    from openai import OpenAI
    e = env()
    if not e.get("NICRRON_API_KEY"):  # else the SDK would fall back to OPENAI_API_KEY and send it to Nicrron
        raise SystemExit("NICRRON_API_KEY missing in ~/dev/quant-bot/.env")
    return OpenAI(base_url=e.get("NICRRON_BASE_URL") or "https://api.nicrron.ai/v1", api_key=e["NICRRON_API_KEY"])


def chat(model: str, system: str, content, max_tokens: int = 4000, retries: int = 2) -> tuple[str, dict]:
    """One streamed call (long non-streamed calls can hit a 502 upstream timeout).

    A reply cut at max_tokens is retried, then raised: a partial transcript must never pass as whole.
    """
    c = client()
    for attempt in range(retries + 1):
        try:
            t = time.time()
            stream = c.chat.completions.create(
                model=model, temperature=0, max_tokens=max_tokens, stream=True,
                stream_options={"include_usage": True},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": content}])
            parts, usage, finish = [], None, None
            for ev in stream:
                if ev.choices:
                    ch = ev.choices[0]
                    if ch.delta and ch.delta.content:
                        parts.append(ch.delta.content)
                    finish = ch.finish_reason or finish
                if getattr(ev, "usage", None):
                    usage = ev.usage
            if finish == "length":
                raise RuntimeError(f"reply cut at max_tokens={max_tokens}")
            meta = {"model": model, "secs": round(time.time() - t, 1), "finish": finish,
                    "tokens_in": getattr(usage, "prompt_tokens", None), "tokens_out": getattr(usage, "completion_tokens", None)}
            return "".join(parts), meta
        except Exception:  # retry transient upstream errors and cut replies, then give up loudly
            if attempt == retries:
                raise
            time.sleep(3 * (attempt + 1))


def png_data_url(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def parse_json(txt: str):
    """JSON from a model reply, with or without a code fence or a line of prose around it."""
    txt = re.sub(r"^\s*```(?:json)?|```\s*$", "", txt.strip(), flags=re.I).strip()
    try:
        return json.loads(txt)
    except ValueError:
        a, b = txt.find("{"), txt.rfind("}")
        if a < 0 or b <= a:
            raise
        return json.loads(txt[a:b + 1])


_TRANS = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                        "→": "->", " ": " "})


def norm(s: str | None, case: bool = False) -> str:
    """Unify quotes, dashes and whitespace; lowercase unless case=True. What the substring checks compare."""
    s = re.sub(r"\s+", " ", (s or "").translate(_TRANS)).strip()
    return s if case else s.lower()


def canon(x) -> str | None:
    """One spelling per number: 32.50, 32.5 and '32.5' all give '32.5'; 52,177.69 gives '52177.69'."""
    if isinstance(x, bool) or x is None:
        return None
    try:
        d = Decimal(str(x).replace(",", ""))
    except InvalidOperation:
        return None
    s = format(abs(d).normalize(), "f")  # the sign is direction ("15% down" sources -15)
    return s.rstrip("0").rstrip(".") if "." in s else s


def numbers_in(s: str | None) -> set[str]:
    """Every number in a text, canonical; only thousands commas are dropped, so '80,90' stays two numbers."""
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s or "")
    return {canon(n) for n in re.findall(r"\d+(?:\.\d+)?", s)}


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def write_jsonl(p: Path, rows: list[dict]) -> None:
    """Write via a temp file and rename, so an interrupted run never leaves a half-written file."""
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    os.replace(tmp, p)


def prism():
    """PRISM client, or None when the keys are missing (the run still works, untraced)."""
    e = env()
    if not (e.get("PRISMTRACE_API_KEY") and e.get("PRISMTRACE_PROJECT_ID")):
        return None
    from prismtrace import PRISMtrace
    return PRISMtrace(api_key=e["PRISMTRACE_API_KEY"], project_id=e["PRISMTRACE_PROJECT_ID"],
                      host=e.get("PRISMTRACE_HOST") or "https://api.prism.blockconvey.com")
