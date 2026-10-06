"""Generate switch plate (one half, order 2 pcs) and bottom plate as KiCad boards.

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


def rounded_rect(board, x1, y1, x2, y2, r):
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)

    def arc(c, start):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetCenter(P(*c))
        s.SetStart(P(*start))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)

    if r <= 0:
        seg((x1, y1), (x2, y1)); seg((x2, y1), (x2, y2)); seg((x2, y2), (x1, y2)); seg((x1, y2), (x1, y1))
        return
    seg((x1 + r, y1), (x2 - r, y1))
    seg((x2, y1 + r), (x2, y2 - r))
    seg((x2 - r, y2), (x1 + r, y2))
    seg((x1, y2 - r), (x1, y1 + r))
    arc((x2 - r, y1 + r), (x2 - r, y1))
    arc((x2 - r, y2 - r), (x2, y2 - r))
    arc((x1 + r, y2 - r), (x1 + r, y2))
    arc((x1 + r, y1 + r), (x1, y1 + r))


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
    half_x2 = design.KEY_X[5] + design.U / 2 - 0.425
    path, b = new_board("eugeo-plate")
    rounded_rect(b, x1, y1, half_x2, y2, R)
    for cx in design.KEY_X[:6]:
        for cy in design.KEY_Y:
            rounded_rect(b, cx - CUT / 2, cy - CUT / 2, cx + CUT / 2, cy + CUT / 2, CUT_R)
    for hx, hy in design.HOLES[:4]:
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
