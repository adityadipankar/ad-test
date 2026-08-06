#!/usr/bin/env python3
"""NID website — static build.

Renders pages from src/content/*.json using the six section types described in
the CMS & Data Model reference. No third-party dependencies: Python 3.9+ only,
so it builds on a bare GitHub Actions runner without an install step.

    python3 build.py            # -> dist/

Section types: text | links | cards | files | rail | mosaic
Link icons are derived from targetType and are never authored, per the model.
"""

import html
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"

# BASE is the absolute prefix used when the site is served from a sub-path,
# e.g. a GitHub project page at /nid-website. When it is empty the build emits
# document-relative URLs instead, so dist/ can be opened straight off disk.
BASE = ""
PREFIX = ""   # per-page relative prefix, e.g. "../", used only when BASE is empty


def url(path):
    """Resolve a site-root-relative path for the page currently being rendered."""
    path = path.lstrip("/")
    return f"{BASE}/{path}" if BASE else f"{PREFIX}{path}"

ICONS = {
    "arrow-up-right": '<path d="M7 17 17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "arrow-left": '<path d="M19 12H5m6-7-7 7 7 7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "file-text": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M14 3v5h5M9 13h6M9 17h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "sun": '<circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18c1 0 1.7-.8 1.7-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.1 0-1 .8-1.7 1.7-1.7H16a5 5 0 0 0 5-5c0-4-4-7.3-9-7.3Z" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="8" cy="11" r="1.1" fill="currentColor"/><circle cx="12" cy="8" r="1.1" fill="currentColor"/><circle cx="16" cy="11" r="1.1" fill="currentColor"/>',
    "search": '<circle cx="11" cy="11" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="m20 20-3.6-3.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
}

# targetType -> icon. The single place link iconography is decided.
LINK_ICON = {
    "page": "arrow-up-right",
    "external": "arrow-up-right",
    "document": "file-text",
    "back": "arrow-left",
    "email": None,
    "phone": None,
}


def e(s):
    return html.escape(str(s), quote=True)


def icon(name, cls="cta__icon"):
    if not name or name not in ICONS:
        return ""
    return (f'<span class="{cls}" aria-hidden="true"><svg viewBox="0 0 24 24">'
            f'{ICONS[name]}</svg></span>')


def href(link):
    t = link.get("targetType", "page")
    if t == "page":
        return url(link.get("page", "").strip("/") + "/")
    if t == "external":
        return link.get("url", "#")
    if t == "document":
        return url(link.get("document", "").strip("/"))
    if t == "email":
        return f'mailto:{link.get("address", "")}'
    if t == "phone":
        return f'tel:{link.get("address", "").replace(" ", "")}'
    return "#"


def cta(link, style="t-heading-5"):
    """The Call to actions component. Icon derived, never authored."""
    ic = LINK_ICON.get(link.get("targetType", "page"))
    new_tab = link.get("targetType") in ("external", "document")
    rel = ' target="_blank" rel="noopener"' if new_tab else ""
    return (f'<a class="cta" href="{e(href(link))}"{rel}>'
            f'<span class="cta__label {style}">{e(link["label"])}</span>'
            f'{icon(ic)}</a>')


def media(item, cls="", ratio_style=""):
    """Image block. Falls back to a labelled placeholder when the asset is absent."""
    asset = item.get("asset")
    path = SRC.parent / "public" / "img" / f"{asset}.jpg" if asset else None
    alt = e(item.get("alt", ""))
    if path and path.exists():
        inner = f'<img src="{e(url("img/" + asset + ".jpg"))}" alt="{alt}" loading="lazy">'
        ph = ""
    else:
        inner = ""
        ph = f' data-placeholder="{e(asset or "image")}"'
    return f'<div class="media {cls}"{ph}{ratio_style}>{inner}</div>'


# ---------------------------------------------------------------- section types

def sec_text(s):
    body = "".join(f'<p class="prose t-body-base-regular">{e(p)}</p>'
                   for p in s.get("body", "").split("\n\n") if p.strip())
    out = [f'<div class="rail"><h2 class="sectiontitle t-heading-2">{e(s["title"])}</h2></div>',
           f'<div class="measure stack">{body}</div>']
    if s.get("links"):
        out.append('<div class="aside linklist">'
                   + "".join(cta(l) for l in s["links"]) + "</div>")
    return out


def sec_links(s):
    return [f'<div class="rail"><h2 class="sectiontitle t-heading-2">{e(s["title"])}</h2></div>',
            '<div class="content linklist">'
            + "".join(cta(l) for l in s.get("items", [])) + "</div>"]


def sec_cards(s):
    variant = s.get("variant", "")
    cards = []
    for it in s.get("items", []):
        cls = f'card card--{variant}' if variant else "card"
        link = {"targetType": it.get("targetType", "page"), "page": it.get("page", "")}
        tag_open = f'<a class="{cls}" href="{e(href(link))}">' if it.get("page") else f'<div class="{cls}">'
        tag_close = "</a>" if it.get("page") else "</div>"
        name = it.get("name") or it.get("headline", "")
        style = "t-heading-6" if variant == "person" else "t-heading-3"
        body = [media(it, f'card__media')]
        body.append(f'<h3 class="card__title {style}">{e(name)}</h3>')
        if it.get("note"):
            body.append(f'<p class="card__note t-label-micro">{e(it["note"])}</p>')
        cards.append(tag_open + "".join(body) + tag_close)

    wrap_cls = "content cards"
    out = [f'<div class="rail"><h2 class="sectiontitle t-heading-2">{e(s["title"])}</h2></div>',
           f'<div class="{wrap_cls}">' + "".join(cards) + "</div>"]
    if s.get("links"):
        out.append('<div class="aside linklist">'
                   + "".join(cta(l) for l in s["links"]) + "</div>")
    return out


def sec_mosaic(s):
    cards = []
    for it in s.get("items", []):
        wide = it.get("featured")
        cls = "card card--wide" if wide else "card"
        link = {"targetType": "page", "page": it.get("page", "")}
        open_t = f'<a class="{cls}" href="{e(href(link))}">' if it.get("page") else f'<div class="{cls}">'
        close_t = "</a>" if it.get("page") else "</div>"
        parts = [media(it, "card__media")]
        if it.get("overline"):
            parts.append(f'<p class="card__meta t-label-overline">{e(it["overline"])}</p>')
        style = "t-heading-4" if wide else "t-heading-5"
        parts.append(f'<h3 class="card__title {style}">{e(it["headline"])}</h3>')
        if it.get("date"):
            parts.append(f'<p class="card__meta t-label-small">{e(it["date"])}</p>')
        cards.append(open_t + "".join(parts) + close_t)

    out = [f'<div class="rail"><h2 class="sectiontitle t-heading-2">{e(s["title"])}</h2></div>',
           '<div class="content cards">' + "".join(cards) + "</div>"]
    if s.get("links"):
        out.append('<div class="aside linklist">'
                   + "".join(cta(l) for l in s["links"]) + "</div>")
    return out


def sec_files(s):
    rows = "".join(cta({**f, "targetType": "document"}, "t-heading-5") for f in s.get("items", []))
    out = [f'<div class="rail"><h2 class="sectiontitle t-heading-2">{e(s["title"])}</h2></div>',
           f'<div class="measure linklist">{rows}</div>']
    if s.get("contacts"):
        out.append('<div class="aside linklist">'
                   + "".join(cta(c) for c in s["contacts"]) + "</div>")
    return out


def sec_rail(s):
    groups = []
    for g in s.get("items", []):
        entries = "".join(
            f'<div class="card card--person">{media(p, "card__media")}'
            f'<h3 class="card__title t-heading-6">{e(p.get("name", ""))}</h3></div>'
            for p in g.get("people", []))
        groups.append(f'<div class="rail"><h3 class="t-label-overline">{e(g.get("label", ""))}</h3></div>'
                      f'<div class="content cards">{entries}</div>')
    return [f'<div class="rail"><h2 class="sectiontitle t-heading-2">{e(s["title"])}</h2></div>',
            '<div class="content"></div>'] + groups


RENDERERS = {
    "text": sec_text, "links": sec_links, "cards": sec_cards,
    "files": sec_files, "rail": sec_rail, "mosaic": sec_mosaic,
}


# ---------------------------------------------------------------------- shell

def masthead():
    return f"""<header class="masthead">
  <div class="masthead__inner">
    <a class="masthead__brand" href="{url('')}">
      <span class="masthead__mark" aria-hidden="true"></span>
      <span class="masthead__wordmark">
        <span class="t-label-micro">राष्ट्रीय डिज़ाइन संस्थान</span>
        <span class="t-label-overline">National Institute of Design</span>
      </span>
    </a>
    <div class="masthead__tools">
      <button class="iconbtn" id="theme-cycle" title="Change theme" aria-label="Change theme"><svg viewBox="0 0 24 24">{ICONS['palette']}</svg></button>
      <button class="iconbtn" id="appearance-toggle" title="Light or dark" aria-label="Toggle light or dark"><svg viewBox="0 0 24 24">{ICONS['sun']}</svg></button>
      <a class="t-label-small" href="#" style="text-decoration:none">Apply</a>
      <button class="iconbtn" title="Search" aria-label="Search"><svg viewBox="0 0 24 24">{ICONS['search']}</svg></button>
      <button class="iconbtn" title="Menu" aria-label="Menu"><svg viewBox="0 0 24 24">{ICONS['menu']}</svg></button>
    </div>
  </div>
</header>"""


def footer(f):
    primary = "".join(f'<a class="footlink t-label-small" href="#">{e(x)}</a>' for x in f["primary"])
    secondary = "".join(f'<a class="footlink t-label-micro" href="#">{e(x)}</a>' for x in f["secondary"])
    c = f["contact"]
    contact = "".join(f'<a class="t-label-micro" href="mailto:{e(x)}">{e(x)}</a>' for x in c["emails"])
    contact += "".join(f'<a class="t-label-micro" href="tel:{e(x.replace(" ", ""))}">{e(x)}</a>' for x in c["phones"])
    logos = "".join(f'<span>{e(x)}</span>' for x in f["collaborations"]["logos"])
    # No explicit column placement: grid auto-placement gives 4 across at four
    # columns, 3 with the fourth wrapping at three, 2x2 at two and a stack at one
    # — exactly the progression the rendering contract describes.
    return f"""<footer class="pagefoot">
  <div class="grid">
    <div class="footcol">{primary}</div>
    <div class="footcol">{secondary}</div>
    <div class="footcol">
      <h2 class="t-label-overline">{e(c['heading'])}</h2>{contact}
    </div>
    <div class="footcol">
      <h2 class="t-label-overline">{e(f['collaborations']['heading'])}</h2>
      <div class="logogrid">{logos}</div>
    </div>
  </div>
</footer>"""


THEME_JS = """
(function () {
  var THEMES = ['lotus','indigo','henna','peacock','grayscale','tanjore','khadi','terracotta','ikkat','tiger'];
  var root = document.documentElement, i = 0;
  var t = document.getElementById('theme-cycle');
  if (t) t.addEventListener('click', function () {
    i = (i + 1) % THEMES.length;
    root.setAttribute('data-theme', THEMES[i]);
    t.title = 'Theme: ' + THEMES[i];
  });
  var a = document.getElementById('appearance-toggle');
  if (a) a.addEventListener('click', function () {
    var cur = root.getAttribute('data-appearance');
    if (!cur) cur = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    root.setAttribute('data-appearance', cur === 'dark' ? 'light' : 'dark');
  });
})();
"""


def render_page(page):
    global PREFIX
    depth = len([p for p in page["slug"].split("/") if p])
    PREFIX = "../" * depth if depth else "./"
    blocks = []

    # Row 0 — page title; row 1 — sub-page rail beside the hero; row 2 — intro
    blocks.append(f'<div class="rail"><h1 class="pagetitle t-heading-1">{e(page["title"])}</h1></div>')
    if page.get("subPages"):
        blocks.append('<nav class="rail linklist" aria-label="In this section">'
                      + "".join(cta(l) for l in page["subPages"]) + "</nav>")
    if page.get("hero"):
        blocks.append('<div class="content">' + media(page["hero"], "media--hero") + "</div>")
    if page.get("intro"):
        blocks.append(f'<div class="measure"><p class="intro t-body-large-regular">{e(page["intro"])}</p></div>')

    for s in page.get("sections", []):
        blocks.append('<hr class="hr">')
        renderer = RENDERERS.get(s["type"])
        if not renderer:
            raise SystemExit(f'Unknown section type: {s["type"]}')
        cls = "section section--aside" if s.get("links") else "section"
        blocks.append(f'<div class="{cls}">' + "".join(renderer(s)) + "</div>")

    body = "\n    ".join(blocks)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(page['title'])} — National Institute of Design</title>
<meta name="description" content="{e(page.get('intro', '')[:155])}">
<link rel="stylesheet" href="{url('styles/tokens.css')}">
<link rel="stylesheet" href="{url('styles/base.css')}">
</head>
<body>
<a class="skip-link t-label-button" href="#main">Skip to content</a>
{masthead()}
<div class="patternstrip" aria-hidden="true"></div>
<main id="main">
  <div class="grid">
    {body}
  </div>
</main>
{footer(page['footer'])}
<div class="patternstrip" aria-hidden="true"></div>
<script>{THEME_JS}</script>
</body>
</html>
"""


def main():
    global BASE
    for arg in sys.argv[1:]:
        if arg.startswith("--base="):
            BASE = arg.split("=", 1)[1].rstrip("/")

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "styles").mkdir(parents=True)

    for css in ("tokens.css", "base.css"):
        shutil.copy(SRC / "styles" / css, DIST / "styles" / css)

    pub = ROOT / "public"
    if pub.exists():
        shutil.copytree(pub, DIST, dirs_exist_ok=True)

    (DIST / ".nojekyll").write_text("")

    count = 0
    for f in sorted((SRC / "content").glob("*.json")):
        page = json.loads(f.read_text())
        out = DIST / page["slug"] / "index.html" if page["slug"] else DIST / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_page(page))
        count += 1
        print(f"  {f.name:24s} -> {out.relative_to(DIST)}")

    # Root redirect to the one page that exists in this proof
    home = f"{BASE}/about/" if BASE else "./about/"
    (DIST / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={home}">'
        f'<title>NID</title><a href="{home}">About NID</a>')

    print(f"built {count} page(s) into {DIST}" + (f' with base "{BASE}"' if BASE else ""))


if __name__ == "__main__":
    main()
