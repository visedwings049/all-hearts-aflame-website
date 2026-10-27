"""Builds the blog from the posts in content/posts/ (written in the AHA Blogger app, or in the Tina editor at /admin/).

For every post it writes a full page at /blog/<slug>/ (site header and footer, the post, share buttons, and the post's own
title, summary and picture for Facebook/X previews), rebuilds the list at /blog/, and writes blog.json (the newest posts,
read by the "From the Blog" cards on the home page).

A post is up to five text blocks, each with an optional picture above or below it. Older posts with a single body still work.

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
MARKER = "<!-- generated-by-build_blog -->"
HOME_CARDS = 6
FIGURE_RE = re.compile(r'<img alt="([^"]*)" src="([^"]*)" title="layout:(full|wide|left|right)" />')


def figure_html(html_text: str) -> str:
    """Older posts: ![caption](picture "layout:left") -> a captioned figure that is full width, centered, or floated left/right."""
    def one(m):
        cap, src, layout = m.group(1), m.group(2), m.group(3)
        return (f'<figure class="post-img {layout}"><img src="{src}" alt="{cap}">'
                + (f"<figcaption>{cap}</figcaption>" if cap else "") + "</figure>")
    return FIGURE_RE.sub(one, html_text)


# ----- shared with the AHA Blogger app (copied from it) -----
FONT_TABLE = [
    # key, name, css font-family, Google Fonts name (None = nothing to load), kind
    ("default", "Site font (Source Sans 3)", None, None, "Sans"),
    ("cormorant", "Cormorant Garamond", "'Cormorant Garamond',Georgia,serif", "Cormorant+Garamond", "Serif"),
    ("playfair", "Playfair Display", "'Playfair Display',Georgia,serif", "Playfair+Display", "Serif"),
    ("lora", "Lora", "'Lora',Georgia,serif", "Lora", "Serif"),
    ("merriweather", "Merriweather", "'Merriweather',Georgia,serif", "Merriweather", "Serif"),
    ("baskerville", "Libre Baskerville", "'Libre Baskerville',Georgia,serif", "Libre+Baskerville", "Serif"),
    ("garamond", "EB Garamond", "'EB Garamond',Georgia,serif", "EB+Garamond", "Serif"),
    ("crimson", "Crimson Text", "'Crimson Text',Georgia,serif", "Crimson+Text", "Serif"),
    ("spectral", "Spectral", "'Spectral',Georgia,serif", "Spectral", "Serif"),
    ("cardo", "Cardo", "'Cardo',Georgia,serif", "Cardo", "Serif"),
    ("georgia", "Georgia", "Georgia,'Times New Roman',serif", None, "Serif"),
    ("times", "Times New Roman", "'Times New Roman',Times,serif", None, "Serif"),
    ("opensans", "Open Sans", "'Open Sans',Arial,sans-serif", "Open+Sans", "Sans"),
    ("roboto", "Roboto", "'Roboto',Arial,sans-serif", "Roboto", "Sans"),
    ("lato", "Lato", "'Lato',Arial,sans-serif", "Lato", "Sans"),
    ("montserrat", "Montserrat", "'Montserrat',Arial,sans-serif", "Montserrat", "Sans"),
    ("poppins", "Poppins", "'Poppins',Arial,sans-serif", "Poppins", "Sans"),
    ("raleway", "Raleway", "'Raleway',Arial,sans-serif", "Raleway", "Sans"),
    ("nunito", "Nunito", "'Nunito',Arial,sans-serif", "Nunito", "Sans"),
    ("worksans", "Work Sans", "'Work Sans',Arial,sans-serif", "Work+Sans", "Sans"),
    ("inter", "Inter", "'Inter',Arial,sans-serif", "Inter", "Sans"),
    ("arial", "Arial", "Arial,Helvetica,sans-serif", None, "Sans"),
    ("verdana", "Verdana", "Verdana,Geneva,sans-serif", None, "Sans"),
    ("trebuchet", "Trebuchet MS", "'Trebuchet MS',Arial,sans-serif", None, "Sans"),
    ("cinzel", "Cinzel", "'Cinzel',Georgia,serif", "Cinzel", "Capitals"),
    ("cinzeldeco", "Cinzel Decorative", "'Cinzel Decorative',Georgia,serif", "Cinzel+Decorative", "Capitals"),
    ("abril", "Abril Fatface", "'Abril Fatface',Georgia,serif", "Abril+Fatface", "Display"),
    ("bebas", "Bebas Neue", "'Bebas Neue',Impact,sans-serif", "Bebas+Neue", "Display"),
    ("oswald", "Oswald", "'Oswald',Impact,sans-serif", "Oswald", "Display"),
    ("robotoslab", "Roboto Slab", "'Roboto Slab',Georgia,serif", "Roboto+Slab", "Slab"),
    ("zilla", "Zilla Slab", "'Zilla Slab',Georgia,serif", "Zilla+Slab", "Slab"),
    ("script", "Dancing Script", "'Dancing Script',cursive", "Dancing+Script", "Script"),
    ("greatvibes", "Great Vibes", "'Great Vibes',cursive", "Great+Vibes", "Script"),
    ("pacifico", "Pacifico", "'Pacifico',cursive", "Pacifico", "Script"),
    ("satisfy", "Satisfy", "'Satisfy',cursive", "Satisfy", "Script"),
    ("caveat", "Caveat", "'Caveat',cursive", "Caveat", "Script"),
    ("allura", "Allura", "'Allura',cursive", "Allura", "Script"),
    ("parisienne", "Parisienne", "'Parisienne',cursive", "Parisienne", "Script"),
]
FONTS = [((n if k == "default" else f"{n}   ({kind})"), k) for k, n, _c, _g, kind in FONT_TABLE]
FONT_BY_KEY = {k: (c, g, kind) for k, _n, c, g, kind in FONT_TABLE}
FONT_LINK_RE = re.compile(r'<a href="font:([a-z]+)">(.*?)</a>', re.S)


def font_spans(html_text: str) -> str:
    """[words](font:cinzel) -> the words in that font, the way the website does it."""
    def one(m):
        return f'<span class="font-{m.group(1)}">{m.group(2)}</span>' if m.group(1) in FONT_BY_KEY and m.group(1) != "default" else m.group(0)
    return FONT_LINK_RE.sub(one, html_text)


def font_head(keys) -> str:
    """The <link> (Google Fonts) and <style> a page needs for the fonts it uses."""
    keys = [k for k in dict.fromkeys(keys) if k in FONT_BY_KEY and k != "default"]
    fams = [FONT_BY_KEY[k][1] for k in keys if FONT_BY_KEY[k][1]]
    link = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?' + "&".join("family=" + f for f in fams) + '&display=swap">') if fams else ""
    rules = "".join(f".font-{k}{{font-family:{FONT_BY_KEY[k][0]}" + (";font-size:1.2em" if FONT_BY_KEY[k][2] == "Script" else "") + "}" for k in keys)
    return link + (f"<style>{rules}</style>" if rules else "")


SHARE_OPTIONS = [("facebook", "Facebook"), ("x", "X (Twitter)"), ("linkedin", "LinkedIn"), ("whatsapp", "WhatsApp"), ("telegram", "Telegram"),
                 ("reddit", "Reddit"), ("pinterest", "Pinterest"), ("email", "Email"), ("copy", "Copy link")]
SHARE_DEFAULT = ["facebook", "x", "email", "copy"]


def share_links(url: str, title: str, image: str = "") -> list:
    """[(key, label, href or None)]; None means the Copy link button."""
    q = urllib.parse.quote
    u, t, m = q(url, safe=""), q(title, safe=""), q(image, safe="")
    hrefs = {
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={u}",
        "x": f"https://twitter.com/intent/tweet?url={u}&text={t}",
        "linkedin": f"https://www.linkedin.com/sharing/share-offsite/?url={u}",
        "whatsapp": f"https://wa.me/?text={t}%20{u}",
        "telegram": f"https://t.me/share/url?url={u}&text={t}",
        "reddit": f"https://www.reddit.com/submit?url={u}&title={t}",
        "pinterest": f"https://pinterest.com/pin/create/button/?url={u}&media={m}&description={t}",
        "email": f"mailto:?subject={t}&body={u}",
        "copy": None,
    }
    return [(k, n, hrefs[k]) for k, n in SHARE_OPTIONS]


BLOCKS = 5
POSITIONS = [("Above the text", "above"), ("Below the text", "below")]
ALIGNS = [("Left", "left"), ("Center", "center"), ("Right", "right")]
SIZES = [("Small", 35), ("Medium", 60), ("Large", 80), ("Full width", 100)]


def empty_block() -> dict:
    return {"text": "", "image": "", "imagePosition": "above", "imageWidth": 60, "imageAlign": "center", "caption": ""}


def clean_block(b: dict) -> dict:
    out = empty_block()
    out["text"] = str(b.get("text") or "").strip("\n")
    out["image"] = str(b.get("image") or "").strip()
    out["imagePosition"] = b.get("imagePosition") if b.get("imagePosition") in ("above", "below") else "above"
    try:
        out["imageWidth"] = max(20, min(100, int(b.get("imageWidth") or 60)))
    except (TypeError, ValueError):
        out["imageWidth"] = 60
    out["imageAlign"] = b.get("imageAlign") if b.get("imageAlign") in ("left", "center", "right") else "center"
    out["caption"] = str(b.get("caption") or "").strip()
    return out


def figure_style(width: int, align: str) -> str:
    margin = {"left": "1.4em auto 1.4em 0", "right": "1.4em 0 1.4em auto"}.get(align, "1.4em auto")
    return f"width:{int(width)}%;margin:{margin}"


def block_html(b: dict, img_src: str = "") -> str:
    """One text block (markdown) with its optional picture above or below it."""
    text = markdown.markdown(b["text"], extensions=["extra", "sane_lists", "nl2br"]) if b["text"].strip() else ""
    text = font_spans(figure_html(text))
    fig = ""
    if b["image"]:
        cap = html.escape(b["caption"], quote=True)
        fig = (f'<figure class="post-fig" style="{figure_style(b["imageWidth"], b["imageAlign"])}"><img src="{html.escape(img_src, quote=True)}" alt="{cap}">'
               + (f"<figcaption>{html.escape(b['caption'])}</figcaption>" if b["caption"] else "") + "</figure>")
    parts = [fig, text] if b["imagePosition"] == "above" else [text, fig]
    return '<section class="post-block">' + "".join(parts) + "</section>"


def post_content_html(p: dict, img_src=lambda site_path: site_path) -> str:
    return "".join(block_html(b, img_src(b["image"]) if b["image"] else "") for b in p["blocks"] if b["text"].strip() or b["image"])



# ----- the website's own part -----
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


def nice_date(iso: str) -> str:
    try:
        d = datetime.datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.strftime('%B')} {d.day}, {d.year}"
    except ValueError:
        return ""


def read_post(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.S)
    meta, body = ({}, raw) if not m else (yaml.safe_load(m.group(1)) or {}, m.group(2))
    d = meta.get("date")
    date = d.strftime("%Y-%m-%d") if isinstance(d, (datetime.date, datetime.datetime)) else str(d or "")[:10]
    blocks = [clean_block(b) for b in (meta.get("blocks") or []) if isinstance(b, dict)]
    if not blocks and body.strip():  # a post written before blocks existed
        blocks = [{**empty_block(), "text": body.strip("\n")}]
    for b in blocks:
        b["image"] = site_path(b["image"])
    first = next((b["text"] for b in blocks if b["text"].strip()), "")
    text = plain(first)
    excerpt = str(meta.get("excerpt") or "").strip() or (text[:200].rsplit(" ", 1)[0] + "..." if len(text) > 200 else text)
    share = meta.get("share")
    share = [k for k in share if k in dict(SHARE_OPTIONS)] if isinstance(share, list) else list(SHARE_DEFAULT)
    font = str(meta.get("font") or "").strip().lower()
    return {
        "slug": path.stem,
        "title": str(meta.get("title") or path.stem.replace("-", " ").title()).strip(),
        "date": date, "excerpt": excerpt, "image": site_path(meta.get("image")), "summary_image": site_path(meta.get("summaryImage")),
        "draft": bool(meta.get("draft")),
        "font": font if font in FONT_BY_KEY and font != "default" else "", "share": share, "blocks": blocks,
    }


def card_image(p) -> str:
    """The picture for the blog list, the home page card and share previews: the summary picture, else the cover, else the first block picture."""
    return p["summary_image"] or p["image"] or next((b["image"] for b in p["blocks"] if b["image"]), "")


def share_html(p, url: str, og_image: str, cls_label: bool = True) -> str:
    out = []
    for k, n, href in share_links(url, p["title"], og_image if og_image.startswith("http") else SITE_URL + og_image):
        if k not in p["share"]:
            continue
        out.append(f'<button type="button" data-copy="{esc(url)}">Copy link</button>' if href is None
                   else f'<a href="{esc(href)}" target="_blank" rel="noopener">{esc(n)}</a>')
    if not out:
        return ""
    return '<span>' + ("Share" if not cls_label else "Share this post") + "</span>" + "".join(out)


def card(p) -> str:
    url = SITE_URL + p["page"]
    cimg = card_image(p)
    pic = (f'<img src="{esc(cimg)}" alt="" loading="lazy">' if cimg
           else '<span class="blog-ph"><svg><use href="#flame-gold"/></svg></span>')
    shares = share_html(p, url, cimg or DEFAULT_IMAGE, cls_label=False)
    return (
        '<article class="blog-card">'
        f'<a class="blog-pic" href="{esc(p["page"])}" tabindex="-1" aria-hidden="true">{pic}</a>'
        '<div class="blog-body">'
        + (f'<p class="blog-date">{esc(nice_date(p["date"]))}</p>' if p["date"] else "")
        + f'<h3><a href="{esc(p["page"])}">{esc(p["title"])}</a></h3>'
        f'<p class="blog-ex">{esc(p["excerpt"])}</p>'
        f'<a class="blog-read" href="{esc(p["page"])}">Read more</a>'
        + (f'<div class="share" aria-label="Share this post">{shares}</div>' if shares else "")
        + '</div></article>'
    )


def main() -> int:
    if not POST_TPL.exists() or not INDEX_TPL.exists():
        print("blog templates missing (scripts/blogpost.html, scripts/blogindex.html)")
        return 1
    posts = [read_post(p) for p in sorted(POSTS_DIR.glob("*.md"))] if POSTS_DIR.exists() else []
    posts = [p for p in posts if not p["draft"]]
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    post_tpl = POST_TPL.read_text(encoding="utf-8")

    blog_dir = SITE_DIR / "blog"
    blog_dir.mkdir(exist_ok=True)
    keep = set()
    for p in posts:
        p["page"] = f"/blog/{p['slug']}/"
        content = post_content_html(p)
        cover = (f'<figure class="post-cover"><img src="{esc(p["image"])}" alt=""></figure>' if p["image"] else "")
        og_source = card_image(p)
        og_image = og_source if og_source.startswith("http") else (SITE_URL + og_source if og_source else DEFAULT_IMAGE)
        used = [p["font"]] + re.findall(r'class="font-([a-z]+)"', content)
        shares = share_html(p, SITE_URL + p["page"], og_image)
        out = post_tpl
        for k, v in {
            "__TITLE__": esc(p["title"]), "__DESC__": esc(p["excerpt"] or p["title"]), "__URL__": SITE_URL + p["page"],
            "__IMAGE__": esc(og_image), "__DATE__": esc(nice_date(p["date"])), "__COVER__": cover,
            "__BODYCLASS__": ("font-" + p["font"]) if p["font"] else "", "__FONTHEAD__": font_head(used),
            "__SHAREBLOCK__": f'<div class="share share-page" aria-label="Share this post">{shares}</div>' if shares else "",
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

    feed = [{"title": p["title"], "url": p["page"], "page": p["page"], "date": p["date"], "excerpt": p["excerpt"],
             "image": card_image(p), "share": p["share"]} for p in posts[:HOME_CARDS]]
    out_json = SITE_DIR / "blog.json"
    old = json.loads(out_json.read_text(encoding="utf-8")).get("posts") if out_json.exists() else None
    if old != feed:
        out_json.write_text(json.dumps({"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                        "posts": feed}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(posts)} posts built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
