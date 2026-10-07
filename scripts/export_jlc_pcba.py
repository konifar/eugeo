#!/usr/bin/env python3
"""JLCPCB assembly files: hot-swap sockets (bottom) + the RP2040 block SMD parts.

    python3 scripts/export_jlc_pcba.py   # -> jlcpcb/eugeo-bom.csv, jlcpcb/eugeo-cpl.csv

Everything through-hole is hand-soldered. CPL coordinates use the same origin as the
Gerbers (KiCad absolute, Y up). Sockets point at the socket body centre (the footprint
is the switch); SMD parts come from KiCad's own position export.
"""
import csv
import os
import subprocess
import sys
import tempfile

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
CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
# JLCPCB rotation = KiCad rotation + offset, per footprint (check the placement preview)
ROT_OFFSET = {}


def smd_rows():
    """[(ref, value, footprint, lcsc, x, y, rot, side)] for every part with an LCSC number."""
    lcsc = {p["ref"]: p for p in design.parts() if p.get("lcsc")}
    out = os.path.join(tempfile.mkdtemp(), "pos.csv")
    subprocess.run([CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                    "-o", out, os.path.join(ROOT, f"{design.PROJECT}.kicad_pcb")], check=True, capture_output=True)
    rows = []
    for r in csv.DictReader(open(out)):
        p = lcsc.get(r["Ref"])
        if not p:
            continue
        fp = p["footprint"].split(":")[1]
        rot = (float(r["Rot"]) + ROT_OFFSET.get(fp, 0)) % 360
        rows.append((r["Ref"], r["Val"], fp, p["lcsc"], float(r["PosX"]), float(r["PosY"]), rot,
                     "Top" if r["Side"] == "top" else "Bottom"))
    missing = set(lcsc) - {r[0] for r in rows}
    if missing:
        raise SystemExit(f"no position for {sorted(missing)}")
    return sorted(rows, key=lambda r: (r[0][0], int(r[0][1:])))


def main():
    out = os.path.join(ROOT, "jlcpcb")
    os.makedirs(out, exist_ok=True)
    refs = [p for p in design.parts() if p["ref"].startswith("MX")]
    refs.sort(key=lambda p: int(p["ref"][2:]))
    smd = smd_rows()
    with open(os.path.join(out, "eugeo-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writerow([COMMENT, ",".join(p["ref"] for p in refs), FOOTPRINT, LCSC])
        groups = {}
        for ref, val, fp, part, *_ in smd:
            groups.setdefault((val, fp, part), []).append(ref)
        for (val, fp, part), rs in sorted(groups.items(), key=lambda g: g[1][0]):
            w.writerow([val, ",".join(rs), fp, part])
    with open(os.path.join(out, "eugeo-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for p in refs:
            x, y = p["pos"][:2]
            w.writerow([p["ref"], f"{x + SOCKET_DX:.4f}mm", f"{-(y + SOCKET_DY):.4f}mm", "Bottom", ROTATION])
        for ref, _, _, _, x, y, rot, side in smd:
            w.writerow([ref, f"{x:.4f}mm", f"{y:.4f}mm", side, f"{rot:g}"])
    print("wrote", out, len(refs), "sockets +", len(smd), "SMD parts")


if __name__ == "__main__":
    main()
