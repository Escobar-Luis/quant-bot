# /// script
# requires-python = ">=3.13"
# dependencies = ["openai>=1.0", "python-dotenv"]
# ///
"""Build data/ziptrader/sources.jsonl from the DOM listing read in Luis's Chrome.

Input: data/ziptrader/discord/dom_listing.tsv (channel, ids, Discord <time datetime>, author, attachment path).
posted_at is always the Discord message timestamp, never a date read off an image.
Run: uv run app/collect/ziptrader/sources.py
"""
import csv

from common import COURSE, DATA, DISCORD, IMG, SERVER_ID, write_jsonl

STAFF = {"Charlie Plattus", "ZipTrader Team"}


def main():
    rows = list(csv.DictReader((DISCORD / "dom_listing.tsv").open(), delimiter="\t"))
    out = []
    for r in rows:
        files = sorted(p.relative_to(DATA).as_posix() for p in IMG.glob(f"{r['message_id']}_*.png"))
        out.append({
            "source_id": f"dc:{r['channel_id']}/{r['message_id']}",
            "course": COURSE,
            "kind": "discord_image",
            "server_id": SERVER_ID,
            "channel": r["channel"],
            "channel_id": r["channel_id"],
            "message_id": r["message_id"],
            "url": f"https://discord.com/channels/{SERVER_ID}/{r['channel_id']}/{r['message_id']}",
            "posted_at": r["posted_at"],
            "author": r["author"],
            "author_role": "staff" if r["author"] in STAFF else "member",
            "image_files": files,
        })
    write_jsonl(DATA / "sources.jsonl", out)
    print(f"sources.jsonl: {len(out)} rows, {sum(bool(o['image_files']) for o in out)} with images")


if __name__ == "__main__":
    main()
