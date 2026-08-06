#!/usr/bin/env python3
"""NID website — static build.

Renders every page in src/content/pages.json using the six section types from
the CMS & Data Model reference. Python standard library only, so it builds on a
bare GitHub Actions runner with no install step.

    python3 build.py                    # -> dist/  (document-relative URLs)
    python3 build.py --base=/repo-name  # -> dist/  (for a GitHub project page)

Section types: text | links | cards | files | rail | mosaic
Link icons are derived from targetType and are never authored, per the model.
"""

import html
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"

# Page titles carry curly quotes and em-dashes. A CI runner with a C/POSIX
# locale gives Python an ASCII stdout, which would make the progress log itself
# crash the build. Every file read and write below is explicitly UTF-8 for the
# same reason — never rely on the platform default encoding.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE = ""
PREFIX = ""

LOGO = (SRC / "assets" / "logo.svg").read_text(encoding="utf-8").strip()

# Interim webfonts. Futura PT and Bodoni PT VF are licensed and are not served
# here; Jost and Bodoni Moda stand in for them and are listed *after* the real
# names in the token font stacks, so adding an Adobe Fonts kit to the <head>
# takes over automatically with no other change. Merriweather Sans is the real
# body face and is served from Google directly.
FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2'
    '?family=Bodoni+Moda:ital,wght@0,400;0,600;0,700;1,400'
    '&family=Jost:wght@300;400;500;600;700;800'
    '&family=Merriweather+Sans:ital,wght@0,300;0,400;0,700;0,800;1,300'
    '&display=swap">'
)

ICONS = {
    "arrow-up-right": '<path d="M7 17 17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "arrow-left": '<path d="M19 12H5m6-7-7 7 7 7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "file-text": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M14 3v5h5M9 13h6M9 17h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "sun": '<circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18c1 0 1.7-.8 1.7-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.1 0-1 .8-1.7 1.7-1.7H16a5 5 0 0 0 5-5c0-4-4-7.3-9-7.3Z" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="8" cy="11" r="1.1" fill="currentColor"/><circle cx="12" cy="8" r="1.1" fill="currentColor"/><circle cx="16" cy="11" r="1.1" fill="currentColor"/>',
    "search": '<circle cx="11" cy="11" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="m20 20-3.6-3.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
}

LINK_ICON = {
    "page": "arrow-up-right", "external": "arrow-up-right", "document": "file-text",
    "back": "arrow-left", "email": None, "phone": None,
}

TITLE_INDEX = {}   # normalised page title -> slug, for resolving unlinked labels


def e(s):
    return html.escape(str(s), quote=True)


def url(path):
    path = path.lstrip("/")
    return f"{BASE}/{path}" if BASE else f"{PREFIX}{path}"


def icon(name, cls="cta__icon"):
    if not name or name not in ICONS:
        return ""
    return f'<span class="{cls}" aria-hidden="true"><svg viewBox="0 0 24 24">{ICONS[name]}</svg></span>'


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def resolve(link):
    """Fill in a missing destination by matching the label against page titles."""
    if link.get("page") or link.get("targetType") in ("email", "phone", "external", "document"):
        return link
    key = norm(link["label"])
    for alias, target in (("allnewsandevents", "about-nid/news-and-events"),
                          ("nidsmandate", "about-nid/charter")):
        if key == alias and target in TITLE_INDEX.values():
            return {**link, "page": target}
    if key in TITLE_INDEX:
        return {**link, "page": TITLE_INDEX[key]}
    return link


def href(link):
    t = link.get("targetType", "page")
    if t == "email":
        return f'mailto:{link.get("address", link["label"])}'
    if t == "phone":
        return f'tel:{link.get("address", link["label"]).replace(" ", "")}'
    if t == "external":
        return link.get("url", "#")
    if t == "document":
        return link.get("url") or "#"
    if link.get("page"):
        return url(link["page"].strip("/") + "/")
    return None


def cta(link, style="t-heading-5", kind=None):
    link = resolve(link)
    t = kind or link.get("targetType", "page")
    ic = LINK_ICON.get(t, "arrow-up-right")
    dest = href(link)
    inner = f'<span class="cta__label {style}">{e(link["label"])}</span>{icon(ic)}'
    if dest is None:
        # No destination yet — render as a non-link so it cannot 404
        return f'<span class="cta cta--todo" title="No destination yet">{inner}</span>'
    rel = ' target="_blank" rel="noopener"' if t in ("external", "document") else ""
    return f'<a class="cta" href="{e(dest)}"{rel}>{inner}</a>'


def media(item, cls="", label=None):
    asset = (item or {}).get("asset")
    alt = e((item or {}).get("alt", ""))
    path = ROOT / "public" / "img" / f"{asset}.jpg" if asset else None
    if path and path.exists():
        return f'<div class="media {cls}"><img src="{e(url("img/" + asset + ".jpg"))}" alt="{alt}" loading="lazy"></div>'
    return f'<div class="media {cls}" data-placeholder="{e(label or asset or "image")}"></div>'


# ---------------------------------------------------------------- section types

def paras(body):
    return "".join(f'<p class="prose t-body-base-regular">{e(p)}</p>'
                   for p in (body or "").split("\n\n") if p.strip())


def head(s):
    if not s.get("title"):
        return ""
    return f'<div class="rail"><h2 class="sectiontitle t-heading-2">{e(s["title"])}</h2></div>'


def aside(s):
    if not s.get("links"):
        return ""
    return '<div class="aside linklist">' + "".join(cta(l) for l in s["links"]) + "</div>"


def sec_text(s):
    out = [head(s), f'<div class="measure stack">{paras(s.get("body"))}</div>']
    if s.get("image"):
        out.append(f'<div class="measure">{media(s["image"], "media--section", s["image"].get("asset"))}</div>')
    out.append(aside(s))
    return out


def sec_links(s):
    return [head(s),
            '<div class="content linklist linklist--wrap">'
            + "".join(cta(l) for l in s.get("items", [])) + "</div>",
            aside(s)]


GO = f'<span class="gobtn" aria-hidden="true"><svg viewBox="0 0 24 24">{ICONS["arrow-up-right"]}</svg></span>'


def sec_cards(s):
    variant = s.get("variant", "")
    cards = []
    for it in s.get("items", []):
        cls = f"card card--{variant}" if variant else "card"
        dest = href(resolve({"label": it.get("name", ""), "page": it.get("page")})) if it.get("page") else None
        o = f'<a class="{cls}" href="{e(dest)}">' if dest else f'<div class="{cls}">'
        c = "</a>" if dest else "</div>"
        name = e(it.get("name", ""))

        if variant == "person":
            # Round portrait with the arrow beside it, then name and note
            parts = [f'<div class="card__head">{media(it, "card__media", it.get("asset"))}{GO}</div>',
                     '<div class="card__body">',
                     f'<h3 class="card__title t-heading-6">{name}</h3>']
            if it.get("note"):
                parts.append(f'<p class="card__note t-label-micro">{e(it["note"])}</p>')
            parts.append("</div>")
        elif variant == "campus":
            # The arch: place name sits on the image
            parts = [media(it, "card__media", it.get("asset")),
                     f'<h3 class="card__title t-heading-3">{name}</h3>']
        else:
            parts = [media(it, "card__media", it.get("asset")),
                     f'<h3 class="card__title t-heading-3">{name}</h3>']
            if it.get("meta"):
                parts.append(f'<p class="card__meta t-label-small">{e(it["meta"])}</p>')
            if it.get("note"):
                parts.append(f'<p class="card__note t-label-micro">{e(it["note"])}</p>')
        cards.append(o + "".join(parts) + c)
    return [head(s), '<div class="content cards">' + "".join(cards) + "</div>", aside(s)]


def sec_mosaic(s):
    cards = []
    for it in s.get("items", []):
        wide = it.get("featured")
        cls = "card card--wide" if wide else "card"
        dest = href(resolve({"label": it.get("name", ""), "page": it.get("page")})) if it.get("page") else None
        o = f'<a class="{cls}" href="{e(dest)}">' if dest else f'<div class="{cls}">'
        c = "</a>" if dest else "</div>"
        parts = [media(it, "card__media", it.get("asset"))]
        if wide:
            # Overline with a rule running off to the right, headline, then the
            # arrow with its own rule closing the card — as the component does it.
            over = e(it.get("overline", "")) or "&nbsp;"
            parts.append(f'<p class="card__rule card__meta card__meta--overline t-label-overline">{over}</p>')
            parts.append(f'<h3 class="card__title t-heading-4">{e(it.get("name", ""))}</h3>')
            if it.get("meta"):
                parts.append(f'<p class="card__meta t-label-small">{e(it["meta"])}</p>')
            parts.append(f'<p class="card__rule card__go">{GO}</p>')
        else:
            if it.get("overline"):
                parts.append(f'<p class="card__meta t-label-overline">{e(it["overline"])}</p>')
            parts.append(f'<h3 class="card__title t-heading-5">{e(it.get("name", ""))}</h3>')
            if it.get("meta"):
                parts.append(f'<p class="card__meta t-label-small">{e(it["meta"])}</p>')
        cards.append(o + "".join(parts) + c)
    return [head(s), '<div class="content cards">' + "".join(cards) + "</div>", aside(s)]


def sec_files(s):
    rows = "".join(cta(f, kind="document") for f in s.get("items", []))
    return [head(s), f'<div class="measure linklist">{rows}</div>', aside(s)]


def sec_rail(s):
    out = [head(s)]
    for g in s.get("items", []):
        entries = "".join(
            f'<div class="card card--person">{media(p, "card__media", p.get("asset"))}'
            f'<h3 class="card__title t-heading-6">{e(p.get("name", ""))}</h3></div>'
            for p in g.get("people", []))
        out.append(f'<div class="rail"><h3 class="t-label-overline">{e(g.get("label", ""))}</h3></div>')
        out.append(f'<div class="content cards">{entries}</div>')
    return out




def statement_html(text):
    """Position Statement: every full stop takes accent/secondary while the words
    take text/primary. The component specifies this per-character, so it is
    generated here rather than authored into the content."""
    lines = []
    for line in text.split("\n"):
        lines.append("".join('<span class="stop">.</span>' if part == "." else e(part)
                             for part in re.split(r"(\.)", line)))
    return "<br>".join(lines)


def sec_tiles(s):
    """The home mosaic: one square tile per module, laid straight onto the page grid."""
    out = []
    for it in s.get("items", []):
        kind = it.get("kind", "blank")
        span = it.get("span", 1)
        dest = href(resolve({"label": it.get("heading", ""), "page": it.get("page")})) if it.get("page") else None
        cls = f"tile tile--{kind}" + (" tile--wide" if span > 1 else "")
        o = f'<a class="{cls}" href="{e(dest)}">' if dest else f'<div class="{cls}">'
        c = "</a>" if dest else "</div>"
        body = []

        if it.get("asset") and kind in ("feature", "quote", "item", "list"):
            body.append(media(it, "tile__bg", it["asset"]))

        inner = ['<div class="tile__inner">']
        if it.get("overline"):
            inner.append(f'<p class="tile__over t-label-overline">{e(it["overline"])}</p>')

        if kind == "statement":
            inner.append(f'<p class="tile__statement">{statement_html(it["text"])}</p>')
        elif kind == "quote":
            inner.append(f'<blockquote class="tile__quote t-display-quote">{e(it["text"])}</blockquote>')
        elif kind == "pairs":
            if it.get("heading"):
                inner.append(f'<h2 class="tile__head t-heading-3">{e(it["heading"])}</h2>')
            rows = "".join(
                f'<div class="tile__pair"><dt class="t-label-button">{e(a)}</dt>'
                f'<dd class="t-label-small">{e(b)}</dd></div>' for a, b in it.get("pairs", []))
            inner.append(f'<dl class="tile__pairs">{rows}</dl>')
        elif kind == "list":
            if it.get("heading"):
                inner.append(f'<h2 class="tile__head t-heading-3">{e(it["heading"])}</h2>')
            style = "t-label-micro" if it.get("micro") else "t-label-small"
            rows = "".join(f'<li class="{style}">{e(x)}</li>' for x in it.get("items", []))
            inner.append(f'<ul class="tile__list">{rows}</ul>')
        elif kind == "feature":
            hs = "t-display-serif" if it.get("serif") else "t-heading-3"
            inner.append(f'<h2 class="tile__head {hs}">{e(it.get("heading", ""))}</h2>')
            if it.get("text"):
                inner.append(f'<p class="tile__text t-label-small">{e(it["text"])}</p>')
        elif kind == "item":
            inner.append(f'<h3 class="tile__head t-heading-5">{e(it.get("heading", ""))}</h3>')
            if it.get("text"):
                inner.append(f'<p class="tile__text t-label-small">{e(it["text"])}</p>')

        if it.get("action"):
            inner.append(f'<p class="tile__action t-label-button">{e(it["action"])}{icon("arrow-up-right", "tile__icon")}</p>')
        inner.append("</div>")

        out.append(o + "".join(body) + "".join(inner) + c)
    return out


RENDERERS = {"text": sec_text, "links": sec_links, "cards": sec_cards,
             "files": sec_files, "rail": sec_rail, "mosaic": sec_mosaic,
             "tiles": sec_tiles}


# ---------------------------------------------------------------------- shell

def masthead():
    return f"""<header class="masthead">
  <div class="masthead__inner">
    <a class="masthead__brand" href="{url('')}" aria-label="National Institute of Design — home">{LOGO}</a>
    <div class="masthead__theme">
      <button class="iconbtn" id="theme-cycle" title="Change theme" aria-label="Change theme"><svg viewBox="0 0 24 24">{ICONS['palette']}</svg></button>
      <button class="iconbtn" id="appearance-toggle" title="Light or dark" aria-label="Toggle light or dark"><svg viewBox="0 0 24 24">{ICONS['sun']}</svg></button>
    </div>
    <div class="masthead__tools">
      <a class="masthead__apply t-label-small" href="#">Apply</a>
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
    logos = "".join(f"<span>{e(x)}</span>" for x in f["collaborations"]["logos"])
    return f"""<footer class="pagefoot">
  <div class="grid">
    <div class="footcol">{primary}</div>
    <div class="footcol">{secondary}</div>
    <div class="footcol"><h2 class="t-label-overline">{e(c['heading'])}</h2>{contact}</div>
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


def render_page(page, foot, titles):
    global PREFIX
    depth = len([p for p in page["slug"].split("/") if p])
    PREFIX = "../" * depth if depth else "./"

    home = page.get("template") == "home"
    blocks = []
    if not home:
        blocks.append(f'<div class="rail"><h1 class="pagetitle t-heading-1">{e(page["title"])}</h1></div>')
    else:
        blocks.append(f'<h1 class="visually-hidden">{e(page["title"])}</h1>')

    # Utility slot: back-navigation on any page with a parent, labelled with the
    # parent's title — derived, never authored.
    if page.get("parent"):
        parent_title = titles.get(page["parent"], page["parent"].split("/")[-1].replace("-", " ").title())
        blocks.append('<div class="aside utility">'
                      + cta({"label": parent_title, "page": page["parent"]}, "t-heading-5", kind="back")
                      + "</div>")

    if page.get("keyInfo"):
        rows = "".join(
            f'<div class="keyinfo__row"><dt class="t-label-overline">{e(k["label"])}</dt>'
            f'<dd class="t-heading-5">{e(k["value"])}</dd></div>' for k in page["keyInfo"])
        blocks.append(f'<dl class="rail keyinfo">{rows}</dl>')

    if page.get("subPages"):
        blocks.append('<nav class="rail linklist" aria-label="In this section">'
                      + "".join(cta(l) for l in page["subPages"]) + "</nav>")

    if page.get("hero"):
        blocks.append('<div class="content">' + media(page["hero"], "media--hero", page["hero"].get("asset")) + "</div>")

    if page.get("intro"):
        blocks.append(f'<div class="measure"><p class="intro t-body-large-regular">{e(page["intro"])}</p></div>')

    for s in page.get("sections", []):
        if not home:
            blocks.append('<hr class="hr">')
        r = RENDERERS.get(s["type"])
        if not r:
            raise SystemExit(f'Unknown section type: {s["type"]}')
        cls = "section section--aside" if s.get("links") else "section"
        blocks.append(f'<div class="{cls}">' + "".join(x for x in r(s) if x) + "</div>")

    body = "\n    ".join(blocks)
    desc = (page.get("intro") or page["title"])[:155]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(page['title'])}{"" if page.get("template") == "home" else " — National Institute of Design"}</title>
<meta name="description" content="{e(desc)}">
{FONT_LINKS}
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
{footer(foot)}
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

    data = json.loads((SRC / "content" / "pages.json").read_text(encoding="utf-8"))
    pages, foot = data["pages"], data["footer"]

    titles = {p["slug"]: p["title"] for p in pages}
    TITLE_INDEX.clear()
    for p in pages:
        TITLE_INDEX[norm(p["title"])] = p["slug"]

    # Clean the output directory, but tolerate filesystems that refuse deletes
    # (network mounts, sandboxed volumes) — writing over the top still produces
    # a correct build, it just leaves any stale file behind.
    if DIST.exists():
        try:
            shutil.rmtree(DIST)
        except OSError as err:
            print(f"  note: could not clear {DIST.name}/ ({err.strerror}); overwriting in place")
    (DIST / "styles").mkdir(parents=True, exist_ok=True)
    for css in ("tokens.css", "base.css"):
        shutil.copy(SRC / "styles" / css, DIST / "styles" / css)
    # base.css references ../pattern-tile.svg relative to itself
    shutil.copy(SRC / "assets" / "pattern-tile.svg", DIST / "pattern-tile.svg")
    pub = ROOT / "public"
    if pub.exists():
        shutil.copytree(pub, DIST, dirs_exist_ok=True)
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    for p in pages:
        out = DIST / p["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_page(p, foot, titles), encoding="utf-8")
        print(f"  {p['slug'] or '(root)':52s} {p['title'][:40]}")

    # The page with an empty slug IS the site root. Only fall back to a redirect
    # if no such page exists — otherwise this would overwrite the home page that
    # the loop above just wrote.
    if not any(p["slug"] == "" for p in pages):
        first = pages[0]["slug"]
        target = f"{BASE}/{first}/" if BASE else f"./{first}/"
        (DIST / "index.html").write_text(
            f'<!doctype html><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={target}">'
            f'<title>NID</title><a href="{target}">{e(pages[0]["title"])}</a>',
            encoding="utf-8")
        print(f"  (root)  -> redirect to /{first}/")

    print(f"built {len(pages)} pages into {DIST}" + (f' with base "{BASE}"' if BASE else ""))


if __name__ == "__main__":
    main()
