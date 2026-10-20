"""Fetch missing LPP morning-session captions with yt-dlp (step 2 of LPP collection).

Step 1 (manual, read-only, in Luis's Chrome): read the YouTube links LPP posts in its Discord
search pages into data/lpp/discord/urls_12mo.txt, one URL per line (notes/strategy-pipeline.md §1).
This command does step 2: for every link in that file whose captions are not on disk yet, ask
yt-dlp for the English auto-captions (json3, word timings) and the video's info.json, never the
video itself, into data/lpp/youtube/<video_id>/. Re-runnable: sessions already on disk are skipped.

  cd app
  uv run python -m lpp.fetch_captions --dry-run        # list what it would fetch, fetch nothing
  uv run python -m lpp.fetch_captions                  # fetch the missing ones (needs yt-dlp on PATH)
  uv run python -m lpp.fetch_captions --urls ../../quant-bot/data/lpp/discord/seed_urls.txt --limit 5

Then `uv run python -m lpp.run` extracts and checks the new sessions. Captions are course content:
they stay in the gitignored data/ folder, never in git.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .common import DATA, YT
from .transcript import load_ok

URLS = DATA / "discord" / "urls_12mo.txt"
_ID = re.compile(r"(?:v=|youtu\.be/|/live/|/shorts/)([A-Za-z0-9_-]{11})")


def video_ids(path: Path) -> list[str]:
    """Video ids in file order, de-duplicated; blank lines and '#' comments skipped."""
    out, seen = [], set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _ID.search(line)
        vid = m.group(1) if m else (line if re.fullmatch(r"[A-Za-z0-9_-]{11}", line) else None)
        if vid is None:
            print(f"skip (no video id): {line}", file=sys.stderr)
        elif vid not in seen:
            seen.add(vid)
            out.append(vid)
    return out


def status(vid: str) -> str:
    """'ok' (captions + info on disk), 'no_captions' (info only: yt-dlp found no English captions), or 'missing'."""
    d = YT / vid
    if d.is_dir() and load_ok(d):
        return "ok"
    if (d / f"{vid}.info.json").exists():
        return "no_captions"
    return "missing"


def ytdlp_cmd(vid: str, exe: str = "yt-dlp") -> list[str]:
    """Captions and metadata only; throttled like the original 4-worker run (0.5 s per request, 1 s per subtitle)."""
    return [exe, "--skip-download", "--write-auto-subs", "--write-subs",
            "--sub-langs", "en-orig,en", "--sub-format", "json3", "--write-info-json",
            "--no-overwrites", "--sleep-requests", "0.5", "--sleep-subtitles", "1",
            "-P", str(YT), "-o", "%(id)s/%(id)s.%(ext)s",
            f"https://www.youtube.com/watch?v={vid}"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--urls", type=Path, default=URLS, help=f"link list (default {URLS})")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched; fetch nothing")
    ap.add_argument("--retry-no-captions", action="store_true",
                    help="also retry sessions where yt-dlp earlier found no English captions")
    ap.add_argument("--limit", type=int, default=0, help="fetch at most N sessions (0 = all)")
    a = ap.parse_args(argv)

    if not a.urls.exists():
        print(f"no link list at {a.urls}; collect the Discord links first (see module docstring)", file=sys.stderr)
        return 2
    ids = video_ids(a.urls)
    st = {vid: status(vid) for vid in ids}
    todo = [v for v in ids if st[v] == "missing" or (a.retry_no_captions and st[v] == "no_captions")]
    if a.limit:
        todo = todo[:a.limit]
    counts = {k: sum(1 for s in st.values() if s == k) for k in ("ok", "no_captions", "missing")}
    print(f"{a.urls.name}: {len(ids)} links; on disk {counts['ok']}, no captions {counts['no_captions']}, "
          f"missing {counts['missing']}; to fetch {len(todo)}")

    if a.dry_run:
        for vid in todo:
            print("would fetch", vid, "->", YT / vid)
        return 0
    if not todo:
        return 0
    exe = shutil.which("yt-dlp")
    if exe is None:
        print("yt-dlp not found on PATH (brew install yt-dlp, or uv tool install yt-dlp)", file=sys.stderr)
        return 2
    YT.mkdir(parents=True, exist_ok=True)
    failed = []
    for i, vid in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {vid}", flush=True)
        if subprocess.run(ytdlp_cmd(vid, exe)).returncode != 0:
            failed.append(vid)
    got = [v for v in todo if status(v) == "ok"]
    print(f"fetched {len(got)} of {len(todo)}; yt-dlp errors {len(failed)}; "
          f"no captions {sum(1 for v in todo if status(v) == 'no_captions')}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
