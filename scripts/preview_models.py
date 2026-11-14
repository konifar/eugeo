"""Illustrative parts for renders only (not for manufacturing): switch plates, gasket pads,
foams, rubber feet, simple MX switch tops and keycaps, in case coordinates.

    .venv/bin/python scripts/preview_models.py /tmp/eugeo-preview
    Blender -b -P scripts/render_case.py -- case/eugeo-case.stl /tmp/eugeo-pcb.glb out.png asm hero \
        /tmp/eugeo-preview/plates.stl:plate /tmp/eugeo-preview/switches.stl:switch \
        /tmp/eugeo-preview/keycaps.stl:keycap case/eugeo-cover.stl:acrylic
"""
import math
import os
import sys

from build123d import (Align, BuildPart, BuildSketch, Circle, Compound, Cylinder, Locations, Mode, Plane, Pos,
                       Rectangle, RectangleRounded, export_stl, extrude, loft)

sys.path.insert(0, os.path.dirname(__file__))
import case as C  # noqa: E402
import design  # noqa: E402


def main(out):
    os.makedirs(out, exist_ok=True)
    x1, y1, x2, y2 = design.EDGE
    half = design.PLATE_X[1]
    plates, pads, pads_lo, foams, case_foams, feet = [], [], [], [], [], []
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
            for z0, dst in ((C.PLATE_TOP - 1.5 - g, pads_lo), (C.PLATE_TOP, pads)):
                with BuildPart() as pad:
                    with BuildSketch(Plane.XY.offset(z0)):
                        with Locations((tx, ty)):
                            Rectangle(sx - 0.4, sy - 0.4)
                    extrude(amount=g)
                dst.append(pad.part)
        mirror = (lambda x: 2 * design.CENTER_X - x) if right else (lambda x: x)
        with BuildPart() as pf:                          # plate foam: PCB top up 3 mm
            with BuildSketch(Plane.XY.offset(C.PCB_T)):
                with Locations(C.to_case((a + b) / 2, (y1 + y2) / 2)):
                    RectangleRounded(b - a, y2 - y1, 1.0)
                with Locations(*[C.to_case(kx, ky) for kx in design.KEY_X for ky in design.KEY_Y if a < kx < b]):
                    RectangleRounded(14.5, 14.5, 0.5, mode=Mode.SUBTRACT)
                with Locations(*[C.to_case(mirror(hx), hy) for hx, hy in design.HOLES[:4]]):
                    Circle(2.2, mode=Mode.SUBTRACT)
            extrude(amount=3.0)
        foams.append(pf.part)
        inset = design.CASE_CLEARANCE - 0.5              # case foam on the floor
        fa, fb = sorted((mirror(x1 - inset), mirror(design.LEFT_END - 0.5)))
        with BuildPart() as cf:
            with BuildSketch(Plane.XY.offset(C.FLOOR_TOP)):
                with Locations(C.to_case((fa + fb) / 2, (y1 + y2) / 2)):
                    RectangleRounded(fb - fa, y2 - y1 + 2 * inset, 1.5)
                with Locations(*[C.to_case(mirror(hx), hy) for hx, hy in design.HOLES[:4]]):
                    Circle((design.CASE_BOSS_D + 1.5) / 2, mode=Mode.SUBTRACT)
            extrude(amount=3.0)
        case_foams.append(cf.part)
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
    t = math.tan(math.radians(C.ANGLE))                  # rubber feet on the corner lands
    for fx in (-141.45, 141.45):
        for fy in (-36.2, 36.2):
            zb = C.FRONT_BOTTOM - (fy + 93.35 / 2) * t
            feet.append(Pos(fx, fy, zb - 2.0) * Cylinder(4.5, 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN)))
    for name, parts in (("plates", plates), ("pads", pads), ("pads-lower", pads_lo), ("plate-foams", foams),
                        ("case-foams", case_foams), ("feet", feet), ("switches", switches), ("keycaps", caps)):
        export_stl(Compound(parts), os.path.join(out, f"{name}.stl"))
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
