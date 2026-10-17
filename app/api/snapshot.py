"""One snapshot folder, loaded once and read-only: results/<course>/<version>.json files (contract results/1).

architecture.md (backend):
- AD-1: the snapshot id is the first 12 hex of sha256 over the sorted "path:sha256" lines of every .json and .jsonl
  file (dotfiles excluded) under the snapshot's data folders (results/, events/, verdicts/), served or not, so any
  change to any data file changes it and stray files (.DS_Store, editor swaps) don't.
- AD-3: a course's headline file is its highest version not marked `same_sessions.proof_set`, else its highest
  version (the rule web/src/data.js `latest()` uses).
A file that breaks the contract is skipped and listed in `skipped`. A course with any skipped file is withheld whole:
the web app ranks any file name by its digits, so serving the rest could headline an older file than it would.
Nothing is half-served.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "results/1"
DATA_DIRS = ("results", "events", "verdicts")
DATA_SUFFIXES = (".json", ".jsonl")
COURSE_ORDER = ("lpp", "ziptrader", "cryptowizard")   # the web app's tab order; other courses sort after
VERSION = re.compile(r"^v([1-9]\d*)$")
ROW_KEYS = ("end", "ret_pct", "hold_end", "hold_ret_pct", "trades", "word")
# backtest.common.PRIVATE_URL's pattern, matched case-insensitively here (a test keeps the patterns equal). Not
# imported: backtest.common runs git and loads .env on import, which a server must not need. The backtest guard's
# second check, bare video IDs from data/lpp/session_keys.json, can't run on a server without data/; the pipeline's
# public_json() is the line of defence for those.
PRIVATE_URL = re.compile(r"yt:[A-Za-z0-9_-]{11}|youtube\.com|youtu\.be", re.IGNORECASE)


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


def is_delay(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _problem(doc: dict, course: str, version: str) -> str | None:
    if doc.get("schema") != SCHEMA:
        return f"schema is {doc.get('schema')!r}, not {SCHEMA!r}"
    if doc.get("course") != course or doc.get("version") != version:
        return f"file says {doc.get('course')}/{doc.get('version')}, path says {course}/{version}"
    delays = doc.get("delays_min")
    if not isinstance(delays, list) or not delays or not all(is_delay(d) for d in delays) \
            or not is_delay(doc.get("default_delay_min")) or doc["default_delay_min"] not in delays:
        return "delays_min must be whole minutes, with default_delay_min among them"
    if not isinstance(doc.get("same_sessions") or {}, dict):
        return "same_sessions is not an object"
    pid = doc.get("headline_portfolio", "all")
    port = next((p for p in doc["portfolios"] if p["id"] == pid), None)
    if not port or port.get("testable") is not True:
        return f"headline portfolio {pid!r} missing or not testable"
    for d in delays:
        row = port["by_delay"].get(str(d))
        if not isinstance(row, dict) or any(k not in row for k in ROW_KEYS):
            return f"headline portfolio at {d} min lacks {', '.join(ROW_KEYS)}"
    return None


def problem(raw: bytes, doc, course: str, version: str) -> str | None:
    """Why a parsed file can't be served, or None. Checks only what the API relies on, plus the privacy rule.
    The privacy scan reads the raw text and the parsed text, so JSON escapes (youtu\\u002ebe) can't hide a link."""
    text = raw.decode(json.detect_encoding(raw), "replace")
    if PRIVATE_URL.search(text) or PRIVATE_URL.search(json.dumps(doc, ensure_ascii=False)):
        return "holds a private video ID or YouTube link"
    if not isinstance(doc, dict):
        return "not a JSON object"
    try:
        return _problem(doc, course, version)
    except (AttributeError, KeyError, TypeError) as e:     # a field of the wrong type deep inside
        return f"malformed: {type(e).__name__} {e}"


def parse(raw: bytes):
    """json.loads, refusing NaN and Infinity (Python writes them, but they aren't JSON and can't be served)."""
    def refuse(name):
        raise ValueError(f"non-finite number {name}")
    return json.loads(raw, parse_constant=refuse)


def snapshot_id(digests: dict[str, str]) -> str:
    lines = "\n".join(f"{path}:{digests[path]}" for path in sorted(digests))
    return hashlib.sha256(lines.encode()).hexdigest()[:12]


def data_files(root: Path) -> list[Path]:
    return sorted(p for d in DATA_DIRS if (root / d).is_dir() for p in (root / d).rglob("*")
                  if p.is_file() and p.suffix in DATA_SUFFIXES and not p.name.startswith("."))


def load(root: Path) -> Snapshot:
    """Read every results/<course>/v<n>.json under `root`. results/_sample.json is never served.
    A missing results/ folder is an error (a mistyped SNAPSHOT_DIR must not look like an empty snapshot).
    Each file is read once: the bytes hashed into the id are the bytes served."""
    root = Path(root)
    if not (root / "results").is_dir():
        raise FileNotFoundError(f"no results/ folder in snapshot {root}")
    raws = {p.relative_to(root).as_posix(): p.read_bytes() for p in data_files(root)}
    files: dict[str, dict[str, ResultsFile]] = {}
    skipped: list[dict] = []
    withheld: set[str] = set()
    for rel in sorted(r for r in raws if re.fullmatch(r"results/[^/]+/[^/]+\.json", r)):
        _, course, name = rel.split("/")
        version, raw = name[: -len(".json")], raws[rel]
        why = None if VERSION.match(version) else "file name is not v<n>.json"
        if not why:
            try:
                doc = parse(raw)
            except ValueError as e:
                why = f"not JSON: {e}"
            else:
                why = problem(raw, doc, course, version)
        if why:
            skipped.append({"path": rel, "why": why})
            withheld.add(course)
            continue
        files.setdefault(course, {})[version] = ResultsFile(course, version, rel, raw, doc)
    for course in sorted(withheld & set(files)):
        for f in files.pop(course).values():
            skipped.append({"path": f.path, "why": "withheld: another file of this course was skipped"})
    return Snapshot(root, snapshot_id({rel: hashlib.sha256(raw).hexdigest() for rel, raw in raws.items()}),
                    files, skipped)
