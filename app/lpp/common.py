"""Shared paths and clients for the LPP morning-session extractor. Never prints key values."""
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent


def _main_checkout() -> Path:
    """The main checkout holds the shared .env and the gitignored data/ folder; every worktree reads them."""
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    return (HERE / common).resolve().parent if common else Path.home() / "dev/quant-bot"


ROOT = _main_checkout()
load_dotenv(HERE.parent / ".env")
load_dotenv(ROOT / ".env")

# LPP_VERSION picks the extractor version: v1 (default) writes data/lpp/*.jsonl; v2 writes data/lpp/v2/*.jsonl.
# lpp-v0 (first draft prompt, gold set only) is kept in data/lpp/extract/lpp-v0/ for the record.
VERSION = os.getenv("LPP_VERSION", "v1")
DATA = Path(os.getenv("DATA_DIR", ROOT / "data")) / "lpp"
YT = DATA / "youtube"
PROMPT_VERSION = f"lpp-{VERSION}"
AGENT_ID = f"extract-lpp-{VERSION}"
OUT = DATA / "extract" if VERSION == "v1" else DATA / "extract" / PROMPT_VERSION   # one cached reply per session
RES = DATA if VERSION == "v1" else DATA / VERSION                                    # sources/events/sessions.jsonl
BARS = Path(os.getenv("DATA_DIR", ROOT / "data")) / "bars"
COURSE = "lpp"


def llm():
    from openai import OpenAI
    return OpenAI(base_url=os.getenv("NICRRON_BASE_URL", "https://api.nicrron.ai/v1"),
                  api_key=os.environ["NICRRON_API_KEY"], timeout=600, max_retries=0)


def has_alpaca() -> bool:
    return bool(os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")) and \
        bool(os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY"))
