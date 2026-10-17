"""One snapshot folder, loaded once and read-only: results/<course>/<version>.json files (contract results/1).

architecture.md (backend):
- AD-1: the snapshot id is the first 12 hex of sha256 over the sorted "path:sha256" lines of the files it serves.
- AD-3: a course's headline file is its highest version not marked `same_sessions.proof_set`, else its highest
  version (the rule web/src/data.js `latest()` uses).
Files that break the contract are skipped and listed in `skipped`, never half-served.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "results/1"
COURSE_ORDER = ("lpp", "ziptrader", "cryptowizard")   # the web app's tab order; other courses sort after
VERSION = re.compile(r"^v(\d+)$")


@dataclass
class ResultsFile:
    course: str
    version: str
    path: str                 # relative to the snapshot folder, e.g. results/lpp/v1.json
    raw: bytes                # served as is by the results endpoint
    doc: dict

    @property
    def proof_set(self) -> bool:
        return bool((self.doc.get("same_sessions") or {}).get("proof_set"))

    def headline_portfolio(self) -> dict:
        pid = self.doc.get("headline_portfolio", "all")
        return next(p for p in self.doc["portfolios"] if p["id"] == pid)


@dataclass
class Snapshot:
    root: Path
    snapshot_id: str
    files: dict[str, dict[str, ResultsFile]]                 # course -> version -> file
    skipped: list[dict] = field(default_factory=list)       # {"path", "why"}

    def courses(self) -> list[str]:
        rank = {c: i for i, c in enumerate(COURSE_ORDER)}
        return sorted(self.files, key=lambda c: (rank.get(c, len(rank)), c))

    def versions(self, course: str) -> list[str]:
        return sorted(self.files[course], key=version_number)

    def headline(self, course: str) -> ResultsFile:
        """AD-3: highest version that isn't the proof set, else the highest version."""
        newest_first = [self.files[course][v] for v in reversed(self.versions(course))]
        return next((f for f in newest_first if not f.proof_set), newest_first[0])


def version_number(version: str) -> int:
    return int(VERSION.match(version).group(1))


def problem(doc: dict, course: str, version: str) -> str | None:
    """Why a parsed file can't be served, or None. Checks only what the API relies on."""
    if doc.get("schema") != SCHEMA:
        return f"schema is {doc.get('schema')!r}, not {SCHEMA!r}"
    if doc.get("course") != course or doc.get("version") != version:
        return f"file says {doc.get('course')}/{doc.get('version')}, path says {course}/{version}"
    delays = doc.get("delays_min")
    if not isinstance(delays, list) or not delays or doc.get("default_delay_min") not in delays:
        return "delays_min missing, or default_delay_min not in it"
    pid = doc.get("headline_portfolio", "all")
    port = next((p for p in doc.get("portfolios") or [] if p.get("id") == pid), None)
    if not port or not port.get("testable"):
        return f"headline portfolio {pid!r} missing or not testable"
    missing = [d for d in delays if str(d) not in (port.get("by_delay") or {})]
    if missing:
        return f"headline portfolio has no numbers for delays {missing}"
    return None


def snapshot_id(digests: dict[str, str]) -> str:
    lines = "\n".join(f"{path}:{digests[path]}" for path in sorted(digests))
    return hashlib.sha256(lines.encode()).hexdigest()[:12]


def load(root: Path) -> Snapshot:
    """Read every results/<course>/<version>.json under `root`. results/_sample.json is never served."""
    root = Path(root)
    files: dict[str, dict[str, ResultsFile]] = {}
    digests: dict[str, str] = {}
    skipped: list[dict] = []
    for p in sorted((root / "results").glob("*/*.json")):
        course, version, rel = p.parent.name, p.stem, p.relative_to(root).as_posix()
        if not VERSION.match(version):
            skipped.append({"path": rel, "why": "file name is not v<n>.json"})
            continue
        raw = p.read_bytes()
        try:
            doc = json.loads(raw)
        except ValueError as e:
            skipped.append({"path": rel, "why": f"not JSON: {e}"})
            continue
        why = problem(doc, course, version) if isinstance(doc, dict) else "not a JSON object"
        if why:
            skipped.append({"path": rel, "why": why})
            continue
        files.setdefault(course, {})[version] = ResultsFile(course, version, rel, raw, doc)
        digests[rel] = hashlib.sha256(raw).hexdigest()
    return Snapshot(root, snapshot_id(digests), files, skipped)
