"""Forward paper test: the frozen rules (app/paper/rules-v1.json) traded with fake money, one session at a time.

    cd app && uv run python -m paper.run                 # every completed session since the freeze not yet done
    cd app && uv run python -m paper.run --shakedown     # the latest completed session before the freeze, into
                                                         # data/paper/shakedown.json (a pipeline check; never counts)

Idempotent and safe to run daily: sessions already in results/paper/ledger.jsonl are skipped, and summary.json is
rewritten only when a session is added. Past sessions are never re-simulated, and the run refuses to start if the
rules file differs from the frozen one (a rule change is a new rules-v2.json with its own ledger).

Fake money only (AGENTS.md shared rule 7): fills are computed from Alpaca market data; nothing is ever sent to a
broker. Network: Alpaca market data (daily bars for the lists and SPY, 1-minute bars for trigger sessions, at most
--fetch-cap new ticker-days per run) and the paper account's asset endpoint for the easy_to_borrow flag (read only).
Cached under data/paper/ and data/bars/alpaca_1m/ (gitignored). Contract: contracts.md, section `paper`.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import numpy as np
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def _main_checkout() -> Path:
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    return (HERE / common).resolve().parent if common else Path.home() / "dev/quant-bot"


ROOT = _main_checkout()
load_dotenv(HERE.parent / ".env")
load_dotenv(ROOT / ".env")
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
BARS = DATA / "bars"
PDATA = DATA / "paper"
OUT = REPO / "results" / "paper"
RULES_FILE = HERE / "rules-v1.json"
ET = ZoneInfo("America/New_York")
ALPACA = "https://data.alpaca.markets/v2/stocks"
ASSETS = "https://paper-api.alpaca.markets/v2/assets"

# The freeze point: the commit that added rules-v1.json (tag paper-rules-v1). Recorded by hand right after it
# (the commit cannot name its own sha). Squash merges keep the tag's commit reachable on origin.
FREEZE = {"sha": "0e79dd8edfb2d44a1023df3d0555993894e35529", "tag": "paper-rules-v1",
          "at": "2026-10-20T21:38:43Z",
          "rules_sha256": "7eb5f5fc74310b58e856f5ab78cc255ffe2e0d34083a00e336447905ed9f0a94"}
COMPLETE_AFTER_ET = dt.time(16, 30)   # a session's bars are final enough to use after this
LOOKBACK_DAYS = 45                    # calendar days of daily bars per session: 20+ sessions for the volume average
MODELS = ("realistic", "x2", "base")


# ---- rules -------------------------------------------------------------------------------------------------------

def load_rules() -> dict:
    raw = RULES_FILE.read_bytes()
    h = hashlib.sha256(raw).hexdigest()
    if h != FREEZE["rules_sha256"]:
        raise SystemExit(f"{RULES_FILE.name} differs from the frozen file ({h[:12]} != {FREEZE['rules_sha256'][:12]}):"
                         " a rule change is a new rules file with its own freeze and ledger, never an edit")
    return json.loads(raw)


def tickers(rule: dict) -> list[str]:
    return [t for lst in rule["lists"].values() for t in lst]


def list_of(rule: dict, t: str) -> str:
    return next(k for k, v in rule["lists"].items() if t in v)


def bps(model: str, px: float, adv: float) -> float:
    if model == "base":
        return 20 if px < 10 else 5
    real = (50 if px < 5 else 30 if px < 10 else 5) + (10 if adv < 50e6 else 0)
    return real * (2 if model == "x2" else 1)


def borrow_fee(model: str, htb: bool | None) -> float:
    """Fraction of notional. Hard to borrow, or unknown, pays one day of a 100%-a-year fee (0.4%) when realistic."""
    if model == "base" or htb is False:
        return 0.0
    return 0.004 * (2 if model == "x2" else 1)


def pnl(entry: float, exit_: float, notional: float, model: str, adv: float, htb: bool | None) -> float:
    q = notional / entry
    return q * (entry - exit_) - q * entry * bps(model, entry, adv) / 1e4 - q * exit_ * bps(model, exit_, adv) / 1e4 \
        - notional * borrow_fee(model, htb)


# ---- time --------------------------------------------------------------------------------------------------------

def et_at(day: str, hm: str) -> int:
    h, m = (int(x) for x in hm.split(":"))
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), ET).timestamp())


def iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def freeze_ts() -> int:
    return int(dt.datetime.fromisoformat(FREEZE["at"].replace("Z", "+00:00")).timestamp())


def counts(day: str) -> bool:
    """Rule `counts_from`: the session's 09:30 ET open is after the freeze commit."""
    return et_at(day, "09:30") > freeze_ts()


def completed(day: str, now: dt.datetime) -> bool:
    n = now.astimezone(ET)
    return day < n.date().isoformat() or (day == n.date().isoformat() and n.time() >= COMPLETE_AFTER_ET)


# ---- Alpaca (market data only) -----------------------------------------------------------------------------------

def _keys() -> dict:
    return {"APCA-API-KEY-ID": os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY") or "",
            "APCA-API-SECRET-KEY": os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY") or ""}


def _get(url: str, params: dict) -> dict:
    for attempt in range(5):
        try:
            r = httpx.get(url, params=params, headers=_keys(), timeout=30)
        except httpx.HTTPError:
            time.sleep(2 + attempt * 2)
            continue
        if r.status_code == 429:
            time.sleep(2 + attempt * 3)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"alpaca {url.rsplit('/', 2)[-2:]} http {r.status_code}")
        return r.json()
    raise RuntimeError(f"alpaca {url}: no answer after 5 tries")


def daily_multi(symbols: list[str], start: str, end: str, adj: str) -> dict[str, list]:
    """{symbol: [[ET date, o, h, l, c, v], ...]} for start..end (ET dates)."""
    out: dict[str, list] = {}
    token = None
    while True:
        params = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": start,
                  "end": iso(min(et_at(end, "17:00"), int(time.time()) - 20 * 60)), "limit": 10000, "feed": "sip", "adjustment": adj}
        if token:
            params["page_token"] = token
        js = _get(f"{ALPACA}/bars", params)
        for s, rows in (js.get("bars") or {}).items():
            for b in rows:
                d = dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET).date().isoformat()
                out.setdefault(s, []).append([d, b["o"], b["h"], b["l"], b["c"], b["v"]])
        token = js.get("next_page_token")
        if not token:
            break
    return {s: sorted(v) for s, v in out.items()}


def minute_path(t: str, day: str) -> Path:
    return BARS / "alpaca_1m" / t / f"{day}.json"


def minutes(t: str, day: str) -> dict[int, list]:
    """{bar open unix_s: [o, h, l, c, v]} for the regular session, cached in the shared alpaca_1m cache."""
    p = minute_path(t, day)
    if p.exists():
        return {int(k): v for k, v in json.loads(p.read_text()).items()}
    rows, token = {}, None
    while True:
        params = {"timeframe": "1Min", "start": iso(et_at(day, "09:30")), "end": iso(et_at(day, "16:00") - 1),
                  "limit": 10000, "feed": "sip", "adjustment": "raw"}
        if token:
            params["page_token"] = token
        js = _get(f"{ALPACA}/{t}/bars", params)
        for b in js.get("bars") or []:
            rows[int(dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp())] = \
                [b["o"], b["h"], b["l"], b["c"], b["v"]]
        token = js.get("next_page_token")
        if not token:
            break
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows))
    return rows


def easy_to_borrow(t: str) -> bool | None:
    """Alpaca's asset flag as of now (read only; null when the lookup fails)."""
    try:
        r = httpx.get(f"{ASSETS}/{t}", headers=_keys(), timeout=30)
        return bool(r.json()["easy_to_borrow"]) if r.status_code == 200 else None
    except (httpx.HTTPError, KeyError, ValueError):
        return None


# ---- one session -------------------------------------------------------------------------------------------------

def day_cache(day: str) -> Path:
    return PDATA / "daily" / f"{day}.json"


def daily_for(day: str, syms: list[str]) -> dict:
    """The daily bars a session needs, fetched once and kept: split (signal), raw (cost tier, volume), SPY all."""
    p = day_cache(day)
    if p.exists():
        return json.loads(p.read_text())
    start = (dt.date.fromisoformat(day) - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    rec = {"day": day, "fetched_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "split": daily_multi(syms, start, day, "split"), "raw": daily_multi(syms, start, day, "raw"),
           "spy_all": daily_multi(["SPY"], start, day, "all").get("SPY", []), "easy_to_borrow": {}}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec))
    return rec


def gap(rows: list, day: str) -> float | None:
    i = next((k for k, r in enumerate(rows) if r[0] == day), None)
    if i is None or i == 0:
        return None
    return round(rows[i][1] / rows[i - 1][4] - 1, 9)


def adv_before(rows: list, day: str) -> float:
    prev = [r for r in rows if r[0] < day][-20:]
    return sum(r[4] * r[5] for r in prev) / len(prev) if prev else 0.0


def short_trade(bars: dict, day: str, rule: dict) -> dict | None:
    ks = sorted(bars)
    after = [k for k in ks if k >= et_at(day, rule["entry_et"])]
    if not after:
        return None
    k0, t_out = after[0], et_at(day, rule["exit_et"])
    entry = bars[k0][0]
    stop = entry * (1 + rule["stop_pct"] / 100)
    for k in after:
        if k >= t_out:
            return {"entry_ts": k0, "entry": entry, "exit_ts": k, "exit": bars[k][0], "kind": "time"}
        if bars[k][1] >= stop:
            return {"entry_ts": k0, "entry": entry, "exit_ts": k, "exit": max(bars[k][0], stop), "kind": "stop"}
    return {"entry_ts": k0, "entry": entry, "exit_ts": ks[-1], "exit": bars[ks[-1]][3], "kind": "last"}


def triggers(rules: dict, day: str, daily: dict) -> list[tuple[dict, str, float]]:
    out = []
    for rule in rules["rules"]:
        for t in tickers(rule):
            g = gap(daily["split"].get(t, []), day)
            if g is not None and g >= rule["gap_min_pct"] / 100:
                out.append((rule, t, g))
    return out


def simulate(rules: dict, day: str, daily: dict, equity: dict) -> dict:
    """One session's ledger line. `equity` = {rule: {model: realized end before this session}}."""
    line = {"day": day, "rules": rules["version"], "rules_sha256": FREEZE["rules_sha256"],
            "spy_factor": None, "rules_out": {}}
    spy = daily["spy_all"]
    i = next((k for k, r in enumerate(spy) if r[0] == day), None)
    if i and i > 0:
        line["spy_factor"] = round(spy[i][4] / spy[i - 1][4], 12)
    trig = triggers(rules, day, daily)
    for rule in rules["rules"]:
        rows, skipped = [], []
        for _, t, g in [x for x in trig if x[0]["id"] == rule["id"]]:
            tr = short_trade(minutes(t, day), day, rule)
            if tr is None:
                skipped.append({"ticker": t, "why": "no_bars"})
                continue
            htb = daily["easy_to_borrow"].get(t)
            rows.append({"ticker": t, "list": list_of(rule, t), "gap": g, **tr,
                         "adv_usd": round(adv_before(daily["raw"].get(t, []), day), 2),
                         "easy_to_borrow": htb})
        rows.sort(key=lambda r: (r["entry_ts"], r["ticker"]))
        eq_out, notional = {}, {}
        for m in MODELS:
            start = equity[rule["id"]][m]
            account = min(10_000.0, start)
            n = len(rows)
            each = 1_000.0 if n * 1_000.0 <= account else max(account, 0.0) / n if n else 0.0
            day_pnl = 0.0
            for r in rows:
                p = pnl(r["entry"], r["exit"], each, m, r["adv_usd"],
                        None if r["easy_to_borrow"] is None else not r["easy_to_borrow"])
                r.setdefault("pnl", {})[m] = round(p, 6)
                day_pnl += p
            notional[m] = round(each, 6)
            eq_out[m] = round(start + day_pnl, 6)
        line["rules_out"][rule["id"]] = {"trades": rows, "skipped": skipped, "notional": notional, "equity": eq_out}
    return line


# ---- summary -----------------------------------------------------------------------------------------------------

def word(trades: int, ret: float, bench: float) -> str:
    if trades < 30:
        return "Not enough trades"
    if ret < 0:
        return "No"
    return "Yes" if ret - bench >= 2 else "Barely" if ret - bench > -2 else "No"


def vs_random(rules: dict, rule: dict, ledger: list[dict]) -> dict | None:
    v = rules["vs_random"]
    trades = [r for ln in ledger for r in ln["rules_out"][rule["id"]]["trades"]]
    if len(trades) < v["min_trades"]:
        return None
    twin, pool, vals = set(), [], []
    for ln in ledger:
        daily = json.loads(day_cache(ln["day"]).read_text())
        for t in tickers(rule):
            s, rw = daily["split"].get(t, []), daily["raw"].get(t, [])
            i = next((k for k, r in enumerate(s) if r[0] == ln["day"]), None)
            j = next((k for k, r in enumerate(rw) if r[0] == ln["day"]), None)
            if not i or j is None:
                continue
            o, c = s[i][1], s[i][4]
            q = 1_000.0 / o
            vals.append(q * (o - c) - 1_000.0 * bps("base", rw[j][1], 0) / 1e4 - q * c * bps("base", rw[j][4], 0) / 1e4)
            pool.append((t, ln["day"]))
            g = round(o / s[i - 1][4] - 1, 9)
            if g >= rule["gap_min_pct"] / 100:
                twin.add(len(pool) - 1)
    arr = np.array(vals)
    tw = float(arr[sorted(twin)].sum())
    rng = np.random.default_rng(v["seed"])
    draws = np.array([arr[rng.choice(len(arr), size=len(twin), replace=False)].sum() for _ in range(v["draws"])])
    return {"twin_pnl_usd": round(tw, 2), "p2_5": round(float(np.percentile(draws, 2.5)), 2),
            "p97_5": round(float(np.percentile(draws, 97.5)), 2),
            "pct_rank": round(100 * float((draws < tw).mean()), 1), "draws": v["draws"]}


def summarize(rules: dict, ledger: list[dict], first_session: str | None) -> dict:
    spy = 1.0
    for ln in ledger:
        spy *= ln["spy_factor"]
    spy_ret = 100 * (spy - 1)
    out_rules = []
    for rule in rules["rules"]:
        trades = [r for ln in ledger for r in ln["rules_out"][rule["id"]]["trades"]]
        n = len(trades)
        costs = {}
        for m in MODELS:
            end = ledger[-1]["rules_out"][rule["id"]]["equity"][m] if ledger else 10_000.0
            peak, mdd = 10_000.0, 0.0
            for ln in ledger:
                e = ln["rules_out"][rule["id"]]["equity"][m]
                peak = max(peak, e)
                mdd = min(mdd, e / peak - 1)
            costs[m] = {"end": round(end, 2), "ret_pct": round(100 * (end / 10_000 - 1), 2),
                        "max_drawdown_pct": round(100 * mdd, 2)}
        real = costs["realistic"]["ret_pct"]
        won = sum(1 for r in trades if r["pnl"]["realistic"] > 0)
        out_rules.append({
            "id": rule["id"], "label": rule["label"], "text": rule["text"], "lists": list(rule["lists"]),
            "trades": n, "won_pct": round(100 * won / n) if n else None,
            "stops": sum(1 for r in trades if r["kind"] == "stop"),
            "skipped_no_bars": sum(len(ln["rules_out"][rule["id"]]["skipped"]) for ln in ledger),
            "sized_down_days": sum(1 for ln in ledger if ln["rules_out"][rule["id"]]["trades"]
                                   and ln["rules_out"][rule["id"]]["notional"]["realistic"] < 1_000.0),
            "hard_to_borrow_trades": sum(1 for r in trades if r["easy_to_borrow"] is False),
            "unknown_borrow_trades": sum(1 for r in trades if r["easy_to_borrow"] is None),
            "costs": costs, "vs_spy_pts": round(real - spy_ret, 2), "word": word(n, real, spy_ret),
            "vs_random": vs_random(rules, rule, ledger),
        })
    return {
        "schema": "paper/1", "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rules_file": "app/paper/rules-v1.json", "rules_version": rules["version"],
        "rules_sha256": FREEZE["rules_sha256"], "freeze": {k: FREEZE[k] for k in ("sha", "tag", "at")},
        "status": "running" if ledger else "waiting",
        "first_session": ledger[0]["day"] if ledger else first_session,
        "last_session": ledger[-1]["day"] if ledger else None,
        "days": len(ledger),
        "money_start": 10000.0, "per_trade_usd": 1000.0, "cost_models": list(MODELS),
        "benchmark": {"symbol": "SPY", "ret_pct": round(spy_ret, 2),
                      "basis": "total return (Alpaca daily adjustment=all) from the close before the first counted "
                               "session to the last counted close"},
        "rules": out_rules,
    }


# ---- the run -----------------------------------------------------------------------------------------------------

def read_ledger(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def sessions_since(start: str, now: dt.datetime) -> list[str]:
    """Market sessions from `start` (ET date) to now, from SPY's daily bars (a holiday has none)."""
    end = now.astimezone(ET).date().isoformat()
    rows = daily_multi(["SPY"], start, end, "raw").get("SPY", [])
    return [r[0] for r in rows if r[0] >= start]


def prepare(rules: dict, day: str, cap_left: int) -> tuple[dict | None, int]:
    """Fetch what `day` needs. Returns (daily, minute ticker-days fetched), or (None, 0) when over the cap."""
    syms = sorted({t for r in rules["rules"] for t in tickers(r)})
    daily = daily_for(day, syms)
    trig = triggers(rules, day, daily)
    need = [t for _, t, _ in trig if not minute_path(t, day).exists()]
    if len(need) > cap_left:
        return None, 0
    for t in need:
        minutes(t, day)
    missing = [t for _, t, _ in trig if t not in daily["easy_to_borrow"]]
    if missing:
        for t in missing:
            daily["easy_to_borrow"][t] = easy_to_borrow(t)
        day_cache(day).write_text(json.dumps(daily))
    return daily, len(need)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-cap", type=int, default=200, help="new 1-minute ticker-days to fetch this run")
    ap.add_argument("--shakedown", action="store_true",
                    help="simulate the latest completed session before the freeze into data/paper/shakedown.json")
    ap.add_argument("--out-dir", default=str(OUT))
    a = ap.parse_args(argv)
    if not (_keys()["APCA-API-KEY-ID"] and _keys()["APCA-API-SECRET-KEY"]):
        print("no Alpaca keys in .env", file=sys.stderr)
        return 2
    rules = load_rules()
    now = dt.datetime.now(dt.UTC)
    freeze_day = dt.datetime.fromtimestamp(freeze_ts(), ET).date()
    out = Path(a.out_dir)
    start = (freeze_day - dt.timedelta(days=7)).isoformat()
    cal = [d for d in sessions_since(start, now) if completed(d, now)]

    if a.shakedown:
        before = [d for d in cal if not counts(d)]
        day = before[-1]
        daily, _ = prepare(rules, day, a.fetch_cap)
        line = simulate(rules, day, daily, {r["id"]: {m: 10_000.0 for m in MODELS} for r in rules["rules"]})
        PDATA.mkdir(parents=True, exist_ok=True)
        (PDATA / "shakedown.json").write_text(json.dumps({"counts": False, **line}, indent=1))
        for rid, x in line["rules_out"].items():
            print(f"shakedown {day} {rid}: trades {len(x['trades'])}, realistic end {x['equity']['realistic']:.2f}",
                  file=sys.stderr)
        return 0

    ledger_p = out / "ledger.jsonl"
    ledger = read_ledger(ledger_p)
    done = {ln["day"] for ln in ledger}
    if any(ln["rules_sha256"] != FREEZE["rules_sha256"] for ln in ledger):
        raise SystemExit("the ledger holds sessions simulated under other rules: refusing to mix")
    todo = [d for d in cal if counts(d) and d not in done]
    if ledger and todo and todo[0] <= ledger[-1]["day"]:
        raise SystemExit(f"session {todo[0]} is before the last ledger session {ledger[-1]['day']}: refusing to "
                         "back-fill out of order")
    first = next((d for d in cal if counts(d)), None)
    added, fetched = 0, 0
    for day in todo:
        daily, n = prepare(rules, day, a.fetch_cap - fetched)
        if daily is None:
            print(f"{day}: over the fetch cap this run; run again to continue", file=sys.stderr)
            break
        fetched += n
        eq = ledger[-1]["rules_out"] if ledger else None
        equity = {r["id"]: (eq[r["id"]]["equity"] if eq else {m: 10_000.0 for m in MODELS}) for r in rules["rules"]}
        line = simulate(rules, day, daily, equity)
        if line["spy_factor"] is None:
            raise SystemExit(f"{day}: no SPY close for this or the previous session")
        out.mkdir(parents=True, exist_ok=True)
        with ledger_p.open("a") as f:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")
        ledger.append(line)
        added += 1
        print(f"{day}: " + "; ".join(f"{rid} {len(x['trades'])} trades, realistic {x['equity']['realistic']:.2f}"
                                       for rid, x in line["rules_out"].items()), file=sys.stderr)
    summary_p = out / "summary.json"
    if added or not summary_p.exists():
        out.mkdir(parents=True, exist_ok=True)
        summary_p.write_text(json.dumps(summarize(rules, ledger, first), indent=1) + "\n")
        print(f"wrote {summary_p} ({len(ledger)} sessions)", file=sys.stderr)
    else:
        print(f"nothing new: {len(ledger)} sessions, last {ledger[-1]['day'] if ledger else 'none'}"
              + ("" if ledger else f"; first counted session {first or 'after ' + freeze_day.isoformat()}"),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
