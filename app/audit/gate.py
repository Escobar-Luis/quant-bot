"""The CAP-3 gate (spec-audit): may the LinkedIn post and the video render go ahead?

  cd app && uv run python -m audit.gate                 # exit 0 only when the gate is open
  cd app && uv run python -m audit.gate --sign "Luis"   # Luis only: record his hand-check sign-off

Open only when all hold:
  1. the last default audit (proofs/audit.json) passed;
  2. `signoff` is present ({by, at, handcheck_sha256});
  3. data/audit/handcheck.md still hashes to the signed handcheck_sha256 (the sheet he checked is this one);
  4. results/ has no change since the audited sha: nothing committed after it, nothing uncommitted or untracked,
     and every results file still has the sha256 the audit recorded.
"""
import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from .paths import DATA, PROOFS, REPO, RESULTS

HANDCHECK = DATA / "audit" / "handcheck.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def results_changes(audited_sha: str | None, recorded: dict, results: Path = RESULTS) -> list[str]:
    """Every way results/ differs from what the audit saw (empty = unchanged)."""
    out = []
    rel = str(results.relative_to(REPO)) if results.is_relative_to(REPO) else str(results)
    if not audited_sha:
        return ["no audited results sha in proofs/audit.json"]
    d = git("diff", "--name-only", audited_sha, "--", rel)
    if d.returncode:
        out.append(f"git diff against {audited_sha[:12]} failed: {d.stderr.strip()[:120]}")
    out += [f"changed since {audited_sha[:12]}: {f}" for f in d.stdout.split() if f.endswith(".json")]
    out += [f"untracked: {f}" for f in git("ls-files", "--others", "--exclude-standard", "--", rel).stdout.split()]
    files = {f"{p.parent.name}/{p.stem}": p for p in results.glob("*/*.json")}
    files |= {p.stem: p for p in results.glob("*.json") if not p.stem.startswith("_")}   # strategy-lab.json
    for k, h in (recorded or {}).items():
        if k not in files:
            out.append(f"missing: results/{k}.json")
        elif sha256(files[k]) != h:
            out.append(f"sha256 differs from the audited file: results/{k}.json")
    out += [f"not audited: results/{k}.json" for k in sorted(set(files) - set(recorded or {}))
            if not k.startswith("_")]
    return out


def check(proofs: Path = PROOFS / "audit.json", handcheck: Path = HANDCHECK, results: Path = RESULTS) -> list[str]:
    """Every reason the gate is closed (empty = open)."""
    if not proofs.exists():
        return [f"no {proofs}: run cd app && uv run python -m audit.run"]
    rec = json.loads(proofs.read_text())
    why = []
    if rec.get("pass") is not True:
        why.append("the last audit did not pass (proofs/audit.json pass != true)")
    s = rec.get("signoff")
    if not s or not all(s.get(k) for k in ("by", "at", "handcheck_sha256")):
        why.append("no hand-check sign-off (signoff is null): Luis signs with python -m audit.gate --sign")
    elif not handcheck.exists():
        why.append(f"{handcheck} is missing")
    elif sha256(handcheck) != s["handcheck_sha256"]:
        why.append("handcheck.md changed after it was signed")
    why += results_changes(rec.get("results_git_sha"), rec.get("results_sha256") or {}, results)
    return why


def sign(by: str, proofs: Path = PROOFS / "audit.json", handcheck: Path = HANDCHECK) -> dict:
    rec = json.loads(proofs.read_text())
    rec["signoff"] = {"by": by, "at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "handcheck_sha256": sha256(handcheck)}
    proofs.write_text(json.dumps(rec, indent=1) + "\n")
    return rec["signoff"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sign", metavar="NAME", help="Luis only: sign off the current data/audit/handcheck.md")
    a = ap.parse_args(argv)
    if a.sign:
        if not HANDCHECK.exists():
            print(f"no {HANDCHECK}: run cd app && uv run python -m audit.handcheck first", file=sys.stderr)
            return 2
        print("signed:", sign(a.sign))
    why = check()
    if why:
        print("GATE CLOSED")
        for w in why:
            print(" -", w)
        return 1
    print("GATE OPEN: audit passed, hand-check signed, results/ unchanged since the audited sha")
    return 0


if __name__ == "__main__":
    sys.exit(main())
