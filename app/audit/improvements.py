"""Recompute `improvements` (contracts.md section improvements, spec-audit CAP-15) from the audit's own positions.

Never imports backtest.*: each change in the file (kind, when, value) is applied again to the audit's own positions
(audit.positions), re-priced by the second calculator (audit.calc), run through its own cash cap
(calc.copied_trades) and split into dev and sealed months; SPY's total return comes from audit.years' holding run.
Checked: as-is, SPY, every variant's dev and sealed trades and returns (and the gaps), the keep decision and its
reason class, and that every `when` uses only features known at entry.
"""
import dataclasses
import datetime as dt

from . import bars as B
from . import calc, years
from . import positions as P
from .strategy import _setup

RET_TOL = 0.01
ENTRY = ("side", "group", "ticker", "time15", "time30", "setup")


def _feats(p, events: dict, defs: dict) -> dict:
    at = dt.datetime.fromtimestamp(p.legs[0].posted_ts, B.ET)
    hm = (at.hour, at.minute)
    why = next((events[lg.event_id].get("why") for lg in p.legs if events.get(lg.event_id, {}).get("why")), None)
    return {"side": p.side, "ticker": p.ticker,
            "group": next((g for g, ts in defs["ticker_groups"].items() if p.ticker in ts), defs["other_group"]),
            "time15": "before 09:30" if hm < (9, 30) else f"{at.hour:02d}:{at.minute // 15 * 15:02d}",
            "time30": "09:30" if hm < (10, 0) else "11:00 or later" if hm >= (11, 0)
            else f"{at.hour:02d}:{at.minute // 30 * 30:02d}",
            "setup": _setup(why, p.side, defs["setups"])}


def _hit(f: dict, when: dict) -> bool:
    return all(f[k] in v for k, v in (when or {}).items())


def _changed(p, t0: calc.Trade, v: dict, delay: int):
    """The position under the change, or None when it is unchanged (contracts.md improvements rule 2)."""
    kind, e = v["kind"], t0.entry
    short = p.side == "short"
    if kind == "no_add_against":
        entries = sorted((lg for lg in p.legs if lg.action in ("open", "add")), key=lambda lg: lg.posted_ts)
        drop = set()
        for lg in entries[1:]:
            if lg.action != "add":
                continue
            try:
                _, b = B.first_bar_at_or_after(p.market, p.ticker, lg.posted_ts + delay * 60)
            except B.MissingBar:
                continue
            if (b[0] > e.px) if short else (b[0] < e.px):
                drop.add(id(lg))
        if not drop:
            return None
        return dataclasses.replace(p, legs=[lg for lg in p.legs if id(lg) not in drop])
    if kind == "max_hold":
        if p.default_exit == "day_close":
            first = min((lg for lg in p.legs if lg.action in ("open", "add")), key=lambda lg: lg.posted_ts)
            own = B.et_time(B.et_day(first.posted_ts), *calc.DAY_EXIT)
        else:
            own = calc.horizon_ts(p, e.ts)
        return dataclasses.replace(p, default_exit=f"at:{min(own, e.ts + int(v['value']) * 60)}")
    if kind == "stop_pct":
        lvl = e.px * (1 + v["value"] / 100) if short else e.px * (1 - v["value"] / 100)
        stop = lvl if p.stop is None else (min(p.stop, lvl) if short else max(p.stop, lvl))
        return dataclasses.replace(p, stop=stop)
    raise ValueError(kind)


def _split(trades: list, sealed_from: str) -> dict:
    kept, *_ = calc.copied_trades([t for t in trades if t.status == "priced"])
    out = {"dev": [], "sealed": []}
    for t, pnl in kept:
        out["dev" if B.day_of(t.market, t.entry.ts).isoformat() < sealed_from else "sealed"].append(pnl)
    return {k: {"trades": len(x), "ret_pct": 100 * sum(x) / calc.MONEY_START} for k, x in out.items()}


def _miss(out, where, field, theirs, ours):
    out.append({"kind": "improvements", "portfolio": where, "field": field, "theirs": theirs,
                "ours": round(ours, 4) if isinstance(ours, float) else ours})


def _num(out, where, field, theirs, ours, tol=RET_TOL):
    if not isinstance(theirs, (int, float)) or abs(theirs - ours) > tol + 1e-9:
        _miss(out, where, field, theirs, ours)


def check(imp: dict, mine: dict, version: str, window: dict, defs: dict, market: str = "us_equities",
          symbol: str = "SPY") -> list[dict]:
    """Mismatches between the file's improvements key and this recompute (empty = reconciles)."""
    out: list[dict] = []
    d = imp.get("delay_min", 5)
    sealed_from = window["sealed_from"]
    pos = P.build("lpp", version)
    events = {e["event_id"]: e for e in P.rows(P.lpp_events_path(version))}
    base = {p.pid: mine[(p.pid, d)] for p in pos}
    feats = {p.pid: _feats(p, events, defs) for p in pos}
    as_is = _split(list(base.values()), sealed_from)
    for part in ("dev", "sealed"):
        _num(out, f"as_is.{part}", "trades", (imp["as_is"].get(part) or {}).get("trades"), as_is[part]["trades"], 0)
        _num(out, f"as_is.{part}", "ret_pct", (imp["as_is"].get(part) or {}).get("ret_pct"), as_is[part]["ret_pct"])
    hv = years.hold_values(market, symbol, window)
    i = max(k for k, day in enumerate(hv["days"]) if day < sealed_from)
    cut = hv["total"][hv["days"][i]]
    spy = {"dev": 100 * (cut / calc.MONEY_START - 1), "sealed": 100 * (hv["total"][hv["days"][-1]] / cut - 1)}
    _num(out, "spy", "dev_ret_pct", imp["spy"].get("dev_ret_pct"), spy["dev"])
    _num(out, "spy", "sealed_ret_pct", imp["spy"].get("sealed_ret_pct"), spy["sealed"])
    if imp["spy"].get("dev_to") != hv["days"][i]:
        _miss(out, "spy", "dev_to", imp["spy"].get("dev_to"), hv["days"][i])
    floor = imp.get("min_trades", calc.MIN_TRADES)
    if floor < calc.MIN_TRADES:
        _miss(out, "file", "min_trades", floor, calc.MIN_TRADES)
    for v in imp.get("variants") or []:
        where = f"variants.{v.get('id')}"
        bad = [k for k in (v.get("when") or {}) if k not in ENTRY]
        if bad:
            _miss(out, where, "when uses a feature known only after entry", bad, list(ENTRY))
            continue
        trades = []
        for p in pos:
            hit = _hit(feats[p.pid], v["when"])
            t0 = base[p.pid]
            if (v["kind"] == "skip" and hit) or (v["kind"] == "only" and not hit):
                continue
            if v["kind"] in ("skip", "only") or not hit or t0.status != "priced":
                trades.append(t0)
                continue
            q = _changed(p, t0, v, d)
            trades.append(t0 if q is None else calc.simulate(q, d))
        got = _split(trades, sealed_from)
        for part in ("dev", "sealed"):
            th, g, a = v.get(part) or {}, got[part], as_is[part]
            _num(out, f"{where}.{part}", "trades", th.get("trades"), g["trades"], 0)
            _num(out, f"{where}.{part}", "ret_pct", th.get("ret_pct"), g["ret_pct"])
            _num(out, f"{where}.{part}", "as_is_ret_pct", th.get("as_is_ret_pct"), a["ret_pct"])
            _num(out, f"{where}.{part}", "vs_as_is_pts", th.get("vs_as_is_pts"), g["ret_pct"] - a["ret_pct"], 0.02)
            _num(out, f"{where}.{part}", "spy_ret_pct", th.get("spy_ret_pct"), spy[part])
            _num(out, f"{where}.{part}", "vs_spy_pts", th.get("vs_spy_pts"), g["ret_pct"] - spy[part], 0.02)
        dv, sv = round(got["dev"]["ret_pct"] - as_is["dev"]["ret_pct"], 2), \
            round(got["sealed"]["ret_pct"] - as_is["sealed"]["ret_pct"], 2)
        enough = got["dev"]["trades"] >= floor and got["sealed"]["trades"] >= floor
        keep = enough and dv > 0 and sv >= 0
        if v.get("kept") is not keep:
            _miss(out, where, "kept", v.get("kept"), keep)
        reason = "trades" if not enough else "dev" if dv <= 0 else "sealed" if sv < 0 else "kept"
        said = v.get("kept_reason") or ""
        want = {"trades": "trades", "dev": "(dev)", "sealed": "lost on the held-out", "kept": "did not lose"}[reason]
        if want not in said:
            _miss(out, where, "kept_reason", said, f"should say: {want}")
    return out
