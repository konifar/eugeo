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
    half = design.KEY_X[5] + design.U / 2 - 0.425
    plates = []
    for a, b in ((x1, half), (x2 - (half - x1), x2)):
        with BuildPart() as p:
            with BuildSketch(Plane.XY.offset(C.PLATE_TOP - 1.5)):
                with Locations(C.to_case((a + b) / 2, (y1 + y2) / 2)):
                    RectangleRounded(b - a, y2 - y1, 1.0)
                with Locations(*[C.to_case(kx, ky) for kx in design.KEY_X for ky in design.KEY_Y if a < kx < b]):
                    RectangleRounded(14, 14, 0.5, mode=Mode.SUBTRACT)
            extrude(amount=1.5)
        plates.append(p.part)
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
    for name, parts in (("plates", plates), ("switches", switches), ("keycaps", caps)):
        export_stl(Compound(parts), os.path.join(out, f"{name}.stl"))
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
