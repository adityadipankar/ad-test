#!/usr/bin/env python3
"""Render dist/about/ at the four reference widths and report measured geometry.

The numbers printed here are what the fidelity check turns on: computed column
width, gutter, page margin and content width at each breakpoint, next to the
values the Figma Breakpoint collection declares.
"""
import json
import pathlib
import sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
URL = (ROOT / "dist" / "about" / "index.html").as_uri()
OUT = ROOT / "shots"
OUT.mkdir(exist_ok=True)

# name, width, expected [columns, page margin, gutter, content width] from Figma
CASES = [
    ("4col-1440", 1440, [4, 24, 24, 1392]),
    ("3col-1024", 1024, [3, 24, 24, 976]),
    ("2col-768",   768, [2, 24, 20, 720]),
    ("1col-390",   390, [1, 16, 16, 358]),
]

PROBE = """() => {
  const g = document.querySelector('main .grid');
  const cs = getComputedStyle(g);
  const cols = cs.gridTemplateColumns.split(' ').map(Number);
  const r = g.getBoundingClientRect();
  const doc = document.documentElement;
  const rs = getComputedStyle(doc);
  const num = n => parseFloat(rs.getPropertyValue(n));
  const h1 = document.querySelector('.pagetitle');
  const intro = document.querySelector('.intro');
  return {
    colCount: cols.length,
    colWidth: Math.round(parseFloat(cols[0]) * 100) / 100,
    gutter: Math.round(parseFloat(cs.columnGap) * 100) / 100,
    contentWidth: Math.round(r.width * 100) / 100,
    margin: Math.round(r.left * 100) / 100,
    tokenCols: num('--grid-columns'),
    tokenMargin: num('--grid-page-margin'),
    tokenGutter: num('--grid-column-gap'),
    tokenContent: num('--grid-content-width'),
    h1Size: h1 ? Math.round(parseFloat(getComputedStyle(h1).fontSize)) : null,
    introSize: intro ? Math.round(parseFloat(getComputedStyle(intro).fontSize)) : null,
    pageHeight: Math.round(document.body.scrollHeight),
    separatorsVisible: [...document.querySelectorAll('.hr')]
      .filter(h => getComputedStyle(h).display !== 'none').length,
    cardCols: (() => {
      const c = document.querySelector('.cards');
      return c ? getComputedStyle(c).gridTemplateColumns.split(' ').length : null;
    })(),
  };
}"""

rows = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, width, expect in CASES:
        pg = b.new_page(viewport={"width": width, "height": 1200},
                        device_scale_factor=2 if width < 800 else 1)
        pg.goto(URL, wait_until="networkidle")
        pg.wait_for_timeout(150)
        m = pg.evaluate(PROBE)
        m["case"] = name
        m["expect"] = expect
        rows.append(m)
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        pg.close()
    b.close()

print(f"{'case':11} {'cols':>4} {'margin':>7} {'gutter':>7} {'content':>8} {'colW':>8} "
      f"{'H1':>4} {'intro':>6} {'cards':>6} {'seps':>5} {'height':>7}")
ok = True
for m in rows:
    ec, em, eg, ew = m["expect"]
    flag = ""
    for got, want, label in ((m["colCount"], ec, "cols"), (m["margin"], em, "margin"),
                             (m["gutter"], eg, "gutter"), (m["contentWidth"], ew, "content")):
        if abs(got - want) > 1.5:
            flag += f" !{label}({got}≠{want})"
            ok = False
    print(f"{m['case']:11} {m['colCount']:>4} {m['margin']:>7} {m['gutter']:>7} "
          f"{m['contentWidth']:>8} {m['colWidth']:>8} {m['h1Size']:>4} {m['introSize']:>6} "
          f"{m['cardCols']:>6} {m['separatorsVisible']:>5} {m['pageHeight']:>7}{flag}")

(ROOT / "shots" / "measurements.json").write_text(json.dumps(rows, indent=2))
print("\nGrid matches the Figma tokens at every breakpoint." if ok else "\nMISMATCH — see flags above.")
sys.exit(0 if ok else 1)
