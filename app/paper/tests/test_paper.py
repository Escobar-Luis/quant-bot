"""Forward paper test (spec-audit story 30, CAP-18): the rule mechanics on synthetic bars, the ledger is append-only
and idempotent, the frozen rules can't be edited, and the audit's independent recompute agrees (and catches a
tampered number)."""
import json

import pytest

from audit import paper as audit_paper
from paper import run

D0, D1, D2 = "2026-10-20", "2026-10-21", "2026-10-22"


def minute_rows(day, rows):
    """rows: [(hh:mm, o, h, l, c)] -> {unix_s: [o, h, l, c, v]}"""
    return {run.et_at(day, hm): [o, h, lo, c, 1000] for hm, o, h, lo, c in rows}


@pytest.fixture
def world(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(run, "PDATA", data / "paper")
    monkeypatch.setattr(run, "BARS", data / "bars")
    monkeypatch.setattr(audit_paper, "DATA", data)
    monkeypatch.setattr(audit_paper, "BARS", data / "bars")
    hist = [[f"2026-09-{d:02d}", 10, 10, 10, 10, 1e6] for d in range(1, 25)]   # 20+ sessions: adv $10M (thin)

    def daily(day, prev_close, open_, close, etb):
        prev = [r for r in hist] + ([[D1, 10, 10, 10, prev_close, 1e6]] if day == D2 else [])
        rows = prev[:-1] + [[prev[-1][0], 10, 10, 10, prev_close, 1e6], [day, open_, open_, close, close, 1e6]]
        spy = [[r[0], 500, 500, 500, 500 + i, 1] for i, r in enumerate(rows)]
        rec = {"day": day, "fetched_at": "x", "split": {"SOGP": rows}, "raw": {"SOGP": rows},
               "spy_all": spy, "easy_to_borrow": {"SOGP": etb}}
        p = run.day_cache(day)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec))

    def minutes(day, rows):
        p = run.minute_path("SOGP", day)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(minute_rows(day, rows)))

    # D1: +8% gap, short at 09:45 at 10.8, covered at 15:55 at 10.0 (a win). D2: +6% gap, stopped at 5% above.
    daily(D1, 10.0, 10.8, 10.0, False)
    minutes(D1, [("09:30", 10.8, 10.9, 10.7, 10.8), ("09:45", 10.8, 10.85, 10.7, 10.75),
                 ("15:55", 10.0, 10.0, 10.0, 10.0)])
    daily(D2, 10.0, 10.6, 11.5, None)
    minutes(D2, [("09:45", 10.0, 10.2, 9.9, 10.1), ("10:00", 10.4, 10.6, 10.3, 10.5), ("15:55", 11, 11, 11, 11)])
    cal = [D0, D1, D2]
    monkeypatch.setattr(run, "sessions_since", lambda start, now: cal)
    monkeypatch.setattr(run, "completed", lambda d, now: d in cal)
    monkeypatch.setattr(run, "easy_to_borrow", lambda t: pytest.fail("no network in tests"))
    monkeypatch.setattr(run, "minutes", lambda t, d: {int(k): v for k, v in
                                                       json.loads(run.minute_path(t, d).read_text()).items()})
    monkeypatch.setattr(run, "_keys", lambda: {"APCA-API-KEY-ID": "x", "APCA-API-SECRET-KEY": "y"})
    return tmp_path / "out", cal


def test_rule_mechanics():
    rule = {"entry_et": "09:45", "stop_pct": 5, "exit_et": "15:55"}
    b = minute_rows(D1, [("09:45", 10, 10.1, 9.9, 10), ("12:00", 9.5, 9.6, 9.4, 9.5), ("15:55", 9, 9, 9, 9)])
    assert run.short_trade(b, D1, rule) == {"entry_ts": run.et_at(D1, "09:45"), "entry": 10,
                                            "exit_ts": run.et_at(D1, "15:55"), "exit": 9, "kind": "time"}
    b = minute_rows(D1, [("09:45", 10, 10.2, 9.9, 10), ("10:00", 11, 11.2, 10.9, 11), ("15:55", 9, 9, 9, 9)])
    assert run.short_trade(b, D1, rule)["exit"] == 11          # gapped through the stop: the bar's open
    assert run.short_trade(minute_rows(D1, [("09:30", 1, 1, 1, 1)]), D1, rule) is None
    assert run.gap([["a", 0, 0, 0, 12.30, 0], ["b", 12.915, 0, 0, 0, 0]], "b") == 0.05   # exactly +5% triggers


def test_costs():
    assert run.bps("base", 9.99, 1e9) == 20 and run.bps("base", 10, 0) == 5
    assert run.bps("realistic", 4.99, 1e9) == 50 and run.bps("realistic", 9, 1e9) == 30
    assert run.bps("realistic", 20, 1e6) == 15 and run.bps("x2", 20, 1e6) == 30
    assert run.borrow_fee("realistic", True) == 0.004 and run.borrow_fee("realistic", None) == 0.004
    assert run.borrow_fee("realistic", False) == 0 and run.borrow_fee("base", True) == 0
    assert run.borrow_fee("x2", True) == 0.008


def test_counts_only_after_the_freeze():
    assert not run.counts(D0)      # frozen 2026-10-20 17:38 ET, after that session
    assert run.counts(D1)


def test_ledger_is_append_only_and_idempotent(world):
    out, _ = world
    assert run.main(["--out-dir", str(out)]) == 0
    lines = (out / "ledger.jsonl").read_text().splitlines()
    assert [json.loads(x)["day"] for x in lines] == [D1, D2]          # D0 is before the freeze
    s1 = (out / "summary.json").read_text()
    assert run.main(["--out-dir", str(out)]) == 0
    assert (out / "ledger.jsonl").read_text().splitlines() == lines   # nothing re-simulated
    assert (out / "summary.json").read_text() == s1                   # nothing rewritten
    s = json.loads(s1)
    s4 = next(r for r in s["rules"] if r["id"] == "S4")
    assert (s["days"], s["first_session"], s["last_session"], s["status"]) == (2, D1, D2, "running")
    assert (s4["trades"], s4["stops"], s4["word"], s4["vs_random"]) == (2, 1, "Not enough trades", None)
    assert s4["hard_to_borrow_trades"] == 1 and s4["unknown_borrow_trades"] == 1
    d1 = json.loads(lines[0])["rules_out"]["S4"]["trades"][0]
    q = 1000 / 10.8   # thin stock: 5 + 10 bps per side; not easy to borrow: one day of fee, 0.4% of $1,000
    assert d1["pnl"]["realistic"] == pytest.approx(q * 0.8 - q * 10.8 * 15e-4 - q * 10.0 * 15e-4 - 4, abs=1e-6)


def test_refuses_edited_rules(world, monkeypatch):
    out, _ = world
    monkeypatch.setitem(run.FREEZE, "rules_sha256", "0" * 64)
    with pytest.raises(SystemExit):
        run.main(["--out-dir", str(out)])


def test_audit_agrees_and_catches_tampering(world):
    out, _ = world
    run.main(["--out-dir", str(out)])
    rep = audit_paper.check(out)
    assert rep["pass"], rep["details"]
    assert (rep["sessions_checked"], rep["trades_checked"]) == (2, 2)
    lines = (out / "ledger.jsonl").read_text().splitlines()
    ln = json.loads(lines[1])
    ln["rules_out"]["S4"]["trades"][0]["pnl"]["realistic"] += 5
    (out / "ledger.jsonl").write_text(lines[0] + "\n" + json.dumps(ln) + "\n")
    rep = audit_paper.check(out)
    assert not rep["pass"] and any(m["field"] == "pnl realistic" for m in rep["details"])


def test_audit_catches_a_missing_session(world):
    out, _ = world
    run.main(["--out-dir", str(out)])
    lines = (out / "ledger.jsonl").read_text().splitlines()
    (out / "ledger.jsonl").write_text(lines[1] + "\n")
    rep = audit_paper.check(out)
    assert not rep["pass"]


def test_frozen_rules_match_the_strategy_lab():
    rules = json.loads(run.RULES_FILE.read_text())
    lab = json.loads((run.REPO / "results" / "strategy-lab.json").read_text())
    lists = {u["id"]: u["tickers"] for u in lab["universes"]}
    for r in rules["rules"]:
        for k, v in r["lists"].items():
            assert v == lists[k]
    assert run.load_rules()["version"] == "v1"
