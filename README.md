# NID website — build from the Figma design system

A working build of the NID website driven by the same tokens the Figma file
uses. The whole **About NID** section is built — 11 pages — extracted
automatically from the Figma boards rather than hand-authored, and rendered
through the six section types in the CMS model.

## Why it is shaped this way

The Figma file is unusually disciplined: every page sits on a real grid, and
2,857 of 2,858 text nodes carry a text style whose size and line height are bound
to variables. That means the translation is mechanical rather than interpretive,
so nothing here hard-codes a size, colour, or breakpoint value. Change a variable
in Figma, re-export, rebuild, and the site moves with it.

Three layers, mirroring the Figma variable collections exactly:

| Figma collection | Becomes | Selector |
|---|---|---|
| Theme (10 modes) | Colour ramps | `[data-theme="lotus"]` … |
| Appearance (Light/Dark) | Semantic colour | `[data-appearance="dark"]` |
| Breakpoint (4 modes) | Type scale and grid metrics | `:root` + media queries |

The palette button in the header cycles all ten themes; the sun button toggles
light and dark. Both work because the semantic layer only ever aliases
primitives, never literal colours — the same indirection the Figma file uses.

## Build

Python 3.9+ and nothing else. No npm, no lockfile, no install step.

```bash
python3 tokens/build_tokens.py    # figma-tokens.json -> src/styles/tokens.css
python3 build.py                  # src/content/*.json -> dist/
open dist/about-nid/index.html
```

For a GitHub project page served from a sub-path:

```bash
python3 build.py --base=/nid-website
```

## Layout

```
tokens/figma-tokens.json   Exported from the Figma variable collections
tokens/build_tokens.py     Generates tokens.css — do not hand-edit the CSS
tokens/extractor.js        Reads the Figma page boards -> src/content/pages.json
src/assets/logo.svg        The real NID logo, exported from the file
src/content/pages.json     All page content in the CMS shape
src/styles/base.css        Grid and components; consumes tokens only
build.py                   Static generator, six section types
.github/workflows/         Builds and publishes to Pages on push to main
```

## Refreshing content from Figma

`tokens/extractor.js` runs inside Figma (via the Figma MCP `use_figma` tool) and
walks each page board: it reads the grid, splits sections on the separator rows,
and classifies each one by what it contains — cards, links, or prose. Text is
classified by the Figma text style it carries rather than by position, so a
headline stays a headline even when the overline moves. Set `SLICE_FROM` and
`SLICE_TO` to page through the boards within the tool's response-size limit.

## Content model

`src/content/pages.json` holds every page record, in the shape the
*CMS & Data Model — Backend Reference* describes: fixed fields plus an ordered
list of sections, each declaring a type. Six types and no more —
`text`, `links`, `cards`, `files`, `rail`, `mosaic`.

Link icons are **derived from `targetType`**, never authored: `page` and
`external` get the up-right arrow, `document` gets the file icon, `email` and
`phone` get none. This is the rule the design file settled on, enforced in one
place (`LINK_ICON` in `build.py`) rather than repeated per link.

## Verified

`python3 shots.py` renders at 1440 / 1024 / 768 / 390 and asserts the measured
geometry against the Figma token values. Current result:

| Breakpoint | Columns | Page margin | Gutter | Content width | H1 | Intro | Separators |
|---|---|---|---|---|---|---|---|
| 1440 | 4 | 24 | 24 | 1392 | 60 | 24 | shown |
| 1024 | 3 | 24 | 24 | 976 | 52 | 22 | shown |
| 768 | 2 | 24 | 20 | 720 | 40 | 20 | shown |
| 390 | 1 | 16 | 16 | 358 | 32 | 18 | hidden |

Every figure matches the Breakpoint collection. The reflow rules the artboards
demonstrate are reproduced from tokens rather than redrawn: the label rail in
column 1 becomes a full-width band at two columns and below, column-four links
drop beneath the content, cards go 3 → 2 → 2 → 1, separators disappear at one
column, and the footer runs 4 across → 3 with the fourth wrapping → 2×2 →
stacked purely through grid auto-placement.

## Known gaps

**Fonts.** Merriweather Sans is the real body face and is now loaded from
Google Fonts. Futura PT and Bodoni PT VF are licensed and cannot be served from
here, so **Jost** and **Bodoni Moda** stand in — Jost is a Futura-derived
geometric sans and reads very close at heading sizes. Both licensed names are
listed *first* in the token font stacks, so adding an Adobe Fonts web project
embed to `FONT_LINKS` in `build.py` makes the real faces take over with no other
change.

**Images.** Every image is a labelled placeholder tile at the correct aspect
ratio. The build environment could not reach Figma's asset CDN. Export the
originals into `public/img/<asset>.jpg` using the `asset` names already in the
content JSON and they appear with no code change.

**The pattern strip** at the top and bottom of each page is a CSS approximation
of the block-print band, standing in until the real SVG is exported.

**Coverage.** 11 pages — the whole About NID section — of roughly 110 in the
architecture. The extractor handles any board built on the standard chassis, so
the remaining sections are a re-run rather than new work.

## Deploying

Push to `main` with Pages set to "GitHub Actions" as the source
(Settings → Pages → Build and deployment). The workflow needs no secrets and
installs nothing. For a user or organisation page rather than a project page,
drop the `--base` argument from the build step.
