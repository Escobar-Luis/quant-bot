"""A 10-trade hand-check sheet: seeded random LPP v1 trades at 5 min, with the raw bars around every fill.

  cd app && uv run python -m audit.handcheck [--seed 20261020] [--n 10] [--delay 5]

Writes data/audit/handcheck.md (gitignored). Numbers only: no quotes or course text. For each trade: the post
times, every fill with the raw 1-minute OHLC rows around it (straight from data/bars/), the P&L arithmetic, and
the engine's ledger P&L beside the audit's, so Luis can redo one by hand and sign off.
"""
import argparse
import datetime as dt
import json
import random

from backtest.common import DATA

from . import bars as B
from . import calc
from .run import loader, positions_for, read_ledger, RESULTS


def et(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, B.ET).strftime("%Y-%m-%d %H:%M:%S ET")


def bar_rows(market: str, symbol: str, ts: int, before: int = 2, after: int = 2) -> list[str]:
    day = B.day_of(market, ts)
    b = B.day_bars(market, symbol, day)
    keys = sorted(b)
    i = keys.index(ts) if ts in keys else min(range(len(keys)), key=lambda j: abs(keys[j] - ts))
    out = []
    for k in keys[max(0, i - before): i + after + 1]:
        o, h, lo, c = b[k]
        mark = "  <- fill bar" if k == ts else ""
        out.append(f"| {B.iso(k)} | {dt.datetime.fromtimestamp(k, B.ET).strftime('%H:%M')} | {o} | {h} | {lo} | {c} |{mark}")
    src = B.source_file(market, symbol, day)
    return [f"Raw bars `{src.relative_to(DATA.parent) if src else '?'}`:", "",
            "| bar open (UTC) | ET | open | high | low | close |", "|---|---|---|---|---|---|"] + out + [""]


def sheet(seed: int, n: int, delay: int) -> str:
    mod = loader("lpp")
    d = json.loads((RESULTS / "lpp" / "v1.json").read_text())
    positions = positions_for(mod, d, "v1")
    ledger = read_ledger(DATA / "audit" / "lpp-v1-ledger.jsonl") or {}
    pool = [p for p in positions if ledger.get((p.pid, delay), {}).get("status") == "priced"]
    picks = random.Random(seed).sample(pool, n)
    lines = [f"# Hand-check: {n} LPP v1 trades at {delay} min (seed {seed})", "",
             "Rules (contracts.md): entry = open of the first 1-minute bar at or after post + delay; his later "
             "posts fill the same way; an open position leaves at the 15:55 ET bar's open (day) or 15:55 on the "
             "5th session after entry (swing); costs 5 bps per side (20 under $10).", "",
             "P&L = sum over exits of (exit - average entry) x shares (short: entry - exit), minus costs on every "
             "fill. Sizing is shown both ways (see the audit report): `trade` = all his entries together are "
             "$1,000 (the engine), `first` = his first entry is $1,000 (contracts.md read literally).", ""]
    for i, p in enumerate(picks, 1):
        e = ledger[(p.pid, delay)]
        tr = calc.simulate(p, delay, "trade")
        lit = calc.simulate(p, delay, "first")
        lines += [f"## {i}. {p.pid}: {p.ticker} {p.side}, {p.portfolio} ({p.default_exit})", "",
                  "His posts (action, his share count, post time):", ""]
        for lg in sorted(p.legs, key=lambda lg: lg.posted_ts):
            lines.append(f"- {lg.action} {lg.qty if lg.qty else '(no count)'} at {B.iso(lg.posted_ts)} "
                         f"({et(lg.posted_ts)}); + {delay} min = {B.iso(lg.posted_ts + delay * 60)}")
        lines += ["", "Fills (audit, `trade` sizing):", "", "| time (UTC) | kind | price | shares | notional | cost |",
                  "|---|---|---|---|---|---|"]
        for f in tr.fills:
            lines.append(f"| {B.iso(f.ts)} | {f.kind} | {f.px} | {f.qty:.4f} | {f.px * f.qty:.2f} | "
                         f"{calc.cost_of(p.market, f.px, f.qty):.4f} |")
        lines.append("")
        lines += ["Entry bar:", ""] + bar_rows(p.market, p.ticker, tr.entry.ts)
        lines += ["Last exit bar:", ""] + bar_rows(p.market, p.ticker, tr.exit.ts)
        sign = 1 if p.side == "long" else -1
        avg, q, parts = 0.0, 0.0, []
        for f in tr.fills:
            if f.kind == "entry":
                avg = (avg * q + f.px * f.qty) / (q + f.qty)
                q += f.qty
            else:
                parts.append(f"{sign:+d} x ({f.px} - {avg:.4f}) x {f.qty:.4f} = {sign * (f.px - avg) * f.qty:.4f}")
                q -= f.qty
        lines += ["P&L:", ""] + [f"- {x}" for x in parts]
        lines += [f"- gross {tr.pnl + tr.cost:.4f} - costs {tr.cost:.4f} = **{tr.pnl:.2f}**", "",
                  f"Engine ledger P&L: **{e['pnl']:.2f}** (entry {e['fills'][0][1]} at {B.iso(e['fills'][0][0])}). "
                  f"Audit `trade`: {tr.pnl:.2f}. Audit `first`: {lit.pnl:.2f}.", "",
                  "- [ ] Luis: entry bar open matches  - [ ] exit bar open matches  - [ ] P&L redone by hand", ""]
    lines += ["---", "", "Signed off by Luis: ____  date: ____", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261020)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--delay", type=int, default=5)
    a = ap.parse_args()
    out = DATA / "audit" / "handcheck.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sheet(a.seed, a.n, a.delay))
    print("wrote", out)


if __name__ == "__main__":
    main()
