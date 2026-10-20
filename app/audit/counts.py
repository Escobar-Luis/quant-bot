"""Per-course counts from local data/ and committed results/: what was collected, digested and priced.

  cd app && uv run python -m audit.counts            # text table
  cd app && uv run python -m audit.counts --json     # same numbers as JSON

Reads only: data/<course>/ (gitignored, in the main checkout) and results/<course>/<version>.json.
Prints counts, never course text.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from backtest.common import DATA, DEFAULT_DELAY_MIN, RESULTS

# (course, extraction version) -> its events file; the results file of the same version prices it.
EVENTS = {("lpp", "v1"): DATA / "lpp" / "events.jsonl",
          ("lpp", "v2"): DATA / "lpp" / "v2" / "events.jsonl",
          ("ziptrader", "v1"): DATA / "ziptrader" / "events.jsonl",
          ("cryptowizard", "v1"): DATA / "cryptowizard" / "events.jsonl"}


def rows(p: Path) -> list[dict]:
    return [json.loads(line) for line in open(p) if line.strip()] if p.exists() else []


def lpp_sources() -> dict:
    from lpp.fetch_captions import status, video_ids
    yt = DATA / "lpp" / "youtube"
    dirs = {d.name for d in yt.iterdir() if d.is_dir()} if yt.exists() else set()
    urls = DATA / "lpp" / "discord" / "urls_12mo.txt"
    ids = video_ids(urls) if urls.exists() else []
    st = Counter(status(v) for v in ids)
    return {"links (urls_12mo.txt)": len(ids), "captions on disk": st["ok"], "no captions": st["no_captions"],
            "not fetched": st["missing"], "other folders (2018 seed)": len(dirs - set(ids)),
            "sources.jsonl": len(rows(DATA / "lpp" / "sources.jsonl"))}


def discord_sources(course: str) -> dict:
    src = rows(DATA / course / "sources.jsonl")
    out = {"sources.jsonl": len(src)}
    by = Counter(s.get("channel") for s in src)
    out.update({f"#{k}": v for k, v in sorted(by.items())})
    if course == "cryptowizard":
        out["skipped posts"] = len(rows(DATA / course / "skipped.jsonl"))
    return out


def events(p: Path) -> dict:
    evs = rows(p)
    st = Counter(e.get("status") for e in evs)
    ts = sorted(e["wall_utc"] for e in evs if e.get("wall_utc"))
    return {"file": str(p.relative_to(DATA.parent)) if p.exists() else f"{p} (missing)",
            "events": len(evs), "by_type": dict(sorted(Counter(e.get("type") for e in evs).items())),
            "passed": st.get("ok", 0), "in_review": st.get("needs_review", 0),
            "other_status": sum(v for k, v in st.items() if k not in ("ok", "needs_review")),
            "first": ts[0][:10] if ts else None, "last": ts[-1][:10] if ts else None}


def priced(course: str, version: str) -> dict | None:
    p = RESULTS / course / f"{version}.json"
    if not p.exists():
        return None
    r = json.loads(p.read_text())
    port = {x["id"]: x for x in r["portfolios"]}
    head = port[r.get("headline_portfolio", "all")]["by_delay"]
    d = str(r.get("default_delay_min", DEFAULT_DELAY_MIN))
    per_delay = {k: v["trades"] for k, v in head.items()}
    return {"file": str(p.relative_to(RESULTS.parent)), "window": r["window"],
            "trades_at_default": head[d]["trades"], "default_delay_min": int(d), "trades_by_delay": per_delay,
            "by_portfolio": {k: v["by_delay"][d]["trades"] for k, v in port.items() if d in v.get("by_delay", {})},
            "sample_trades_in_file": len(r.get("trades") or [])}


def collect() -> dict:
    out = {}
    for course in ("lpp", "ziptrader", "cryptowizard"):
        out[course] = {"sources": lpp_sources() if course == "lpp" else discord_sources(course),
                       "versions": {v: {"events": events(p), "results": priced(course, v)}
                                    for (c, v), p in EVENTS.items() if c == course}}
    return out


def show(c: dict) -> None:
    for course, x in c.items():
        print(f"== {course}")
        print("  sources: " + ", ".join(f"{k} {v}" for k, v in x["sources"].items()))
        for v, y in x["versions"].items():
            e, r = y["events"], y["results"]
            print(f"  {v} events {e['events']} ({', '.join(f'{k} {n}' for k, n in e['by_type'].items())}); "
                  f"passed every check {e['passed']}, in review {e['in_review']}; posted {e['first']} to {e['last']}")
            if r is None:
                print(f"  {v} priced: no results/{course}/{v}.json")
                continue
            w = r["window"]
            print(f"  {v} priced ({r['file']}): {r['trades_at_default']} trades at {r['default_delay_min']} min "
                  f"[{', '.join(f'{k}m {n}' for k, n in r['trades_by_delay'].items())}]; "
                  f"by portfolio {r['by_portfolio']}; {r['sample_trades_in_file']} trade rows in file")
            print(f"  {v} window {w['start']} to {w['end']}, sealed from {w['sealed_from']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Per-course collection, extraction and pricing counts.")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    c = collect()
    print(json.dumps(c, indent=1)) if a.json else show(c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
