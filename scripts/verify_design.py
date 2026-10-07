"""Functional review of the routed board (run with KiCad's python).

    $KP scripts/verify_design.py [lumberjack.net]

Reads the nets straight from eugeo.kicad_pcb and checks the things DRC cannot:
RP2040 pin functions, power / +1V1 / decoupling, crystal, RUN / BOOT, QSPI flash,
USB and LED wiring, diode polarity, and that every key lands where the QMK
keyboard.json says it does.
With a Lumberjack netlist (kicad-cli sch export netlist) it also lists the
support-circuit differences from Lumberjack (expected: eugeo uses an RP2040).
"""
import json
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import sexpr  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# RP2040 QFN-56 pinout, from the RP2040 datasheet (section 1.4.2)
QFN56 = {1: "IOVDD", 2: "GPIO0", 3: "GPIO1", 4: "GPIO2", 5: "GPIO3", 6: "GPIO4", 7: "GPIO5",
         8: "GPIO6", 9: "GPIO7", 10: "IOVDD", 11: "GPIO8", 12: "GPIO9", 13: "GPIO10", 14: "GPIO11",
         15: "GPIO12", 16: "GPIO13", 17: "GPIO14", 18: "GPIO15", 19: "TESTEN", 20: "XIN", 21: "XOUT",
         22: "IOVDD", 23: "DVDD", 24: "SWCLK", 25: "SWD", 26: "RUN", 27: "GPIO16", 28: "GPIO17",
         29: "GPIO18", 30: "GPIO19", 31: "GPIO20", 32: "GPIO21", 33: "IOVDD", 34: "GPIO22",
         35: "GPIO23", 36: "GPIO24", 37: "GPIO25", 38: "GPIO26", 39: "GPIO27", 40: "GPIO28",
         41: "GPIO29", 42: "IOVDD", 43: "ADC_AVDD", 44: "VREG_VIN", 45: "VREG_VOUT", 46: "USB_DM",
         47: "USB_DP", 48: "USB_VDD", 49: "IOVDD", 50: "DVDD", 51: "QSPI_SD3", 52: "QSPI_SCLK",
         53: "QSPI_SD0", 54: "QSPI_SD2", 55: "QSPI_SD1", 56: "QSPI_SS", 57: "GND"}
# W25Q16JV SOIC-8 (datasheet figure 1b): pin -> RP2040 QSPI signal it must meet
FLASH = {1: "QSPI_SS", 2: "QSPI_SD1", 3: "QSPI_SD2", 4: "GND", 5: "QSPI_SD0", 6: "QSPI_SCLK",
         7: "QSPI_SD3", 8: "+3V3"}

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
    two = lambda ref: {net(ref, 1), net(ref, 2)}

    # --- 0. copper connectivity (independent of DRC report) --------------------
    board.BuildConnectivity()
    check(board.GetConnectivity().GetUnconnectedCount(False) == 0, "all pads connected by copper")

    # --- 1. MCU symbol pins match the datasheet ----------------------------------
    lib = sexpr.parse(open(os.path.join(ROOT, "symbols", "eugeo.kicad_sym")).read())
    sym = [s for s in lib.children("symbol") if s.items[1] == "RP2040"][0]
    names = {}
    for n in sym.walk():
        if n.tag == "pin":
            names[int(n.child("number").items[1])] = n.child("name").items[1]
    alias = {"VREG_VIN": ("VREG_VIN", "VREG_IN")}              # KiCad's library spells it VREG_IN
    bad = [p for p, f in QFN56.items() if not names.get(p, "").startswith(alias.get(f, (f,)))]
    check(not bad, f"RP2040 symbol pin names match the QFN-56 datasheet pinout (mismatch: {bad})")
    gpio_of = {}
    for pin, f in QFN56.items():
        if f.startswith("GPIO"):
            gpio_of.setdefault(net("U1", pin), []).append("GP" + f[4:])
    fn = lambda pin: net("U1", pin)

    # --- 2. power ------------------------------------------------------------------
    supply = {k: fn(k) for k, f in QFN56.items() if f in ("IOVDD", "ADC_AVDD", "VREG_VIN", "USB_VDD")}
    check(set(supply.values()) == {"+3V3"}, f"IOVDD x6, ADC_AVDD, VREG_VIN, USB_VDD on +3V3 {supply}")
    check(fn(45) == fn(23) == fn(50) == "+1V1", "VREG_VOUT (45) feeds DVDD (23, 50) on +1V1")
    check(fn(57) == "GND" and fn(19) == "GND", "exposed pad and TESTEN (19) on GND")
    check({net("U3", 1), net("U3", 2), net("U3", 3)} == {"GND", "+5V", "+3V3"} and net("U3", 1) == "GND"
          and net("U3", 2) == "+5V" and net("U3", 3) == "+3V3", "MCP1700 TO-92: 1 GND, 2 VIN (+5V), 3 VOUT (+3V3)")
    vb = {net("J1", p) for p in ("A4", "A9", "B4", "B9")}
    check(vb == {"VBUS"} and two("F1") == {"VBUS", "+5V"}, "VBUS pins -> F1 polyfuse -> +5V")
    check(two("C3") == {"+5V", "GND"} and net("C3", 1) == "+5V", "C3 electrolytic + (pad 1) on +5V")
    check(two("C6") == {"+5V", "GND"} and two("C7") == {"+3V3", "GND"}, "MCP1700 input (C6) / output (C7) capacitors")
    caps = {r: fps[r] for r in fps if r.startswith("C") and fps[r].GetValue() in ("100n", "1u")}
    c33 = [r for r in caps if two(r) == {"+3V3", "GND"}]
    c11 = [r for r in caps if two(r) == {"+1V1", "GND"}]
    check(len(c33) >= 6 and len(c11) >= 3, f"decoupling: {len(c33)} on +3V3 {sorted(c33)}, {len(c11)} on +1V1 {sorted(c11)}")
    check(fps["C17"].GetValue() == "1u" and net("C17", 1) == "+3V3" and fps["C18"].GetValue() == "1u"
          and net("C18", 1) == "+1V1", "1 uF on VREG_VIN (C17) and VREG_VOUT (C18)")
    u1 = fps["U1"].GetPosition()
    far = [r for r in c33 + c11 if r not in ("C22", "C7") and (caps[r].GetPosition() - u1).EuclideanNorm() > pcbnew.FromMM(7)]
    check(not far, f"MCU decoupling within 7 mm of the RP2040 (too far: {far})")

    # --- 3. clock / reset / boot / flash ------------------------------------------
    check(fps["Y1"].GetValue() == "12MHz", "12 MHz crystal (RP2040 boot ROM / USB PLL)")
    check(net("Y1", 1) == fn(20) == "XIN", "Y1 pin 1 on XIN (20)")
    check(two("R11") == {fn(21), net("Y1", 2)} and fps["R11"].GetValue() == "1k", "XOUT (21) -> R11 1k -> Y1 pin 2")
    check(two("C1") == {"XIN", "GND"} and two("C2") == {net("Y1", 2), "GND"}
          and fps["C1"].GetValue() == fps["C2"].GetValue() == "22p", "22 pF load capacitors on both crystal pins")
    check(fn(26) == "RUN" and two("R9") == {"+3V3", "RUN"} and two("SW1") == {"RUN", "GND"},
          "RUN (26): 10k pull-up R9, RESET button SW1 to GND")
    check(two("R10") == {fn(56), "BOOTSEL"} and two("SW2") == {"BOOTSEL", "GND"},
          "BOOT button SW2 pulls QSPI_SS (56) low through R10 1k")
    for pin, want in FLASH.items():
        if want.startswith("QSPI"):
            k = [p for p, f in QFN56.items() if f == want][0]
            check(net("U2", pin) == fn(k), f"flash pin {pin} -> RP2040 {want} ({k})")
        else:
            check(net("U2", pin) == want, f"flash pin {pin} on {want}")
    check(two("C22") == {"+3V3", "GND"}, "flash VCC decoupled by C22")

    # --- 4. USB (full speed) --------------------------------------------------------
    dp, dm = net("J1", "A6"), net("J1", "A7")
    check(net("J1", "B6") == dp and net("J1", "B7") == dm, "USB-C D+ (A6/B6) and D- (A7/B7) pairs joined")
    check(two("R2") == {dp, fn(47)} and fps["R2"].GetValue() == "27R", "D+ -> R2 27R -> USB_DP (47)")
    check(two("R3") == {dm, fn(46)} and fps["R3"].GetValue() == "27R", "D- -> R3 27R -> USB_DM (46)")
    check(net("U4", 1) == net("U4", 6) == dp and net("U4", 3) == net("U4", 4) == dm
          and net("U4", 2) == "GND" and net("U4", 5) == "VBUS", "USBLC6-2SC6 on the connector side of D+/D-, GND, VBUS")
    for cc, r in (("A5", "R5"), ("B5", "R6")):
        check(two(r) == {net("J1", cc), "GND"} and fps[r].GetValue() == "5.1k",
              f"CC {cc} -> {r} 5.1k -> GND (5 V from USB-C hosts)")
    check({net("J1", p) for p in ("A1", "A12", "B1", "B12", "S1")} == {"GND"}, "USB GND + shield on GND")

    check(fn(24).startswith("unconnected") and fn(25).startswith("unconnected"),
          "SWCLK / SWDIO (24, 25) left open (flashing is over USB)")

    # --- 5. LEDs -------------------------------------------------------------------
    kb = json.load(open(os.path.join(ROOT, "firmware/qmk/keyboards/eugeo/keyboard.json")))
    for led, r in (("LED1", "R7"), ("LED2", "R8")):
        a = net(led, 2)
        mcu = ({net(r, 1), net(r, 2)} - {a}).pop()
        check(net(led, 1) == "GND" and gpio_of.get(mcu), f"{led}: cathode (pad 1) GND, anode via {r} to {gpio_of.get(mcu)}")
    caps = kb["indicators"]["caps_lock"]
    check(gpio_of[net("R7", 1)] == [caps], f"QMK caps_lock pin {caps} drives LED1")
    src = open(os.path.join(ROOT, "firmware/qmk/keyboards/eugeo/eugeo.c")).read()
    check(f"#define LAYER_LED {gpio_of[net('R8', 1)][0]}" in src, f"eugeo.c layer LED pin is {gpio_of[net('R8', 1)]} (LED2)")
    check(kb["processor"] == "RP2040" and kb["bootloader"] == "rp2040", "QMK processor RP2040 / bootloader rp2040")

    # --- 6. matrix vs QMK ----------------------------------------------------------
    check(kb["diode_direction"] == "COL2ROW", "diode_direction COL2ROW")
    rows = kb["matrix_pins"]["rows"]
    cols = kb["matrix_pins"]["cols"]
    used = rows + cols
    check(len(set(used)) == len(used), "matrix pins unique")
    check(all(p in sum(gpio_of.values(), []) for p in used), "every matrix pin is an RP2040 GPIO wired on the board")
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
        col_port = gpio_of.get(net(mx, 2))
        d = diode_of.get(net(mx, 1))
        if d is None:
            errors.append(f"{mx}: no diode on switch pad 1")
            continue
        row_port = gpio_of.get(net(d, 1))
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
        n = [k for k, v in gpio_of.items() if v == [p]][0]
        check(sum(1 for ref, _ in members[n] if ref.startswith("D")) == 6, f"{p} row has 6 diode cathodes")
    for p in cols:
        n = [k for k, v in gpio_of.items() if v == [p]][0]
        check(sum(1 for ref, _ in members[n] if ref.startswith("MX")) == 8, f"{p} column has 8 switches")

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
