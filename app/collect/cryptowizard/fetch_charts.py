"""Download the TradingView snapshot attached to each trade-entry post (Luis approved, 2026-10-17).

Snapshots are public PNGs at s3.tradingview.com/snapshots/<first char>/<id>.png.
They go to DATA_DIR/cryptowizard/charts/<message_id>_<tv_id>.png (gitignored).

Run: python fetch_charts.py
"""
import re
import time
import urllib.request

from common import CW, load_raw

out = CW / "charts"
out.mkdir(parents=True, exist_ok=True)
posts = [p for p in load_raw() if p["channel"] == "wzrd-chat-crypto" and re.search(r"Entry\s*:", p["text"])]
done = skipped = failed = 0
for p in posts:
    ids = [re.sub(r".*/x/", "", l).strip("/") for l in p["links"] if "tradingview.com/x/" in l]
    for tv in dict.fromkeys(ids):
        dst = out / f"{p['message_id']}_{tv}.png"
        if dst.exists():
            skipped += 1
            continue
        url = f"https://s3.tradingview.com/snapshots/{tv[0].lower()}/{tv}.png"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if not data.startswith(b"\x89PNG"):
                raise ValueError("not a PNG")
            dst.write_bytes(data)
            done += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("failed", p["message_id"], tv, str(e)[:80])
        time.sleep(0.3)
print(f"entry posts {len(posts)}; downloaded {done}; already had {skipped}; failed {failed}")
