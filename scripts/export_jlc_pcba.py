#!/usr/bin/env python3
"""JLCPCB assembly files: hot-swap sockets (bottom) + the RP2040 block SMD parts.

    python3 scripts/export_jlc_pcba.py          # -> jlcpcb/eugeo-bom.csv, jlcpcb/eugeo-cpl.csv
    python3 scripts/export_jlc_pcba.py --full   # -> jlcpcb/full/ (USB-C and through-hole parts too)

Everything through-hole is hand-soldered. CPL coordinates use the same origin as the
Gerbers (KiCad absolute, Y up). Sockets point at the socket body centre (the footprint
is the switch); SMD parts come from KiCad's own position export.
"""
import csv
import os
import re
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
# --full: also let JLCPCB fit the USB-C and every through-hole part (in stock on 2026-10-09)
FULL_LCSC = {
    "J1": "C165948",                      # HRO TYPE-C-31-M-12
    **{f"D{i}": "C84410" for i in range(1, 49)},   # 1N4148 DO-35
    "R2": "C119144", "R3": "C119144",     # 27R 1/8W metal film
    "R5": "C119195", "R6": "C119195",     # 5.1k 1/8W
    "R9": "C119202",                      # 10k 1/8W
    "R10": "C2903331",                    # 1k 1/8W
    "C1": "C2170230", "C2": "C2170230",   # 22pF C0G, P2.5
    "C6": "C1620326", "C7": "C1620326",   # 1uF X7R, P2.5
    "C3": "C43846",                       # 10uF 25V, D4 P1.5
    "Y1": "C16369",                       # 12 MHz HC-49S, 20 pF
    "U3": "C511277",                      # MCP1700-3302E/TO
    "F1": "C89660",                       # Bourns MF-R010
    "SW1": "C83205", "SW2": "C83205",     # 6x6 mm tact, THT
    "LED1": "C99772",                     # 3 mm red
    "LED2": "C85161",                     # 3 mm yellow-green
}
# JLCPCB rotation = KiCad rotation + offset, per (footprint, side). Checked against the
# part models in JLCPCB's placement preview on 2026-10-08 (pin 1 on pad 1, leads on pads).
ROT_OFFSET = {
    ("SOIC-8_5.3x5.3mm_P1.27mm", "Top"): 270,
    ("SOT-23-6", "Bottom"): 90,
    ("LED_D3.0mm", "Top"): 180,           # --full only: JLCPCB's 3 mm LED model has its cathode the other way
    ("TYPE-C-31-M-12", "Bottom"): 180,     # --full only: JLCPCB's model opens away from the board edge otherwise
}


KP = os.environ.get("KICAD_PYTHON", "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/"
                    "Versions/Current/bin/python3")


def tht_centres():
    """{ref: (x, y)} centre of the pads of every through-hole footprint (KiCad's origin is pad 1)."""
    code = (
        "import pcbnew,sys\n"
        "b=pcbnew.LoadBoard(sys.argv[1])\n"
        "for f in b.GetFootprints():\n"
        "  ps=[p for p in f.Pads() if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH]\n"
        "  if ps and not f.GetAttributes()&pcbnew.FP_SMD:\n"
        "    print(f.GetReference(),pcbnew.ToMM(sum(p.GetPosition().x for p in ps)/len(ps)),"
        "pcbnew.ToMM(sum(p.GetPosition().y for p in ps)/len(ps)))\n")
    r = subprocess.run([KP, "-c", code, os.path.join(ROOT, f"{design.PROJECT}.kicad_pcb")],
                       check=True, capture_output=True, text=True)
    out = {}
    for line in r.stdout.splitlines():
        ref, x, y = line.split()
        out[ref] = (float(x), -float(y))       # Gerber / CPL: y up
    return out


def smd_rows(full=False):
    """[(ref, value, footprint, lcsc, x, y, rot, side)] for every part with an LCSC number."""
    lcsc = {p["ref"]: dict(p, lcsc=p.get("lcsc") or FULL_LCSC.get(p["ref"])) for p in design.parts()
            if p.get("lcsc") or (full and p["ref"] in FULL_LCSC)}
    out = os.path.join(tempfile.mkdtemp(), "pos.csv")
    subprocess.run([CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                    "-o", out, os.path.join(ROOT, f"{design.PROJECT}.kicad_pcb")], check=True, capture_output=True)
    centres = {k: v for k, v in tht_centres().items() if k != "J1"} if full else {}   # J1 is SMD
    rows = []
    for r in csv.DictReader(open(out)):
        p = lcsc.get(r["Ref"])
        if not p:
            continue
        fp = p["footprint"].split(":")[1]
        side = "Top" if r["Side"] == "top" else "Bottom"
        rot = (float(r["Rot"]) + ROT_OFFSET.get((fp, side), 0)) % 360
        x, y = centres.get(r["Ref"], (float(r["PosX"]), float(r["PosY"])))
        rows.append((r["Ref"], r["Val"], fp, p["lcsc"], x, y, rot, side))
    missing = set(lcsc) - {r[0] for r in rows}
    if missing:
        raise SystemExit(f"no position for {sorted(missing)}")
    return sorted(rows, key=lambda r: (re.sub(r"\d", "", r[0]), int(re.sub(r"\D", "", r[0]))))


def main(full=False):
    out = os.path.join(ROOT, "jlcpcb", "full") if full else os.path.join(ROOT, "jlcpcb")
    os.makedirs(out, exist_ok=True)
    refs = [p for p in design.parts() if p["ref"].startswith("MX")]
    refs.sort(key=lambda p: int(p["ref"][2:]))
    smd = smd_rows(full)
    with open(os.path.join(out, "eugeo-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writerow([COMMENT, ",".join(p["ref"] for p in refs), FOOTPRINT, LCSC])
        groups = {}                       # one line per LCSC part (JLCPCB flags duplicates)
        for ref, val, fp, part, *_ in smd:
            g = groups.setdefault((fp, part), ([], []))
            g[0].append(ref)
            if val not in g[1]:
                g[1].append(val)
        for (fp, part), (rs, vals) in sorted(groups.items(), key=lambda g: g[1][0][0]):
            w.writerow(["/".join(vals), ",".join(rs), fp, part])
    with open(os.path.join(out, "eugeo-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for p in refs:
            x, y = p["pos"][:2]
            w.writerow([p["ref"], f"{x + SOCKET_DX:.4f}mm", f"{-(y + SOCKET_DY):.4f}mm", "Bottom", ROTATION])
        for ref, _, _, _, x, y, rot, side in smd:
            w.writerow([ref, f"{x:.4f}mm", f"{y:.4f}mm", side, f"{rot:g}"])
    print("wrote", out, len(refs), "sockets +", len(smd), "other parts")


if __name__ == "__main__":
    main("--full" in sys.argv[1:])
