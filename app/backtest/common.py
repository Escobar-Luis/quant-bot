"""Shared paths and settings for the copy-trade backtester. Never prints key values."""
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent  # this checkout: results/ is written here


def _main_checkout() -> Path:
    """The main checkout holds the shared .env and the gitignored data/ folder; every worktree reads them."""
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    return (HERE / common).resolve().parent if common else Path.home() / "dev/quant-bot"


ROOT = _main_checkout()
load_dotenv(HERE.parent / ".env")
load_dotenv(ROOT / ".env")

DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
BARS = DATA / "bars"
RESULTS = REPO / "results"

DELAYS_MIN = [1, 3, 5, 10, 15, 30, 60]
DEFAULT_DELAY_MIN = 5
MONEY_START = 10_000.0
PER_TRADE_USD = 1_000.0
COSTS_BPS = {"stocks": 5, "stocks_under_10": 20, "crypto": 25}


def has_alpaca() -> bool:
    return bool(os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")) and \
        bool(os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY"))


def git_sha() -> str | None:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    return out or None
