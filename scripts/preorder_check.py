"""Pre-order checks beyond DRC (run with KiCad's python before every order).

    $KP scripts/preorder_check.py [--base <git-rev>]

  1. KiCad DRC (with schematic parity) and ERC are clean
  2. every footprint sits exactly where design.py puts it; outline matches
  3. the change against <git-rev> (default HEAD~1) is limited to added/removed footprints
  4. no exposed copper under standoffs, screw heads or case bosses
  5. real minimum feature sizes vs JLCPCB capabilities
  6. the Gerber / drill zip matches a fresh export of the current board
  7. drill file holes, JLCPCB CPL, plate / cover / bottom holes all line up with the PCB,
     and the Yushakobo laser-cut SVGs follow their rules
  8. functional checks (verify_design.py)
"""
import csv
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import zipfile

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import design  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
BOARD = os.path.join(ROOT, "eugeo.kicad_pcb")
mm = pcbnew.ToMM

# JLCPCB 2-layer standard capabilities (mm)
JLC = dict(track=0.127, clearance=0.127, via_drill=0.3, via_diameter=0.5, annular=0.13,
           pth_drill=0.3, npth_drill=0.5, slot=0.5, silk_text=1.0, silk_stroke=0.15, edge=0.2)

results = []


def check(ok, msg):
    results.append((bool(ok), msg))


def run(args):
    return subprocess.run(args, capture_output=True, text=True)


def pads_of(board):
    out = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            key = (fp.GetReference(), p.GetNumber(), round(mm(p.GetPosition().x), 3), round(mm(p.GetPosition().y), 3))
            out[key] = p.GetNetname()
    return out


def main(base):
    tmp = tempfile.mkdtemp()
    board = pcbnew.LoadBoard(BOARD)

    # 1. DRC / ERC ---------------------------------------------------------------
    rep = os.path.join(tmp, "drc.json")
    run([CLI, "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity", "-o", rep, BOARD])
    drc = json.load(open(rep))
    n = len(drc.get("violations", [])) + len(drc.get("unconnected_items", [])) + len(drc.get("schematic_parity", []))
    check(n == 0, f"DRC + schematic parity: {n} issues")
    erc = os.path.join(tmp, "erc.json")
    run([CLI, "sch", "erc", "--format", "json", "--severity-all", "-o", erc, os.path.join(ROOT, "eugeo.kicad_sch")])
    ev = sum(len(s.get("violations", [])) for s in json.load(open(erc)).get("sheets", []))
    check(ev == 0, f"ERC: {ev} issues")

    # 2. placement vs design.py ---------------------------------------------------
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    bad = []
    parts = design.parts()
    for p in parts:
        fp = fps.get(p["ref"])
        if fp is None:
            bad.append(f"{p['ref']} missing")
            continue
        x, y, rot, side = p["pos"]
        if abs(mm(fp.GetPosition().x) - x) > 1e-3 or abs(mm(fp.GetPosition().y) - y) > 1e-3:
            bad.append(f"{p['ref']} moved")
        if (side == "B") != fp.IsFlipped():
            bad.append(f"{p['ref']} wrong side")
        if not fp.IsFlipped() and abs(((fp.GetOrientationDegrees() - rot) + 180) % 360 - 180) > 1e-3:
            bad.append(f"{p['ref']} rotated")
    extra = set(fps) - {p["ref"] for p in parts}
    check(not bad and not extra, f"all {len(parts)} footprints placed as designed {bad[:5]} extra={sorted(extra)}")
    bb = board.GetBoardEdgesBoundingBox()
    edge = (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
    check(all(abs(a - b) < 0.06 for a, b in zip(edge, design.EDGE)), f"board outline {[round(v, 3) for v in edge]}")

    # 3. diff against the previous revision ---------------------------------------
    old = os.path.join(tmp, "old.kicad_pcb")
    r = run(["/usr/bin/git", "-C", ROOT, "show", f"{base}:eugeo.kicad_pcb"])
    if r.returncode == 0:
        open(old, "w").write(r.stdout)
        a, b = pads_of(pcbnew.LoadBoard(old)), pads_of(board)
        removed = sorted({k[0] for k in set(a) - set(b)})
        added = sorted({k[0] for k in set(b) - set(a)})
        renet = sorted(f"{k[0]}.{k[1]}" for k in set(a) & set(b) if a[k] != b[k])
        check(not renet, f"vs {base}: footprints added {added}, removed {removed}, pads with changed net {renet[:5]}")

    # 4. hardware vs exposed copper -----------------------------------------------
    exposed = []   # (x, y, radius, side, what)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                continue
            r_ = max(mm(p.GetSize().x), mm(p.GetSize().y)) / 2
            for side, layer in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)):
                if p.IsOnLayer(layer):
                    exposed.append((mm(p.GetPosition().x), mm(p.GetPosition().y), r_, side, f"{fp.GetReference()}.{p.GetNumber()}"))
    tented = 0
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            front, back = t.IsTented(pcbnew.F_Mask), t.IsTented(pcbnew.B_Mask)
            tented += front and back
            for side, ok in (("F", front), ("B", back)):
                if not ok:
                    exposed.append((mm(t.GetPosition().x), mm(t.GetPosition().y), mm(t.GetWidth(pcbnew.F_Cu)) / 2, side, "via"))
    vias = sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
    check(tented == vias, f"vias tented (covered by solder mask): {tented}/{vias}")
    hardware = []
    for x, y in design.HOLES:
        hardware += [(x, y, 2.4, "F", "M2 3.5 mm standoff under plate"), (x, y, design.CASE_BOSS_D / 2 + 0.2, "B", "case boss")]
    for x, y in design.COVER_HOLES:
        hardware += [(x, y, 2.4, "F", "M2 10 mm cover standoff"), (x, y, 2.1, "B", "M2 screw head")]
    hits = []
    for hx, hy, hr, hside, what in hardware:
        for ex, ey, er, eside, name in exposed:
            if eside == hside and math.hypot(ex - hx, ey - hy) < hr + er:
                hits.append(f"{what} at ({hx},{hy}) touches {name}")
    check(not hits, f"no exposed copper under standoffs / screw heads / case bosses {hits[:4]}")

    # 5. manufacturing minimums -----------------------------------------------------
    tracks = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    vias_ = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    tw = min(mm(t.GetWidth()) for t in tracks)
    vd = min(mm(v.GetDrillValue()) for v in vias_)
    vo = min(mm(v.GetWidth(pcbnew.F_Cu)) for v in vias_)
    ring = min((mm(v.GetWidth(pcbnew.F_Cu)) - mm(v.GetDrillValue())) / 2 for v in vias_)
    pth, npth, slot = [], [], []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            ds = p.GetDrillSize()
            if ds.x <= 0:
                continue
            d = min(mm(ds.x), mm(ds.y))
            if ds.x != ds.y:
                slot.append(d)
            (npth if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else pth).append(d)
    texts = []
    for d in board.GetDrawings():
        if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            texts.append((mm(d.GetTextHeight()), mm(d.GetTextThickness()), d.GetText()))
    for fp in board.GetFootprints():
        for t in [fp.Reference(), fp.Value()] + [g for g in fp.GraphicalItems() if g.GetClass() == "PCB_TEXT"]:
            if t.IsVisible() and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                texts.append((mm(t.GetTextHeight()), mm(t.GetTextThickness()), f"{fp.GetReference()}:{t.GetText()}"))
    small = [t for t in texts if t[0] < JLC["silk_text"] - 1e-6 or t[1] < JLC["silk_stroke"] - 1e-6]
    check(tw >= JLC["track"], f"min track {tw:.3f} mm (JLC >= {JLC['track']})")
    check(vd >= JLC["via_drill"] and vo >= JLC["via_diameter"] and ring >= JLC["annular"] - 1e-6,
          f"min via drill {vd:.2f} / diameter {vo:.2f} / annular ring {ring:.3f} mm")
    check(min(pth) >= JLC["pth_drill"], f"min plated hole {min(pth):.2f} mm")
    check(min(npth) >= JLC["npth_drill"], f"min non-plated hole {min(npth):.2f} mm")
    check(not slot or min(slot) >= JLC["slot"], f"min slot width {min(slot) if slot else '-'} mm")
    check(not small, f"silkscreen text >= {JLC['silk_text']} mm / {JLC['silk_stroke']} mm stroke {small[:4]}")

    # 6. Gerber zip is a fresh export -------------------------------------------------
    fresh = os.path.join(tmp, "fresh")
    os.makedirs(fresh)
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
    run([CLI, "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask", "--no-x2", "-o", fresh + "/", BOARD])
    run([CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map",
         "--map-format", "gerberx2", "-o", fresh + "/", BOARD])
    strip = lambda s: "\n".join(l for l in s.splitlines() if not re.search(r"CreationDate|Created by|TF\.|DRILL file|; #@!|^G04 ", l))
    z = zipfile.ZipFile(os.path.join(ROOT, "gerbers", "eugeo.zip"))
    diff = []
    for name in sorted(os.listdir(fresh)):
        if name.endswith(".gbrjob"):
            continue
        new = strip(open(os.path.join(fresh, name), errors="ignore").read())
        try:
            zipped = strip(z.read(name).decode(errors="ignore"))
        except KeyError:
            diff.append(f"{name} missing")
            continue
        if new != zipped:
            diff.append(name)
    check(not diff, f"gerbers/eugeo.zip matches the current board {diff}")
    via_xy = [(mm(t.GetPosition().x), -mm(t.GetPosition().y)) for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    open_vias = 0
    for name in ("eugeo-F_Mask.gts", "eugeo-B_Mask.gbs"):
        flashes = [(int(a_) / 1e6, int(b_) / 1e6) for a_, b_ in re.findall(r"X(-?\d+)Y(-?\d+)D03", z.read(name).decode())]
        open_vias += sum(1 for vx, vy in via_xy if any(abs(vx - fx) < 0.01 and abs(vy - fy) < 0.01 for fx, fy in flashes))
    check(open_vias == 0, f"solder mask Gerbers have no opening on any of the {len(via_xy)} vias")

    # 7. drill / CPL / mechanical parts line up ------------------------------------
    drl = z.read("eugeo-NPTH.drl").decode()
    tools, holes, cur = {}, [], None
    for line in drl.splitlines():
        m = re.match(r"T(\d+)C([\d.]+)", line)
        if m:
            tools[m.group(1)] = float(m.group(2))
        elif re.match(r"T\d+$", line):
            cur = line[1:]
        else:
            m = re.match(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
            if m and cur and abs(tools[cur] - 2.2) < 1e-6:
                holes.append((round(float(m.group(1)), 3), round(-float(m.group(2)), 3)))
    want = sorted((round(x, 3), round(y, 3)) for x, y in design.HOLES + design.COVER_HOLES)
    check(sorted(holes) == want, f"NPTH drill file has the {len(want)} M2 holes at the designed positions ({len(holes)} found)")
    cpl = {r["Designator"]: r for r in csv.DictReader(open(os.path.join(ROOT, "jlcpcb", "eugeo-cpl.csv")))}
    off = []
    for ref, fp in fps.items():
        if not ref.startswith("MX"):
            continue
        p1, p2 = fp.FindPadByNumber("1").GetPosition(), fp.FindPadByNumber("2").GetPosition()
        cx, cy = mm(p1.x + p2.x) / 2, -mm(p1.y + p2.y) / 2
        r_ = cpl.get(ref)
        if not r_ or abs(float(r_["Mid X"][:-2]) - cx) > 0.01 or abs(float(r_["Mid Y"][:-2]) - cy) > 0.01 or r_["Layer"] != "Bottom":
            off.append(ref)
    check(sum(1 for r_ in cpl if r_.startswith("MX")) == 48 and not off,
          f"JLCPCB CPL: 48 sockets at the pad centres on Bottom {off[:5]}")
    lcsc = {p["ref"]: p["lcsc"] for p in design.parts() if p.get("lcsc")}
    bom = {}
    for r_ in csv.DictReader(open(os.path.join(ROOT, "jlcpcb", "eugeo-bom.csv"))):
        for ref in r_["Designator"].split(","):
            bom[ref] = r_["LCSC Part #"]
    off = []
    for ref, part in lcsc.items():
        fp, r_ = fps[ref], cpl.get(ref)
        side = "Bottom" if fp.IsFlipped() else "Top"
        if (not r_ or bom.get(ref) != part or r_["Layer"] != side
                or abs(float(r_["Mid X"][:-2]) - mm(fp.GetPosition().x)) > 0.01
                or abs(float(r_["Mid Y"][:-2]) + mm(fp.GetPosition().y)) > 0.01):
            off.append(ref)
    check(len(lcsc) and not off, f"JLCPCB BOM/CPL: {len(lcsc)} SMD parts with LCSC numbers at the footprint positions {off[:5]}")

    def circles(path, shift=(0, 0)):
        b = pcbnew.LoadBoard(path)
        return sorted((round(mm(d.GetCenter().x) - shift[0], 2), round(mm(d.GetCenter().y) - shift[1], 2))
                      for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_CIRCLE)
    r2 = lambda pts: sorted((round(x, 2), round(y, 2)) for x, y in pts)
    check(circles(os.path.join(ROOT, "plates", "eugeo-plate.kicad_pcb")) == r2(design.HOLES[:4]), "switch plate holes = PCB H1-H4")
    check(circles(os.path.join(ROOT, "plates", "eugeo-cover.kicad_pcb")) == r2(design.COVER_HOLES), "cover holes = PCB H9-H12")
    check(circles(os.path.join(ROOT, "plates", "eugeo-bottom.kicad_pcb")) == r2(design.HOLES), "bottom plate holes = PCB H1-H8")

    r = run(["python3", os.path.join(ROOT, "scripts", "check_lasercut_svg.py")])
    check(r.returncode == 0, "Yushakobo laser-cut SVGs follow the submission rules\n     " + r.stdout.strip().replace("\n", "\n     "))

    # 8. functional checks --------------------------------------------------------------
    r = run([sys.executable, os.path.join(ROOT, "scripts", "verify_design.py")])
    last = [l for l in r.stdout.splitlines() if "checks passed" in l]
    check(last and last[0].split("/")[0] == last[0].split("/")[1].split()[0], f"verify_design.py: {last[0] if last else r.stderr[-200:]}")

    for ok, msg in results:
        print("PASS" if ok else "FAIL", msg)
    print(f"\n{sum(ok for ok, _ in results)}/{len(results)} pre-order checks passed")
    sys.exit(0 if all(ok for ok, _ in results) else 1)


if __name__ == "__main__":
    base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "HEAD~1"
    main(base)
