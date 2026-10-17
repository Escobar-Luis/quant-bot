"""Shared paths and helpers for the Crypto Wizard collector.

Raw course content lives only under DATA_DIR/cryptowizard (gitignored, never in git).
Keys come from the main checkout's .env; this module never prints their values.
"""
import glob
import json
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", Path.home() / "dev" / "quant-bot" / "data"))
CW = DATA_DIR / "cryptowizard"
RAW = CW / "raw"
BARS = DATA_DIR / "bars" / "binance"

COURSE = "cryptowizard"
SERVER_ID = "639275844795367454"
CHANNEL_IDS = {
    "wzrd-chat-crypto": "639277011164200960",
    "wzrd-crypto-setups": "773537812233715713",
    "wzrd-lessons": "855852754392449065",
    "wzrd-bible": "780134916955963412",
    "wzrd-risk-management": "861320318480285697",
    "wzrd-trends": "873996764808609842",
}
STAFF = {"CRYPTOWZRD", "WZRD SUPPORT", "FOREXWZRD"}

# Coin names as said in posts -> Binance spot USDT pair (their charts are BINANCE:<COIN>USDT).
COIN_ALIASES = {"BITCOIN": "BTC", "ETHEREUM": "ETH", "LITECOIN": "LTC", "SOLANA": "SOL", "RIPPLE": "XRP"}
NOT_CRYPTO = {"S&P 500", "S&P", "SPX", "SPX500", "RUT", "RUT/RUSSELL 2000", "OIL", "NAS", "NASDAQ", "NAS100", "US100",
              "USDCAD", "US30", "US30/DOW", "DOW", "GOLD", "XAUUSD", "DXY"}


def load_env():
    """Load ~/dev/quant-bot/.env (shared by every worktree) without printing anything."""
    from dotenv import load_dotenv
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    if common:
        load_dotenv((HERE / common).resolve().parent / ".env")


def load_raw():
    """All collected posts, de-duplicated by message id; keeps every search query that found each post."""
    posts = {}
    for f in sorted(glob.glob(str(RAW / "cw_posts_*.json"))):
        for p in json.load(open(f))["posts"]:
            q = p.get("query")
            if p["message_id"] in posts:
                posts[p["message_id"]]["queries"].add(q)
            else:
                p["queries"] = {q}
                posts[p["message_id"]] = p
    for p in posts.values():
        p["queries"] = sorted(x for x in p["queries"] if x)
    return sorted(posts.values(), key=lambda p: p["posted_at"])


def source_id(p):
    return f"dc:{CHANNEL_IDS[p['channel']]}/{p['message_id']}"


def message_url(p):
    return f"https://discord.com/channels/{SERVER_ID}/{CHANNEL_IDS[p['channel']]}/{p['message_id']}"


def coin_of(header):
    """'XRP 2ND Trade Update: (Risky-Scalp)' -> ('XRP', '2ND'); 'BITCOIN Trade Update:' -> ('BTC', '')."""
    m = re.match(r"\s*(.+?)\s+(?:(\d)(?:ST|ND|RD|TH)\s+)?(?:LONG\s+|SHORT\s+)?Trade Update", header, re.I)
    if not m:
        return None, ""
    said = re.sub(r"\s+", " ", m.group(1)).strip().upper()
    nth = (m.group(2) or "1")
    return COIN_ALIASES.get(said, said), nth


def to_symbol(coin):
    """Exchange pair we price on (Binance spot), e.g. BTC -> BTCUSDT. None for non-crypto names."""
    if coin is None or coin in NOT_CRYPTO or not re.fullmatch(r"[A-Z0-9]{2,10}", coin):
        return None
    return f"{coin}USDT"


def to_ticker(coin):
    """Cross-course ticker id the SurrealDB loader uses (ticker:BTCUSD); the pair stays in `pair`."""
    return f"{coin}USD" if to_symbol(coin) else None


def event_id(message_id, n=0):
    """`cw:<message_id>:<nnn>`, the loader's id convention (lpp uses lpp:<video>:<nnn>)."""
    return f"cw:{message_id}:{n:03d}"


def mid_of(eid):
    """Message id inside an event id, for both `cw:<mid>:000` and the older `cw-<mid>`."""
    return eid.split(":")[1] if eid.startswith("cw:") else eid.split("-", 1)[1]


def num(s):
    return float(s.replace(",", "").replace("$", ""))


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# --- Nicrron (OpenAI-compatible) and PRISM -------------------------------------------------------
PROMPT_VERSION = "cw-v1"
SONNET = "anthropic/claude-sonnet-5-5"
HAIKU = "anthropic/claude-haiku-5-5"


def _env():
    from dotenv import dotenv_values
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    root = (HERE / common).resolve().parent if common else Path.home() / "dev" / "quant-bot"
    return {**dotenv_values(root / ".env"),
            **{k: v for k, v in os.environ.items() if k.startswith(("NICRRON_", "PRISMTRACE_"))}}


def chat(model, system, content, max_tokens=4000, retries=2):
    """One streamed, temperature-0 call (long non-streamed calls can hit a 502 upstream timeout)."""
    import time
    from openai import OpenAI
    e = _env()
    c = OpenAI(base_url=e.get("NICRRON_BASE_URL") or "https://api.nicrron.ai/v1", api_key=e["NICRRON_API_KEY"])
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
            return "".join(parts), {"model": model, "ms": int((time.time() - t) * 1000),
                                    "tokens_in": getattr(usage, "prompt_tokens", 0) or 0,
                                    "tokens_out": getattr(usage, "completion_tokens", 0) or 0}
        except Exception:  # noqa: BLE001  transient upstream errors: retry, then raise
            if attempt == retries:
                raise
            time.sleep(3 * (attempt + 1))


def parse_json(txt):
    txt = re.sub(r"^\s*```(?:json)?|```\s*$", "", txt.strip()).strip()
    return json.loads(txt)


def prism_run(agent_id, agent_name, steps, model, final_status="success", conversation_id=None):
    """Trace one run to PRISM: locators and extracted fields only, never raw post text (AGENTS.md rule 5).

    Off unless CW_TRACE=1: AGENTS.md contract 5 traces only the LPP proof set and verdict runs.
    """
    if os.getenv("CW_TRACE") != "1":
        return None
    try:
        from prismtrace import PRISMtrace
        e = _env()
        pt = PRISMtrace(api_key=e["PRISMTRACE_API_KEY"], project_id=e["PRISMTRACE_PROJECT_ID"],
                        host=e.get("PRISMTRACE_HOST") or "https://api.prism.blockconvey.com")
        run = pt.submit_trajectory(steps, agent_id=agent_id, agent_name=agent_name, model=model,
                                   final_status=final_status, conversation_id=conversation_id)
        pt.flush(timeout=30)
        pt.close()
        return (run or {}).get("id")
    except Exception as ex:  # noqa: BLE001  tracing must never break extraction
        print("prism trace failed:", type(ex).__name__)
        return None
