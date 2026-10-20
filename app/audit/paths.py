"""Where the audit reads and writes, resolved without importing backtest.* (the code under audit).

data/ (gitignored) lives in the main checkout, shared by every worktree; results/ and proofs/ in this checkout.
DATA_DIR overrides data/, as it does for the engine.
"""
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def _main_checkout() -> Path:
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    return (HERE / common).resolve().parent if common else Path.home() / "dev/quant-bot"


DATA = Path(os.getenv("DATA_DIR", _main_checkout() / "data"))
BARS = DATA / "bars"
RESULTS = REPO / "results"
PROOFS = REPO / "proofs"
