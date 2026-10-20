"""Pulls the newest posts from the Wix blog's RSS feed into blog.json (read by the "From the Blog" section).

Run by .github/workflows/update-blog.yml every few hours; safe to run by hand:  python scripts/update_blog.py
Standard library only. Keeps the existing blog.json if the feed can't be reached.
"""
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

FEED = os.environ.get("BLOG_FEED", "https://jolie738.wixsite.com/allheartsaflame/blog-feed.xml")
BLOG = os.environ.get("BLOG_URL", "https://jolie738.wixsite.com/allheartsaflame")
OUT = Path(__file__).resolve().parent.parent / "blog.json"
LIMIT = 6
UA = {"User-Agent": "Mozilla/5.0 (compatible; allheartsaflame-blog-sync/1.0)"}


def get(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def og_image(page_url: str) -> str:
    try:
        page = get(page_url)
    except Exception:
        return ""
    m = (re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page, re.I)
         or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', page, re.I))
    return html.unescape(m.group(1)) if m else ""


def main() -> int:
    old = {}
    if OUT.exists():
        try:
            old = {p["url"]: p for p in json.loads(OUT.read_text(encoding="utf-8")).get("posts", [])}
        except Exception:
            old = {}
    try:
        root = ET.fromstring(get(FEED))
    except Exception as exc:  # feed down or malformed: leave the current file alone
        print(f"feed not read ({exc}); keeping existing blog.json")
        return 0
    posts = []
    for item in root.iter("item"):
        url = (item.findtext("link") or "").strip()
        if not url:
            continue
        try:
            date = parsedate_to_datetime(item.findtext("pubDate")).astimezone(timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            date = ""
        excerpt = clean(item.findtext("description"))
        if len(excerpt) > 220:
            excerpt = excerpt[:217].rsplit(" ", 1)[0] + "..."
        posts.append({
            "title": clean(item.findtext("title")),
            "url": url,
            "date": date,
            "excerpt": excerpt,
            "image": (old.get(url) or {}).get("image") or og_image(url),
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    posts = posts[:LIMIT]
    prev = json.loads(OUT.read_text(encoding="utf-8")).get("posts") if OUT.exists() else None
    if prev == posts:
        print(f"{len(posts)} posts, no change")
        return 0
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "blog_url": BLOG, "posts": posts}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(posts)} posts to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
