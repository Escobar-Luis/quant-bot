"""Gold set: a hand-drafted answer key for 5 sessions, a review checklist for Luis, and metrics vs the extractor.

  uv run python -m lpp.gold checklist   # write data/lpp/gold/<id>.md from drafts + extractor extras
  uv run python -m lpp.gold metrics     # score data/lpp/events.jsonl against gold (reviewed checklist if present)

Matching (one-to-one, nearest in time first):
  trade: same ticker, same action group (entry = open/add, exit = trim/close), within 30 s; `strict` also needs the same action
  call:  same ticker within 60 s
  rule:  any extracted rule within 60 s of the gold rule
Unsure gold events neither count against recall nor against precision until Luis decides them.
"""
import json
import re
import sys
from pathlib import Path

from .common import DATA, RES
from .transcript import load

GOLD = DATA / "gold"
DRAFT = GOLD / "draft"
GOLD_IDS = ["E_sa74f6Ctw", "zSJD7GANqwo", "XQ8DS0EnyXY", "5xvxykJ1W7Y", "8bG7TPrnj5E"]
WIN = {"trade": 30, "call": 60, "rule": 60}
GROUP = {"open": "entry", "add": "entry", "trim": "exit", "close": "exit"}


def _gold_events(vid: str) -> list[dict]:
    """Draft gold with quote-located times; a reviewed checklist (if any) decides keep/drop and adds events."""
    g = json.loads((DRAFT / f"{vid}.json").read_text())
    tr = load(vid)
    evs = []
    for i, e in enumerate(g["events"]):
        t = tr.find(e["quote"], near=e["t"])
        evs.append({**e, "gid": f"g{i:02d}", "t_s": t if t is not None else e["t"], "status": "sure" if e.get("sure") else "unsure"})
    md = GOLD / f"{vid}.md"
    if md.exists() and reviewed(md.read_text()):
        evs = _apply_review(md.read_text(), evs, tr)
    return evs


def reviewed(text: str) -> bool:
    """The header line says `·  reviewed: yes` once Luis is done (the instruction text in brackets doesn't count)."""
    return bool(re.search(r"·\s+reviewed:\s*yes", text, re.I))


_LINE = re.compile(r"^- \[(?P<mark>[ xX])\]\s+(?:\[(?P<m1>\d+):(?P<s1>\d\d)\]\([^)]*?(?:t=(?P<t>\d+))?\)|(?P<m2>\d+):(?P<s2>\d\d))"
                   r"\s+(?P<type>TRADE|CALL|RULE)\s+(?P<body>.*?)(?:\s+\*\*\(unsure\)\*\*)?:\s+\"(?P<quote>[^\"]*)\"(?P<rest>.*)$", re.M)
_NUMBER = re.compile(r"^\$?\d+(?:\.\d+)?$")


def parse_line(m) -> dict:
    """A checklist line as Luis left it -> a gold event, so edited tickers, qty, prices and added lines count."""
    t = int(m["t"]) if m["t"] else int(m["m1"] or m["m2"]) * 60 + int(m["s1"] or m["s2"])
    e = {"type": m["type"].lower(), "t": t, "t_s": float(t), "quote": m["quote"]}
    toks = m["body"].split()
    if e["type"] == "rule":
        return {**e, "rule": m["body"]}
    e["ticker"] = toks[0].upper() if toks else None
    e["side"] = next((x for x in toks if x in ("long", "short")), None)
    if e["type"] == "trade":
        e["action"] = next((x for x in toks if x in ("open", "add", "trim", "close")), None)
        nums = [(i, float(x.lstrip("$"))) for i, x in enumerate(toks) if _NUMBER.match(x)]
        at = toks.index("@") if "@" in toks else len(toks)
        e["qty"] = next((n for i, n in nums if i < at), None)
        e["price"] = next((n for i, n in nums if i > at), None)
    else:
        e["level_kind"] = next((x for x in toks if x in ("entry", "stop", "target", "support", "resistance")), None)
        e["level"] = next((float(x.lstrip("$")) for x in reversed(toks) if _NUMBER.match(x)), None)
    return e


def _apply_review(text: str, evs: list[dict], tr) -> list[dict]:
    """[x] keeps a line as gold, [ ] drops it. Each ticked line is read as written (Luis's edits count), and
    ticked extractor extras and added lines become gold too. A line that can't be read falls back to the draft."""
    by = {e["gid"]: e for e in evs}
    out = []
    for i, m in enumerate(_LINE.finditer(text)):
        if m["mark"].lower() != "x" or "(write it like this" in m["rest"]:
            continue
        gid = re.search(r"`([gm]\d+)`", m["rest"])
        gid = gid.group(1) if gid else f"a{i:02d}"
        try:
            e = parse_line(m)
        except (ValueError, TypeError):
            e = by.get(gid)
            if e is None:
                continue
        out.append({**e, "gid": gid, "status": "sure"})
    return out


def _match(gold, pred, typ, strict=False):
    """Greedy one-to-one matching by time distance. Returns {gold_idx: pred_idx}."""
    pairs = []
    for gi, g in enumerate(gold):
        for pi, p in enumerate(pred):
            if g["t_s"] is None or p["t_s"] is None or abs(g["t_s"] - p["t_s"]) > WIN[typ]:
                continue
            if typ in ("trade", "call") and (g.get("ticker") or "").upper() != (p.get("ticker") or "").upper():
                continue
            if typ == "trade":
                if strict and g.get("action") != p.get("action"):
                    continue
                if GROUP.get(g.get("action")) != GROUP.get(p.get("action")):
                    continue
            pairs.append((abs(g["t_s"] - p["t_s"]), gi, pi))
    used_g, used_p, m = set(), set(), {}
    for _, gi, pi in sorted(pairs):
        if gi not in used_g and pi not in used_p:
            m[gi] = pi
            used_g.add(gi)
            used_p.add(pi)
    return m


def score(pred_by_vid: dict, ids=GOLD_IDS) -> dict:
    tot = {k: 0 for k in ["trade_gold", "trade_hit", "trade_hit_strict", "trade_pred", "trade_pred_ok", "trade_pred_ok_strict",
                          "call_pred", "call_pred_ok", "rule_gold", "rule_hit", "trade_unsure_gold"]}
    per = {}
    for vid in ids:
        gold = _gold_events(vid)
        pred = pred_by_vid.get(vid, [])
        s = {}
        for typ in ("trade", "call", "rule"):
            g_all = [g for g in gold if g["type"] == typ]
            g_sure = [g for g in g_all if g["status"] == "sure"]
            p = [x for x in pred if x["type"] == typ]
            m_sure = _match(g_sure, p, typ)
            m_all = _match(g_all, p, typ)
            if typ == "trade":
                s.update(gold=len(g_sure), hit=len(m_sure), hit_strict=len(_match(g_sure, p, typ, strict=True)),
                         pred=len(p), pred_ok=len(m_all), pred_ok_strict=len(_match(g_all, p, typ, strict=True)),
                         unsure=len(g_all) - len(g_sure),
                         missed=[g["gid"] for gi, g in enumerate(g_sure) if gi not in m_sure],
                         extra=[p[pi]["event_id"] for pi in range(len(p)) if pi not in m_all.values()])
                tot["trade_gold"] += len(g_sure); tot["trade_hit"] += len(m_sure)
                tot["trade_hit_strict"] += s["hit_strict"]; tot["trade_pred"] += len(p); tot["trade_pred_ok"] += len(m_all)
                tot["trade_pred_ok_strict"] += s["pred_ok_strict"]
                tot["trade_unsure_gold"] += s["unsure"]
            elif typ == "call":
                s.update(call_pred=len(p), call_pred_ok=len(m_all), call_gold=len(g_sure),
                         call_extra=[p[pi]["event_id"] for pi in range(len(p)) if pi not in m_all.values()])
                tot["call_pred"] += len(p); tot["call_pred_ok"] += len(m_all)
            else:
                s.update(rule_gold=len(g_sure), rule_hit=len(m_sure), rule_pred=len(p))
                tot["rule_gold"] += len(g_sure); tot["rule_hit"] += len(m_sure)
        per[vid] = s
    r = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    # spec metric = strict (same ticker AND same action within 30 s); the entry/exit-group version is looser
    return {"trade_recall": r(tot["trade_hit_strict"], tot["trade_gold"]),
            "trade_precision": r(tot["trade_pred_ok_strict"], tot["trade_pred"]),
            "trade_recall_entry_exit": r(tot["trade_hit"], tot["trade_gold"]),
            "trade_precision_entry_exit": r(tot["trade_pred_ok"], tot["trade_pred"]),
            "call_precision": r(tot["call_pred_ok"], tot["call_pred"]),
            "rule_recall": r(tot["rule_hit"], tot["rule_gold"]), "totals": tot, "per_session": per}


def load_pred(path=None) -> dict:
    out = {}
    for line in open(path or RES / "events.jsonl"):
        e = json.loads(line)
        out.setdefault(e["source_id"].split(":", 1)[1], []).append(e)
    return out


def _fmt(e):
    if e["type"] == "trade":
        px = f" @ {e['price']:g}" if e.get("price") is not None else ""
        q = f" {e['qty']:g}" if e.get("qty") is not None else ""
        return f"TRADE {e.get('ticker')} {e.get('side') or ''} {e.get('action')}{q}{px}"
    if e["type"] == "call":
        return f"CALL {e.get('ticker')} {e.get('side') or ''} {e.get('level_kind') or ''} {e.get('level')}"
    return f"RULE {e.get('rule')}"


def checklist(vid: str, pred: list[dict]) -> str:
    g = json.loads((DRAFT / f"{vid}.json").read_text())
    tr = load(vid)
    gold = []
    for i, e in enumerate(g["events"]):
        t = tr.find(e["quote"], near=e["t"])
        gold.append({**e, "gid": f"g{i:02d}", "t_s": t if t is not None else e["t"],
                     "status": "sure" if e.get("sure") else "unsure"})
    url = f"https://youtu.be/{vid}"
    date = pred[0]["session_date"] if pred else ""
    lines = [f"# LPP gold: {date} `{vid}`", "",
             f"Video: {url}  ·  reviewed: no  (change to `reviewed: yes` when done)", "",
             "Tick `[x]` if the host really did or said this, untick `[ ]` if not. Fix a ticker, qty or price by editing the line.",
             "Click a time to hear it. Only the host's own trades count, not viewers' trades he reads out.", ""]
    if g.get("note"):
        lines += [f"> {g['note']}", ""]
    for typ, title in (("trade", "Trades"), ("call", "Calls (ticker + direction + level)"), ("rule", "Rules")):
        lines += [f"## {title}", ""]
        for e in [x for x in gold if x["type"] == typ]:
            t = int(e["t_s"])
            box = "x" if e["status"] == "sure" else " "
            unsure = " **(unsure)**" if e["status"] != "sure" else ""
            note = f" ({e['note']})" if e.get("note") else ""
            lines.append(f"- [{box}] [{t // 60}:{t % 60:02d}]({url}?t={t}) {_fmt(e)}{unsure}: \"{e['quote']}\"{note} `{e['gid']}`")
        lines.append("")
    # extractor events that match no gold event: maybe gold misses them
    m_ids = set()
    for typ in ("trade", "call", "rule"):
        gt = [x for x in gold if x["type"] == typ]
        pt = [x for x in pred if x["type"] == typ]
        m_ids |= {pt[pi]["event_id"] for pi in _match(gt, pt, typ).values()}
    extra = [p for p in pred if p["event_id"] not in m_ids and p["type"] in ("trade", "call")]
    lines += ["## The extractor also found these (tick only if real)", ""]
    for i, p in enumerate(extra):
        t = int(p["t_s"] or 0)
        keep = {k: p.get(k) for k in ("type", "ticker", "side", "action", "qty", "price", "level", "level_kind", "quote")}
        keep["t"] = t
        lines.append(f"- [ ] [{t // 60}:{t % 60:02d}]({url}?t={t}) {_fmt(p)}: \"{p['quote']}\" `m{i:02d}` <!--{json.dumps(keep)}-->")
    lines += ["", "## Missed anything? Add a line", "", "- [x] 12:34 TRADE TICKER short open 100 @ 1.23: \"quote\" (write it like this; I'll add it)", ""]
    return "\n".join(lines)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "metrics"
    pred = load_pred()
    if cmd == "checklist":
        for vid in GOLD_IDS:
            p = GOLD / f"{vid}.md"
            if p.exists() and "--force" not in sys.argv:  # never overwrite a review in progress
                print("kept", p, "(reviewed)" if reviewed(p.read_text()) else "(pass --force to rewrite)")
                continue
            p.write_text(checklist(vid, pred.get(vid, [])))
            print("wrote", p)
    else:
        print(json.dumps(score(pred), indent=1))


if __name__ == "__main__":
    main()
