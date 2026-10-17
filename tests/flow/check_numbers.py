#!/usr/bin/env python3
"""Full-flow number check (story/5-full-flow-test).

Loads every results/<course>/<version>.json and proofs/prism.json from a git ref (default origin/main),
checks each file against the contract, builds the strings the app should show, then checks:
  1. the public build carries main's numbers (data is bundled at build time, so a stale deploy shows here);
  2. every PRISM link in proofs/prism.json opens a real run in project "bot" with the agent_id it claims.

    python3 tests/flow/check_numbers.py                 # main + live URL + PRISM
    python3 tests/flow/check_numbers.py --no-live --no-prism
    python3 tests/flow/check_numbers.py --expect tests/flow/expected.json   # also write the screen table

PRISM lookups need the prismtrace SDK (run with app/.venv/bin/python or `uv run --project app`); without it
they are skipped with a WARN. Never prints key values. Exit 1 on any FAIL.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DELAYS = [1, 3, 5, 10, 15, 30, 60]
WORDS = {"Yes", "Barely", "No", "Not enough trades"}
COURSES = ["lpp", "ziptrader", "cryptowizard"]
URL = "https://day-trader-ai.vercel.app"
PROOFS_FALLBACK = "origin/story/2-prism-proofs"

out = {"PASS": 0, "WARN": 0, "FAIL": 0}


def say(level: str, msg: str) -> None:
    out[level] += 1
    print(f"{level:4}  {msg}")


# ---------- the app's own formatters (web/src/main.js) ----------
def money(v: float) -> str:
    return "$" + f"{round_half_up(v):,}"


def round_half_up(v: float) -> int:
    # JS Math.round: halves go up, also for negatives.
    import math
    return int(math.floor(v + 0.5))


def pct(v: float) -> str:
    r = round_half_up(v * 10) / 10
    a = abs(r)
    sign = "+" if r > 0 else "−" if r < 0 else ""
    return sign + (str(int(a)) if a == int(a) else f"{a:.1f}") + "%"


def word_for(ret: float, hold_ret: float, trades: int | None) -> str:
    if trades is not None and trades < 30:
        return "Not enough trades"
    d = ret - hold_ret
    return "Yes" if d >= 2 else "No" if d <= -2 else "Barely"


# ---------- loading from git ----------
def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def load_ref(ref: str, path: str):
    try:
        return json.loads(git("show", f"{ref}:{path}"))
    except subprocess.CalledProcessError:
        return None


def results_files(ref: str) -> dict:
    names = [n for n in git("ls-tree", "-r", "--name-only", ref, "results").split()
             if re.fullmatch(r"results/[a-z]+/v\d+\.json", n)]
    return {n: load_ref(ref, n) for n in names}


# ---------- contract checks ----------
def close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def check_metrics(where: str, m: dict, start: float, need_trades: bool = True) -> None:
    for k in ("end", "ret_pct", "hold_end", "hold_ret_pct", "word") + (("trades",) if need_trades else ()):
        if m.get(k) is None:
            say("FAIL", f"{where}: missing {k}")
            return
    if not close(m["ret_pct"], (m["end"] / start - 1) * 100, 0.06):
        say("FAIL", f"{where}: ret_pct {m['ret_pct']} ≠ end {m['end']} / {start}")
    if not close(m["hold_ret_pct"], (m["hold_end"] / start - 1) * 100, 0.06):
        say("FAIL", f"{where}: hold_ret_pct {m['hold_ret_pct']} ≠ hold_end {m['hold_end']} / {start}")
    if m["word"] not in WORDS:
        say("FAIL", f"{where}: word {m['word']!r} not one of {sorted(WORDS)}")
    elif m["word"] != word_for(m["ret_pct"], m["hold_ret_pct"], m.get("trades")):
        say("FAIL", f"{where}: word {m['word']!r}, rule says "
                    f"{word_for(m['ret_pct'], m['hold_ret_pct'], m.get('trades'))!r}")


def short(where: str, text: str | None, n: int) -> None:
    if text and len(text.split()) > n:
        say("FAIL", f"{where}: {len(text.split())} words (max {n}): {' '.join(text.split()[:6])} …")


def check_file(path: str, r: dict) -> None:
    course, version = re.match(r"results/([a-z]+)/(v\d+)\.json", path).groups()
    bad = out["FAIL"]
    if r.get("schema") != "results/1":
        say("FAIL", f"{path}: schema {r.get('schema')!r}")
    if r.get("course") != course or r.get("version") != version:
        say("FAIL", f"{path}: course/version inside ({r.get('course')}/{r.get('version')}) ≠ path")
    if r.get("delays_min") != DELAYS or r.get("default_delay_min") != 5:
        say("FAIL", f"{path}: delays_min {r.get('delays_min')} / default {r.get('default_delay_min')}")
    start = r.get("money_start") or 10000
    ports = {p["id"]: p for p in r.get("portfolios", [])}
    head = ports.get(r.get("headline_portfolio"))
    if not head or not head.get("testable"):
        say("FAIL", f"{path}: headline portfolio {r.get('headline_portfolio')!r} missing or untestable")
    for p in ports.values():
        if not p.get("testable"):
            if not p.get("count") and p.get("count") != 0:
                say("WARN", f"{path}: untestable {p['id']} has no count")
            continue
        bd = p.get("by_delay") or {}
        miss = [d for d in DELAYS if str(d) not in bd]
        if miss:
            say("FAIL", f"{path}: {p['id']} missing delays {miss}")
        holds = {bd[k]["hold_end"] for k in bd if bd[k].get("hold_end") is not None}
        if len(holds) > 1:
            say("FAIL", f"{path}: {p['id']} hold_end differs by delay {sorted(holds)}")
        for k, m in bd.items():
            check_metrics(f"{path} {p['id']}@{k}m", m, start)
        s = p.get("series")
        if s:
            n = len(s.get("dates", []))
            if len(s.get("hold", [])) != n:
                say("FAIL", f"{path}: {p['id']} series.hold {len(s.get('hold', []))} ≠ dates {n}")
            for k, ys in (s.get("by_delay") or {}).items():
                if len(ys) != n:
                    say("FAIL", f"{path}: {p['id']} series@{k}m {len(ys)} points ≠ dates {n}")
                elif k in bd and not close(ys[-1], bd[k]["end"], 1.0):
                    say("WARN", f"{path}: {p['id']} curve@{k}m ends {ys[-1]} but end is {bd[k]['end']}")
    for rule in r.get("rules", []):
        short(f"{path} rule {rule.get('id')} quote", rule.get("quote"), 12)
        short(f"{path} rule {rule.get('id')} text", rule.get("text"), 15)
    for t in r.get("trades", []):
        short(f"{path} trade {t.get('trade_id')} quote", t.get("quote"), 12)
    check_v2(path, r, start)
    if out["FAIL"] == bad:
        say("PASS", f"{path}: contract ok ({len(ports)} portfolios, {len(r.get('trades', []))} sample trades)")


def check_v2(path: str, r: dict, start: float) -> None:
    head = next((p for p in r.get("portfolios", []) if p["id"] == r.get("headline_portfolio")), {})
    dates = (head.get("series") or {}).get("dates") or []
    for st in r.get("strategies") or []:
        w = f"{path} strategy {st.get('id')}"
        for k in ("id", "name", "entails", "by_delay"):
            if not st.get(k):
                say("FAIL", f"{w}: missing {k}")
        bd = st.get("by_delay") or {}
        if st.get("testable", True):
            miss = [d for d in DELAYS if str(d) not in bd]
            if miss:
                say("FAIL", f"{w}: missing delays {miss}")
        for k, m in bd.items():
            check_metrics(f"{w}@{k}m", m, start)
        for q in st.get("quotes") or []:
            short(f"{w} quote", q.get("text"), 12)
        for k, ys in ((st.get("series") or {}).get("by_delay") or {}).items():
            if dates and len(ys) != len(dates):
                say("FAIL", f"{w} series@{k}m {len(ys)} points ≠ shared dates {len(dates)}")
    rg = r.get("ranges")
    if rg is not None:
        for name in ("3m", "6m", "1y"):
            bd = (rg.get(name) or {}).get("by_delay")
            if not bd:
                say("WARN", f"{path} ranges.{name} missing (its chip hides)")
                continue
            miss = [d for d in DELAYS if str(d) not in bd]
            if miss:
                say("FAIL", f"{path} ranges.{name}: missing delays {miss}")
            for k, m in bd.items():
                if m.get("end") is None or m.get("hold_end") is None or m.get("word") not in WORDS:
                    say("FAIL", f"{path} ranges.{name}@{k}m: needs end, hold_end, word")
                    continue
                if m["word"] != "Not enough trades":
                    want = word_for((m["end"] / start - 1) * 100, (m["hold_end"] / start - 1) * 100,
                                    m.get("trades"))
                    if m["word"] != want:
                        say("FAIL", f"{path} ranges.{name}@{k}m: word {m['word']!r}, rule says {want!r}")
    bs = r.get("best_stop")
    if bs is not None:
        w0, w1 = r["window"]["start"], r["window"]["end"]
        curves = (head.get("series") or {}).get("by_delay") or {}
        for k, m in (bs.get("by_delay") or {}).items():
            if not (m.get("date") and m.get("end") is not None):
                say("FAIL", f"{path} best_stop@{k}m: needs date and end")
                continue
            if not (w0 <= m["date"] <= w1):
                say("FAIL", f"{path} best_stop@{k}m: {m['date']} outside window {w0}–{w1}")
            ys = curves.get(k)
            if ys and not close(max(ys), m["end"], 1.0):
                say("WARN", f"{path} best_stop@{k}m: end {m['end']} but curve peak is {max(ys)}")


# ---------- what the app should show ----------
def headline_version(files: dict, course: str) -> str | None:
    """The full-window file is the headline; a file with `same_sessions` is a v1-vs-v2 comparison on fewer sessions."""
    vs = sorted((int(p.split("/v")[1][:-5]), p) for p in files if p.startswith(f"results/{course}/"))
    full = [p for _, p in vs if not files[p].get("same_sessions") and not files[p].get("partial")]
    pick = (full or [p for _, p in vs])
    return pick[-1] if pick else None


def screen_table(files: dict) -> dict:
    table = {}
    for course in COURSES:
        path = headline_version(files, course)
        if not path:
            table[course] = {"tested": False}
            continue
        r = files[path]
        head = next(p for p in r["portfolios"] if p["id"] == r["headline_portfolio"])
        by = {}
        for k, m in head["by_delay"].items():
            by[k] = {
                "word": m["word"], "end": money(m["end"]), "hold_end": money(m["hold_end"]),
                "ret": pct(m["ret_pct"]), "hold_ret": pct(m["hold_ret_pct"]),
                "trades": f"{m['trades']:,} trade" + ("" if m["trades"] == 1 else "s"),
                "couldnt_copy": m.get("couldnt_copy") or 0, "sized_down": m.get("sized_down") or 0,
                "not_triggered": m.get("not_triggered") or 0,
            }
            for rg, v in ((r.get("ranges") or {}).items()):
                x = (v.get("by_delay") or {}).get(k)
                if x:
                    by[k].setdefault("ranges", {})[rg] = {"end": money(x["end"]), "hold_end": money(x["hold_end"]),
                                                          "word": x["word"]}
            b = ((r.get("best_stop") or {}).get("by_delay") or {}).get(k)
            if b:
                by[k]["best_stop"] = {"date": b["date"], "end": money(b["end"])}
            strat = [{"name": s["name"], "trades": f"{s['by_delay'][k]['trades']:,}", "word": s["by_delay"][k]["word"],
                      "ret": pct(s["by_delay"][k]["ret_pct"])}
                     for s in (r.get("strategies") or []) if k in (s.get("by_delay") or {})]
            if strat:
                by[k]["strategies"] = strat
        table[course] = {"tested": True, "file": path, "course_name": r.get("course_name"),
                         "hold": r["hold"]["symbol"], "untestable": {p["id"]: p.get("count") for p in r["portfolios"]
                                                                    if not p.get("testable")},
                         "by_delay": by}
    return table


# ---------- live build ----------
def fetch(url: str) -> tuple[bytes, float]:
    t = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "flow-test"}), timeout=20) as r:
        return r.read(), time.time() - t


def num_tokens(v: float) -> set[str]:
    """How a JSON number can look after Vite/esbuild minifies it."""
    s = json.dumps(v)
    toks = {s, s.rstrip("0").rstrip(".") if "." in s else s}
    if s.startswith("0."):
        toks.add(s[1:])
    if s.startswith("-0."):
        toks.add("-" + s[2:])
    return toks


def check_live(url: str, files: dict, proofs: dict | None) -> None:
    try:
        html, t_html = fetch(url + "/")
    except Exception as e:  # noqa: BLE001
        say("FAIL", f"live {url}: {type(e).__name__} {e}")
        return
    assets = re.findall(r'(?:src|href)="(/assets/[^"]+\.(?:js|css))"', html.decode())
    js, total, t_all = b"", len(html), t_html
    for a in assets:
        body, t = fetch(url + a)
        total += len(body)
        t_all += t
        if a.endswith(".js"):
            js += body
    level = "PASS" if t_all < 3 else "WARN"
    say(level, f"live load: html + {len(assets)} assets = {total / 1024:.0f} KB in {t_all:.2f} s")
    text = js.decode("utf-8", "replace")
    for path, r in sorted(files.items()):
        head = next((p for p in r["portfolios"] if p["id"] == r.get("headline_portfolio")), None)
        if not head:
            continue
        want = [m[k] for m in head["by_delay"].values() for k in ("end", "hold_end")]
        miss = [v for v in want if not any(re.search(rf"(?<![\d.]){re.escape(t)}(?!\d)", text) for t in num_tokens(v))]
        if miss:
            say("FAIL", f"live build stale for {path}: {len(miss)}/{len(want)} numbers missing "
                        f"(e.g. {miss[0]}); redeploy story 3")
        else:
            say("PASS", f"live build carries {path} ({len(want)} numbers)")
        for key in ("strategies", "ranges", "best_stop"):
            if r.get(key) is not None and not re.search(rf"\b{key}\b", text):
                say("FAIL", f"live build lacks {path} {key}; redeploy story 3")
    if proofs:
        ids = re.findall(r"/trajectories/([0-9a-f-]{36})", json.dumps(proofs))
        miss = [i for i in ids if i not in text]
        say("FAIL" if miss else "PASS",
            f"live build {'lacks' if miss else 'carries'} proofs/prism.json run links ({len(ids) - len(miss)}/{len(ids)})")


# ---------- PRISM links ----------
def env() -> dict:
    vals = {}
    for p in (REPO / ".env", Path.home() / "dev/quant-bot/.env"):
        if p.exists():
            for line in p.read_text().splitlines():
                m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
                if m and m.group(1) not in vals:
                    vals[m.group(1)] = m.group(2).strip().strip("'\"")
    return vals


def links(node, agent=None, where="proofs"):
    """(where, url, agent_id it claims) for every PRISM URL in proofs/prism.json."""
    if isinstance(node, dict):
        agent = node.get("agent_id", agent)
        for k, v in node.items():
            yield from links(v, agent, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from links(v, agent, f"{where}[{i}]")
    elif isinstance(node, str) and node.startswith("https://prism.blockconvey.com/") and where != "proofs.prism_app":
        yield where, node, agent


def check_proofs(proofs: dict, src: str, use_prism: bool) -> None:
    if proofs.get("schema") != "proofs/1":
        say("FAIL", f"proofs ({src}): schema {proofs.get('schema')!r}")
    kb, rc, ev = proofs.get("knowledge_base") or {}, proofs.get("root_cause") or {}, proofs.get("evaluator") or {}
    say("PASS" if kb.get("run_url") and kb.get("hits") else "WARN",
        f"proof Knowledge Base: {len(kb.get('hits') or [])} hits, run {'linked' if kb.get('run_url') else 'pending'}")
    say("PASS" if rc.get("failed_runs") and rc.get("our_sentence") and rc.get("url") else "WARN",
        f"proof Root Cause: {rc.get('failed_runs')} failed runs, cluster {rc.get('cluster')!r}, "
        f"sentence {'set' if rc.get('our_sentence') else 'pending'} (UI must show pending, not 'null')")
    v1, v2 = (ev.get("v1") or {}).get("pass_pct"), (ev.get("v2") or {}).get("pass_pct")
    mirror = ev.get("code_mirror") or {}
    say("PASS" if v1 is not None and v2 is not None else "WARN",
        f"proof Evaluator: PRISM v1 {v1} → v2 {v2}; our code {mirror.get('v1_pass_pct')} → {mirror.get('v2_pass_pct')} "
        f"(UI must not show 0% → 0% for null)")
    found = list(links(proofs))
    if not use_prism:
        say("WARN", f"PRISM lookups skipped ({len(found)} links)")
        return
    try:
        from prismtrace import PRISMtrace
    except ImportError:
        say("WARN", f"PRISM lookups skipped: no prismtrace SDK here ({len(found)} links); run with app/.venv/bin/python")
        return
    e = env()
    if not e.get("PRISMTRACE_API_KEY") or not e.get("PRISMTRACE_PROJECT_ID"):
        say("WARN", "PRISM lookups skipped: no PRISMTRACE_* keys in .env")
        return
    pt = PRISMtrace(api_key=e["PRISMTRACE_API_KEY"], project_id=e["PRISMTRACE_PROJECT_ID"],
                    host=e.get("PRISMTRACE_HOST", "https://api.prism.blockconvey.com"))
    project = (pt._get_sync(f"/api/projects/{pt.project_id}") or {}).get("name")
    say("PASS" if project == "bot" else "FAIL", f"PRISM project for our key: {project!r} (want 'bot')")
    for where, url, agent in found:
        m = re.search(r"/trajectories/([0-9a-f-]{36})", url)
        if not m:
            say("WARN", f"{where}: not a run link, opened by hand only: {url}")
            continue
        t = pt._get_sync(f"/api/trajectories/{m.group(1)}") or {}
        if not t.get("id"):
            say("FAIL", f"{where}: run {m.group(1)[:8]} not found in PRISM")
        elif t.get("project_id") != pt.project_id:
            say("FAIL", f"{where}: run {m.group(1)[:8]} is in another project")
        elif agent and t.get("agent_id") != agent:
            say("FAIL", f"{where}: run {m.group(1)[:8]} is {t.get('agent_id')}, file says {agent}")
        else:
            say("PASS", f"{where}: opens {t.get('agent_id')} run {m.group(1)[:8]} ({t.get('final_status')}, "
                        f"{t.get('step_count')} steps)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", default="origin/main", help="git ref to read results/ and proofs/ from")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--no-live", action="store_true")
    ap.add_argument("--no-prism", action="store_true")
    ap.add_argument("--expect", help="write the expected screen table (JSON) here")
    ap.add_argument("--dom-js", help="write the browser check (dom_check.js + the table) here")
    a = ap.parse_args()
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=REPO)
    print(f"ref {a.ref} @ {git('rev-parse', '--short', a.ref).strip()}")

    files = {p: r for p, r in results_files(a.ref).items() if r}
    if not files:
        say("FAIL", f"no results/<course>/<version>.json on {a.ref}")
    for path, r in sorted(files.items()):
        check_file(path, r)
    for course in COURSES:
        if not any(p.startswith(f"results/{course}/") for p in files):
            say("WARN", f"results/{course}: no file on {a.ref} (app shows 'Not tested yet' or the sample)")

    proofs, src = load_ref(a.ref, "proofs/prism.json"), a.ref
    if proofs is None:
        proofs, src = load_ref(PROOFS_FALLBACK, "proofs/prism.json"), PROOFS_FALLBACK
        say("WARN", f"proofs/prism.json not on {a.ref}; checking {PROOFS_FALLBACK} instead (story 2 PR unmerged)")
    if proofs:
        check_proofs(proofs, src, not a.no_prism)

    table = screen_table(files)
    print("\nWhat the app should show at 5 min late (headline):")
    for c, v in table.items():
        if not v.get("tested"):
            print(f"  {c:13} Not tested yet")
            continue
        s = v["by_delay"]["5"]
        print(f"  {c:13} {s['word']:18} $10k → {s['end']:>8} vs {s['hold_end']:>8} holding {v['hold']:4} "
              f"{s['trades']:>11}  ({v['file']})")
    if a.expect:
        Path(a.expect).write_text(json.dumps(table, indent=1, ensure_ascii=False))
        print(f"  screen table → {a.expect}")
    if a.dom_js:
        Path(a.dom_js).write_text(f"const EXPECTED = {json.dumps(table, ensure_ascii=False)};\n"
                                  + (HERE / "dom_check.js").read_text())
        print(f"  browser check → {a.dom_js} (paste into the signed-in page)")
    print()

    if not a.no_live:
        check_live(a.url.rstrip("/"), files, proofs)

    print(f"\n{out['PASS']} pass · {out['WARN']} warn · {out['FAIL']} fail")
    return 1 if out["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
