"""Builds the blog from the Markdown posts in content/posts/ (written in the Tina editor at /admin/).

For every post it writes a full page at /blog/<slug>/ (site header and footer, the post, share buttons, and the post's own
title, summary and picture for Facebook/X previews), rebuilds the list at /blog/, and writes blog.json (the newest posts,
read by the "From the Blog" cards on the home page).

Run by .github/workflows/build-blog.yml whenever a post changes; safe to run by hand:  python scripts/build_blog.py
Needs:  pip install markdown pyyaml
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

import markdown
import yaml

SITE_DIR = Path(__file__).resolve().parent.parent
POSTS_DIR = SITE_DIR / "content" / "posts"
POST_TPL = SITE_DIR / "scripts" / "blogpost.html"
INDEX_TPL = SITE_DIR / "scripts" / "blogindex.html"
SITE_URL = os.environ.get("SITE_URL", "https://allheartsaflame.com")
DEFAULT_IMAGE = SITE_URL + "/assets/images/book-america-cover.webp"
FIGURE_RE = re.compile(r'<img alt="([^"]*)" src="([^"]*)" title="layout:(full|wide|left|right)" />')


def figures(html_text: str) -> str:
    """![caption](picture "layout:left") -> a captioned figure that is full width, centered, or floated left/right."""
    def one(m):
        cap, src, layout = m.group(1), m.group(2), m.group(3)
        return (f'<figure class="post-img {layout}"><img src="{src}" alt="{cap}" loading="lazy">'
                + (f"<figcaption>{cap}</figcaption>" if cap else "") + "</figure>")
    return FIGURE_RE.sub(one, html_text)


FONT_LINK_RE = re.compile(r'<a href="font:(cormorant|cinzel|playfair|lora|georgia|script)">(.*?)</a>', re.S)
FONT_NAMES = {"cormorant", "cinzel", "playfair", "lora", "georgia", "script"}


def fonts(html_text: str) -> str:
    """[some words](font:cinzel) -> the words in that font."""
    return FONT_LINK_RE.sub(lambda m: f'<span class="font-{m.group(1)}">{m.group(2)}</span>', html_text)


MARKER = "<!-- generated-by-build_blog -->"
HOME_CARDS = 6


def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def plain(md_text: str) -> str:
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md_text)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[#>*_`~-]+", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def site_path(p: str) -> str:
    """'assets/images/x.jpg' or '/assets/images/x.jpg' -> '/assets/images/x.jpg'; full web addresses are left alone."""
    p = (p or "").strip()
    if not p or p.startswith(("http://", "https://")):
        return p
    return "/" + p.lstrip("/")


def read_post(path: Path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.S)
    meta, body = ({}, raw) if not m else (yaml.safe_load(m.group(1)) or {}, m.group(2))
    d = meta.get("date")
    if isinstance(d, (datetime.date, datetime.datetime)):
        date = d.strftime("%Y-%m-%d")
    else:
        date = str(d or "")[:10]
    excerpt = (meta.get("excerpt") or "").strip() or (plain(body)[:200].rsplit(" ", 1)[0] + "..." if len(plain(body)) > 200 else plain(body))
    return {
        "slug": path.stem,
        "title": str(meta.get("title") or path.stem.replace("-", " ").title()).strip(),
        "date": date,
        "excerpt": excerpt,
        "image": site_path(meta.get("image")),
        "draft": bool(meta.get("draft")),
        "font": str(meta.get("font") or "").strip().lower() if str(meta.get("font") or "").strip().lower() in FONT_NAMES else "",
        "body": body,
    }


def nice_date(iso: str) -> str:
    try:
        d = datetime.datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.strftime('%B')} {d.day}, {d.year}"
    except ValueError:
        return ""


def card(p) -> str:
    url = SITE_URL + p["page"]
    u, t = urllib.parse.quote(url, safe=""), urllib.parse.quote(p["title"], safe="")
    pic = (f'<img src="{esc(p["image"])}" alt="" loading="lazy">' if p["image"]
           else '<span class="blog-ph"><svg><use href="#flame-gold"/></svg></span>')
    return (
        '<article class="blog-card">'
        f'<a class="blog-pic" href="{esc(p["page"])}" tabindex="-1" aria-hidden="true">{pic}</a>'
        '<div class="blog-body">'
        + (f'<p class="blog-date">{esc(nice_date(p["date"]))}</p>' if p["date"] else "")
        + f'<h3><a href="{esc(p["page"])}">{esc(p["title"])}</a></h3>'
        f'<p class="blog-ex">{esc(p["excerpt"])}</p>'
        f'<a class="blog-read" href="{esc(p["page"])}">Read more</a>'
        '<div class="share" aria-label="Share this post"><span>Share</span>'
        f'<a href="https://www.facebook.com/sharer/sharer.php?u={u}" target="_blank" rel="noopener">Facebook</a>'
        f'<a href="https://twitter.com/intent/tweet?url={u}&amp;text={t}" target="_blank" rel="noopener">X</a>'
        f'<a href="mailto:?subject={t}&amp;body={u}">Email</a>'
        f'<button type="button" data-copy="{esc(url)}">Copy link</button></div>'
        '</div></article>'
    )


def main() -> int:
    if not POST_TPL.exists() or not INDEX_TPL.exists():
        print("blog templates missing (scripts/blogpost.html, scripts/blogindex.html)")
        return 1
    posts = [read_post(p) for p in sorted(POSTS_DIR.glob("*.md"))] if POSTS_DIR.exists() else []
    posts = [p for p in posts if not p["draft"]]
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    md = markdown.Markdown(extensions=["extra", "sane_lists", "nl2br"])
    post_tpl = POST_TPL.read_text(encoding="utf-8")

    blog_dir = SITE_DIR / "blog"
    blog_dir.mkdir(exist_ok=True)
    keep = set()
    for p in posts:
        p["page"] = f"/blog/{p['slug']}/"
        md.reset()
        content = fonts(figures(md.convert(p["body"])))
        cover = (f'<figure class="post-cover"><img src="{esc(p["image"])}" alt=""></figure>' if p["image"] else "")
        og_image = p["image"] if p["image"].startswith("http") else (SITE_URL + p["image"] if p["image"] else DEFAULT_IMAGE)
        out = post_tpl
        for k, v in {
            "__TITLE__": esc(p["title"]), "__DESC__": esc(p["excerpt"] or p["title"]), "__URL__": SITE_URL + p["page"],
            "__IMAGE__": esc(og_image), "__DATE__": esc(nice_date(p["date"])), "__COVER__": cover,
            "__BODYCLASS__": ("font-" + p["font"]) if p["font"] else "",
        }.items():
            out = out.replace(k, v)
        out = out.replace("__CONTENT__", content)  # last, so post text can never be mistaken for a placeholder
        dest = blog_dir / p["slug"] / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_text(encoding="utf-8") != out:
            dest.write_text(out, encoding="utf-8")
        keep.add(p["slug"])

    # remove pages of posts that were deleted (only pages this script made)
    for d in blog_dir.iterdir():
        f = d / "index.html"
        if d.is_dir() and d.name not in keep and f.exists() and MARKER in f.read_text(encoding="utf-8"):
            f.unlink()
            d.rmdir()

    cards = "".join(card(p) for p in posts) or '<p class="blog-empty">New posts are coming soon.</p>'
    index_html = INDEX_TPL.read_text(encoding="utf-8").replace("__POSTS__", cards)
    idx = blog_dir / "index.html"
    if not idx.exists() or idx.read_text(encoding="utf-8") != index_html:
        idx.write_text(index_html, encoding="utf-8")

    feed = [{"title": p["title"], "url": p["page"], "page": p["page"], "date": p["date"], "excerpt": p["excerpt"], "image": p["image"]}
            for p in posts[:HOME_CARDS]]
    out_json = SITE_DIR / "blog.json"
    old = json.loads(out_json.read_text(encoding="utf-8")).get("posts") if out_json.exists() else None
    if old != feed:
        out_json.write_text(json.dumps({"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                        "posts": feed}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(posts)} posts built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
