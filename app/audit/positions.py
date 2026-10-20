"""The audit's own positions: the course's posted trades -> round trips, from the events and contracts.md alone.

  cd app && uv run python -m audit.positions            # compare with the course loaders, print the differences

Never imports backtest.*: the engine-side loaders (backtest.lpp, .cryptowizard, .ziptrader) are only imported by
`compare()`, to diff their positions with these field by field. A difference is a finding: neither side is
changed to match the other. Where the contract is silent, the choice is written next to the code as ASSUMPTION.
"""
import argparse
import datetime as dt
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from . import bars as B
from .paths import DATA

OPTION_WORDS = ("option", "call", "put")


@dataclass
class Leg:
    event_id: str
    posted_ts: float          # rule 1: the moment it was said (unix seconds, may carry a fraction)
    action: str               # open | add | trim | close
    qty: float | None = None  # the course's own size; None = not stated
    frac: float | None = None # exits only: share of the held position to sell
    tp_index: int | None = None   # a trim that reports the course's own take-profit n (Crypto Wizard)


@dataclass
class Position:
    pid: str
    course: str
    market: str
    ticker: str
    side: str
    portfolio: str            # day | swing | crypto (rule 8)
    legs: list[Leg]
    default_exit: str         # day_close | sessions:5 | hours:24 | at:<unix>  (rule 4)
    stop: float | None = None
    targets: list[float] = field(default_factory=list)
    target_fracs: list[float] = field(default_factory=list)
    trigger: float | None = None
    be_after_target: int | None = None
    notes: list[str] = field(default_factory=list)


def rows(path) -> list[dict]:
    return [json.loads(line) for line in open(path) if line.strip()] if path.exists() else []


def ts_of(iso: str) -> float:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def unique_ids(ps: list[Position]) -> None:
    """results/ names a second position with the same id -2, -3, ... (contracts.md: trade_id is unique)."""
    seen = Counter()
    for p in ps:
        seen[p.pid] += 1
        if seen[p.pid] > 1:
            p.pid = f"{p.pid}-{seen[p.pid]}"


# ---- Learn Plan Profit ----------------------------------------------------------------------------------------

def lpp_events_path(version: str):
    return DATA / "lpp" / ("events.jsonl" if version == "v1" else f"{version}/events.jsonl")


def lpp_proof_set() -> set[str]:
    return {f"yt:{v}" for v in json.loads((DATA / "lpp" / "gold" / "proof_set.json").read_text())}


def lpp_release() -> dict[str, float]:
    """Rule 1: an LPP post time is the video's release timestamp + t_s (data/lpp/sources.jsonl)."""
    return {s["source_id"]: ts_of(s["release_utc"]) for s in rows(DATA / "lpp" / "sources.jsonl")
            if s.get("release_utc")}


def lpp_session_key() -> dict[str, str]:
    p = DATA / "lpp" / "session_keys.json"
    return {v["video_id"]: k for k, v in json.loads(p.read_text()).items()} if p.exists() else {}


LEDGER_FAILS = {"open_never_closed", "close_without_open", "qty_exceeds_position"}   # contracts.md rule 11
CARRY_S = 7 * 86400                                                                   # rule 11: within 7 days


def lpp_copyable(e: dict) -> bool:
    """Rule 11: every check passed, or the only failures are the three ledger checks (resolved by the ledger)."""
    fails = set(e.get("fail") or [])
    return e["status"] == "ok" or (bool(fails) and fails <= LEDGER_FAILS)


def lpp(version: str, only: set[str] | None = None) -> dict:
    """LPP trade legs -> round trips, contracts.md rules 1, 4, 8 and 11 (the LPP ledger).

    - rule 11: `trade` events that passed every check, or failed only the ledger checks; options are counted,
      never priced (rule 8);
    - rule 1: post time = release + t_s, kept to the fraction of a second;
    - rule 11: per ticker and side, open/add start or grow a position, trim shrinks it, close ends it; an exit
      naming no side belongs to his one open position on that ticker, else it is skipped; an exit with no open
      position is skipped;
    - rule 11: a position held at the end of a session carries to a later session only when his next word on
      it, within 7 days of his last one, is an add, trim or close; otherwise it ends (15:55 ET of its session)
      and the new word starts afresh (an open or add opens a new position; a trim or close is skipped);
    - rule 8: legs in one session = `day` (exit 15:55 ET), legs across sessions = `swing` (5 sessions);
    - rule 3/4: a stop, targets or horizon on the opening post are kept (none of LPP's events state one);
      ASSUMPTION: LPP's `entry`/`price` are the fills he reports, not trigger levels (level_kind is never set);
    - ASSUMPTION: legs posted at the same moment keep their event order.
    """
    evs = rows(lpp_events_path(version))
    if only:
        evs = [e for e in evs if e["source_id"] in only]
    release, keys = lpp_release(), lpp_session_key()
    stats = Counter()

    def post_ts(e):
        r = release.get(e["source_id"])
        stats["post_time_from_release" if r is not None else "post_time_from_wall_utc"] += 1
        return r + float(e["t_s"] or 0) if r is not None else ts_of(e["wall_utc"])

    trades = []
    for e in evs:
        if e["type"] != "trade" or not lpp_copyable(e) or not e.get("ticker") or not e.get("action"):
            continue
        if any(w in (e.get("instrument") or "").lower() for w in OPTION_WORDS):
            stats["options"] += e["action"] == "open"
            continue
        trades.append((post_ts(e), e["event_id"], e))
    trades.sort(key=lambda x: (x[0], x[1]))

    positions: list[Position] = []
    open_: dict[tuple, dict] = {}            # (ticker, side) -> {"legs", "first"}

    def finish(key):
        o = open_.pop(key)
        legs, first = o["legs"], o["first"]
        swing = len({B.et_day(lg.posted_ts) for lg in legs}) > 1
        vid = first["source_id"].split(":", 1)[-1]
        sess = keys.get(vid, f"lpp:{first['session_date']}")[4:]
        positions.append(Position(
            pid=f"lpp-{sess}-{first['event_id'].rsplit(':', 1)[-1]}", course="lpp", market="us_equities",
            ticker=key[0], side=key[1], portfolio="swing" if swing else "day", legs=legs,
            default_exit="sessions:5" if swing else "day_close", stop=first.get("stop"),
            targets=list(first.get("targets") or [])))

    for ts, _, e in trades:
        side = e.get("side")
        if side not in ("long", "short"):
            held = [k for k in open_ if k[0] == e["ticker"]]
            if e["action"] in ("open", "add") or len(held) != 1:
                stats["side_unknown"] += 1
                continue
            side = held[0][1]
        key = (e["ticker"], side)
        if key in open_:
            last = open_[key]["legs"][-1].posted_ts
            if B.et_day(last) != B.et_day(ts):
                carries = e["action"] in ("add", "trim", "close") and ts - last <= CARRY_S
                if not carries:
                    finish(key)
        leg = Leg(e["event_id"], ts, e["action"], qty=e.get("qty") or None)
        if e["action"] in ("open", "add"):
            if key not in open_:
                open_[key] = {"legs": [], "first": e}
            open_[key]["legs"].append(leg)
        elif key not in open_:
            stats["exit_without_open"] += 1
        else:
            open_[key]["legs"].append(leg)
            if e["action"] == "close":
                finish(key)
    for key in sorted(open_, key=lambda k: open_[k]["legs"][0].posted_ts):
        finish(key)
    positions.sort(key=lambda p: (p.legs[0].posted_ts, p.legs[0].event_id))
    unique_ids(positions)
    return {"positions": positions, "stats": dict(stats)}


# ---- Crypto Wizard ---------------------------------------------------------------------------------------------

def cryptowizard(version: str = "v1") -> dict:
    """Each `call` (their Trade Update template: entry, stop, TP1-TP4 with close shares) -> one position.

    - ok calls only, with a side and a pair; post time = the Discord timestamp (rule 1);
    - ASSUMPTION: entry wording "Now or as close to" is a market entry (rule 3's open), not a trigger;
    - targets close their stated shares of the start size (`close_pcts`); the last closes the rest;
    - the break-even move is taken from their own words (`be_move` "... TP<n>": stop to entry after TP n);
    - their linked follow-ups are the course's own exits (rule 4): the first close sells the rest, a trim reporting
      TP n sells TP n's share unless the copier's own TP n order already filled (ASSUMPTION);
    - rule 4: a setup they never close leaves 24 hours after entry (`hours:24`).
    """
    evs = rows(DATA / "cryptowizard" / "events.calls.jsonl")
    follow: dict[str, list] = {}
    for e in evs:
        if e["type"] == "trade" and e["status"] == "ok" and e.get("links_to"):
            follow.setdefault(e["links_to"], []).append(e)
    stats, positions = Counter(), []
    for c in sorted((e for e in evs if e["type"] == "call" and e["status"] == "ok"), key=lambda e: e["wall_utc"]):
        side = (c.get("side") or "").lower()
        sym = c.get("pair")
        if side not in ("long", "short") or not sym:
            stats["skipped_no_side_or_pair"] += 1
            continue
        x = c.get("extra") or {}
        trig = None
        if c.get("entry") is not None and not (x.get("entry_wording") or "").lower().startswith("now"):
            trig = c["entry"]
        legs = [Leg(c["event_id"], ts_of(c["wall_utc"]), "open")]
        for f in sorted(follow.get(c["event_id"], []), key=lambda e: e["wall_utc"]):
            if f["action"] not in ("trim", "close"):
                continue
            if legs[-1].action == "close":
                break                        # a close ends the position; later posts on it have nothing to sell
            tp = (f.get("extra") or {}).get("tp_index")
            legs.append(Leg(f["event_id"], ts_of(f["wall_utc"]), f["action"], tp_index=tp if f["action"] == "trim" else None))
        pcts = x.get("close_pcts") or []
        tgts = list(c.get("targets") or [])
        m = re.search(r"TP\s*(\d)", x.get("be_move") or "", re.I)
        positions.append(Position(
            pid=f"cw-{c['source_id'].rsplit('/', 1)[-1]}", course="cryptowizard", market="crypto", ticker=sym,
            side=side, portfolio="crypto", legs=legs, default_exit="hours:24", stop=c.get("stop"), targets=tgts,
            target_fracs=[p / 100 for p in pcts] if len(pcts) == len(tgts) else [], trigger=trig,
            be_after_target=int(m.group(1)) if m else None))
    unique_ids(positions)
    return {"positions": positions, "stats": dict(stats)}


# ---- ZipTrader -------------------------------------------------------------------------------------------------

HORIZON_DAYS = re.compile(r"(\d+)\s*(day|session|week)", re.I)


def ziptrader(version: str = "v1") -> dict:
    """A briefing item that says which way to trade (a side) -> one position; the rest are watch notes.

    - ok call/setup/trade events with a ticker and a side; post time = the Discord timestamp (rule 1);
    - rule 3: a stated `entry` is the trigger level; rule 4: its stop and targets;
    - rule 8: `swing` only when the extracted `horizon` is in days or sessions (rule 4's "horizon as written"),
      else `day`. ASSUMPTION: the quote's own words are not read (the structured field is the contract input).
    """
    evs = rows(DATA / "ziptrader" / "events.jsonl")
    stats, positions = Counter(), []
    for e in sorted(evs, key=lambda e: e["wall_utc"]):
        if e["type"] not in ("call", "setup", "trade") or e["status"] != "ok" or not e.get("ticker"):
            continue
        if e.get("side") not in ("long", "short"):
            stats["watch_only"] += 1
            continue
        hz = HORIZON_DAYS.search(e.get("horizon") or "")
        swing = bool(hz)
        n = (int(hz.group(1)) * (5 if hz.group(2).lower() == "week" else 1)) if hz else 5
        positions.append(Position(
            pid=f"zt-{e['event_id'].split(':', 1)[-1].replace(':', '-')}", course="ziptrader",
            market="us_equities", ticker=e["ticker"], side=e["side"], portfolio="swing" if swing else "day",
            legs=[Leg(e["event_id"], ts_of(e["wall_utc"]), "open")],
            default_exit=f"sessions:{n}" if swing else "day_close", stop=e.get("stop"),
            targets=list(e.get("targets") or []), trigger=e.get("entry")))
    unique_ids(positions)
    return {"positions": positions, "stats": dict(stats)}


def build(course: str, version: str, only: set[str] | None = None) -> list[Position]:
    if course == "lpp":
        return lpp(version, only)["positions"]
    if course == "cryptowizard":
        return cryptowizard(version)["positions"]
    if course == "ziptrader":
        return ziptrader(version)["positions"]
    raise ValueError(f"unknown course {course}")


# ---- the comparison with the engine-side loaders --------------------------------------------------------------

def _minute(ts: float) -> int:
    return math.ceil(ts / 60)


def _same_ts(a: float, b: float) -> bool:
    """Equal when they reach the same first bar: rule 3 fills at the first 1-minute bar at or after the post
    (+ a whole-minute delay), so only a difference that crosses a minute boundary changes a fill. LPP's t_s is
    stored to 0.1 s, so differences inside a minute are below what the data can tell."""
    return _minute(a) == _minute(b)


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-5] + "Z"


def _norm(v):
    return None if v in (None, [], 0, 0.0) else v


def diff_positions(theirs: list, ours: list[Position]) -> list[dict]:
    """Every difference between the loaders' positions and the audit's, matched by first leg's event id."""
    out = []
    by_t = {p.legs[0].event_id: p for p in theirs if p.legs}
    by_o = {p.legs[0].event_id: p for p in ours if p.legs}
    for k in sorted(set(by_t) - set(by_o)):
        p = by_t[k]
        out.append({"kind": "position", "field": "presence", "pid": p.pid, "first_event": k,
                    "loader": f"{p.side} {p.ticker} {p.portfolio}, {len(p.legs)} legs", "audit": "absent"})
    for k in sorted(set(by_o) - set(by_t)):
        p = by_o[k]
        out.append({"kind": "position", "field": "presence", "pid": p.pid, "first_event": k,
                    "loader": "absent", "audit": f"{p.side} {p.ticker} {p.portfolio}, {len(p.legs)} legs"})
    for k in sorted(set(by_t) & set(by_o)):
        t, o = by_t[k], by_o[k]

        def add(f, a, b):
            out.append({"kind": "position", "field": f, "pid": o.pid, "first_event": k, "loader": a, "audit": b})

        for f in ("pid", "ticker", "side", "portfolio", "default_exit", "trigger", "be_after_target"):
            a, b = getattr(t, f, None), getattr(o, f, None)
            if _norm(a) != _norm(b):
                add(f, a, b)
        if _norm(t.stop) != _norm(o.stop):
            add("stop", t.stop, o.stop)
        if list(t.targets or []) != list(o.targets or []):
            add("targets", t.targets, o.targets)
        if [round(x, 6) for x in (t.target_fracs or [])] != [round(x, 6) for x in (o.target_fracs or [])]:
            add("target_fracs", t.target_fracs, o.target_fracs)
        tl = {lg.event_id: lg for lg in t.legs}
        ol = {lg.event_id: lg for lg in o.legs}
        for e in sorted(set(tl) - set(ol)):
            add("leg", f"{tl[e].action} {e}", "absent")
        for e in sorted(set(ol) - set(tl)):
            add("leg", "absent", f"{ol[e].action} {e}")
        for e in sorted(set(tl) & set(ol)):
            a, b = tl[e], ol[e]
            if a.action != b.action:
                add("leg.action", f"{e} {a.action}", f"{e} {b.action}")
            if _norm(a.qty) != _norm(b.qty):
                add("leg.qty", f"{e} {a.qty}", f"{e} {b.qty}")
            if not _same_ts(a.posted_ts, b.posted_ts):
                add("leg.posted_ts", f"{e} {_iso(a.posted_ts)}", f"{e} {_iso(b.posted_ts)}")
            if _norm(getattr(a, "frac", None)) != _norm(b.frac):
                add("leg.frac", f"{e} {a.frac}", f"{e} {b.frac}")
    return out


def loader_positions(course: str, version: str, only: set[str] | None = None) -> list:
    """The engine-side loaders' positions (the thing under audit), with results/'s unique ids."""
    if course == "lpp":
        from backtest import lpp as mod
        ps = (mod.build(version, only) if only else mod.build(version))["positions"]
    elif course == "cryptowizard":
        from backtest import cryptowizard as mod
        ps = mod.build(version)["positions"]
    else:
        from backtest import ziptrader as mod
        ps = mod.build(version)["positions"]
    seen = Counter()
    for p in ps:
        seen[p.pid] += 1
        if seen[p.pid] > 1:
            p.pid = f"{p.pid}-{seen[p.pid]}"
    return ps


def _causes(course: str, version: str, theirs: list, d: list[dict]) -> None:
    """Tag each LPP difference whose loader side rests on an event that failed a check (status != ok)."""
    if course != "lpp":
        return
    st = {e["event_id"]: e for e in rows(lpp_events_path(version))}
    legs = {p.legs[0].event_id: p.legs for p in theirs if p.legs}

    def bad(eid):
        e = st.get(eid)
        return e and e["status"] != "ok" and f"{e['status']} ({', '.join(e.get('fail') or [])})"

    for x in d:
        if x["field"] == "presence" and x["audit"] == "absent":
            why = sorted({b for lg in legs.get(x["first_event"], []) if (b := bad(lg.event_id))})
        elif x["field"].startswith("leg") and isinstance(x["loader"], str) and x["loader"] != "absent":
            why = [b for b in [bad(x["loader"].split()[-1] if x["field"] == "leg" else x["loader"].split()[0])] if b]
        else:
            why = []
        if why:
            x["cause"] = "loader copies an event that failed a check: " + "; ".join(why)


def compare(course: str, version: str, only: set[str] | None = None) -> dict:
    theirs = loader_positions(course, version, only)
    ours = build(course, version, only)
    d = diff_positions(theirs, ours)
    _causes(course, version, theirs, d)
    return {"course": course, "version": version, "loader_positions": len(theirs), "audit_positions": len(ours),
            "differences": len(d), "by_field": dict(Counter(x["field"] for x in d)),
            "positions_differing": len({x["first_event"] for x in d}),
            "from_failed_events": sum("cause" in x for x in d), "details": d}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", action="append")
    a = ap.parse_args(argv)
    sets = [("lpp", "v1", None), ("lpp", "v2", lpp_proof_set()), ("cryptowizard", "v1", None),
            ("ziptrader", "v1", None)]
    for course, version, only in sets:
        if a.course and course not in a.course:
            continue
        r = compare(course, version, only)
        print(f"{course}/{version}: loader {r['loader_positions']} positions, audit {r['audit_positions']}, "
              f"{r['positions_differing']} differ ({r['differences']} fields) {r['by_field']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
