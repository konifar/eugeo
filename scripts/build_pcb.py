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
FAN_X0 = 123.2        # first fan-out turn column (left side; mirrored on the right)
FAN_PITCH = 0.7
REF_POS = {"Y1": (152.4, 88.0, 1.0), "C7": (144.45, 95.4, 1.0), "C1": (149.25, 95.4, 1.0),
           "C2": (155.55, 95.4, 1.0), "C6": (160.35, 95.4, 1.0)}
CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")


def nc_nets():
    """Names KiCad gives to no-connect pins, read from the schematic netlist."""
    import subprocess
    import tempfile
    import sexpr
    out = os.path.join(tempfile.mkdtemp(), "n.net")
    subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out,
                    os.path.join(ROOT, f"{design.PROJECT}.kicad_sch")], check=True, capture_output=True)
    nets = {}
    for n in sexpr.parse(open(out).read()).child("nets").children("net"):
        name = n.child("name").items[1]
        if name.startswith("unconnected-"):
            for node in n.children("node"):
                nets[(node.child("ref").items[1], node.child("pin").items[1])] = name
    return nets


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    NC_NETS = nc_nets()
    board = pcbnew.NewBoard(OUT)
    nets = {}

    def net(name):
        # label nets live under the root sheet ("/COL0"); power and auto nets do not
        if name not in ("+5V", "+3V3", "GND") and not name.startswith(("Net-(", "/", "unconnected-(")):
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
        if p["ref"] in ("J1", "U4"):                  # fine-pitch back-side pads: solid to the GND pour
            fp.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
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
        if p.get("lcsc") and fp.GetAttributes() & pcbnew.FP_SMD and p["ref"][0] in "CR":
            fp.Reference().SetVisible(False)          # 0402 parts: no room for a designator
        if p["ref"].startswith("D") and p["ref"][1:].isdigit():
            a_, b_ = fp.FindPadByNumber("1").GetPosition(), fp.FindPadByNumber("2").GetPosition()
            fp.Reference().SetPosition(pcbnew.VECTOR2I((a_.x + b_.x) // 2, (a_.y + b_.y) // 2))
            fp.Reference().SetTextAngleDegrees(0)     # on the diode body, clear of the zigzag pads
        if p["footprint"] == design.FP_R:            # axial resistors: designator on the body
            a_, b_ = fp.FindPadByNumber("1").GetPosition(), fp.FindPadByNumber("2").GetPosition()
            fp.Reference().SetPosition(pcbnew.VECTOR2I((a_.x + b_.x) // 2, (a_.y + b_.y) // 2))
            fp.Reference().SetTextAngleDegrees(90 if abs(a_.x - b_.x) < abs(a_.y - b_.y) else 0)
        if p["ref"] in ("U1", "U2", "U4", "LED1", "LED2", "SW1", "SW2"):   # marked otherwise / no room
            fp.Reference().SetVisible(False)
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

    text("eugeo", design.CENTER_X, 63.4, size=1.2, thick=0.2)
    text("RESET", 145.25, 112.25, size=1.0, thick=0.15)
    text("BOOT", 159.55, 112.25, size=1.0, thick=0.15)
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
                ax = design.diode_x(side, 6 * r_ + i)[0]
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
        bus = design.BUS_Y[k]                 # same y for COLk on both halves
        track((x, ys[-1]), (x, bus), pcbnew.B_Cu, n)
        track((x, bus), (design.LEFT_END if c < 6 else design.RIGHT_END, bus), pcbnew.B_Cu, n)

    # join the two halves of every column straight across the bottom edge
    for k in range(design.MATRIX_COLS):
        bus = design.BUS_Y[k]
        track((design.LEFT_END, bus), (design.RIGHT_END, bus), pcbnew.B_Cu, f"COL{k}")

    # USB-C: join the duplicated A/B-side pins right at the connector
    jx, jy = design.CENTER_X, 62.106 - 0.725        # pad centre row (back side)
    X = lambda dx: round(jx + dx, 3)
    # D-: B7 + A7 joined above the pads (towards the edge), on to R3 pad 1
    track((X(-0.75), jy), (X(-0.75), 58.8), pcbnew.B_Cu, "CONN_D-")
    track((X(0.25), jy), (X(0.25), 58.8), pcbnew.B_Cu, "CONN_D-")
    track((X(-0.75), 58.8), (158.6, 58.8), pcbnew.B_Cu, "CONN_D-")
    track((158.6, 58.8), (158.6, 59.5), pcbnew.B_Cu, "CONN_D-")
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

    # ---- RP2040 block (hand-routed; Freerouting only joins the escapes) -----
    fps = {f.GetReference(): f for f in board.GetFootprints()}

    def pad(ref, num):
        q = fps[ref].FindPadByNumber(str(num)).GetPosition()
        return round(pcbnew.ToMM(q.x), 4), round(pcbnew.ToMM(q.y), 4)

    def path(pts, n, layer=pcbnew.F_Cu, w=0.2):
        for a_, b_ in zip(pts, pts[1:]):
            if abs(a_[0] - b_[0]) + abs(a_[1] - b_[1]) > 1e-3:
                track(a_, b_, layer, n, w)

    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    up = lambda k: pad("U1", k)

    # +3V3 ring inside the pin ring (0.3-0.4 mm from the pin ends, clear of the
    # exposed pad): ties IOVDD 1/10/33/42/49, USB_VDD 48, VREG_VIN 44, ADC_AVDD 43.
    RL, RR, RT, RB = 149.8, 155.0, 74.5, 79.3
    path([(RL, RB), (RL, RT), (RR, RT), (RR, 78.0)], "+3V3")
    for k in (1, 10):
        path([up(k), (RL, up(k)[1])], "+3V3")
    for k in (33, 42):
        path([up(k), (RR, up(k)[1])], "+3V3")
    for k in (43, 44, 48, 49):
        path([up(k), (up(k)[0], RT)], "+3V3")
    # pin 22 (IOVDD) has no room on the ring: via under the pin, joined on the back
    va, vb, vc = (150.4, RB), (152.2, RB), (153.6, RB)
    path([(RL, RB), va], "+3V3")
    via(va, "+3V3")
    path([up(22), (up(22)[0], RB), vb], "+3V3")
    via(vb, "+3V3")
    track(va, vb, B, "+3V3", 0.25)
    # TESTEN (19) straight into the exposed pad; exposed pad -> 4 vias to the GND pour
    path([up(19), (up(19)[0], 78.6)], "GND", w=0.15)
    for dx in (-0.8, 0.8):
        for dy in (-0.8, 0.8):
            via((152.4 + dx, 77.0 + dy), "GND")

    # +1V1: VREG_VOUT 45 and DVDD 50 on the top edge, DVDD 23 at the bottom.
    v50, v45 = (152.75, 72.0), (154.45, 72.15)
    path([up(50), (up(50)[0], 72.55), v50], "+1V1")
    path([up(45), (up(45)[0], 72.55), (154.45, 72.3), v45], "+1V1")
    path([up(23), (up(23)[0], RB), vc], "+1V1")
    for v in (v50, v45, vc):
        via(v, "+1V1")
    path([v50, v45], "+1V1", B, 0.25)
    path([v50, (152.4, 72.35), (152.4, 78.6), (152.9, 78.6), vc], "+1V1", B, 0.25)
    # top-edge decoupling: C20 (DVDD 50) and C18 (VREG_VOUT 45) with their GND vias
    for ref, v_, g in (("C20", v50, (152.75, 69.1)), ("C18", v45, (154.45, 69.2))):
        path([v_, pad(ref, 1)], "+1V1")
        path([pad(ref, 2), g], "GND")
        via(g, "GND")
    # back-side C12 (pin 22) / C13 (pin 23)
    path([vb, pad("C12", 1)], "+3V3", B, 0.25)
    path([vc, pad("C13", 1)], "+1V1", B, 0.25)

    # +3V3 decoupling on the outer pin ends
    path([up(1), pad("C10", 1)], "+3V3")
    path([up(10), pad("C11", 1)], "+3V3")
    path([up(33), pad("C14", 1)], "+3V3")
    path([up(42), pad("C15", 1)], "+3V3")
    path([up(43), (155.4, 72.725), pad("C17", 1)], "+3V3")
    g10, g11, g14, g17 = (146.64, 73.5), (145.7, 78.0), (159.1, 78.0), (158.0, 72.9)
    path([pad("C10", 2), g10], "GND")
    path([pad("C11", 2), g11], "GND")
    path([pad("C14", 2), g14], "GND")
    path([pad("C17", 2), g17], "GND")
    path([pad("C15", 2), g17], "GND")
    for g in (g10, g11, g14, g17):
        via(g, "GND")

    # QSPI flash (U2, rotated 180 to the upper left): pins 1-3 face the RP2040,
    # pins 5-7 come round over the top of the package.
    path([up(56), (149.8, 71.905), (149.4, 71.505), pad("U2", 1)], "QSPI_SS")
    path([up(55), (150.2, 70.635), (149.8, 70.235), pad("U2", 2)], "QSPI_SD1")
    path([up(54), (150.6, 69.365), (150.2, 68.965), pad("U2", 3)], "QSPI_SD2")
    gf = (150.35, 67.695)
    path([pad("U2", 4), gf], "GND")
    via(gf, "GND")
    x5, y5 = pad("U2", 5)
    path([up(53), (151.0, 67.0), (150.6, 66.6), (x5, 66.6), (x5, y5)], "QSPI_SD0")
    x6, y6 = pad("U2", 6)
    path([up(52), (151.4, 66.6), (151.0, 66.2), (140.5, 66.2), (140.5, y6), (x6, y6)], "QSPI_SCLK")
    x7, y7 = pad("U2", 7)
    path([up(51), (151.8, 66.2), (151.4, 65.8), (140.1, 65.8), (140.1, y7), (x7, y7)], "QSPI_SD3")
    # flash VCC: C22 under pin 8, fed from pin 1's capacitor C10
    path([pad("U2", 8), pad("C22", 1), (pad("C10", 1)[0], pad("C22", 1)[1]), pad("C10", 1)], "+3V3")
    g22 = (140.75, 73.68)
    path([pad("C22", 2), g22], "GND")
    via(g22, "GND")

    # USB: D+ / D- straight up between C20 and C18, then round the right LED to R2 / R3
    r2, r3 = pad("R2", 2), pad("R3", 2)
    path([up(47), (153.4, 67.8), (164.6, 67.8), (164.6, r2[1]), r2], "USB_D+")
    path([up(46), (153.8, 68.4), (165.0, 68.4), (165.0, r3[1]), r3], "USB_D-")

    # crystal: XIN straight down, XOUT through R11
    xi = pad("Y1", 1)
    path([up(20), (151.8, xi[1] - 0.8), (xi[0], xi[1])], "XIN")
    path([up(21), (152.2, 81.4), (152.6, 81.8), pad("R11", 1)], "XOUT")
    xo = pad("Y1", 2)
    path([pad("R11", 2), (152.6, 84.2), (xo[0], 84.2 + xo[0] - 152.6), xo], "XOUT_X")

    # signal escapes: left / right rows + columns
    # rows: out sideways, then down a channel next to the diode stack to the first
    # cathode of their zigzag that faces the MCU
    for side in (0, 1):
        for r_ in range(4):
            k = (5, 7, 13, 19)[r_]                      # odd k: the cathode stepped towards the centre
            cx, cy = design.diode_x(side, k)[1], design.diode_stack_y(k)
            pin = up(design.GPIO_PIN[design.ROW_GPIO[r_ + 4 * side]])
            sgn = 1 if side == 0 else -1
            if r_ == 0:
                path([pin, (cx + sgn * 1.7, pin[1]), (cx, cy)], f"ROW{r_ + 4 * side}")
            else:
                xv = design.CENTER_X - sgn * (11.6 - 0.4 * (r_ - 1))   # 140.8 / 141.2 / 141.6
                path([pin, (xv, pin[1]), (xv, cy), (cx, cy)], f"ROW{r_ + 4 * side}")

    # the three columns spread from 0.4 to 0.8 mm pitch so vias fit
    netof = lambda k: fps["U1"].FindPadByNumber(str(k)).GetNetname().lstrip("/")
    for side, x_end, cols_ in ((-1, 145.0, (12, 13, 14)), (1, 159.8, (31, 30, 29))):
        x0 = up(cols_[0])[0] + side * 0.75          # just past the pad tips
        for i, k in enumerate(cols_):
            y0 = up(k)[1]
            dy = 0.4 * i                              # 78.8 / 79.2 / 79.6 -> 78.8 / 79.6 / 80.4
            bend = x0 + side * 0.4 * (2 - i)
            path([up(k), (bend, y0), (bend + side * dy, y0 + dy), (x_end, y0 + dy)], netof(k))
            # via at the end, back side down a channel beside the diode stack, top side
            # again past the other column buses, via onto its own bus
            n = netof(k)
            ye = y0 + dy
            xv = design.CENTER_X + side * (12.8 - 0.6 * i)        # 139.6 / 140.2 / 140.8
            yv = 116.0 - i
            yb = design.BUS_Y[int(n[3:])]
            via((x_end, ye), n)
            path([(x_end, ye), (xv, ye + abs(x_end - xv)), (xv, yv)], n, B)
            via((xv, yv), n)
            path([(xv, yv), (xv, yb)], n)
            via((xv, yb), n)
    # LEDs: the topmost GPIO on each side runs out above the rows, drops to the back
    # and climbs through its 0402 resistor (R7 / R8, back side) to the LED above
    netpad = lambda ref, n: [(pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y))
                             for q in fps[ref].Pads() if q.GetNetname().lstrip("/") == n][0]
    for led, res, k, sgn in (("LED1", "R7", 3, -1), ("LED2", "R8", 40, 1)):
        pin = up(k)
        v = (design.CENTER_X + sgn * 7.0, 74.6)               # 145.4 / 159.4
        path([pin, (v[0] - sgn * 0.6, pin[1]), v], led)
        via(v, led)
        an = pad(led, 2)
        path([v, netpad(res, led)], led, B)
        path([netpad(res, led + "_A"), (v[0], an[1] + 1.0), an], led + "_A", B)
    # RUN through a via and along the back to R9 and the RESET button
    vr = (154.2, 84.0)
    path([up(26), vr], "RUN")
    via(vr, "RUN")
    r9, s1 = pad("R9", 2), [q for q in (fps["SW1"].Pads()) if q.GetNetname().lstrip("/") == "RUN"]
    s1 = min(((pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y)) for q in s1), key=lambda t: t[1])
    path([vr, (design.CENTER_X, vr[1] + vr[0] - design.CENTER_X), (design.CENTER_X, r9[1] - 1.8), r9], "RUN", B)
    path([r9, (r9[0] - 0.6, r9[1] - 0.6), (s1[0], r9[1] - 0.6), s1], "RUN", B)
    # QSPI_SS also feeds the BOOT button (R10): via inside the flash footprint
    vs = (147.3, 71.5)
    path([pad("U2", 1), vs], "QSPI_SS")
    via(vs, "QSPI_SS")

    # GND of the regulator corner: tie the THT grounds together on top
    sw2 = lambda ref: min((t for t in ((pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y))
                                       for q in fps[ref].Pads() if q.GetNetname() == "GND")), key=lambda t: t[1])
    path([pad("U3", 1), pad("C7", 2), (sw2("SW1")[0], pad("C7", 2)[1] + 1.8), sw2("SW1")], "GND", F, 0.4)
    path([pad("C6", 2), (sw2("SW2")[0], pad("C6", 2)[1] + 1.8), sw2("SW2")], "GND", F, 0.4)

    # +3V3 feed: ring -> back side -> via -> MCP1700 output
    vd = (147.6, 82.8)
    path([va, (147.6, 82.1), vd], "+3V3", B, 0.25)
    via(vd, "+3V3")
    o3 = pad("U3", 3)
    path([vd, (vd[0] - (o3[1] - vd[1]), o3[1]), o3], "+3V3", F, 0.25)

    # cathodes of each row group: a zigzag F.Cu track through the six cathode pads
    for side in (0, 1):
        for r_ in range(design.ROWS):
            pts = [(design.diode_x(side, k)[1], design.diode_stack_y(k)) for k in range(6 * r_, 6 * r_ + 6)]
            for a_, b_ in zip(pts, pts[1:]):
                track(a_, b_, pcbnew.F_Cu, f"ROW{r_ + 4 * side}")

    board.BuildConnectivity()
    pcbnew.SaveBoard(OUT, board)
    print("wrote", OUT, "footprints", len(board.GetFootprints()), "tracks", len(board.GetTracks()))


if __name__ == "__main__":
    main()
