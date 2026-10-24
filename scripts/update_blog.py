"""Pulls the newest posts from the Wix blog's RSS feed into blog.json (read by the "From the Blog" section)
and writes a wrapper page for each post at /blog/<slug>/ (our header and footer, the Wix post framed inside,
and the post's own title, summary and picture for Facebook/X share previews).

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
SITE_DIR = Path(__file__).resolve().parent.parent
OUT = SITE_DIR / "blog.json"
TEMPLATE = SITE_DIR / "scripts" / "blogpost.html"
SITE_URL = os.environ.get("SITE_URL", "https://allheartsaflame.com")
DEFAULT_IMAGE = SITE_URL + "/assets/images/book-america-cover.webp"
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


def slug_of(url: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", url.rstrip("/").rsplit("/", 1)[-1].lower()).strip("-") or "post"


def write_pages(posts: list) -> None:
    if not TEMPLATE.exists():
        print("no scripts/blogpost.html template; skipping post pages")
        return
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for p in posts:
        page = p["page"]
        values = {
            "__TITLE__": html.escape(p["title"], quote=True),
            "__DESC__": html.escape(p["excerpt"] or p["title"], quote=True),
            "__URL__": SITE_URL + page,
            "__IMAGE__": html.escape(p["image"] or DEFAULT_IMAGE, quote=True),
            "__WIX__": html.escape(p["url"], quote=True),
        }
        out = tpl
        for k, v in values.items():
            out = out.replace(k, v)
        dest = SITE_DIR / page.strip("/") / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_text(encoding="utf-8") != out:
            dest.write_text(out, encoding="utf-8")


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
            "page": f"/blog/{slug_of(url)}/",
            "date": date,
            "excerpt": excerpt,
            "image": (old.get(url) or {}).get("image") or og_image(url),
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    posts = posts[:LIMIT]
    prev = json.loads(OUT.read_text(encoding="utf-8")).get("posts") if OUT.exists() else None
    write_pages(posts)
    if prev == posts:
        print(f"{len(posts)} posts, no change")
        return 0
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "blog_url": BLOG, "posts": posts}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(posts)} posts to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
