"""Plate foam and case foam outlines (KiCad boards -> DXF / 1:1 PDF via export_foams).

    $KP scripts/build_foams.py

Both pieces are left/right symmetric: cut one shape twice (flip it for the other side).
  plate foam : between switch plate and PCB (3.5 mm gap, 3 mm PORON), same outline as the plate
  case foam  : between PCB and the raised floor under the key areas (2.8 mm gap, 3 mm foam
               lightly squeezed), cut out around the hot-swap sockets, switch centre posts and
               pegs, key area only - the centre (diodes / MCU / USB-C) stays open. The sockets
               face the same way on both halves, so the left and right pieces differ.
  gasket pad : 10 x 4 mm, one above and one below each plate tab (20 in all)
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import build_plates as bp  # noqa: E402
import design  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SWITCH_CUT = 14.5        # clears the switch bottom housing under the plate
STANDOFF_HOLE = 4.4      # M2 3.5 mm hex standoff (~4.0 mm across corners); keeps a 1 mm web to the switch cut-outs
BOSS_HOLE = design.CASE_BOSS_D + 1.5   # M2 screw heads under the PCB (plate / PCB sandwich)
CASE_FOAM_INSET = 0.5    # foam smaller than the case pocket on every side
CENTER_GAP = 0.5         # case foam stops this far before the centre component area
GASKET_PADS = 4 * len(design.gasket_tabs())   # above + below each tab, two plates


PAGE_OFFSET = design.FOAM_PAGE_OFFSET   # keep the 1:1 print clear of printer margins


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


SOCKET_MARGIN = 0.5      # around the socket body / pads and the switch holes


def socket_cutouts(board_path, x_range):
    """Union of the hot-swap socket keep-outs (B.Fab body, B-side pads, centre post and peg
    holes, plus SOCKET_MARGIN) of every switch within x_range, from the PCB itself."""
    pcb = pcbnew.LoadBoard(board_path)
    mm, m = pcbnew.ToMM, SOCKET_MARGIN
    poly = pcbnew.SHAPE_POLY_SET()

    def add(points):
        ch = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in points:
            ch.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        ch.SetClosed(True)
        poly.AddOutline(ch)

    def rect(x1, y1, x2, y2):
        add([(x1 - m, y1 - m), (x2 + m, y1 - m), (x2 + m, y2 + m), (x1 - m, y2 + m)])

    def circle(cx, cy, r, n=48):
        add([(cx + (r + m) * math.cos(2 * math.pi * i / n), cy + (r + m) * math.sin(2 * math.pi * i / n))
             for i in range(n)])

    count = 0
    for fp in pcb.GetFootprints():
        if not fp.GetReference().startswith("MX"):
            continue
        p = fp.GetPosition()
        if not x_range[0] < mm(p.x) < x_range[1]:
            continue
        count += 1
        for it in fp.GraphicalItems():
            if it.GetLayer() == pcbnew.B_Fab:
                bb = it.GetBoundingBox()
                rect(mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
        for pad in fp.Pads():
            q, size = pad.GetPosition(), pad.GetSize()
            if pad.GetDrillSize().x > 0:          # centre post / pegs / switch pins
                circle(mm(q.x), mm(q.y), mm(pad.GetDrillSize().x) / 2)
            elif pad.IsOnLayer(pcbnew.B_Cu):      # socket solder pads
                w, h = mm(size.x) / 2, mm(size.y) / 2
                rect(mm(q.x) - w, mm(q.y) - h, mm(q.x) + w, mm(q.y) + h)
    return poly, count


MIN_WEB = 2.0            # foam strips narrower than this between cut-outs / the edge are removed


def chain_points(ch):
    return [(pcbnew.ToMM(ch.CPoint(j).x), pcbnew.ToMM(ch.CPoint(j).y)) for j in range(ch.PointCount())]


def add_poly_edges(board, poly):
    """Outline and holes of a SHAPE_POLY_SET as Edge.Cuts segments."""
    for i in range(poly.OutlineCount()):
        loops = [poly.Outline(i)] + [poly.Hole(i, h) for h in range(poly.HoleCount(i))]
        for ch in loops:
            pts = chain_points(ch)
            for a, b in zip(pts, pts[1:] + pts[:1]):
                bp.seg(board, a, b)


def foam_with_cutouts(x1, y1, x2, y2, r, cut):
    """Rounded rectangle minus the cut-outs, opened by MIN_WEB / 2 so that thin strips (for
    example between a socket pad and the edge) become notches instead of fragile webs."""
    outline = pcbnew.SHAPE_POLY_SET()
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for cx, cy, a0 in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0), (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180)):
        for i in range(7):
            a = math.radians(a0 + 15 * i)
            ch.Append(pcbnew.FromMM(cx + r * math.cos(a)), pcbnew.FromMM(cy + r * math.sin(a)))
    ch.SetClosed(True)
    outline.AddOutline(ch)
    outline.BooleanSubtract(cut)
    err = pcbnew.FromMM(0.01)
    outline.Deflate(pcbnew.FromMM(MIN_WEB / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, err)
    outline.Inflate(pcbnew.FromMM(MIN_WEB / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, err)
    outline.BooleanIntersection(outline)          # normalise
    return outline


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
    finish(b, path, "eugeo plate foam - cut 2, 3 mm PORON")

    # case foam: pocket outline minus inset, cut short of the centre area; left and right
    # differ because the socket cut-outs are not mirrored
    pocket = design.CASE_CLEARANCE - CASE_FOAM_INSET
    pcb = os.path.join(ROOT, "eugeo.kicad_pcb")
    for side, (fx1, fx2), holes in (("left", (x1 - pocket, design.LEFT_END - CENTER_GAP), design.HOLES[:4]),
                                    ("right", (design.RIGHT_END + CENTER_GAP, x2 + pocket), design.HOLES[4:])):
        path, b = new_board(f"eugeo-case-foam-{side}")
        cut, n = socket_cutouts(pcb, (fx1, fx2))
        for hx, hy in holes:                       # screw heads under the PCB, merged with the sockets
            ch = pcbnew.SHAPE_LINE_CHAIN()
            for i in range(48):
                a = 2 * math.pi * i / 48
                ch.Append(pcbnew.FromMM(hx + BOSS_HOLE / 2 * math.cos(a)), pcbnew.FromMM(hy + BOSS_HOLE / 2 * math.sin(a)))
            ch.SetClosed(True)
            cut.AddOutline(ch)
        cut.Simplify()
        foam = foam_with_cutouts(fx1, y1 - pocket, fx2, y2 + pocket, 1.5, cut)
        if foam.OutlineCount() != 1:
            raise SystemExit(f"case foam {side}: {foam.OutlineCount()} pieces")
        add_poly_edges(b, foam)
        if n != 24:
            raise SystemExit(f"case foam {side}: {n} switches")
        finish(b, path, f"eugeo case foam {side} - 3 mm PORON, top side up (do not flip)")

    # gasket pad: one above and one below every plate tab (5 tabs per plate, 2 plates)
    path, b = new_board("eugeo-gasket-pad")
    pw, ph = design.GASKET_PAD
    bp.rounded_rect(b, 0, 0, pw, ph, 0.5)
    finish(b, path, f"eugeo gasket pad - cut {GASKET_PADS}, 3 mm PORON")


if __name__ == "__main__":
    main()
