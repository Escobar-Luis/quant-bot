"""How sure? Honest evaluation of every strategy claim (spec-audit CAP-16, story audit-28-honest-eval; absorbs 27).

  cd app && uv run python -m backtest.howsure [--fetch-cap 2000]

Writes results/how-sure.json (contracts.md, section `how-sure`). Code only, no model (AGENTS.md rule 3). Claims:
  1. each course's headline (`all`, 5 min, the realistic cost case the card leads with): LPP v1, Crypto Wizard v1,
     ZipTrader v1 (LPP v2 is the 30-session proof set, judged only against v1: not a strategy claim);
  2. story 20's improvements V1-V6 (results/lpp/v1.json `improvements`, simple costs as on its card);
  3. story 21's strategy lab: S4 and S5 (variant P) and the control C on every list (results/strategy-lab.json).
For each: trials (from the logs) and a multiple-testing luck test (deflated Sharpe, Bailey & Lopez de Prado 2014,
when the family's other variants are priced; else a Harvey-Liu Bonferroni haircut), a shuffle test (1,000 seeded
draws) unless one exists, walk-forward folds (improvements only: the one family where something was picked),
threshold sensitivity (+-20%, +-50%), up vs down SPY months, and risk under realistic costs. A claim is "proven"
only when it has an edge and passes every test that applies; anything else is "not proven".
app/audit/howsure.py recomputes the luck tests and the shuffle percentiles with its own code and the same seeds.
Network: none, except Alpaca 1-minute bars the lab's gap sensitivity needs (at most --fetch-cap per run).
"""
import argparse
import bisect
import datetime as dt
import json
import math
import sys
from statistics import NormalDist

import numpy as np

from . import bars as B
from . import costs as CO
from . import engine, improvements, lab
from .common import BARS, DATA, DEFAULT_DELAY_MIN, DELAYS_MIN, MONEY_START, RESULTS, git_sha, public_json

SCHEMA = "how-sure/1"
SEED, DRAWS = 28, 1000
DSR_PASS, HL_ALPHA, SHUFFLE_PASS = 0.95, 0.05, 95.0
MIN_TRADES, MIN_POOL = 30, 5
GAMMA = 0.5772156649015329            # Euler-Mascheroni
N01 = NormalDist()
STEPS = (0.5, 0.8, 1.2, 1.5)          # thresholds moved -50%, -20%, +20%, +50%
TRAIN_MONTHS, TEST_MONTHS = 3, 1
LOG = "notes/research/backtesting.md, section 8"
# Trials per headline family, from the log (section 8): every headline rule priced for that course's full window.
HEADLINE_TRIALS = {
    "lpp": {"n": 4, "what": "rule 11 as taught (whole-trade sizing), rule 11 stitched, rule 13 provisional "
                            "(no hold intent), rule 13 with hold intent (the headline since story 17)"},
    "cryptowizard": {"n": 1, "what": "one copy rule, never changed"},
    "ziptrader": {"n": 1, "what": "one copy rule, never changed"},
}
COURSES = (("lpp", "v1"), ("cryptowizard", "v1"), ("ziptrader", "v1"))
# The engineer's smoke tests (improvements.SMOKE_TESTS), as the code kinds they were priced as (the log, section 6).
SMOKE_AS_CODE = {
    "Skip TSLA shorts": {"kind": "skip", "when": {"side": ["short"], "ticker": ["TSLA"]}},
    "Leave shorts 60 min after the first buy": {"kind": "max_hold", "when": {"side": ["short"]}, "value": 60},
    "2% stop on every trade": {"kind": "stop_pct", "when": {}, "value": 2.0},
    "Only crypto-linked or hot small and mid caps":
        {"kind": "only", "when": {"group": ["crypto-linked", "hot small and mid caps"]}},
}
LAB_ROWS = (("S4", "P"), ("S5", "P"), ("C", "control"))
LAB_THRESHOLDS = ("gap_pct", "stop_pct")


def r2(x):
    return None if x is None else round(float(x) + 0.0, 2)


def r4(x):
    return None if x is None else round(float(x) + 0.0, 4)


# ---- luck tests (pure; app/audit/howsure.py has its own copy) -------------------------------------------------

def moments(x) -> tuple[float, float, float, float]:
    """mean, sample std (ddof 1), skew and kurtosis (non-excess; biased central moments) of a daily series."""
    a = np.asarray(x, dtype=float)
    m = float(a.mean())
    sd = float(a.std(ddof=1)) if len(a) > 1 else 0.0
    m2 = float(((a - m) ** 2).mean())
    if m2 <= 0:
        return m, sd, 0.0, 3.0
    return m, sd, float(((a - m) ** 3).mean() / m2 ** 1.5), float(((a - m) ** 4).mean() / m2 ** 2)


def sharpe(x) -> float:
    m, sd, *_ = moments(x)
    return m / sd if sd > 0 else 0.0


def expected_max_sr(n: int, var_sr: float) -> float:
    """SR0: the best Sharpe expected from n unskilled trials whose Sharpes vary by var_sr (per period)."""
    if n <= 1 or var_sr <= 0:
        return 0.0
    return math.sqrt(var_sr) * ((1 - GAMMA) * N01.inv_cdf(1 - 1 / n) + GAMMA * N01.inv_cdf(1 - 1 / (n * math.e)))


def psr_from(sr: float, t: int, skew: float, kurt: float, sr0: float) -> float:
    """Probabilistic Sharpe ratio: P(true Sharpe > sr0) for a per-period Sharpe over t periods."""
    den = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if t < 2 or den <= 0:
        return 0.0
    return N01.cdf((sr - sr0) * math.sqrt(t - 1) / math.sqrt(den))


def psr(x, sr0: float) -> float:
    m, sd, g3, g4 = moments(x)
    return psr_from(m / sd if sd > 0 else 0.0, len(x), g3, g4, sr0)


def deflated(x, n: int, var_sr: float, per_year: int) -> dict:
    sr0 = expected_max_sr(n, var_sr)
    p = psr(x, sr0)
    return {"method": "deflated_sharpe", "trials": n, "sharpe_ann": r2(sharpe(x) * math.sqrt(per_year)),
            "sr0_ann": r2(sr0 * math.sqrt(per_year)), "var_trial_sr": float(f"{var_sr:.6g}"), "dsr": r4(p),
            "passes": p >= DSR_PASS}


def harvey_liu(x, n: int, per_year: int) -> dict:
    """Bonferroni haircut (Harvey & Liu 2015), one-sided: p = 1 - Phi(SR * sqrt(T)), adjusted p = min(1, n p);
    the haircut Sharpe is the one whose p equals the adjusted p."""
    sr, t = sharpe(x), len(x)
    p = 1 - N01.cdf(sr * math.sqrt(t)) if t else 1.0
    pa = min(1.0, n * p)
    hc = N01.inv_cdf(1 - pa) / math.sqrt(t) if 0 < pa < 1 else (0.0 if pa >= 1 else sr)
    return {"method": "harvey_liu_bonferroni", "trials": n, "sharpe_ann": r2(sr * math.sqrt(per_year)),
            "haircut_sharpe_ann": r2(max(hc, 0.0) * math.sqrt(per_year)), "p": r4(p), "p_adjusted": r4(pa),
            "passes": sr > 0 and pa < HL_ALPHA}


# ---- shuffle test: same names, same clock times, same hold, random days (pure apart from the bar cache) --------

def cached_days(market: str, sym: str) -> list[str]:
    dirs = [BARS / "alpaca_1m" / sym, BARS / "yahoo_1m" / sym] if market == "us_equities" else \
        [BARS / "binance" / sym / "1m"]
    return sorted({p.stem for d in dirs if d.exists() for p in d.glob("*.json")})


_BARS: dict = {}


def cached_bars(market: str, sym: str, day: str) -> dict[int, list]:
    k = (market, sym, day)
    if k not in _BARS:
        if market == "us_equities":
            p = next((q for q in (BARS / "alpaca_1m" / sym / f"{day}.json", BARS / "yahoo_1m" / sym / f"{day}.json")
                      if q.exists()), None)
            _BARS[k] = {int(t): v for t, v in json.loads(p.read_text()).items()} if p else {}
        else:
            p = BARS / "binance" / sym / "1m" / f"{day}.json"
            _BARS[k] = {int(r[0] // 1000): r[1:] for r in json.loads(p.read_text())} if p.exists() else {}
    return _BARS[k]


def clock(market: str, ts: int) -> tuple[dt.date, dt.time]:
    z = B.ET if market == "us_equities" else dt.UTC
    t = dt.datetime.fromtimestamp(ts, z)
    return t.date(), t.time()


def at(market: str, day: dt.date, t: dt.time) -> int:
    z = B.ET if market == "us_equities" else dt.UTC
    return int(dt.datetime.combine(day, t, z).timestamp())


def twin_pnl(tr: dict, d_in: dt.date, flag: str) -> float | None:
    """$1,000 in at the entry's clock time on d_in, out at the exit's clock time `days` later; realistic costs
    (contracts rule 5) and, for a short, the borrow fee per calendar day held (at least 1). None: no entry bar."""
    m = tr["market"]
    d_out = d_in + dt.timedelta(days=tr["days"])
    bi, bo = cached_bars(m, tr["ticker"], d_in.isoformat()), cached_bars(m, tr["ticker"], d_out.isoformat())
    t_in, t_out = at(m, d_in, tr["t_in"]), at(m, d_out, tr["t_out"])
    k_in = min((k for k in bi if k >= t_in), default=None)
    if k_in is None or not bo:
        return None
    k_out = min((k for k in bo if k >= t_out), default=None)
    px_in, px_out = bi[k_in][0], (bo[k_out][0] if k_out is not None else bo[max(bo)][3])
    sign = 1 if tr["side"] == "long" else -1
    adv = (lambda d: CO.adv_before(tr["ticker"], d) if m == "us_equities" else None)
    c_in = CO.side_bps("realistic", m, px_in, adv(d_in)) / 1e4
    c_out = CO.side_bps("realistic", m, px_out, adv(d_out)) / 1e4
    q = 1000.0 / px_in
    pnl = sign * q * (px_out - px_in) - 1000.0 * c_in - q * px_out * c_out
    if sign < 0:
        pnl -= CO.borrow_usd("realistic", "crypto" if m == "crypto" else flag, 1000.0, max(1, tr["days"]))
    return pnl


def shuffle_inputs(kept: list, market: str) -> list[dict]:
    """The headline's copied trades, in time order: name, side, entry and exit clock time, calendar days held."""
    out = []
    for r, _ in sorted(kept, key=lambda x: (x[0].entry.ts, x[0].position.ticker, x[0].position.side)):
        e, x = r.entry.ts, r.last_exit.ts
        (d0, t0), (d1, t1) = clock(market, e), clock(market, x)
        out.append({"ticker": r.position.ticker, "side": r.position.side, "market": market, "entry_ts": e,
                    "exit_ts": x, "day": d0, "t_in": t0, "t_out": t1, "days": (d1 - d0).days})
    return out


def shuffle(trades: list[dict], window: dict, flags: dict) -> dict:
    """Each trade moved to a random day of its name's cached sessions in the window (days held kept), 1,000
    seeded draws; the actual trades priced the same way are the twin. Trades whose name has fewer than MIN_POOL
    candidate days stay on their own day in every draw."""
    rng = np.random.default_rng(SEED)
    lo, hi = window["start"], window["end"]
    twin, total, moved, fixed = 0.0, np.zeros(DRAWS), 0, 0
    for tr in trades:
        flag = flags.get(tr["ticker"], "unknown")
        own = twin_pnl(tr, tr["day"], flag)
        if own is None:
            raise SystemExit(f"shuffle: no bars for the actual trade {tr['ticker']} {tr['day']}")
        twin += own
        pool = []
        have = set(cached_days(tr["market"], tr["ticker"]))
        for d in sorted(have):
            if lo <= d <= hi and (dt.date.fromisoformat(d) + dt.timedelta(days=tr["days"])).isoformat() in have:
                v = twin_pnl(tr, dt.date.fromisoformat(d), flag)
                if v is not None:
                    pool.append(v)
        if len(pool) < MIN_POOL:
            total += own
            fixed += 1
            continue
        moved += 1
        total += np.asarray(pool)[rng.integers(0, len(pool), size=DRAWS)]
    return {"method": "random_days", "twin_pnl_usd": r2(twin), "p2_5": r2(np.percentile(total, 2.5)),
            "p97_5": r2(np.percentile(total, 97.5)), "pct_rank": round(100 * float((total < twin).mean()), 1),
            "draws": DRAWS, "seed": SEED, "trades_moved": moved, "trades_fixed": fixed,
            "passes": 100 * float((total < twin).mean()) >= SHUFFLE_PASS}


def label_shuffle(delta: list[float], treated: list[int]) -> dict:
    """Is the change's own pick of trades better than as many trades picked at random? Per-position change in
    P&L (simple costs, no cash cap); 1,000 seeded draws of len(treated) positions without replacement."""
    rng = np.random.default_rng(SEED)
    d = np.asarray(delta, dtype=float)
    actual = float(d[treated].sum())
    draws = np.array([d[rng.choice(len(d), size=len(treated), replace=False)].sum() for _ in range(DRAWS)])
    rank = 100 * float((draws < actual).mean())
    return {"method": "random_trades", "actual_change_usd": r2(actual), "p2_5": r2(np.percentile(draws, 2.5)),
            "p97_5": r2(np.percentile(draws, 97.5)), "pct_rank": round(rank, 1), "draws": DRAWS, "seed": SEED,
            "picked": len(treated), "of": len(d), "passes": rank >= SHUFFLE_PASS}


# ---- series, months, risk --------------------------------------------------------------------------------------

def daily_pnl(kept: list, dates: list[str], market: str) -> list[float]:
    """Copied P&L by exit day on the calendar (a day off it counts on the next listed date, as the headline)."""
    out = [0.0] * len(dates)
    for r, pnl in kept:
        day = B.day_of(market, r.last_exit.ts).isoformat()
        out[min(bisect.bisect_left(dates, day), len(dates) - 1)] += pnl
    return out


def month_returns(market: str, symbol: str, start: str, end: str) -> dict[str, float]:
    """Return per calendar month (last close / previous month's last close - 1; the first month from the window's
    first close), daily closes (Alpaca for stocks, Binance for crypto; cached)."""
    c = B.daily_closes(market, symbol, dt.date.fromisoformat(start), dt.date.fromisoformat(end))
    out, prev, last = {}, None, {}
    for d, px in c.items():
        last[d[:7]] = px
    first = next(iter(c.values()))
    for m in sorted(last):
        base = prev if prev is not None else first
        out[m] = 100 * (last[m] / base - 1)
        prev = last[m]
    return out


def spy_months(start: str, end: str) -> dict[str, float]:
    return month_returns("us_equities", "SPY", start, end)


def regime(dates: list[str], pnl: list[float], spy: dict[str, float], bench: dict[str, float] | None,
           bench_name: str) -> dict:
    """Return and edge in months SPY rose vs months it fell. Edge: the return minus the benchmark's summed monthly
    returns (an account), or the return itself when bench is None (an improvement: pnl is already a difference)."""
    out = {}
    for name, up in (("up", True), ("down", False)):
        ms = sorted(m for m, v in spy.items() if (v > 0) == up)
        ret = 100 * sum(p for d, p in zip(dates, pnl) if d[:7] in ms) / MONEY_START
        b = sum(bench.get(m, 0.0) for m in ms) if bench is not None else 0.0
        out[name] = {"months": len(ms), "ret_pct": r2(ret), "bench_ret_pct": r2(b), "edge_pts": r2(ret - b)}
    have = [x for x in out.values() if x["months"]]
    out["passes"] = all(x["edge_pts"] > 0 for x in have) if have else None
    out["bench"] = bench_name
    out["basis"] = "months split by SPY's monthly return sign; P&L by exit day; benchmark months summed"
    return out


def risk(daily: list[float], dates: list[str], trades_pnl: list[float], ret: float) -> dict:
    eq, peak, mdd = MONEY_START, MONEY_START, 0.0
    for v in daily:
        eq += v
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    best = cur = 0
    for p in trades_pnl:
        cur = cur + 1 if p <= 0 else 0
        best = max(best, cur)
    i = min(range(len(daily)), key=lambda k: (daily[k], dates[k])) if daily else None
    return {"costs": "realistic", "ret_pct": r2(ret), "max_drawdown_pct": r2(100 * mdd),
            "longest_losing_streak": best,
            "worst_day": {"day": dates[i], "pnl_usd": r2(daily[i])} if i is not None and daily[i] < 0 else None}


def verdict(row: dict) -> dict:
    """proven only with an edge, 30+ trades, and every test that applies passed; else "not proven" and why."""
    tests = {k: (row.get(k) or {}).get("passes") for k in ("luck", "shuffle", "walk_forward", "sensitivity", "regime")}
    why = []
    if row["trades"] < MIN_TRADES:
        why.append(f"fewer than {MIN_TRADES} trades")
    if row["edge_pts"] is None or row["edge_pts"] <= 0:
        why.append("no edge to prove")
    why += [f"{k} failed" for k, ok in tests.items() if ok is False]
    row["tests"] = tests
    row["proven"] = not why
    row["label"] = "survives" if not why else "not proven"
    row["why_not"] = why
    return row


# ---- 1. course headlines ---------------------------------------------------------------------------------------

def course_claim(course: str, version: str) -> tuple[dict, dict]:
    from .run import course_module
    mod = course_module(course)
    res = json.loads((RESULTS / course / f"{version}.json").read_text())
    d5 = str(DEFAULT_DELAY_MIN)
    cc = next(p for p in res["cost_cases"]["portfolios"] if p["id"] == "all")["by_delay"]
    row5 = cc[d5]["realistic"]
    flags = res["cost_cases"]["borrow"]["flags"]
    positions, base = improvements.headline(mod, version, DEFAULT_DELAY_MIN)
    model = CO.Model("realistic", flags)
    kept, *_ = engine.fit_to_cash([engine.reprice(r, model) for r in base.values() if r.status == "priced"], model)
    end = MONEY_START + sum(p for _, p in kept)
    if abs(end - row5["end"]) > 0.02 or len(kept) != row5["trades"]:
        raise SystemExit(f"{course}/{version}: realistic headline {end:.2f}/{len(kept)} != file "
                         f"{row5['end']}/{row5['trades']}; rerun backtest.run first")
    dates = next(p for p in res["portfolios"] if p["id"] == "all")["series"]["dates"]
    per_year = 252 if mod.MARKET == "us_equities" else 365
    daily = [round(v, 2) for v in daily_pnl(kept, dates, mod.MARKET)]   # the published series, to the cent
    ret, hold = row5["ret_pct"], row5["hold_ret_pct"]
    n = HEADLINE_TRIALS[course]["n"]
    enough = len(kept) >= MIN_TRADES
    sens = [{"delay_min": int(d), "ret_pct": cc[d]["realistic"]["ret_pct"],
             "edge_pts": r2(cc[d]["realistic"]["ret_pct"] - cc[d]["realistic"]["hold_ret_pct"])}
            for d in sorted(cc, key=int)]
    trades_in = shuffle_inputs(kept, mod.MARKET) if enough else []
    row = {"id": f"course:{course}", "family": f"{course}-headline", "card": "verdict", "course": course,
           "version": version, "name": f"{res['course_name']}: copy every post (all, 5 min)",
           "costs": "realistic", "trades": len(kept), "ret_pct": r2(ret),
           "edge_pts": r2(ret - hold), "edge_vs": f"just holding {res['hold']['symbol']} ({r2(hold)}%)",
           "luck": harvey_liu(daily, n, per_year) if enough else None,
           "shuffle": shuffle(trades_in, mod.WINDOW, flags) if enough else None,
           "walk_forward": None, "walk_forward_note": "nothing was picked: the copy takes every post",
           "sensitivity": None if not enough else {"threshold": "delay_min", "base": DEFAULT_DELAY_MIN, "values": sens,
                           "ret_range_pct": [min(x["ret_pct"] for x in sens), max(x["ret_pct"] for x in sens)],
                           "edge_range_pts": [min(x["edge_pts"] for x in sens), max(x["edge_pts"] for x in sens)],
                           "passes": all(x["edge_pts"] > 0 for x in sens),
                           "note": "the delay is the copy's only free number; every delay the slider offers"},
           "regime": regime(dates, daily, spy_months(dates[0], dates[-1]),
                            month_returns(mod.MARKET, getattr(mod, "HOLD_BARS", mod.HOLD["symbol"]), dates[0],
                                          dates[-1]), res["hold"]["symbol"]) if enough else None,
           "regime_note": None if enough else f"fewer than {MIN_TRADES} trades",
           "sensitivity_note": None if enough else f"fewer than {MIN_TRADES} trades",
           "risk": risk(daily, dates, [p for _, p in kept], ret),
           "series": {"calendar": f"{course}-{version}", "pnl": [r2(v) for v in daily]}}
    if enough:
        row["shuffle_trades"] = [[t["ticker"], t["side"], t["entry_ts"], t["exit_ts"]] for t in trades_in]
    return verdict(row), {f"{course}-{version}": dates}


# ---- 2. improvements (story 20) --------------------------------------------------------------------------------

def months_between(a: str, b: str) -> list[str]:
    y, m = int(a[:4]), int(a[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= b[:7]:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def walk_forward(by_month: dict[str, dict[str, float]], months: list[str], spy: dict[str, float]) -> dict:
    """Rolling folds: pick the candidate with the best summed return over TRAIN_MONTHS, report it on the next
    month; the out-of-sample result is the sum of the test months. Ties go to as-is, then the first listed."""
    folds = []
    names = list(by_month)
    for i in range(TRAIN_MONTHS, len(months) - TEST_MONTHS + 1):
        train, test = months[i - TRAIN_MONTHS:i], months[i:i + TEST_MONTHS]
        score = {k: sum(by_month[k].get(m, 0.0) for m in train) for k in names}
        best = max(names, key=lambda k: (round(score[k], 6), k == "as-is", -names.index(k)))
        folds.append({"train": [train[0], train[-1]], "test": test[0], "picked": best,
                      "train_ret_pct": r2(score[best]),
                      "test_ret_pct": r2(sum(by_month[best].get(m, 0.0) for m in test)),
                      "as_is_test_ret_pct": r2(sum(by_month["as-is"].get(m, 0.0) for m in test)),
                      "spy_test_ret_pct": r2(sum(spy.get(m, 0.0) for m in test))})
    oos = sum(f["test_ret_pct"] for f in folds)
    base = sum(f["as_is_test_ret_pct"] for f in folds)
    return {"train_months": TRAIN_MONTHS, "test_months": TEST_MONTHS, "folds": folds,
            "oos_ret_pct": r2(oos), "as_is_oos_ret_pct": r2(base), "oos_vs_as_is_pts": r2(oos - base),
            "spy_oos_ret_pct": r2(sum(f["spy_test_ret_pct"] for f in folds)),
            "candidates": names, "picked_count": {k: sum(f["picked"] == k for f in folds) for k in names},
            "passes": oos - base > 0}


def improvement_claims(dates: list[str]) -> tuple[list[dict], dict]:
    from . import lpp as mod
    res = json.loads((RESULTS / "lpp" / "v1.json").read_text())
    imp = res["improvements"]
    d = imp["delay_min"]
    sealed_from = mod.WINDOW["sealed_from"]
    positions, base = improvements.headline(mod, "v1", d)
    feats = improvements.all_features(mod, "v1", positions, base, d)
    flags = res["cost_cases"]["borrow"]["flags"]
    real = CO.Model("realistic", flags)
    months = months_between(mod.WINDOW["start"], mod.WINDOW["end"])
    spy = spy_months(dates[0], dates[-1])

    def run(v: dict | None) -> dict:
        rs = list(base.values()) if v is None else improvements.apply(mod, positions, base, v, d, feats)
        kept, *_ = engine.fit_to_cash([r for r in rs if r.status == "priced"])
        mon = {}
        for r, pnl in kept:
            m = B.day_of(r.position.market, r.entry.ts).isoformat()[:7]
            mon[m] = mon.get(m, 0.0) + 100 * pnl / MONEY_START
        dev = sum(p for r, p in kept if B.day_of(r.position.market, r.entry.ts).isoformat() < sealed_from)
        kr, *_ = engine.fit_to_cash([engine.reprice(r, real) for r in rs if r.status == "priced"], real)
        return {"kept": kept, "daily": daily_pnl(kept, dates, mod.MARKET), "months": mon,
                "dev_ret": round(100 * dev / MONEY_START, 2),
                "sealed_ret": round(100 * (sum(p for _, p in kept) - dev) / MONEY_START, 2),
                "real": kr, "real_daily": daily_pnl(kr, dates, mod.MARKET)}

    as_is = run(None)
    cands = {"as-is": as_is}
    for v in imp["variants"]:
        got = run(v)
        if got["dev_ret"] != v["dev"]["ret_pct"] or got["sealed_ret"] != v["sealed"]["ret_pct"]:
            raise SystemExit(f"improvements {v['id']}: {got['dev_ret']}/{got['sealed_ret']} != file "
                             f"{v['dev']['ret_pct']}/{v['sealed']['ret_pct']}; rerun backtest.run first")
        cands[v["id"]] = got
    smoke = [t for t in improvements.SMOKE_TESTS if t["priced"] and not t.get("same_as")]
    for t in smoke:
        cands[t["rule"]] = run(SMOKE_AS_CODE[t["rule"]])
    n = imp["variants_tried"]["distinct_priced"]
    if n != len(cands) - 1:
        raise SystemExit(f"improvements: the log says {n} distinct variants, code priced {len(cands) - 1}")
    delta = {k: [round(a - b, 2) for a, b in zip(c["daily"], as_is["daily"])] for k, c in cands.items() if k != "as-is"}
    var_sr = float(np.var([sharpe(x) for x in delta.values()], ddof=1))
    wf = walk_forward({k: c["months"] for k, c in cands.items()}, months, spy)

    # label shuffle inputs: each position's simple-cost P&L as-is and under the change applied to every position
    order = sorted(positions, key=lambda p: p.pid)
    pnl0 = [base[p.pid].pnl if base[p.pid].status == "priced" else 0.0 for p in order]
    claims = []
    for v in imp["variants"]:
        c = cands[v["id"]]
        hit = [improvements.strategy.matches(feats[p.pid], v["when"]) for p in order]
        if v["kind"] in ("skip", "only"):
            dl = [-x for x in pnl0]
            treated = [i for i, h in enumerate(hit) if h == (v["kind"] == "skip")]
        else:
            every = {**v, "when": {}}
            ch = {r.position.pid: r for r in improvements.apply(mod, positions, base, every, d, feats)}
            dl = [(ch[p.pid].pnl if ch[p.pid].status == "priced" else 0.0) - x for p, x in zip(order, pnl0)]
            treated = [i for i, h in enumerate(hit) if h and base[order[i].pid].status == "priced"]
        sens = None
        if v["kind"] in improvements.RANGES:
            vals = []
            for s in STEPS:
                val = v["value"] * s
                val = round(val, 2) if v["kind"] == "stop_pct" else int(round(val))
                got = run({**v, "value": val})
                tot = got["dev_ret"] + got["sealed_ret"] - as_is["dev_ret"] - as_is["sealed_ret"]
                vals.append({"value": val, "step": s, "vs_as_is_pts": r2(tot),
                             "sealed_vs_as_is_pts": r2(got["sealed_ret"] - as_is["sealed_ret"])})
            base_pts = v["dev"]["vs_as_is_pts"] + v["sealed"]["vs_as_is_pts"]
            allv = [x["vs_as_is_pts"] for x in vals] + [base_pts]
            sens = {"threshold": v["kind"], "base": v["value"], "values": vals,
                    "edge_range_pts": [r2(min(allv)), r2(max(allv))], "passes": all(x > 0 for x in allv),
                    "note": "full window vs as-is, simple costs, each value one run through the cash cap"}
        total = v["dev"]["vs_as_is_pts"] + v["sealed"]["vs_as_is_pts"]
        rret = 100 * sum(p for _, p in c["real"]) / MONEY_START
        row = {"id": f"improvements:{v['id']}", "family": "improvements", "card": "improvements",
               "variant": v["id"], "name": v["rule"], "costs": "simple", "trades": len(c["kept"]),
               "ret_pct": r2(c["dev_ret"] + c["sealed_ret"]), "edge_pts": r2(total), "edge_vs": "the as-is copy",
               "luck": deflated(delta[v["id"]], n, var_sr, 252),
               "shuffle": label_shuffle(dl, treated),
               "walk_forward": {"oos_ret_pct": wf["oos_ret_pct"], "as_is_oos_ret_pct": wf["as_is_oos_ret_pct"],
                                "oos_vs_as_is_pts": wf["oos_vs_as_is_pts"],
                                "picked_folds": wf["picked_count"][v["id"]], "folds": len(wf["folds"]),
                                "passes": wf["passes"] and wf["picked_count"][v["id"]] > 0},
               "sensitivity": sens,
               "sensitivity_note": None if sens else "no number to move (a choice of trades, not a threshold)",
               "regime": regime(dates, delta[v["id"]], spy, None, "as-is"),
               "risk": risk(c["real_daily"], dates, [p for _, p in c["real"]], rret),
               "series": {"calendar": "lpp-v1", "pnl": [r2(x) for x in delta[v["id"]]]},
               "shuffle_positions": {"order": "pid", "treated": treated}}
        claims.append(verdict(row))
    fam = {"trials": n, "log": imp["variants_tried"]["log"] + "; " + LOG,
           "members": [k for k in cands if k != "as-is"], "var_trial_sr": float(f"{var_sr:.6g}"),
           "member_series": {k: [r2(x) for x in v] for k, v in delta.items()}, "walk_forward": wf}
    return claims, fam


# ---- 3. strategy lab (story 21) --------------------------------------------------------------------------------

def lab_trades(rule: dict, uni: dict, v: dict, split: dict, raw: dict, flags: dict) -> list[dict]:
    out = []
    for t in uni["tickers"]:
        for d in lab.gap_sessions(split[t], v["gap_pct"]):
            tr = lab.short_trade(lab.load_minutes(t, d), dt.date.fromisoformat(d), rule["entry_et"], v["stop_pct"],
                                 v["exit_et"])
            if tr is not None:
                out.append({"ticker": t, "day": d, **tr, "adv": lab.adv_before(raw[t], d),
                            "htb": flags[t] is False, "flag": CO.flag_word("us_equities", flags[t])})
    return out


def lab_claims(fetch_cap: int) -> tuple[list[dict], dict, dict]:
    L = json.loads((RESULTS / "strategy-lab.json").read_text())
    ledger = json.loads((DATA / "lab" / "ledger.json").read_text())
    tickers = sorted({t for u in lab.UNIVERSES for t in u["tickers"]})
    split = {t: lab.daily(t, "split") for t in tickers}
    raw = {t: lab.daily(t, "raw") for t in tickers}
    cal = lab.sessions(lab.daily("SPY", "all"))
    flags = lab.borrow_flags(tickers)
    spy_full = L["benchmark"]["ret_pct"]
    # minute bars the gap sensitivity needs (gap thresholds below the pre-registered 5% were never fetched)
    need = sorted({(t, d) for r in lab.RULES[:2] for u in r["universes"]
                   for t in next(x for x in lab.UNIVERSES if x["id"] == u)["tickers"]
                   for d in lab.gap_sessions(split[t], 5 * STEPS[0])})
    fetched, still = lab.fetch_minutes(need, fetch_cap)
    print(f"lab sensitivity: minute ticker-days needed {len(need)}, fetched {fetched}, still missing {still}",
          file=sys.stderr)
    if still:
        raise SystemExit(3)
    series_all = {}
    for k, ts in ledger.items():
        s = [0.0] * len(cal)
        for t in ts:
            s[cal.index(t["day"])] += t["pnl"]
        series_all[k] = [round(x, 2) for x in s]
    var_sr = float(np.var([sharpe(s) for s in series_all.values()], ddof=1))
    n = L["variants_tried"]
    spy = spy_months(cal[0], cal[-1])
    claims = []
    for rid, vid in LAB_ROWS:
        rule = next(r for r in lab.RULES if r["id"] == rid)
        for uid in rule["universes"]:
            run = next(r for r in L["runs"] if r["rule"] == rid and r["variant"] == vid and r["universe"] == uid)
            key = f"{rid}|{vid}|{uid}"
            ts = ledger[key]
            s = series_all[key]
            if abs(sum(s) - run["pnl_usd"]) > 1.0:   # each day rounded to the cent
                raise SystemExit(f"lab {key}: ledger {sum(s):.2f} != file {run['pnl_usd']}; rerun backtest.lab")
            plain = [{k: x for k, x in t.items() if k not in ("notional", "pnl", "borrow")} for t in ts]
            rb = lab.book(plain, cal, case="realistic")
            rs = [0.0] * len(cal)
            for t in rb["trades"]:
                rs[cal.index(t["day"])] += t["pnl"]
            sens = None
            if rid != "C":
                uni = next(x for x in lab.UNIVERSES if x["id"] == uid)
                p = next(x for x in lab.VARIANTS if x["id"] == "P")
                vals = []
                for th in LAB_THRESHOLDS:
                    for st in STEPS:
                        v = {**p, th: p[th] * st}
                        b = lab.book(lab_trades(rule, uni, v, split, raw, flags), cal)
                        ret = 100 * b["pnl"] / MONEY_START
                        vals.append({"threshold": th, "value": v[th], "step": st, "trades": len(b["trades"]),
                                     "ret_pct": r2(ret), "edge_pts": r2(ret - spy_full)})
                allv = [x["edge_pts"] for x in vals] + [r2(run["ret_pct"] - spy_full)]
                sens = {"threshold": "gap_pct and stop_pct", "base": {"gap_pct": 5, "stop_pct": 5}, "values": vals,
                        "ret_range_pct": [min(x["ret_pct"] for x in vals + [run]),
                                          max(x["ret_pct"] for x in vals + [run])],
                        "edge_range_pts": [min(allv), max(allv)], "passes": all(x > 0 for x in allv),
                        "note": "one threshold moved at a time; base costs, as the run; edge vs SPY"}
            vr = run.get("vs_random")
            row = {"id": f"lab:{key}", "family": "strategy-lab", "card": "lab", "rule": rid, "variant": vid,
                   "universe": uid, "name": f"{rule['label']} ({uid})", "costs": "simple",
                   "trades": run["trades"], "ret_pct": run["ret_pct"], "edge_pts": run["vs_spy_pts"],
                   "edge_vs": f"SPY ({spy_full}%)",
                   "luck": deflated(s, n, var_sr, 252) if run["trades"] >= MIN_TRADES else None,
                   "shuffle": ({"method": "lab_vs_random", "pct_rank": vr["pct_rank"], "draws": vr["draws"],
                                "seed": lab.SEED, "twin_pnl_usd": vr["twin_pnl_usd"], "p2_5": vr["p2_5"],
                                "p97_5": vr["p97_5"], "passes": vr["pct_rank"] >= SHUFFLE_PASS,
                                "note": "story 21's own test (daily-bar twin, base costs), reused"} if vr else None),
                   "shuffle_note": None if vr else "the control is the random baseline",
                   "walk_forward": None, "walk_forward_note": "pre-registered: nothing was picked on these months",
                   "sensitivity": sens, "sensitivity_note": None if sens else "no threshold: shorts every open",
                   "regime": regime(cal, s, spy, spy, "SPY"),
                   "risk": risk(rs, cal, [t["pnl"] for t in sorted(rb["trades"],
                                                                   key=lambda t: (t["entry_ts"], t["ticker"]))],
                                100 * rb["pnl"] / MONEY_START),
                   "series": {"calendar": "strategy-lab", "pnl": [r2(x) for x in s]}}
            claims.append(verdict(row))
    fam = {"trials": n, "log": "results/strategy-lab.json variants_tried; notes/research/backtesting.md, section 7",
           "members": sorted(series_all), "var_trial_sr": float(f"{var_sr:.6g}"),
           "member_series": {k: [r2(x) for x in v] for k, v in sorted(series_all.items())}}
    return claims, fam, {"strategy-lab": cal}


# ---- run ---------------------------------------------------------------------------------------------------------

def build(fetch_cap: int) -> dict:
    claims, cals, fams = [], {}, {}
    for course, version in COURSES:
        row, cal = course_claim(course, version)
        claims.append(row)
        cals.update(cal)
        fams[f"{course}-headline"] = {"trials": HEADLINE_TRIALS[course]["n"], "log": LOG,
                                      "members": [HEADLINE_TRIALS[course]["what"]]}
        print(f"{row['id']:<26} {row['name']}: {row['trades']} trades, edge {row['edge_pts']} -> {row['label']}",
              file=sys.stderr)
    imp, fams["improvements"] = improvement_claims(cals["lpp-v1"])
    lc, fams["strategy-lab"], lcal = lab_claims(fetch_cap)
    cals.update(lcal)
    claims += imp + lc
    for c in claims:
        print(f"  {c['id']:<36} edge {c['edge_pts']:>7}  luck {c['tests']['luck']!s:<5} shuffle "
              f"{c['tests']['shuffle']!s:<5} wf {c['tests']['walk_forward']!s:<5} sens "
              f"{c['tests']['sensitivity']!s:<5} regime {c['tests']['regime']!s:<5} -> {c['label']}", file=sys.stderr)
    return {
        "schema": SCHEMA, "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(), "spec": "spec-audit CAP-16 (story 28)", "seed": SEED, "draws": DRAWS,
        "rules": {
            "proven": "an edge, 30+ trades, and every test that applies passed; anything else is not proven",
            "luck": f"deflated Sharpe >= {DSR_PASS} when the family's variants are priced (Bailey & Lopez de Prado "
                    f"2014, N = trials, V = variance of their daily Sharpes); else Harvey-Liu Bonferroni haircut, "
                    f"one-sided adjusted p < {HL_ALPHA}",
            "shuffle": f"actual at or above the {SHUFFLE_PASS:g}th percentile of {DRAWS} seeded draws",
            "walk_forward": f"{TRAIN_MONTHS}-month train / {TEST_MONTHS}-month test rolling folds; pick on train, "
                            "report test; passes when the summed test months beat as-is and the change was picked",
            "sensitivity": "each threshold at -50%, -20%, +20%, +50%: the edge stays above 0 at every value",
            "regime": "the edge is above 0 in both SPY up months and SPY down months",
            "risk": "max drawdown, longest losing streak and worst day under realistic costs (reported, not tested)"},
        "families": fams, "calendars": cals, "claims": claims,
        "summary": {"claims": len(claims), "proven": sum(c["proven"] for c in claims),
                    "proven_ids": [c["id"] for c in claims if c["proven"]]},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-cap", type=int, default=2000, help="new 1-minute ticker-days to fetch this run")
    ap.add_argument("--out", default=str(RESULTS / "how-sure.json"))
    a = ap.parse_args(argv)
    out = build(a.fetch_cap)
    with open(a.out, "w") as f:
        f.write(public_json(out) + "\n")
    print(f"wrote {a.out}: {out['summary']['proven']} of {out['summary']['claims']} claims proven", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
