"""Interference check: case vs. PCB (with component 3D models), hot-swap sockets and plates.

    kicad-cli pcb export step --subst-models -o /tmp/eugeo-pcb.step eugeo.kicad_pcb
    .venv/bin/python scripts/check_case_fit.py /tmp/eugeo-pcb.step
"""
import os
import sys

from build123d import Box, Compound, Cylinder, Pos, import_step

sys.path.insert(0, os.path.dirname(__file__))
import case as C  # noqa: E402
import design  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def vol(shape):
    if shape is None:
        return 0.0
    if hasattr(shape, "volume"):
        return shape.volume
    return sum(s.volume for s in shape)


def main(pcb_step):
    case = import_step(os.path.join(ROOT, "case", "eugeo-case-bottom.step")).fuse(
        import_step(os.path.join(ROOT, "case", "eugeo-case-top.step")))
    pcb = import_step(pcb_step)
    solids = pcb.solids()
    board = max(solids, key=lambda s: s.bounding_box().size.X * s.bounding_box().size.Y)
    bb = board.bounding_box()
    # KiCad STEP: X = x, Y = -y; move board centre to the origin and its underside to Z = 0
    shift = Pos(-bb.center().X, -bb.center().Y, -bb.min.Z)
    parts = [shift * s for s in solids if s is not board]

    # hot-swap sockets have no 3D model: approximate body + pads under every key
    n_pcb_parts = len(parts)
    for cx in design.KEY_X:
        for cy in design.KEY_Y:
            x, y = C.to_case(cx, cy)
            parts.append(Pos(x - 0.65, y + 3.8, -0.95) * Box(15.7, 6.1, 1.9))
    # switch plates (left / right halves) and their gasket tabs
    half = design.PLATE_X[1] - design.PLATE_X[0]
    for sign in (-1, 1):
        x = sign * (design.EDGE[2] - design.EDGE[0] - half) / 2
        parts.append(Pos(x, 0, C.PLATE_TOP - 0.75) * Box(half, C.PCB_H, 1.5))
    w, d = design.GASKET_TAB_W, design.GASKET_TAB_D
    tabs = []
    for right in (False, True):
        for edge, pos in design.gasket_tabs(right):
            if edge in ("back", "front"):
                y = (C.PCB_H + d) / 2 * (1 if edge == "back" else -1)
                tabs.append(Pos(pos - C.CX, y, C.PLATE_TOP - 0.75) * Box(w, d, 1.5))
            else:
                x = (C.PCB_W + d) / 2 * (1 if right else -1)
                tabs.append(Pos(x, C.CY - pos, C.PLATE_TOP - 0.75) * Box(d, w, 1.5))
    parts += tabs

    worst = []
    for p in parts:
        inter = case.intersect(p)
        v = vol(inter)
        if v > 1e-3:
            pb = p.bounding_box()
            worst.append((v, pb.center(), pb.size))
    pcb_inter = case.intersect(shift * board)
    print("board/case overlap:", round(vol(pcb_inter), 3), "mm3")
    print("parts checked:", len(parts), "interfering:", len(worst))
    for v, c, sz in sorted(worst, key=lambda w: -w[0])[:10]:
        print(f"  {v:.2f} mm3 at ({c.X:.1f}, {c.Y:.1f}, {c.Z:.1f}) size ({sz.X:.1f}, {sz.Y:.1f}, {sz.Z:.1f})")
    # gasket: each tab must have the pad gap above and below it inside its recess
    squeezed = 0
    for t in tabs:
        tb = t.bounding_box()
        for z in (tb.min.Z - design.GASKET_GAP / 2, tb.max.Z + design.GASKET_GAP / 2):
            probe = Pos(tb.center().X, tb.center().Y, z) * Box(tb.size.X, tb.size.Y, design.GASKET_GAP - 0.05)
            if vol(case.intersect(probe)) > 1e-3:
                squeezed += 1
    print("gasket tabs:", len(tabs), "/ pad spaces blocked:", squeezed)
    print("board underside clearance to floor:", -C.FLOOR_TOP, "mm (centre),", -C.KEY_FLOOR,
          "mm (key areas); lowest part bottom:", round(min(p.bounding_box().min.Z for p in parts), 2), "mm")
    # case foam, squeezed between the raised floor and the PCB: only the sockets' cut-outs may be empty
    from foam_solids import foam_solid
    # sockets as in eugeo:MX_Hotswap_Kailh: body (B.Fab) 1.85 mm tall, solder tabs, and the
    # switch centre post / pegs poking through the PCB
    sockets = []
    for cx in design.KEY_X:
        for cy in design.KEY_Y:
            for (x1, y1, x2, y2), h in (((-6.05, -6.8, 4.85, -0.8), 1.85), ((4.565, -6.33, 7.115, -3.83), 0.5),
                                        ((-8.365, -3.79, -5.815, -1.29), 0.5)):
                x, y = C.to_case(cx + (x1 + x2) / 2, cy + (y1 + y2) / 2)
                sockets.append(Pos(x, y, -h / 2) * Box(x2 - x1, y2 - y1, h))
            for dx, r in ((0, 2.0), (-5.08, 0.875), (5.08, 0.875)):
                x, y = C.to_case(cx + dx, cy)
                sockets.append(Pos(x, y, -0.75) * Cylinder(r, 1.5))
    t = -C.KEY_FLOOR
    for side in ("left", "right"):
        foam = foam_solid(f"foam/eugeo-case-foam-{side}.kicad_pcb", C.KEY_FLOOR + 0.01, t - 0.02)
        hit = [p for p in sockets + parts[:n_pcb_parts] if vol(foam.intersect(p)) > 1e-3]
        in_case = vol(case.intersect(foam))
        area = foam.volume / (t - 0.02)
        support = vol(case.intersect(Pos(0, 0, -0.02) * foam)) / (area * 0.01)
        print(f"case foam {side}: {t:.1f} mm between floor and PCB ({design.CASE_FOAM_T} mm PORON), "
              f"socket / part hits: {len(hit)}, case overlap: {in_case:.2f} mm3, resting on the floor: {support:.0%}")

    # centre cover: nothing may reach the acrylic, and it must not touch the case
    cover = C.cover_solid()
    cbb = cover.bounding_box()
    under = [p for p in parts if p.bounding_box().max.Z > C.PCB_T and
             p.bounding_box().min.X < cbb.max.X and p.bounding_box().max.X > cbb.min.X and
             p.bounding_box().min.Y < cbb.max.Y and p.bounding_box().max.Y > cbb.min.Y]
    tallest = max(under, key=lambda p: p.bounding_box().max.Z)
    tb = tallest.bounding_box()
    print(f"cover underside {cbb.min.Z - C.PCB_T:.1f} mm above PCB; tallest part under it "
          f"{tb.max.Z - C.PCB_T:.2f} mm at ({tb.center().X:.1f}, {tb.center().Y:.1f})")
    hits = [p for p in under if vol(cover.intersect(p)) > 1e-3]
    print("parts touching the cover:", len(hits), "/ cover vs case overlap:", round(vol(case.intersect(cover)), 3), "mm3")


if __name__ == "__main__":
    main(sys.argv[1])
