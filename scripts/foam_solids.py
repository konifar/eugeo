"""3D solids of the foam pieces, read back from their KiCad Edge.Cuts (for the fit check and renders).

    foam_solid("foam/eugeo-case-foam-left.kicad_pcb", z0, thickness)  # in case coordinates
"""
import math
import os
import sys

from build123d import Face, Polyline, Pos, Wire, extrude

sys.path.insert(0, os.path.dirname(__file__))
import case as C  # noqa: E402
import design  # noqa: E402
from export_yushakobo_svg import edge_loops  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def loop_points(loop, step=0.5):
    if loop[0][0] == "circle":
        (cx, cy), r = loop[0][1], loop[0][2]
        n = max(24, int(2 * math.pi * r / step))
        return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    pts = []
    for s in loop:
        if s[0] == "line":
            pts.append(s[1])
        else:                                          # arc through start / mid / end
            (sx, sy), (mx, my), (tx, ty) = s[1], s[3], s[2]
            a = 2 * (sx * (my - ty) + mx * (ty - sy) + tx * (sy - my))
            ux = ((sx * sx + sy * sy) * (my - ty) + (mx * mx + my * my) * (ty - sy) + (tx * tx + ty * ty) * (sy - my)) / a
            uy = ((sx * sx + sy * sy) * (tx - mx) + (mx * mx + my * my) * (sx - tx) + (tx * tx + ty * ty) * (mx - sx)) / a
            r = math.dist((ux, uy), (sx, sy))
            a0, am, a1 = (math.atan2(p[1] - uy, p[0] - ux) for p in ((sx, sy), (mx, my), (tx, ty)))
            span = (a1 - a0) % (2 * math.pi)
            if (am - a0) % (2 * math.pi) > span:       # goes the other way round
                span -= 2 * math.pi
            n = max(4, int(abs(span) * r / step))
            pts += [(ux + r * math.cos(a0 + span * i / n), uy + r * math.sin(a0 + span * i / n)) for i in range(n)]
    return pts


def foam_solid(board, z0, thickness):
    ox, oy = design.FOAM_PAGE_OFFSET
    faces = []
    for loop in edge_loops(os.path.join(ROOT, board)):
        pts = [C.to_case(x - ox, y - oy) for x, y in loop_points(loop)]
        faces.append(Face(Wire(Polyline(*pts, close=True))))
    faces.sort(key=lambda f: -f.area)
    face = faces[0]
    for h in faces[1:]:
        face = face - h
    return extrude(Pos(0, 0, z0) * face, amount=thickness, dir=(0, 0, 1))
