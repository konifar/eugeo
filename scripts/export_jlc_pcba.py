#!/usr/bin/env python3
"""JLCPCB assembly files for the hot-swap sockets only (everything else is hand-soldered THT).

    python3 scripts/export_jlc_pcba.py   # -> jlcpcb/eugeo-bom.csv, jlcpcb/eugeo-cpl.csv

The sockets sit on the bottom side. CPL coordinates use the same origin as the Gerbers
(KiCad absolute, Y up) and point at the socket body centre, not the switch centre.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import design  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CPG151101S11-16 (HanElectricity, Kailh-compatible): Economic + Standard PCBA, large stock.
# The genuine Kailh part C5184526 is Standard PCBA only and was short of stock on 2026-10-06.
LCSC = "C41430893"
COMMENT = "CPG151101S11 hot-swap socket"
FOOTPRINT = "Kailh_MX_Hotswap_Socket"
# socket body centre relative to the switch centre (KiCad coords, y down):
# midpoint of the two pads (-7.085, -2.54) and (5.842, -5.08)
SOCKET_DX, SOCKET_DY = (-7.085 + 5.842) / 2, (-2.54 + -5.08) / 2
ROTATION = 0                 # verified in JLCPCB's placement preview (bottom view) on 2026-10-06


def main():
    out = os.path.join(ROOT, "jlcpcb")
    os.makedirs(out, exist_ok=True)
    refs = [p for p in design.parts() if p["ref"].startswith("MX")]
    refs.sort(key=lambda p: int(p["ref"][2:]))
    with open(os.path.join(out, "eugeo-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writerow([COMMENT, ",".join(p["ref"] for p in refs), FOOTPRINT, LCSC])
    with open(os.path.join(out, "eugeo-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for p in refs:
            x, y = p["pos"][:2]
            w.writerow([p["ref"], f"{x + SOCKET_DX:.4f}mm", f"{-(y + SOCKET_DY):.4f}mm", "Bottom", ROTATION])
    print("wrote", out, len(refs), "sockets")


if __name__ == "__main__":
    main()
