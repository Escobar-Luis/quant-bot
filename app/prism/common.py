"""Shared plumbing for the PRISM proofs (story 2): env, paths, the PRISM client, traced runs. Never prints key values."""
import datetime as dt
import json
import os
import re
import subprocess
import uuid
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent  # this checkout: kb/, proofs/, results/


def _main_checkout() -> Path:
    """The main checkout holds the shared .env and the gitignored data/ folder; every worktree reads them."""
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    return (HERE / common).resolve().parent if common else Path.home() / "dev/quant-bot"


ROOT = _main_checkout()
load_dotenv(HERE.parent / ".env")
load_dotenv(ROOT / ".env")

DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
KB = REPO / "kb"
PROOFS = REPO / "proofs"
RESULTS = REPO / "results"
COURSES = {"lpp": "Learn Plan Profit", "ziptrader": "ZipTrader", "cryptowizard": "Crypto Wizard"}
HOST = os.getenv("PRISMTRACE_HOST", "https://api.prism.blockconvey.com")
APP_URL = "https://prism.blockconvey.com"
QUOTE_MAX = 12


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True,
                          text=True).stdout.strip()


def words(s: str | None) -> list[str]:
    return (s or "").split()


def clip(s: str | None, n: int = QUOTE_MAX) -> str:
    """At most n words: quotes stay short (course content is copyrighted)."""
    w = words(s)
    return " ".join(w[:n]) + (" …" if len(w) > n else "")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in open(path)] if path.exists() else []


def client():
    from prismtrace import PRISMtrace
    return PRISMtrace(api_key=os.environ["PRISMTRACE_API_KEY"], project_id=os.environ["PRISMTRACE_PROJECT_ID"],
                      host=HOST)


def entitlements(pt) -> dict:
    return pt._get_sync("/api/entitlements") or {}


def can_write(pt, feature: str) -> bool:
    """evaluators_hub / guardrails writes need the Builder plan on the key's workspace."""
    return bool(((entitlements(pt).get("feature_access") or {}).get(feature) or {}).get("write"))


def submit(pt, steps: list[dict], *, agent_id: str, agent_name: str, conversation_id: str, model: str | None,
           final_status: str, metadata: dict) -> dict | None:
    """submit_trajectory plus `metadata` (SDK 0.5.3 has no metadata argument), same payload otherwise."""
    payload = {"project_id": pt.project_id, "conversation_id": conversation_id, "request_id": str(uuid.uuid4()),
               "agent_id": agent_id, "agent_name": agent_name, "steps": steps,
               "total_duration_ms": sum(s.get("duration_ms") or 0 for s in steps),
               "final_status": final_status, "model": model, "metadata": metadata}
    return pt._post_sync("/api/trajectories", payload)


NUM = re.compile(r"(?<![\w.])\$?-?\d[\d,]*(?:\.\d+)?%?")


def numbers_in(text: str) -> list[float]:
    """Every number written in a text, as floats ($, %, commas stripped)."""
    out = []
    for m in NUM.findall(text or ""):
        s = m.replace("$", "").replace("%", "").replace(",", "")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out
