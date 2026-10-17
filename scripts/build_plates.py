"""Generate switch plate (one half with gasket tabs, order 2 pcs; turn one over for the right) and bottom plate as KiCad boards.

    $KP scripts/build_plates.py
Then export DXF / gerbers with kicad-cli (see README).
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import design  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUT = 14.0          # MX switch cutout
CUT_R = 0.5         # inner corner radius (JLCPCB routes with a round bit anyway)
R = 1.0             # outer corner radius


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def seg(board, a, b):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(pcbnew.FromMM(0.1))
    board.Add(s)


def arc(board, c, start):
    """90 degree arc around c, clockwise on screen (y down) from start."""
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
    s.SetCenter(P(*c))
    s.SetStart(P(*start))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(pcbnew.FromMM(0.1))
    board.Add(s)


def rounded_rect(board, x1, y1, x2, y2, r, tabs=(), tab_w=0.0, tab_d=0.0):
    """Rounded rectangle; tabs = [(edge, pos)] with edge back (y1) / front (y2) / outer (x1)."""
    def edge_with_tabs(a, b, along, out):
        # a -> b is a straight edge; insert rectangular tabs at the given positions along it
        pts = [a]
        ax, ay = a
        horiz = a[1] == b[1]
        sign = 1 if (b[0] - a[0] if horiz else b[1] - a[1]) > 0 else -1
        for pos in sorted(along, key=lambda p: sign * p):
            lo, hi = pos - sign * tab_w / 2, pos + sign * tab_w / 2
            if horiz:
                pts += [(lo, ay), (lo, ay + out), (hi, ay + out), (hi, ay)]
            else:
                pts += [(ax, lo), (ax + out, lo), (ax + out, hi), (ax, hi)]
        pts.append(b)
        for p, q in zip(pts, pts[1:]):
            seg(board, p, q)

    if r <= 0 and not tabs:
        for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
            seg(board, a, b)
        return
    at = lambda e: [p for k, p in tabs if k == e]
    edge_with_tabs((x1 + r, y1), (x2 - r, y1), at("back"), -tab_d)
    edge_with_tabs((x2, y1 + r), (x2, y2 - r), [], 0)
    edge_with_tabs((x2 - r, y2), (x1 + r, y2), at("front"), tab_d)
    edge_with_tabs((x1, y2 - r), (x1, y1 + r), at("outer"), -tab_d)
    arc(board, (x2 - r, y1 + r), (x2 - r, y1))
    arc(board, (x2 - r, y2 - r), (x2, y2 - r))
    arc(board, (x1 + r, y2 - r), (x1 + r, y2))
    arc(board, (x1 + r, y1 + r), (x1, y1 + r))


def hole(board, x, y, d=2.2):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
    s.SetCenter(P(x, y))
    s.SetEnd(P(x + d / 2, y))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(pcbnew.FromMM(0.1))
    board.Add(s)


def label(board, text, x, y):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(P(x, y))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.2), pcbnew.FromMM(1.2)))
    t.SetTextThickness(pcbnew.FromMM(0.18))
    board.Add(t)


def new_board(name):
    path = os.path.join(ROOT, "plates", name + ".kicad_pcb")
    if os.path.exists(path):
        os.remove(path)
    return path, pcbnew.NewBoard(path)


def main():
    x1, y1, x2, y2 = design.EDGE
    # switch plate: left half only (the right half is identical), keys 6 x 4
    half_x2 = design.PLATE_X[1]
    path, b = new_board("eugeo-plate")
    rounded_rect(b, x1, y1, half_x2, y2, R, design.gasket_tabs(), design.GASKET_TAB_W, design.GASKET_TAB_D)
    for cx in design.KEY_X[:6]:
        for cy in design.KEY_Y:
            rounded_rect(b, cx - CUT / 2, cy - CUT / 2, cx + CUT / 2, cy + CUT / 2, CUT_R)
    for hx, hy in design.HOLES[:4]:
        hole(b, hx, hy)
    pcbnew.SaveBoard(path, b)
    print("wrote", path)

    # centre cover: 2 mm acrylic on 10 mm standoffs (Lumberjack style)
    path, b = new_board("eugeo-cover")
    (cx1, cx2), (cy1, cy2) = design.COVER_X, design.COVER_Y
    rounded_rect(b, cx1, cy1, cx2, cy2, design.COVER_R)
    for hx, hy in design.COVER_HOLES:
        hole(b, hx, hy)
    pcbnew.SaveBoard(path, b)
    print("wrote", path)

    # bottom plate: full outline + 8 holes
    path, b = new_board("eugeo-bottom")
    rounded_rect(b, x1, y1, x2, y2, R)
    for hx, hy in design.HOLES:
        hole(b, hx, hy)
    label(b, f"eugeo rev{design.REV}", design.CENTER_X, (y1 + y2) / 2)
    pcbnew.SaveBoard(path, b)
    print("wrote", path)


if __name__ == "__main__":
    main()
