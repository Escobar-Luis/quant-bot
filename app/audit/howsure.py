"""Independent recompute of results/how-sure.json's luck tests and shuffle percentiles (contracts.md, section
how-sure; spec-audit CAP-16, story audit-28-honest-eval). Never imports app/backtest; reads only cached files and
the results files audit.run already reconciles.

Recomputed with this module's own code and the same seeds:
  1. every luck test: the deflated Sharpe (Bailey & Lopez de Prado 2014; SR0 from the family's member series) or the
     Harvey-Liu Bonferroni haircut, from the published daily series; each series' total is checked against the
     audited numbers (a headline's realistic end in its results file; an improvement's dev + sealed points; a lab
     run's P&L), and each claim's own series against its family member's;
  2. the headline shuffle (`random_days`): every published trade is checked against the engine's ledger (the one
     audit.run reconciles), then re-priced on every candidate day from the cached 1-minute bars with this
     module's realistic costs, and drawn again with seed 28;
  3. the improvements' label shuffle (`random_trades`): each LPP v1 position re-priced by audit.calc as-is and
     under the change (audit.improvements' own definitions), then drawn again;
  4. the lab's `vs_random`: the daily-bar twin and its 2,000 seeded draws (seed 21) from data/bars/lab_daily/.
Also checked: `tests` and `proven` follow the contract's rules from the blocks. Walk-forward, sensitivity and the
regime split are not recomputed (listed under `not_recomputed`).
Tolerance: 0.001 on dsr / p / p_adjusted, 0.05 on annualized Sharpes, 0.1 pt on pct_rank, $1 on series totals.
"""
import datetime as dt
import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np

from . import bars as B
from . import calc, improvements
from . import lab as AL
from . import positions as P
from .paths import BARS, DATA, RESULTS

HOW = RESULTS / "how-sure.json"
G = 0.5772156649015329
Z = NormalDist()
TOL_P, TOL_SR, TOL_RANK, TOL_USD = 0.001, 0.05, 0.1, 1.0
PASS_DSR, PASS_HL, PASS_RANK, MIN_N, MIN_POOL = 0.95, 0.05, 95.0, 30, 5
PER_YEAR = {"us_equities": 252, "crypto": 365}
MARKET = {"lpp": "us_equities", "ziptrader": "us_equities", "cryptowizard": "crypto"}


# ---- luck ------------------------------------------------------------------------------------------------------

def _stats(x: list[float]) -> tuple[float, float, float, int]:
    """(Sharpe per day with a ddof-1 std, skew, kurtosis from biased central moments, n)."""
    n = len(x)
    mu = sum(x) / n
    dev = [v - mu for v in x]
    m2 = sum(d * d for d in dev) / n
    s = math.sqrt(sum(d * d for d in dev) / (n - 1)) if n > 1 else 0.0
    if m2 == 0:
        return 0.0, 0.0, 3.0, n
    return (mu / s if s else 0.0), sum(d ** 3 for d in dev) / n / m2 ** 1.5, sum(d ** 4 for d in dev) / n / m2 ** 2, n


def dsr(x: list[float], trials: int, members: list[list[float]]) -> tuple[float, float, float]:
    """(dsr, SR0 per day, variance of the members' Sharpes)."""
    srs = [_stats(m)[0] for m in members]
    k = len(srs)
    mean = sum(srs) / k
    var = sum((s - mean) ** 2 for s in srs) / (k - 1) if k > 1 else 0.0
    sr0 = 0.0 if trials <= 1 or var <= 0 else math.sqrt(var) * (
        (1 - G) * Z.inv_cdf(1 - 1 / trials) + G * Z.inv_cdf(1 - 1 / (trials * math.e)))
    sr, sk, ku, n = _stats(x)
    den = 1 - sk * sr + (ku - 1) / 4 * sr * sr
    return (Z.cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(den)) if den > 0 and n > 1 else 0.0), sr0, var


def hl(x: list[float], trials: int) -> tuple[float, float, float]:
    """(Sharpe per day, one-sided p, Bonferroni-adjusted p)."""
    sr, _, _, n = _stats(x)
    p = 1 - Z.cdf(sr * math.sqrt(n))
    return sr, p, min(1.0, trials * p)


# ---- shuffles --------------------------------------------------------------------------------------------------

def _pool_days(market: str, sym: str) -> list[str]:
    if market == "us_equities":
        dirs = [BARS / "alpaca_1m" / sym, BARS / "yahoo_1m" / sym]
    else:
        dirs = [BARS / "binance" / sym / "1m"]
    return sorted({f.stem for d in dirs if d.exists() for f in d.glob("*.json")})


def _bars(market: str, sym: str, day: str) -> dict:
    try:
        return B.day_bars(market, sym, dt.date.fromisoformat(day))
    except B.MissingBar:
        return {}


def _zone(market: str):
    return B.ET if market == "us_equities" else dt.UTC


def _twin(market: str, sym: str, side: str, day_in: dt.date, t_in: dt.time, days: int, t_out: dt.time,
          flag: str) -> float | None:
    z = _zone(market)
    day_out = day_in + dt.timedelta(days=days)
    bi, bo = _bars(market, sym, day_in.isoformat()), _bars(market, sym, day_out.isoformat())
    a = int(dt.datetime.combine(day_in, t_in, z).timestamp())
    b = int(dt.datetime.combine(day_out, t_out, z).timestamp())
    ks = sorted(k for k in bi if k >= a)
    if not ks or not bo:
        return None
    ko = sorted(k for k in bo if k >= b)
    p0 = bi[ks[0]][0]
    p1 = bo[ko[0]][0] if ko else bo[max(bo)][3]
    shares = 1000.0 / p0
    s = 1 if side == "long" else -1
    out = s * shares * (p1 - p0) - 1000.0 * calc.side_rate("realistic", market, sym, p0, ks[0]) \
        - shares * p1 * calc.side_rate("realistic", market, sym, p1, ko[0] if ko else max(bo))
    if s < 0:
        rate = calc.BORROW_YR["crypto" if market == "crypto" else flag]
        out -= 1000.0 * rate * max(1, days) / 360
    return out


def headline_shuffle(trades: list, market: str, window: dict, flags: dict, seed: int, draws: int) -> dict:
    rng = np.random.default_rng(seed)
    total, twin = np.zeros(draws), 0.0
    for sym, side, e, x in trades:
        z = _zone(market)
        te, tx = dt.datetime.fromtimestamp(e, z), dt.datetime.fromtimestamp(x, z)
        days = (tx.date() - te.date()).days
        flag = flags.get(sym, "unknown")
        mine = _twin(market, sym, side, te.date(), te.time(), days, tx.time(), flag)
        if mine is None:
            raise B.MissingBar(f"{sym} {te.date()}: no bars for the actual trade")
        twin += mine
        cached = set(_pool_days(market, sym))
        vals = []
        for day in sorted(cached):
            if not window["start"] <= day <= window["end"]:
                continue
            d = dt.date.fromisoformat(day)
            if (d + dt.timedelta(days=days)).isoformat() not in cached:
                continue
            v = _twin(market, sym, side, d, te.time(), days, tx.time(), flag)
            if v is not None:
                vals.append(v)
        if len(vals) < MIN_POOL:
            total = total + mine
            continue
        total = total + np.array(vals)[rng.integers(0, len(vals), size=draws)]
    return {"twin_pnl_usd": twin, "pct_rank": 100 * float(np.mean(total < twin))}


def label_shuffle(variants: list[dict], seed: int, draws: int, delay: int = 5) -> dict:
    """{variant id: (pct_rank, actual change, treated indices)} from the audit's own LPP v1 positions."""
    pos = sorted(P.build("lpp", "v1"), key=lambda p: p.pid)
    base = {p.pid: calc.simulate(p, delay) for p in pos}
    events = {e["event_id"]: e for e in P.rows(P.lpp_events_path("v1"))}

    def first_fill(p):
        t = base[p.pid]
        if t.status == "priced" and t.entry:
            return t.entry.ts
        return min(lg.posted_ts for lg in p.legs if lg.action in ("open", "add")) + delay * 60

    feats = {p.pid: improvements._feats(p, events, first_fill(p)) for p in pos}
    pnl0 = [base[p.pid].pnl if base[p.pid].status == "priced" else 0.0 for p in pos]
    out = {}
    for v in variants:
        hit = [improvements._hit(feats[p.pid], v["when"]) for p in pos]
        if v["kind"] in ("skip", "only"):
            change = [-x for x in pnl0]
            picked = [i for i, h in enumerate(hit) if h == (v["kind"] == "skip")]
        else:
            change = []
            for p, x in zip(pos, pnl0):
                t0 = base[p.pid]
                if t0.status != "priced":
                    change.append(0.0)
                    continue
                q = improvements._changed(p, t0, v, delay)
                t1 = t0 if q is None else calc.simulate(q, delay)
                change.append((t1.pnl if t1.status == "priced" else 0.0) - x)
            picked = [i for i, h in enumerate(hit) if h and base[pos[i].pid].status == "priced"]
        rng = np.random.default_rng(seed)
        c = np.array(change)
        actual = float(c[picked].sum())
        sims = np.array([c[rng.choice(len(c), size=len(picked), replace=False)].sum() for _ in range(draws)])
        out[v["id"]] = (100 * float(np.mean(sims < actual)), actual, picked)
    return out


def lab_vs_random(lab_file: Path) -> dict:
    """{(rule, variant, universe): pct_rank} for every S4/S5 run: the daily-bar twin (short open -> close, $1,000,
    base costs) vs 2,000 draws of as many sessions from the list (seed 21, without replacement)."""
    d = json.loads(lab_file.read_text())
    w, d0 = AL.SPEC["window"], AL.SPEC["daily_from"]
    spy = AL._daily("SPY", "all", d0, w["to"])
    cal = [k for k in sorted(spy) if w["from"] <= k <= w["to"]]
    out = {}
    for run in d["runs"]:
        if run["rule"] == "C":
            continue
        tick = AL.SPEC["universes"][run["universe"]]
        split = {t: AL._daily(t, "split", d0, w["to"]) for t in tick}
        raw = {t: AL._daily(t, "raw", d0, w["to"]) for t in tick}
        pool = [(t, day) for t in tick for day in cal if day in split[t] and any(k < day for k in split[t])]
        gap = AL.SPEC["variants"][run["variant"]]["gap_pct"]
        twin = [(t, day) for t in tick for day in AL._gap_days(split[t], gap, w["from"], w["to"])]

        def one(t, day):
            o, c = split[t][day][0], split[t][day][3]
            sh = 1000.0 / o
            return sh * (o - c) - 1000.0 * AL._side_cost("base", raw[t][day][0], 0) \
                - sh * c * AL._side_cost("base", raw[t][day][3], 0)

        vals = np.array([one(t, day) for t, day in pool])
        at = {k: i for i, k in enumerate(pool)}
        tw = float(sum(vals[at[k]] for k in twin))
        rng = np.random.default_rng(21)
        sims = np.array([vals[rng.choice(len(pool), size=len(twin), replace=False)].sum() for _ in range(2000)])
        out[(run["rule"], run["variant"], run["universe"])] = 100 * float(np.mean(sims < tw))
    return out


# ---- the check -------------------------------------------------------------------------------------------------

def _ledger_trades(course: str, version: str, delay: int = 5) -> set[tuple[int, int]]:
    path = DATA / "audit" / f"{course}-{version}-ledger.jsonl"
    out = set()
    with open(path) as f:
        next(f)
        for line in f:
            r = json.loads(line)
            if r["delay"] == delay and r["status"] == "priced":
                fs = r["fills"]
                out.add((next(x[0] for x in fs if x[3] == "entry"), [x for x in fs if x[3] != "entry"][-1][0]))
    return out


def check(path: Path = HOW, lab_file: Path = RESULTS / "strategy-lab.json") -> dict:
    d = json.loads(path.read_text())
    out: list[dict] = []
    unverifiable: list[str] = []

    def miss(cid, field, theirs, ours):
        out.append({"kind": "how-sure", "claim": cid, "field": field, "theirs": theirs,
                    "ours": round(ours, 4) if isinstance(ours, float) else ours})

    def near(cid, field, theirs, ours, tol):
        if not isinstance(theirs, (int, float)) or abs(theirs - ours) > tol + 1e-9:
            miss(cid, field, theirs, ours)

    seed, draws = d.get("seed"), d.get("draws")
    if (seed, draws) != (28, 1000):
        miss("file", "seed/draws", [seed, draws], [28, 1000])
    fams, cals = d.get("families") or {}, d.get("calendars") or {}
    imp_vars = {}
    lpp = json.loads((RESULTS / "lpp" / "v1.json").read_text())
    for v in (lpp.get("improvements") or {}).get("variants") or []:
        imp_vars[v["id"]] = v
    want_trials = {"improvements": (lpp.get("improvements") or {}).get("variants_tried", {}).get("distinct_priced"),
                   "strategy-lab": json.loads(lab_file.read_text()).get("variants_tried") if lab_file.exists()
                   else None}
    lab_rank, ls = None, {}
    labf = json.loads(lab_file.read_text()) if lab_file.exists() else {"runs": []}
    checked = 0
    for c in d.get("claims") or []:
        cid, fam = c["id"], fams.get(c["family"]) or {}
        checked += 1
        series = (c.get("series") or {}).get("pnl") or []
        cal = cals.get((c.get("series") or {}).get("calendar")) or []
        if len(series) != len(cal):
            miss(cid, "series length", len(series), len(cal))
            continue
        # the series' total against the audited numbers
        if c["card"] == "verdict":
            res = json.loads((RESULTS / c["course"] / f"{c['version']}.json").read_text())
            row = next(p for p in res["cost_cases"]["portfolios"] if p["id"] == "all")["by_delay"]["5"]["realistic"]
            near(cid, "series total vs results realistic end", sum(series), row["end"] - 10_000, TOL_USD)
            near(cid, "trades", c["trades"], row["trades"], 0)
            near(cid, "edge_pts", c["edge_pts"], row["ret_pct"] - row["hold_ret_pct"], 0.011)
        elif c["card"] == "improvements":
            v = imp_vars.get(c["variant"]) or {}
            pts = (v.get("dev") or {}).get("vs_as_is_pts", 0) + (v.get("sealed") or {}).get("vs_as_is_pts", 0)
            near(cid, "series total vs dev+sealed points", sum(series), 100 * pts, 2.5)
            near(cid, "edge_pts", c["edge_pts"], pts, 0.011)
        else:
            run = next((r for r in labf["runs"] if r["rule"] == c["rule"] and r["variant"] == c["variant"]
                        and r["universe"] == c["universe"]), None)
            if run is None:
                miss(cid, "lab run", "claim", "no such run")
                continue
            near(cid, "series total vs lab pnl_usd", sum(series), run["pnl_usd"], TOL_USD)
            near(cid, "edge_pts", c["edge_pts"], run["vs_spy_pts"], 0.011)
        # luck
        lk = c.get("luck")
        if c["trades"] >= MIN_N and lk is None:
            miss(cid, "luck", None, "required with 30+ trades")
        if lk:
            if c["family"] in want_trials and lk["trials"] != want_trials[c["family"]]:
                miss(cid, "luck.trials", lk["trials"], want_trials[c["family"]])
            py = PER_YEAR[MARKET.get(c.get("course"), "us_equities")]
            if lk["method"] == "deflated_sharpe":
                mem = fam.get("member_series") or {}
                own = c["variant"] if c["card"] == "improvements" else f"{c['rule']}|{c['variant']}|{c['universe']}"
                if own not in mem or mem[own] != series:
                    miss(cid, "series vs family member", "differs or missing", own)
                p, sr0, var = dsr(series, lk["trials"], list(mem.values()))
                near(cid, "luck.dsr", lk["dsr"], p, TOL_P)
                near(cid, "luck.sr0_ann", lk["sr0_ann"], sr0 * math.sqrt(py), TOL_SR)
                ok = p >= PASS_DSR
            else:
                sr, p, pa = hl(series, lk["trials"])
                near(cid, "luck.p", lk["p"], p, TOL_P)
                near(cid, "luck.p_adjusted", lk["p_adjusted"], pa, TOL_P)
                ok = sr > 0 and pa < PASS_HL
            near(cid, "luck.sharpe_ann", lk["sharpe_ann"], _stats(series)[0] * math.sqrt(py), TOL_SR)
            if lk.get("passes") is not ok:
                miss(cid, "luck.passes", lk.get("passes"), ok)
        # shuffle
        sh = c.get("shuffle")
        if sh and sh["method"] == "random_days":
            res = json.loads((RESULTS / c["course"] / f"{c['version']}.json").read_text())
            have = _ledger_trades(c["course"], c["version"])
            bad = [t for t in c.get("shuffle_trades") or [] if (t[2], t[3]) not in have]
            if bad or len(c.get("shuffle_trades") or []) != c["trades"]:
                miss(cid, "shuffle_trades vs the engine ledger", len(bad), "every trade in the ledger at 5 min")
            try:
                got = headline_shuffle(c["shuffle_trades"], MARKET[c["course"]], res["window"],
                                       calc.read_flags(), seed, draws)
                near(cid, "shuffle.pct_rank", sh["pct_rank"], got["pct_rank"], TOL_RANK)
                near(cid, "shuffle.twin_pnl_usd", sh["twin_pnl_usd"], got["twin_pnl_usd"], TOL_USD)
            except (B.MissingBar, calc.B.MissingBar) as e:
                unverifiable.append(f"{cid}: {e}")
        elif sh and sh["method"] == "random_trades":
            v = imp_vars.get(c["variant"])
            if v is None:
                miss(cid, "variant", c["variant"], "not in results/lpp/v1.json improvements")
            else:
                if not ls:
                    ls.update(label_shuffle(list(imp_vars.values()), seed, draws))
                rank, actual, picked = ls[v["id"]]
                near(cid, "shuffle.pct_rank", sh["pct_rank"], rank, TOL_RANK)
                near(cid, "shuffle.actual_change_usd", sh["actual_change_usd"], actual, TOL_USD)
                if sh.get("picked") != len(picked):
                    miss(cid, "shuffle.picked", sh.get("picked"), len(picked))
        elif sh and sh["method"] == "lab_vs_random":
            if lab_rank is None:
                lab_rank = lab_vs_random(lab_file)
            got = lab_rank.get((c["rule"], c["variant"], c["universe"]))
            run = next(r for r in labf["runs"] if r["rule"] == c["rule"] and r["variant"] == c["variant"]
                       and r["universe"] == c["universe"])
            near(cid, "shuffle.pct_rank (lab vs_random)", sh["pct_rank"], got, TOL_RANK)
            near(cid, "strategy-lab vs_random.pct_rank", (run.get("vs_random") or {}).get("pct_rank"), got, TOL_RANK)
        if sh and sh.get("passes") is not (sh["pct_rank"] >= PASS_RANK):
            miss(cid, "shuffle.passes", sh.get("passes"), sh["pct_rank"] >= PASS_RANK)
        # tests and the label follow the blocks
        tests = {k: (c.get(k) or {}).get("passes") for k in ("luck", "shuffle", "walk_forward", "sensitivity",
                                                             "regime")}
        if c.get("tests") != tests:
            miss(cid, "tests", c.get("tests"), tests)
        proven = c["trades"] >= MIN_N and (c["edge_pts"] or 0) > 0 and all(x is not False for x in tests.values())
        if c.get("proven") is not proven or c.get("label") != ("survives" if proven else "not proven"):
            miss(cid, "proven/label", [c.get("proven"), c.get("label")], proven)
    s = d.get("summary") or {}
    n_proven = sum(bool(c.get("proven")) for c in d.get("claims") or [])
    if s.get("proven") != n_proven:
        miss("file", "summary.proven", s.get("proven"), n_proven)
    return {"file": "how-sure", "pass": not out, "claims_checked": checked, "mismatches": len(out),
            "unverifiable": unverifiable, "not_recomputed": ["walk_forward", "sensitivity", "regime", "risk"],
            "details": out}
