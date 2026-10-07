#!/usr/bin/env python3
"""Generate eugeo.kicad_sch from design.py.

Symbols are taken from lib_symbols.sexpr (extracted from Lumberjack's schematic).
Every pin is tied to its net with a short wire and a net label / power symbol,
so the schematic and the PCB share exactly the same netlist.

    python3 scripts/gen_schematic.py
"""
import math
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
import design  # noqa: E402
import sexpr  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NS = uuid.UUID("6f1c3e1e-6a8b-4c55-9d0e-2f6b8e0e9a10")
ROOT_UUID = str(uuid.uuid5(NS, "root"))
POWER = {"+5V": "eugeo:+5V", "GND": "eugeo:GND"}
G = 2.54


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(map(str, parts))))


def fmt(v):
    v = round(v, 4)
    return ("%.4f" % v).rstrip("0").rstrip(".") if v != int(v) else str(int(v))


def load_lib():
    text = open(os.path.join(HERE, "lib_symbols.sexpr")).read()
    root = sexpr.parse(text)
    syms, pins = {}, {}
    for s in root.children("symbol"):
        name = s.items[1]
        syms[name] = text[s.start:s.end]
        plist = []
        for n in s.walk():
            if n.tag == "pin":
                at = n.child("at")
                num = n.child("number").items[1]
                plist.append((str(num), float(at.items[1]), float(at.items[2]), float(at.items[3])))
        pins[name] = plist
    return syms, pins


SYMS, PINS = load_lib()


def pin_points(lib_id, x, y, rot=0):
    """Absolute schematic position and outward unit vector of each pin."""
    out = []
    t = math.radians(rot)
    for num, px, py, a in PINS[lib_id]:
        # lib coords are y-up; schematic is y-down; rotation is CCW on screen
        rx = px * math.cos(t) - py * math.sin(t)
        ry = px * math.sin(t) + py * math.cos(t)
        ax = math.radians(a + rot)
        ox, oy = -math.cos(ax), math.sin(ax)   # outward direction on screen
        out.append((num, round(x + rx, 3), round(y - ry, 3), round(ox), round(oy)))
    return out


class Sheet:
    def __init__(self):
        self.items = []
        self.pwr_n = 0

    def symbol(self, lib_id, ref, value, x, y, rot=0, footprint="", fields_hidden=False, in_bom=True,
               ref_at=None, val_at=None, pins=None):
        u = uid("sym", ref)
        rx, ry = ref_at or (x, y - 3.81)
        vx, vy = val_at or (x, y + 3.81)
        hide = " hide" if fields_hidden else ""
        pin_lines = "".join(f'\n    (pin "{p}" (uuid {uid("pin", ref, p)}))' for p in pins or [])
        self.items.append(f"""  (symbol (lib_id "{lib_id}") (at {fmt(x)} {fmt(y)} {rot}) (unit 1)
    (in_bom {"yes" if in_bom else "no"}) (on_board yes) (dnp no)
    (uuid {u})
    (property "Reference" "{ref}" (at {fmt(rx)} {fmt(ry)} 0)
      (effects (font (size 1.27 1.27)){" hide" if ref.startswith("#") else ""})
    )
    (property "Value" "{value}" (at {fmt(vx)} {fmt(vy)} 0)
      (effects (font (size 1.27 1.27)){hide})
    )
    (property "Footprint" "{footprint}" (at {fmt(x)} {fmt(y)} 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Datasheet" "~" (at {fmt(x)} {fmt(y)} 0)
      (effects (font (size 1.27 1.27)) hide)
    ){pin_lines}
    (instances
      (project "{design.PROJECT}"
        (path "/{ROOT_UUID}"
          (reference "{ref}") (unit 1)
        )
      )
    )
  )
""")

    def wire(self, x1, y1, x2, y2):
        self.items.append(f"""  (wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}))
    (stroke (width 0) (type default))
    (uuid {uid("wire", x1, y1, x2, y2)})
  )
""")

    def label(self, name, x, y, angle):
        just = "right" if angle in (180, 270) else "left"
        self.items.append(f"""  (label "{name}" (at {fmt(x)} {fmt(y)} {angle}) (fields_autoplaced)
    (effects (font (size 1.27 1.27)) (justify {just} bottom))
    (uuid {uid("label", name, x, y)})
  )
""")

    def no_connect(self, x, y):
        self.items.append(f"  (no_connect (at {fmt(x)} {fmt(y)}) (uuid {uid('nc', x, y)}))\n")

    def power(self, net, x, y, out=None):
        """Power symbol whose graphic points along the outward direction `out`."""
        self.pwr_n += 1
        ref = f"#PWR{self.pwr_n:03d}"
        if out is None:
            out = (0, 1) if net == "GND" else (0, -1)
        if net == "GND":
            rot = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[out]
        else:
            rot = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[out]
        vx, vy = x + out[0] * 5.08, y + out[1] * 5.08
        self.symbol(POWER[net], ref, net, x, y, rot, val_at=(vx, vy), ref_at=(x, y), pins=["1"])

    def flag(self, x, y, name):
        self.symbol("eugeo:PWR_FLAG", name, "PWR_FLAG", x, y, 0, val_at=(x, y - 3.81),
                    ref_at=(x, y), pins=["1"])

    def text(self, s, x, y, size=1.27):
        self.items.append(f"""  (text "{s}" (at {fmt(x)} {fmt(y)} 0)
    (effects (font (size {size} {size})) (justify left bottom))
    (uuid {uid("text", s)})
  )
""")

    def tie_pins(self, part, x, y, rot=0, stub=G):
        """Wire every pin outwards and attach its net label / power symbol."""
        seen = set()
        for num, px, py, ox, oy in pin_points(part["symbol"], x, y, rot):
            if (px, py) in seen:
                continue
            seen.add((px, py))
            net = part["pins"].get(num)
            if net is None:
                self.no_connect(px, py)
                continue
            sx, sy = px + ox * stub, py + oy * stub
            self.wire(px, py, sx, sy)
            if net in POWER:
                self.power(net, sx, sy, (ox, oy))
            else:
                angle = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[(ox, oy)]
                self.label(net, sx, sy, angle)


def main():
    parts = {p["ref"]: p for p in design.parts()}
    sh = Sheet()

    # --- key matrix: 4 x 12 cells, diode anode touches switch pin 1 -------
    sh.text("Key matrix (COL2ROW, electrical 8 rows x 6 cols)", 25.4, 22.86, 2)
    for p in parts.values():
        if not p["ref"].startswith("MX"):
            continue
        r, c = p["row"], p["col"]
        x = 25.4 + 30.48 * c + 12.7
        y = 33.02 + 15.24 * r
        d = parts[f"D{p['ref'][2:]}"]
        sh.symbol(p["symbol"], p["ref"], p["value"], x, y, 0, p["footprint"], fields_hidden=True,
                  ref_at=(x, y - 3.81), pins=["1", "2"])
        sh.symbol(d["symbol"], d["ref"], d["value"], x - 7.62, y, 0, d["footprint"], fields_hidden=True,
                  ref_at=(x - 7.62, y - 2.54), pins=["1", "2"])
        sh.label(p["pins"]["2"], x + 5.08, y, 0)
        sh.label(d["pins"]["1"], x - 10.16, y, 180)

    # --- MCU ---------------------------------------------------------------
    sh.text("MCU", 25.4, 104.14, 2)
    sh.symbol(parts["U1"]["symbol"], "U1", parts["U1"]["value"], 63.5, 157.48, 0,
              parts["U1"]["footprint"], ref_at=(52.07, 116.84), val_at=(68.58, 116.84),
              pins=[str(i) for i in range(1, 29)])
    sh.tie_pins(parts["U1"], 63.5, 157.48)

    # --- passives & connectors in a grid --------------------------------
    grid = [
        ["Y1", "C1", "C2", "SW1", "R4", "SW2"],
        ["C3", "C4", "C5", "R7", "LED1", "R8", "LED2"],
        ["F1", "R1", "R2", "R3", "D49", "D50", "R5", "R6"],
    ]
    sh.text("Crystal / reset / bootloader", 114.3, 104.14, 2)
    sh.text("Power / LEDs", 114.3, 142.24, 2)
    sh.text("USB (V-USB)", 114.3, 180.34, 2)
    rows_y = [124.46, 162.56, 200.66]
    for gi, row in enumerate(grid):
        for i, ref in enumerate(row):
            p = parts[ref]
            x = 124.46 + 22.86 * i
            y = rows_y[gi]
            pin_names = [n for n, *_ in PINS[p["symbol"]]]
            sh.symbol(p["symbol"], ref, p["value"], x, y, 0, p["footprint"],
                      ref_at=(x + 5.08, y - 1.27), val_at=(x + 5.08, y + 1.27), pins=sorted(set(pin_names)))
            sh.tie_pins(p, x, y)

    p = parts["J2"]
    sh.symbol(p["symbol"], "J2", p["value"], 297.18, 124.46, 0, p["footprint"],
              ref_at=(298.45, 116.84), val_at=(298.45, 132.08), pins=[str(i) for i in range(1, 7)])
    sh.tie_pins(p, 297.18, 124.46, stub=5.08)
    sh.text("ISP: 1 GND  2 RST  3 MOSI  4 SCK  5 VCC  6 MISO", 274.32, 139.7)

    p = parts["J1"]
    sh.symbol(p["symbol"], "J1", p["value"], 50.8, 236.22, 0, p["footprint"],
              ref_at=(40.64, 213.36), val_at=(66.04, 213.36),
              pins=sorted(set(n for n, *_ in PINS[p["symbol"]])))
    sh.tie_pins(p, 50.8, 236.22)

    # --- mounting holes -------------------------------------------------
    sh.text("Mounting holes (M2): H1-H8 case / plate, H9-H12 centre cover", 332.74, 104.14, 2)
    holes = sorted((r for r in parts if r.startswith("H")), key=lambda r: int(r[1:]))
    for i, ref in enumerate(holes, 1):
        p = parts[ref]
        x = 337.82 + 15.24 * ((i - 1) % 4)
        y = 116.84 + 12.7 * ((i - 1) // 4)
        sh.symbol(p["symbol"], p["ref"], p["value"], x, y, 0, p["footprint"], in_bom=False,
                  ref_at=(x + 2.54, y - 1.27), val_at=(x + 2.54, y + 1.27))

    # --- power flags ----------------------------------------------------
    sh.text("Power flags", 332.74, 162.56, 2)
    sh.flag(340.36, 180.34, "#FLG01")
    sh.wire(340.36, 180.34, 340.36, 185.42)
    sh.power("+5V", 340.36, 185.42, (0, 1))
    sh.flag(360.68, 180.34, "#FLG02")
    sh.wire(360.68, 180.34, 360.68, 185.42)
    sh.power("GND", 360.68, 185.42)
    sh.flag(381.0, 180.34, "#FLG03")
    sh.wire(381.0, 180.34, 381.0, 185.42)
    sh.label("VBUS", 381.0, 185.42, 270)

    sh.text("eugeo: 6x4x2 ortholinear, through-hole, Kailh MX hot-swap. "
            "Derived from Lumberjack by Paul James (peej), MIT License.", 25.4, 281.94)

    used = set()
    for it in sh.items:
        if it.startswith("  (symbol (lib_id"):
            used.add(it.split('"')[1])
    libs = "\n".join("    " + SYMS[name].replace("\n", "\n  ") for name in sorted(used))

    out = f"""(kicad_sch (version 20230121) (generator eeschema)

  (uuid {ROOT_UUID})

  (paper "A3")

  (title_block
    (title "eugeo")
    (date "2026-10-06")
    (rev "{design.REV}")
    (comment 1 "Derived from Lumberjack (github.com/peej/lumberjack-keyboard) by Paul James, MIT License")
  )

  (lib_symbols
{libs}
  )

{"".join(sh.items)}
  (sheet_instances
    (path "/" (page "1"))
  )
)
"""
    path = os.path.join(ROOT, f"{design.PROJECT}.kicad_sch")
    open(path, "w").write(out)
    print("wrote", path)


if __name__ == "__main__":
    main()
