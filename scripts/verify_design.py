"""Functional review of the routed board (run with KiCad's python).

    $KP scripts/verify_design.py [lumberjack.net]

Reads the nets straight from eugeo.kicad_pcb and checks the things DRC cannot:
MCU pin functions, USB / crystal / reset / ISP / LED wiring, diode polarity, and
that every key lands where the QMK keyboard.json says it does.
With a Lumberjack netlist (kicad-cli sch export netlist) it also diffs the
support circuitry against the proven Lumberjack design.
"""
import json
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import sexpr  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ATmega328P-PU (PDIP-28) pinout, from the datasheet
DIP28 = {1: "PC6", 2: "PD0", 3: "PD1", 4: "PD2", 5: "PD3", 6: "PD4", 7: "VCC", 8: "GND",
         9: "PB6", 10: "PB7", 11: "PD5", 12: "PD6", 13: "PD7", 14: "PB0", 15: "PB1", 16: "PB2",
         17: "PB3", 18: "PB4", 19: "PB5", 20: "AVCC", 21: "AREF", 22: "GND", 23: "PC0", 24: "PC1",
         25: "PC2", 26: "PC3", 27: "PC4", 28: "PC5"}

results = []


def check(ok, msg):
    results.append((bool(ok), msg))


def main(lj_net=None):
    board = pcbnew.LoadBoard(os.path.join(ROOT, "eugeo.kicad_pcb"))
    pads, fps = {}, {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        fps[ref] = fp
        for p in fp.Pads():
            if p.GetNumber():
                pads.setdefault((ref, p.GetNumber()), p.GetNetname().lstrip("/"))
    net = lambda ref, pin: pads.get((ref, str(pin)))
    members = {}
    for (ref, pin), n in pads.items():
        members.setdefault(n, set()).add((ref, pin))

    # --- 0. copper connectivity (independent of DRC report) --------------------
    board.BuildConnectivity()
    check(board.GetConnectivity().GetUnconnectedCount(False) == 0, "all pads connected by copper")

    # --- 1. MCU symbol pins match the datasheet ----------------------------------
    lib = sexpr.parse(open(os.path.join(ROOT, "symbols", "eugeo.kicad_sym")).read())
    sym = [s for s in lib.children("symbol") if s.items[1] == "ATmega328P-PU"][0]
    names = {}
    for n in sym.walk():
        if n.tag == "pin":
            names[int(n.child("number").items[1])] = n.child("name").items[1]
    bad = [p for p, port in DIP28.items() if port not in names.get(p, "") and not
           (port == "GND" and "GND" in names.get(p, ""))]
    check(not bad, f"symbol pin names match ATmega328P PDIP-28 datasheet (mismatch: {bad})")
    port_of = {}
    for pin, port in DIP28.items():
        port_of.setdefault(net("U1", pin), []).append(port)

    # --- 2. power / clock / reset ------------------------------------------------
    check(net("U1", 7) == net("U1", 20) == "+5V", "VCC (7) and AVCC (20) on +5V")
    check(net("U1", 8) == net("U1", 22) == "GND", "both GND pins (8, 22) on GND")
    check(net("U1", 21).startswith("unconnected"), "AREF (21) left open (as Lumberjack)")
    for c in ("C3", "C4", "C5"):
        check({net(c, 1), net(c, 2)} == {"+5V", "GND"}, f"{c} decouples +5V/GND")
    check(net("C3", 1) == "+5V", "C3 electrolytic + (pad 1, square) on +5V")
    check({net("Y1", 1), net("Y1", 2)} == {net("U1", 9), net("U1", 10)}, "Y1 across XTAL1/XTAL2 (pins 9/10)")
    for c in ("C1", "C2"):
        check(net(c, 2) == "GND" and net(c, 1) in (net("U1", 9), net("U1", 10)), f"{c} load cap XTAL -> GND")
    check(fps["Y1"].GetValue() == "16MHz", "16 MHz crystal (V-USB supported clock)")
    check(net("U1", 1) == "RESET" and {net("R4", 1), net("R4", 2)} == {"+5V", "RESET"}, "RESET pulled up by R4 10k")
    check({net("SW1", 1), net("SW1", 2)} == {"RESET", "GND"}, "SW1 pulls RESET to GND")

    # --- 3. USB (V-USB low-speed) -----------------------------------------------
    dp, dm = net("J1", "A6"), net("J1", "A7")
    check(net("J1", "B6") == dp and net("J1", "B7") == dm, "USB-C D+ (A6/B6) and D- (A7/B7) pairs joined")
    check({net("R2", 1), net("R2", 2)} == {dp, net("U1", 4)} and port_of[net("U1", 4)] == ["PD2"],
          "D+ -> R2 75R -> PD2 (INT0, V-USB default)")
    check({net("R3", 1), net("R3", 2)} == {dm, net("U1", 5)} and port_of[net("U1", 5)] == ["PD3"],
          "D- -> R3 75R -> PD3 (V-USB default)")
    check({net("R1", 1), net("R1", 2)} == {dm, "+5V"}, "1.5k pull-up on D- (low-speed device)")
    check(net("D49", 1) == dp and net("D49", 2) == "GND", "D49 zener: cathode on D+, anode GND")
    check(net("D50", 1) == dm and net("D50", 2) == "GND", "D50 zener: cathode on D-, anode GND")
    for cc, r in (("A5", "R5"), ("B5", "R6")):
        check({net(r, 1), net(r, 2)} == {net("J1", cc), "GND"} and fps[r].GetValue() == "5.1k",
              f"CC {cc} -> {r} 5.1k -> GND (5 V from USB-C hosts)")
    vb = {net("J1", p) for p in ("A4", "A9", "B4", "B9")}
    check(vb == {"VBUS"} and {net("F1", 1), net("F1", 2)} == {"VBUS", "+5V"}, "VBUS pins -> F1 polyfuse -> +5V")
    check({net("J1", p) for p in ("A1", "A12", "B1", "B12", "S1")} == {"GND"}, "USB GND + shield on GND")

    # --- 4. ISP header vs silkscreen ---------------------------------------------
    j2 = sorted(((fps["J2"].FindPadByNumber(str(i)).GetPosition(), i) for i in range(1, 7)),
                key=lambda t: (t[0].y, t[0].x))
    top = [net("J2", i) for _, i in j2[:3]]
    bottom = [net("J2", i) for _, i in j2[3:]]
    want_top = ["RESET", net("U1", 19), net("U1", 18)]        # RST SCK(PB5) MISO(PB4)
    want_bottom = ["GND", net("U1", 17), "+5V"]                 # GND MOSI(PB3) VCC
    check(top == want_top and bottom == want_bottom, "ISP header nets match the 'RST SCK MISO / GND MOSI VCC' silk")

    # --- 5. LEDs -------------------------------------------------------------------
    kb = json.load(open(os.path.join(ROOT, "firmware/qmk/keyboards/eugeo/keyboard.json")))
    for led, r in (("LED1", "R7"), ("LED2", "R8")):
        a = net(led, 2)
        mcu = ({net(r, 1), net(r, 2)} - {a}).pop()
        check(net(led, 1) == "GND" and port_of.get(mcu), f"{led}: cathode (pad 1) GND, anode via {r} to {port_of.get(mcu)}")
    caps = "P" + kb["indicators"]["caps_lock"]
    check(port_of[net("R7", 1)] == [caps], f"QMK caps_lock pin {caps} drives LED1")

    # --- 6. matrix vs QMK ----------------------------------------------------------
    check(kb["diode_direction"] == "COL2ROW", "diode_direction COL2ROW")
    rows = ["P" + p for p in kb["matrix_pins"]["rows"]]
    cols = ["P" + p for p in kb["matrix_pins"]["cols"]]
    used = rows + cols
    check(len(set(used)) == len(used), "matrix pins unique")
    check(not {"PD2", "PD3", "PB6", "PB7", "PC6"} & set(used), "matrix avoids USB / crystal / reset pins")
    layout = kb["layouts"]["LAYOUT_ortho_4x12"]["layout"]
    diode_of = {}
    for ref, fp in fps.items():
        if ref.startswith("D") and ref[1:].isdigit() and int(ref[1:]) <= 48:
            diode_of[net(ref, 2)] = ref
    seen, errors = set(), []
    for i, k in enumerate(layout):
        r, c = divmod(i, 12)
        mr, mc = k["matrix"]
        mx = f"MX{r * 12 + c + 1}"
        fp = fps[mx]
        if (k["x"], k["y"]) != (c, r):
            errors.append(f"{mx} layout position")
        col_port = port_of.get(net(mx, 2))
        d = diode_of.get(net(mx, 1))
        if d is None:
            errors.append(f"{mx}: no diode on switch pad 1")
            continue
        row_port = port_of.get(net(d, 1))
        if col_port != [cols[mc]]:
            errors.append(f"{mx}: column {col_port} != {cols[mc]}")
        if row_port != [rows[mr]]:
            errors.append(f"{mx}: row {row_port} != {rows[mr]}")
        if (mr, mc) in seen:
            errors.append(f"{mx}: duplicate matrix position")
        seen.add((mr, mc))
        pad1 = fps[d].FindPadByNumber("1")
        if pad1.GetShape() not in (pcbnew.PAD_SHAPE_RECT, pcbnew.PAD_SHAPE_ROUNDRECT):
            errors.append(f"{d}: pad 1 is not the square cathode pad")
    xs = [fps[f"MX{c + 1}"].GetPosition().x for c in range(12)]
    ys = [fps[f"MX{r * 12 + 1}"].GetPosition().y for r in range(4)]
    check(xs == sorted(xs) and ys == sorted(ys), "MX1..MX48 are placed left->right, top->bottom like the layout")
    check(not errors, f"all 48 keys: switch -> diode (anode) -> row, switch -> column, as keyboard.json says {errors[:5]}")
    for p in rows:
        n = [k for k, v in port_of.items() if v == [p]][0]
        check(sum(1 for ref, _ in members[n] if ref.startswith("D")) == 6, f"{p} row has 6 diode cathodes")
    for p in cols:
        n = [k for k, v in port_of.items() if v == [p]][0]
        check(sum(1 for ref, _ in members[n] if ref.startswith("MX")) == 8, f"{p} column has 8 switches")
    boot = port_of[({net("SW2", 1), net("SW2", 2)} - {"GND"}).pop()]
    check(boot == ["PD5"], f"BOOT button on {boot} (Lumberjack USBaspLoader jumper pin PD5)")

    # --- 7. diff against Lumberjack ------------------------------------------------
    if lj_net:
        lj = sexpr.parse(open(lj_net).read())
        ljpads = {}
        for n in lj.child("nets").children("net"):
            for node in n.children("node"):
                ljpads[(node.child("ref").items[1], node.child("pin").items[1])] = n.child("name").items[1]
        rename = {"D61": "D49", "D62": "D50"}
        skip = lambda ref: ref.startswith(("MX", "2u_", "J3", "J4", "J5", "H")) or (
            ref.startswith("D") and ref[1:].isdigit() and int(ref[1:]) <= 60)

        def groups(padmap, rn):
            g = {}
            for (ref, pin), n in padmap.items():
                ref = rn.get(ref, ref)
                if skip(ref) or n.startswith("unconnected"):
                    continue
                g.setdefault(n, set()).add(f"{ref}.{pin}")
            return {frozenset(v) for v in g.values()}
        a, b = groups(ljpads, rename), groups(pads, {})
        diff_lj = sorted(sorted(s) for s in a - b)
        diff_eu = sorted(sorted(s) for s in b - a)
        print("\nLumberjack-only connection groups:")
        for s in diff_lj:
            print("  ", s)
        print("eugeo-only connection groups:")
        for s in diff_eu:
            print("  ", s)

    print()
    for ok, msg in results:
        print("PASS" if ok else "FAIL", msg)
    print(f"\n{sum(ok for ok, _ in results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
