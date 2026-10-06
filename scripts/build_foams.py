"""Plate foam and case foam outlines (KiCad boards -> DXF / 1:1 PDF via export_foams).

    $KP scripts/build_foams.py

Both pieces are left/right symmetric: cut one shape twice (flip it for the other side).
  plate foam : between switch plate and PCB (3.5 mm gap), same outline as the plate
  case foam  : between PCB and case floor (5 mm gap; 3 mm foam clears the 1.8 mm sockets),
               key area only - the centre (diodes / MCU / USB-C) stays open
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import build_plates as bp  # noqa: E402
import design  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SWITCH_CUT = 14.5        # clears the switch bottom housing under the plate
STANDOFF_HOLE = 5.0      # M2 3.5 mm hex standoff
BOSS_HOLE = design.CASE_BOSS_D + 1.5
CASE_FOAM_INSET = 0.5    # foam smaller than the case pocket on every side
CENTER_GAP = 0.5         # case foam stops this far before the centre component area


PAGE_OFFSET = (20.0, 20.0)   # keep the 1:1 print clear of printer margins


def finish(board, path, label):
    """Shift everything onto the page and add a 100 mm scale bar for checking the print."""
    for d in board.GetDrawings():
        d.Move(bp.P(*PAGE_OFFSET))
    bb = board.GetBoardEdgesBoundingBox()
    x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetBottom()) + 12
    for a, b in (((x0, y0), (x0 + 100, y0)), ((x0, y0 - 2), (x0, y0 + 2)), ((x0 + 100, y0 - 2), (x0 + 100, y0 + 2))):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(bp.P(*a))
        s.SetEnd(bp.P(*b))
        s.SetLayer(pcbnew.Dwgs_User)
        s.SetWidth(pcbnew.FromMM(0.2))
        board.Add(s)
    for text, y in ((f"100 mm (print at 100% / actual size)", y0 + 5), (label, y0 + 10)):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.Dwgs_User)
        t.SetPosition(bp.P(x0, y))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(3), pcbnew.FromMM(3)))
        t.SetTextThickness(pcbnew.FromMM(0.3))
        board.Add(t)
    pcbnew.SaveBoard(path, board)
    print("wrote", path)


def new_board(name):
    path = os.path.join(ROOT, "foam", name + ".kicad_pcb")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    return path, pcbnew.NewBoard(path)


def main():
    x1, y1, x2, y2 = design.EDGE
    half_x2 = design.KEY_X[5] + design.U / 2 - 0.425

    path, b = new_board("eugeo-plate-foam")
    bp.rounded_rect(b, x1, y1, half_x2, y2, bp.R)
    for cx in design.KEY_X[:6]:
        for cy in design.KEY_Y:
            h = SWITCH_CUT / 2
            bp.rounded_rect(b, cx - h, cy - h, cx + h, cy + h, 0.5)
    for hx, hy in design.HOLES[:4]:
        bp.hole(b, hx, hy, STANDOFF_HOLE)
    finish(b, path, "eugeo plate foam - cut 2 (flip one), 3.5 mm PORON / PE")

    # case foam: pocket outline minus inset, cut short of the centre area
    pocket = design.CASE_CLEARANCE - CASE_FOAM_INSET
    path, b = new_board("eugeo-case-foam")
    bp.rounded_rect(b, x1 - pocket, y1 - pocket, design.LEFT_END - CENTER_GAP, y2 + pocket, 1.5)
    for hx, hy in design.HOLES[:4]:
        bp.hole(b, hx, hy, BOSS_HOLE)
    finish(b, path, "eugeo case foam - cut 2 (flip one), 3 mm PORON / EVA")


if __name__ == "__main__":
    main()
