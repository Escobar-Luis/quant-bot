"""Recompute `strategy_profile` (contracts.md section strategy_profile, spec-audit CAP-14) from the audit's own trades.

Never imports backtest.*: the features are worked out again from the audit's positions (audit.positions), its
priced trades (audit.calc) and the events, following the contract's text; the lists and buckets come from the
file's own `definitions` (they are definitions, not numbers). Every number in the key is checked: the summary,
every table row, setup, rule (and the keep rule itself), the three losing patterns (and that they are the three
the contract's selection picks) and the worst days.
"""
import datetime as dt
import json
from collections import Counter, defaultdict
from statistics import median

from . import bars as B
from . import calc
from . import positions as P

MONEY_TOL = 1.0     # a sum of copied P&L: $1 (each trade is already checked to the cent)
AVG_TOL = 0.02      # an average of copied P&L


def _in(value: float, buckets: list) -> str:
    for top, label in buckets:
        if top is None or value < top:
            return label
    return buckets[-1][1]


def _setup(why: str | None, side: str, setups: list) -> str:
    w = (why or "").lower()
    for s in setups:
        if s["side"] == side and (not s["words"] or any(k in w for k in s["words"])):
            return s["id"]
    return "other-longs" if side == "long" else "other-shorts"


def _adds(t: calc.Trade) -> str:
    buys = [f for f in t.fills if f.kind == "entry"]
    if len(buys) < 2:
        return "none"
    held = spent = 0.0
    for k, f in enumerate(buys):
        avg = spent / held if held else None
        if k and ((f.px > avg) if t.side == "short" else (f.px < avg)):
            return "to_loser"
        held, spent = held + f.qty, spent + f.qty * f.px
    return "to_winner"


def rows(kept: list, pos: dict, events: dict, defs: dict) -> list[dict]:
    groups = defs["ticker_groups"]
    out = []
    for t, pnl in kept:
        p = pos[t.pid]
        at = dt.datetime.fromtimestamp(p.legs[0].posted_ts, B.ET)
        hm = (at.hour, at.minute)
        t15 = "before 09:30" if hm < (9, 30) else f"{at.hour:02d}:{at.minute // 15 * 15:02d}"
        t30 = "09:30" if hm < (10, 0) else "11:00 or later" if hm >= (11, 0) else f"{at.hour:02d}:{at.minute // 30 * 30:02d}"
        why = next((events[lg.event_id].get("why") for lg in p.legs if events.get(lg.event_id, {}).get("why")), None)
        qty = p.legs[0].qty
        out.append({"pid": t.pid, "day": at.date().isoformat(), "ticker": p.ticker, "side": p.side,
                    "group": next((g for g, ts in groups.items() if p.ticker in ts), defs["other_group"]),
                    "time15": t15, "time30": t30, "setup": _setup(why, p.side, defs["setups"]), "adds": _adds(t),
                    "exit": "assumed" if t.assumed_exit else "stated",
                    "hold": "overnight" if p.portfolio == "swing"
                    else _in((t.exit.ts - t.entry.ts) / 60, defs["hold_buckets_min"]),
                    "size": _in(qty * t.entry.px, defs["size_buckets_usd"]) if qty else "not stated",
                    "portfolio": p.portfolio, "pnl": pnl, "qty": qty, "usd": qty * t.entry.px if qty else None})
    n_day = Counter(x["day"] for x in out)
    for x in out:
        x["day_trades"] = _in(n_day[x["day"]], defs["day_buckets"])
    return out


def _hit(x: dict, cond: dict) -> bool:
    return all(x.get(k) in (v if isinstance(v, list) else [v]) for k, v in (cond or {}).items())


def _stats(g: list[dict], n_all: int | None = None) -> dict:
    won = [x["pnl"] for x in g if x["pnl"] > 0]
    lost = [x["pnl"] for x in g if x["pnl"] <= 0]
    s = {"trades": len(g), "won_pct": round(100 * len(won) / len(g)) if g else 0, "pnl_usd": sum(x["pnl"] for x in g),
         "avg_win_usd": sum(won) / len(won) if won else None, "avg_loss_usd": sum(lost) / len(lost) if lost else None}
    if n_all:
        s["share_pct"] = round(100 * len(g) / n_all, 1)
    return s


def _cmp(where: str, theirs: dict, ours: dict, out: list) -> None:
    for f, v in ours.items():
        t = theirs.get(f, "missing")
        if f in ("pnl_usd",):
            ok = isinstance(t, (int, float)) and abs(t - v) <= MONEY_TOL
        elif f in ("avg_win_usd", "avg_loss_usd"):
            ok = (t is None and v is None) or (isinstance(t, (int, float)) and v is not None and abs(t - v) <= AVG_TOL)
        else:
            ok = t == v
        if not ok:
            out.append({"kind": "strategy_profile", "portfolio": where, "field": f, "theirs": t,
                        "ours": round(v, 2) if isinstance(v, float) else v})


def _patterns(rs: list[dict], defs: dict, n: int = 3) -> list[dict]:
    """The contract's selection, rule 6 of section strategy_profile, written again."""
    what, how = ("side", "group", "ticker", "setup"), ("time30", "adds", "exit", "hold")
    singles = what + how + ("size", "day_trades")
    conds = [{a: [v]} for a in singles for v in sorted({x[a] for x in rs})]
    for i, a in enumerate(what):
        for b in what[i + 1:] + how:
            for va in sorted({x[a] for x in rs}):
                for vb in sorted({x[b] for x in rs if x[a] == va}):
                    conds.append({a: [va], b: [vb]})
    scored = []
    for c in conds:
        ids = frozenset(x["pid"] for x in rs if _hit(x, c))
        if len(ids) >= defs["pattern_min_trades"]:
            scored.append((round(sum(x["pnl"] for x in rs if x["pid"] in ids), 2), len(c),
                           json.dumps({k: c[k] for k in sorted(c)}), c, ids))
    scored.sort(key=lambda s: s[:3])
    picked = []
    for pnl, _, _, c, ids in scored:
        if pnl >= 0 or len(picked) == n:
            break
        if all(len(ids & q) <= 0.5 * min(len(ids), len(q)) for _, q in picked):
            picked.append((c, ids))
    return [c for c, _ in picked]


def check(sp: dict, mine: dict, headline5: dict, version: str) -> list[dict]:
    """Mismatches between the file's strategy_profile and this recompute (empty = reconciles)."""
    out: list[dict] = []
    d = sp.get("delay_min", 5)
    defs = sp["definitions"]
    pos = {p.pid: p for p in P.build("lpp", version)}
    events = {e["event_id"]: e for e in P.rows(P.lpp_events_path(version))}
    kept, *_ = calc.copied_trades([t for (pid, dl), t in mine.items() if dl == d])
    rs = rows(kept, pos, events, defs)
    n = len(rs)
    s = sp["summary"]
    usd = [x["usd"] for x in rs if x["usd"]]
    qty = [x["qty"] for x in rs if x["qty"]]
    per_day = Counter(x["day"] for x in rs)
    _cmp("summary", s, {"trades": n, "sessions": len(per_day), "pnl_usd": sum(x["pnl"] for x in rs),
                        "won_pct": _stats(rs)["won_pct"]}, out)
    _cmp("summary.headline", {"trades": s["trades"], "pnl_usd": s["pnl_usd"]},
         {"trades": headline5["trades"], "pnl_usd": headline5["end"] - calc.MONEY_START}, out)
    _cmp("summary.trades_per_session", s["trades_per_session"],
         {"median": median(per_day.values()), "max": max(per_day.values())}, out)
    _cmp("summary.his_size", s["his_size"], {"stated_on": len(qty), "median_shares": median(qty) if qty else None,
                                             "median_usd": round(median(usd)) if usd else None,
                                             "p90_usd": round(sorted(usd)[int(0.9 * (len(usd) - 1))]) if usd else None}, out)
    _cmp("summary.adds", s["adds"], {"copied_with_adds": sum(x["adds"] != "none" for x in rs),
                                     "to_loser": sum(x["adds"] == "to_loser" for x in rs),
                                     "to_winner": sum(x["adds"] == "to_winner" for x in rs)}, out)
    for tb in sp["tables"]:
        by, listed = tb["by"], []
        for r in tb["rows"]:
            if r["key"] == "other" and "keys" in r:
                g = [x for x in rs if x[by] not in listed]
                _cmp(f"tables.{by}.other", r, {**_stats(g, n), "keys": len({x[by] for x in g})}, out)
                continue
            listed.append(r["key"])
            _cmp(f"tables.{by}.{r['key']}", r, _stats([x for x in rs if x[by] == r["key"]], n), out)
        if sum(r["trades"] for r in tb["rows"]) != n:
            out.append({"kind": "strategy_profile", "portfolio": f"tables.{by}", "field": "rows cover every trade",
                        "theirs": sum(r["trades"] for r in tb["rows"]), "ours": n})
    for i, st in enumerate(sp.get("setups") or []):
        _cmp(f"setups.{i}", st, _stats([x for x in rs if _hit(x, st["when"])], n), out)
    keep = defs["kept_if"]
    for r in sp.get("rules") or []:
        situ = [x for x in rs if _hit(x, r["when"])]
        follow = [x for x in situ if _hit(x, r["does"])]
        pct = round(100 * len(follow) / len(situ), 1) if situ else 0.0
        _cmp(f"rules.{r['id']}", r, {"situation_trades": len(situ), "follows_pct": pct, **_stats(follow, n)}, out)
        if len(situ) < keep["min_trades"] or len(follow) < keep["min_trades"] or pct < keep["min_follows_pct"]:
            out.append({"kind": "strategy_profile", "portfolio": f"rules.{r['id']}", "field": "kept_if",
                        "theirs": "kept", "ours": f"{len(follow)} of {len(situ)} trades, {pct}%: should be dropped"})
        q = r.get("quote")
        if q and len(q["text"].split()) > 12:
            out.append({"kind": "strategy_profile", "portfolio": f"rules.{r['id']}", "field": "quote words",
                        "theirs": len(q["text"].split()), "ours": "12 or fewer"})
    for x in sp.get("dropped") or []:
        if "situation_trades" in x:
            situ = [y for y in rs if _hit(y, x["when"])]
            follow = [y for y in situ if _hit(y, x["does"])]
            pct = round(100 * len(follow) / len(situ), 1) if situ else 0.0
            if len(situ) >= keep["min_trades"] and len(follow) >= keep["min_trades"] and pct >= keep["min_follows_pct"]:
                out.append({"kind": "strategy_profile", "portfolio": "dropped", "field": "kept_if",
                            "theirs": x.get("why"), "ours": f"{len(follow)} of {len(situ)}, {pct}%: should be kept"})
    losses = -sum(x["pnl"] for x in rs if x["pnl"] < 0)
    for i, lp in enumerate(sp.get("losing_patterns") or []):
        g = [x for x in rs if _hit(x, lp["when"])]
        lost = -sum(x["pnl"] for x in g if x["pnl"] < 0)
        _cmp(f"losing_patterns.{lp['id']}", lp, {**_stats(g, n),
             "share_of_losses_pct": round(100 * lost / losses, 1) if losses else 0}, out)
    want = _patterns(rs, defs)
    have = [{k: lp["when"][k] for k in sorted(lp["when"])} for lp in sp.get("losing_patterns") or []]
    if [{k: c[k] for k in sorted(c)} for c in want] != have:
        out.append({"kind": "strategy_profile", "portfolio": "losing_patterns", "field": "selection",
                    "theirs": have, "ours": want})
    by_day = defaultdict(list)
    for x in rs:
        by_day[x["day"]].append(x)
    worst = sorted(by_day, key=lambda k: (sum(x["pnl"] for x in by_day[k]), k))[:len(sp.get("worst_days") or [])]
    for i, wd in enumerate(sp.get("worst_days") or []):
        day = worst[i] if i < len(worst) else None
        if wd["day"] != day:
            out.append({"kind": "strategy_profile", "portfolio": f"worst_days.{i}", "field": "day",
                        "theirs": wd["day"], "ours": day})
            continue
        g = by_day[day]
        _cmp(f"worst_days.{day}", wd, {**_stats(g), "shorts": sum(x["side"] == "short" for x in g),
                                       "adds_to_loser": sum(x["adds"] == "to_loser" for x in g),
                                       "exits_assumed": sum(x["exit"] == "assumed" for x in g)}, out)
    return out
