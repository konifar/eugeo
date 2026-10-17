"""Illustrative parts for renders only (not for manufacturing): switch plates, simple MX
switch tops and keycaps, in case coordinates.

    .venv/bin/python scripts/preview_models.py /tmp/eugeo-preview
    Blender -b -P scripts/render_case.py -- case/eugeo-case.stl /tmp/eugeo-pcb.glb out.png asm hero \
        /tmp/eugeo-preview/plates.stl:plate /tmp/eugeo-preview/switches.stl:switch \
        /tmp/eugeo-preview/keycaps.stl:keycap case/eugeo-cover.stl:acrylic
"""
import os
import sys

from build123d import (BuildPart, BuildSketch, Compound, Locations, Mode, Plane, Rectangle,
                       RectangleRounded, export_stl, extrude, loft)

sys.path.insert(0, os.path.dirname(__file__))
import case as C  # noqa: E402
import design  # noqa: E402


def main(out):
    os.makedirs(out, exist_ok=True)
    x1, y1, x2, y2 = design.EDGE
    half = design.PLATE_X[1]
    plates, pads = [], []
    w, d, g = design.GASKET_TAB_W, design.GASKET_TAB_D, design.GASKET_GAP
    for right, (a, b) in ((False, (x1, half)), (True, (x2 - (half - x1), x2))):
        tabs = []
        for edge, pos in design.gasket_tabs(right):
            if edge in ("back", "front"):
                ty = (y1 - d / 2) if edge == "back" else (y2 + d / 2)
                tabs.append((C.to_case(pos, ty), (w, d)))
            else:
                tx = (x2 + d / 2) if right else (x1 - d / 2)
                tabs.append((C.to_case(tx, pos), (d, w)))
        with BuildPart() as p:
            with BuildSketch(Plane.XY.offset(C.PLATE_TOP - 1.5)):
                with Locations(C.to_case((a + b) / 2, (y1 + y2) / 2)):
                    RectangleRounded(b - a, y2 - y1, 1.0)
                for (tx, ty), (sx, sy) in tabs:
                    with Locations((tx, ty)):
                        Rectangle(sx, sy)
                with Locations(*[C.to_case(kx, ky) for kx in design.KEY_X for ky in design.KEY_Y if a < kx < b]):
                    RectangleRounded(14, 14, 0.5, mode=Mode.SUBTRACT)
            extrude(amount=1.5)
        plates.append(p.part)
        for (tx, ty), (sx, sy) in tabs:                  # PORON pads (compressed) above and below
            for z0 in (C.PLATE_TOP - 1.5 - g, C.PLATE_TOP):
                with BuildPart() as pad:
                    with BuildSketch(Plane.XY.offset(z0)):
                        with Locations((tx, ty)):
                            Rectangle(sx - 0.4, sy - 0.4)
                    extrude(amount=g)
                pads.append(pad.part)
    switches, caps = [], []
    for kx in design.KEY_X:
        for ky in design.KEY_Y:
            x, y = C.to_case(kx, ky)
            with BuildPart() as s:                       # top housing + stem
                with BuildSketch(Plane.XY.offset(C.PLATE_TOP)):
                    with Locations((x, y)):
                        RectangleRounded(15, 15, 1.0)
                with BuildSketch(Plane.XY.offset(C.PLATE_TOP + 6)):
                    with Locations((x, y)):
                        RectangleRounded(11, 11, 1.0)
                loft()
                with BuildSketch(Plane.XY.offset(C.PLATE_TOP + 6)):
                    with Locations((x, y)):
                        Rectangle(4, 4)
                extrude(amount=2)
            switches.append(s.part)
            with BuildPart() as k:                       # generic keycap
                with BuildSketch(Plane.XY.offset(C.PLATE_TOP + 7)):
                    with Locations((x, y)):
                        RectangleRounded(18, 18, 1.5)
                with BuildSketch(Plane.XY.offset(C.PLATE_TOP + 15)):
                    with Locations((x, y)):
                        RectangleRounded(13, 14, 2.0)
                loft()
            caps.append(k.part)
    for name, parts in (("plates", plates), ("pads", pads), ("switches", switches), ("keycaps", caps)):
        export_stl(Compound(parts), os.path.join(out, f"{name}.stl"))
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
