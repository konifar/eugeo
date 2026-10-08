"""Outline the back-side logo (Futura, as on the case nameplate) into plain polygons.

    .venv/bin/python scripts/logo_outline.py      # -> scripts/logo_eugeo.json

KiCad's python cannot pick a TrueType face, so the letters are converted here and
stump_art.py draws them as filled B.Silkscreen polygons. Letters with a counter
(the O) are cut in two so every polygon is hole-free. Coordinates are in mm, y up,
with the logo centred on (0, 0) as read from the back.
"""
import json
import os
import sys

from build123d import Align, Box, Location, Text

sys.path.insert(0, os.path.dirname(__file__))
import case as C  # noqa: E402  (same face as the case nameplate)

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = C.BADGE_TEXT                 # "EUGEO"
SIZE = 9.4                          # cap height ~7.5 mm
TRACKING = 4.0
STEP = 0.15                         # max chord length when flattening curves


def flatten(wire):
    pts = []
    for e in wire.edges():
        n = max(2, int(e.length / STEP) + 1)
        seg = [e.position_at(i / (n - 1)) for i in range(n)]
        if pts and (pts[-1] - seg[0]).length > 1e-6 and (pts[-1] - seg[-1]).length < 1e-6:
            seg.reverse()
        if pts:
            seg = seg[1:]
        pts += seg
    return [(round(p.X, 4), round(p.Y, 4)) for p in pts]


def main():
    letters, x = [], 0.0
    for ch in TEXT:
        t = Text(ch, SIZE, font=C.BADGE_FONT, align=(Align.MIN, Align.NONE))
        bb = t.bounding_box()
        t = t.moved(Location((x - bb.min.X, 0, 0)))
        letters.append(t)
        x += bb.size.X + TRACKING
    width = x - TRACKING
    polys = []
    ys = []
    for t in letters:
        for f in t.faces():
            parts = [f]
            if f.inner_wires():
                bb = f.bounding_box()
                cx = (bb.min.X + bb.max.X) / 2
                big = 4 * max(bb.size.X, bb.size.Y)
                parts = []
                for sx in (-1, 1):
                    half = Box(big, big, 1).moved(Location((cx + sx * big / 2, (bb.min.Y + bb.max.Y) / 2, 0)))
                    parts += (f & half).faces()
            for p in parts:
                pts = flatten(p.outer_wire())
                polys.append(pts)
                ys += [y for _, y in pts]
    cy = (min(ys) + max(ys)) / 2
    polys = [[(round(px - width / 2, 4), round(py - cy, 4)) for px, py in pts] for pts in polys]
    out = {"text": TEXT, "font": C.BADGE_FONT, "width": round(width, 3),
           "height": round(max(ys) - min(ys), 3), "polygons": polys}
    with open(os.path.join(HERE, "logo_eugeo.json"), "w") as fh:
        json.dump(out, fh)
    print(f"logo {TEXT}: {out['width']} x {out['height']} mm, {len(polys)} polygons")


if __name__ == "__main__":
    main()
