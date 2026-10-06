"""Build eugeo.kicad_pcb from design.py (run with KiCad's bundled python).

    KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
    $KP scripts/build_pcb.py

Places every footprint, draws the outline and routes the key area with locked
tracks. The centre (diodes / MCU / USB) is left for Freerouting (route.sh).
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import design  # noqa: E402
import gen_schematic  # noqa: E402  (for symbol UUIDs)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STD = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
LOCAL = os.path.join(ROOT, "footprints", "eugeo.pretty")
OUT = os.path.join(ROOT, f"{design.PROJECT}.kicad_pcb")

W_SIG = 0.25
VIA = (0.6, 0.3)
VIA_DX = 8.0          # via to the right of socket pad 1
SLOT0 = 3.0           # first F.Cu slot below key centre
SLOT_PITCH = 0.8
BUS0 = 124.0          # first B.Cu column bus below bottom row
FAN_X0 = 123.2        # first fan-out turn column (left side; mirrored on the right)
FAN_PITCH = 0.7
REF_POS = {"LED1": (152.0, 118.0, 1.0), "LED2": (165.6, 118.0, 1.0), "C4": (157.5, 121.6, 1.0)}
BUS_PITCH = 1.0
# names KiCad gives to no-connect pins in the schematic
NC_NETS = {("U1", "21"): "unconnected-(U1-AREF-Pad21)",
           ("U1", "23"): "unconnected-(U1-PC0-Pad23)",
           ("U1", "25"): "unconnected-(U1-PC2-Pad25)",
           ("J1", "A8"): "unconnected-(J1-SBU1-PadA8)",
           ("J1", "B8"): "unconnected-(J1-SBU2-PadB8)"}


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    board = pcbnew.NewBoard(OUT)
    nets = {}

    def net(name):
        # label nets live under the root sheet ("/COL0"); power and auto nets do not
        if name not in ("+5V", "GND") and not name.startswith(("Net-(", "/", "unconnected-(")):
            name = "/" + name
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            nets[name] = n
        return nets[name]

    # ---- footprints -------------------------------------------------------
    for p in design.parts():
        lib, name = p["footprint"].split(":")
        path = LOCAL if lib == "eugeo" else os.path.join(STD, lib + ".pretty")
        fp = pcbnew.FootprintLoad(path, name)
        if fp is None:
            raise SystemExit(f"footprint not found: {p['footprint']}")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        board.Add(fp)
        x, y, rot, side = p["pos"]
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + gen_schematic.uid("sym", p["ref"])))
        fp.SetSheetname("Root")
        fp.SetSheetfile(f"{design.PROJECT}.kicad_sch")
        for pad in fp.Pads():
            num = pad.GetNumber()
            n = p["pins"].get(num) or NC_NETS.get((p["ref"], num))
            if n:
                pad.SetNet(net(n))
        if p["ref"] == "J1":
            fp.SetLocalClearance(pcbnew.FromMM(0.15))   # 0.5 mm pitch USB-C pads
        if p["ref"].startswith(("MX", "H")):
            fp.SetLocked(True)
        if p["ref"].startswith("MX"):
            fp.Reference().SetVisible(False)
            fp.Value().SetVisible(False)
        if p["ref"].startswith("H"):
            fp.Reference().SetVisible(False)
        if p["ref"].startswith("D") and p["ref"][1:].isdigit():
            # the stacked diodes sit 2.55 mm apart; the library "K" mark would land on the next pad
            for item in fp.GraphicalItems():
                if item.GetClass() == "PCB_TEXT" and item.GetText() == "K":
                    item.SetLayer(pcbnew.F_Fab)
        if p["ref"] in REF_POS:
            rx, ry, rsize = REF_POS[p["ref"]]
            fp.Reference().SetPosition(P(rx, ry))
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(rsize), pcbnew.FromMM(rsize)))

    # ---- outline ------------------------------------------------------------
    x1, y1, x2, y2 = design.EDGE
    r = 1.0

    def seg(a, b, layer=pcbnew.Edge_Cuts, w=0.1):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*b))
        s.SetLayer(layer)
        s.SetWidth(pcbnew.FromMM(w))
        board.Add(s)

    def arc(c, start, deg):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetCenter(P(*c))
        s.SetStart(P(*start))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)

    seg((x1 + r, y1), (x2 - r, y1))
    seg((x2, y1 + r), (x2, y2 - r))
    seg((x2 - r, y2), (x1 + r, y2))
    seg((x1, y2 - r), (x1, y1 + r))
    arc((x2 - r, y1 + r), (x2 - r, y1), 90)
    arc((x2 - r, y2 - r), (x2, y2 - r), 90)
    arc((x1 + r, y2 - r), (x1 + r, y2), 90)
    arc((x1 + r, y1 + r), (x1, y1 + r), 90)

    # ---- silkscreen -----------------------------------------------------------
    def text(s, x, y, layer=pcbnew.F_SilkS, size=1.0, rot=0, thick=0.15):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(P(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
        t.SetTextThickness(pcbnew.FromMM(thick))
        t.SetTextAngleDegrees(rot)
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        board.Add(t)

    text("eugeo", design.CENTER_X, 65.3, size=1.5, thick=0.25)
    text("RST  SCK  MISO", 146.6, 78.3, size=1.0, thick=0.15)
    text("GND  MOSI  VCC", 146.6, 84.9, size=1.0, thick=0.15)
    text("RESET", 151.4, 72.35, size=1.0, rot=90, thick=0.15)
    text("BOOT", 151.4, 103.9, size=1.0, rot=90, thick=0.15)
    text(f"eugeo rev{design.REV}  6x4x2 hot-swap", design.CENTER_X, 126.2, pcbnew.B_SilkS, 1.0)
    text("based on Lumberjack by peej (MIT)", design.CENTER_X, 128.2, pcbnew.B_SilkS, 1.0)

    # ---- key area routing ---------------------------------------------------
    def track(a, b, layer, n, w=W_SIG):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetLayer(layer)
        t.SetWidth(pcbnew.FromMM(w))
        t.SetNet(net(n))
        t.SetLocked(True)
        board.Add(t)

    def via(at, n, size=VIA):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(*at))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetWidth(pcbnew.FromMM(size[0]))
        v.SetDrill(pcbnew.FromMM(size[1]))
        v.SetNet(net(n))
        v.SetLocked(True)
        board.Add(v)

    # Key -> diode: socket pad 1 -> via (B.Cu) -> down to the row's slot below the
    # key centre -> along the slot to the centre -> staircase fan-out -> anode (F.Cu).
    # Track i of a row is the i-th closest column to the centre: it gets the i-th
    # shallowest slot and the i-th diode of the row group, so nothing crosses.
    for r_ in range(design.ROWS):
        cy = design.KEY_Y[r_]
        for side in (0, 1):
            ax = design.DIODE_ANODE_X[side]
            sign = 1 if side == 0 else -1            # direction towards the centre
            x0 = FAN_X0 if side == 0 else 2 * design.CENTER_X - FAN_X0
            items = []
            for i in range(6):
                c = 5 - i if side == 0 else 6 + i
                n = design.key_ref(r_, c)
                k = 6 * r_ + i
                items.append((i, c, n, cy + SLOT0 + SLOT_PITCH * i, design.diode_stack_y(k)))
            up = [it for it in items if it[4] < it[3] - 1e-6]
            down = [it for it in items if it[4] > it[3] + 1e-6]
            turn = {}
            for rank, it in enumerate(up):                    # top track turns first
                turn[it[0]] = x0 + sign * FAN_PITCH * rank
            for rank, it in enumerate(reversed(down)):        # bottom track turns first
                turn[it[0]] = x0 + sign * FAN_PITCH * rank
            for i, c, n, slot, dy in items:
                cx = design.KEY_X[c]
                net_ = design.key_net(n)
                pad1 = (cx + 5.842, cy - 5.08)
                v = (cx + VIA_DX, cy - 5.08)
                track(pad1, v, pcbnew.B_Cu, net_)
                via(v, net_)
                track(v, (v[0], slot), pcbnew.F_Cu, net_)
                tx = turn.get(i)
                if tx is None:                                # already level with the diode
                    track((v[0], slot), (ax, slot), pcbnew.F_Cu, net_)
                    continue
                track((v[0], slot), (tx, slot), pcbnew.F_Cu, net_)
                track((tx, slot), (tx, dy), pcbnew.F_Cu, net_)
                track((tx, dy), (ax, dy), pcbnew.F_Cu, net_)

    for c in range(design.COLS):
        cx = design.KEY_X[c]
        x = cx - 7.085
        k = design.matrix_pos(0, c)[1]
        n = f"COL{k}"
        ys = [cy - 2.54 for cy in design.KEY_Y]
        for a, b in zip(ys, ys[1:]):
            track((x, a), (x, b), pcbnew.B_Cu, n)
        bus = BUS0 + BUS_PITCH * (5 - k)      # same y for COLk on both halves
        track((x, ys[-1]), (x, bus), pcbnew.B_Cu, n)
        track((x, bus), (design.LEFT_END if c < 6 else design.RIGHT_END, bus), pcbnew.B_Cu, n)

    # join the two halves of every column straight across the bottom edge
    for k in range(design.MATRIX_COLS):
        bus = BUS0 + BUS_PITCH * (5 - k)
        track((design.LEFT_END, bus), (design.RIGHT_END, bus), pcbnew.B_Cu, f"COL{k}")

    # USB-C: join the duplicated A/B-side pins right at the connector
    jx, jy = design.CENTER_X, 62.106 - 0.725        # pad centre row (back side)
    X = lambda dx: round(jx + dx, 3)
    # D-: B7 + A7 joined above the pads (towards the edge), on to R3 pad 1
    track((X(-0.75), jy), (X(-0.75), 58.8), pcbnew.B_Cu, "CONN_D-")
    track((X(0.25), jy), (X(0.25), 58.8), pcbnew.B_Cu, "CONN_D-")
    track((X(-0.75), 58.8), (158.6, 58.8), pcbnew.B_Cu, "CONN_D-")
    track((158.6, 58.8), (158.6, 59.8), pcbnew.B_Cu, "CONN_D-")
    # D+: A6 + B6 joined below the pads
    track((X(-0.254), jy), (X(-0.254), 63.0), pcbnew.B_Cu, "CONN_D+")
    track((X(0.75), jy), (X(0.75), 63.0), pcbnew.B_Cu, "CONN_D+")
    track((X(-0.254), 63.0), (X(0.75), 63.0), pcbnew.B_Cu, "CONN_D+")
    # VBUS: A4 and A9 drop to vias and are joined on F.Cu
    for dx, vx in ((-2.45, -3.1), (2.45, 3.1)):
        track((X(dx), jy), (X(dx), 62.6), pcbnew.B_Cu, "VBUS", 0.4)
        track((X(dx), 62.6), (X(vx), 63.25), pcbnew.B_Cu, "VBUS", 0.4)
        via((X(vx), 63.25), "VBUS", (0.8, 0.4))
    track((X(-3.1), 63.25), (X(3.1), 63.25), pcbnew.F_Cu, "VBUS", 0.4)

    # cathodes of each row group are stacked: tie them with one vertical F.Cu track
    for x in design.DIODE_CATHODE_X:
        for r_ in range(design.ROWS):
            ya, yb = design.diode_stack_y(6 * r_), design.diode_stack_y(6 * r_ + 5)
            track((x, ya), (x, yb), pcbnew.F_Cu, f"ROW{r_ if x < design.CENTER_X else r_ + 4}")

    board.BuildConnectivity()
    pcbnew.SaveBoard(OUT, board)
    print("wrote", OUT, "footprints", len(board.GetFootprints()), "tracks", len(board.GetTracks()))


if __name__ == "__main__":
    main()
