#!/usr/bin/env python3
"""Check the Yushakobo laser-cut SVGs against the submission rules.

    python3 scripts/check_lasercut_svg.py
"""
import glob
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = "{http://www.w3.org/2000/svg}"
INK = "{http://www.inkscape.org/namespaces/inkscape}"
CUT_COLORS = {"#ff0000", "#0000ff", "#00ff00", "#ff00ff", "#ff6600"}
EXPECT = {  # file prefix -> (parts, {hole diameters mm})
    "eugeo-cover": (1, {2.2}),
    "eugeo-switch-plate": (2, {2.2}),
    "eugeo-foam": (4, {4.4, 7.0}),
}


def path_points(d):
    """Endpoints + arc radii of an M/L/A/Z path (as written by export_yushakobo_svg.py)."""
    pts, radii = [], []
    for cmd, args in re.findall(r"([MLAZ])([^MLAZ]*)", d):
        nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", args)]
        if cmd in "ML":
            pts.append((nums[0], nums[1]))
        elif cmd == "A":
            radii.append(nums[0])
            pts.append((nums[5], nums[6]))
    return pts, radii


def main():
    ok_all = True
    for f in sorted(glob.glob(os.path.join(ROOT, "lasercut", "yushakobo", "*.svg"))):
        name = os.path.basename(f)
        root = ET.parse(f).getroot()
        wmm, hmm = float(root.get("width")[:-2]), float(root.get("height")[:-2])
        vb = [float(v) for v in root.get("viewBox").split()]
        k = vb[2] / wmm
        errs = []
        if not name.isascii():
            errs.append("non-ASCII file name")
        sizes = [g.get(INK + "label") for g in root if re.match(r"^\d+x\d+", g.get(INK + "label") or "")]
        if sizes != [f"{int(wmm)}x{int(hmm)}"]:
            errs.append(f"size layers {sizes}")
        cut = [g for g in root if g.get("id") == "eugeo_cut"][0]
        parts, holes = [], []
        for p in cut:
            st = dict(kv.split(":") for kv in p.get("style").split(";"))
            if st.get("fill") != "none" or st.get("stroke") not in CUT_COLORS:
                errs.append(f"style {p.get('style')}")
            if abs(float(st["stroke-width"]) / k - 0.001) > 1e-5:
                errs.append(f"stroke width {float(st['stroke-width']) / k:.4f} mm")
            pts, radii = path_points(p.get("d"))
            xs, ys = [x / k for x, _ in pts], [y / k for _, y in pts]
            if radii and len(pts) == 3:                      # full circle drawn as two arcs
                xs += [min(xs) , max(xs)]
                cy = ys[0]
                ys += [cy - radii[0] / k, cy + radii[0] / k]
                holes.append(round(2 * radii[0] / k, 2))
            box = (min(xs), min(ys), max(xs), max(ys))
            if st["stroke"] == "#0000ff":
                parts.append(box)
            if box[0] < 3 or box[1] < 3 or box[2] > wmm - 3 or box[3] > hmm - 3:
                errs.append(f"inside the 3 mm margin: {box}")
        for i, a in enumerate(parts):
            for b in parts[i + 1:]:
                gap = max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])
                if gap < 2:
                    errs.append(f"parts {gap:.1f} mm apart")
        # nothing filled (= engraved) on the sheet except the off-page notes layer
        skip = set(cut.iter())
        for g in root:
            if g.get(INK + "label") == "諸注意":
                skip |= set(g.iter())
        for el in root.iter():
            if el in skip or el.tag.split("}")[1] not in ("path", "rect", "circle", "polygon", "text"):
                continue
            fill = dict(kv.split(":") for kv in (el.get("style") or "fill:none").split(";") if ":" in kv).get("fill", "black")
            if fill != "none":
                errs.append(f"filled element {el.get('id')} ({fill}) would be engraved")
        prefix = name.split("_")[0]
        n_parts, hole_d = EXPECT[prefix]
        if len(parts) != n_parts:
            errs.append(f"{len(parts)} parts (expected {n_parts})")
        if set(holes) != hole_d:
            errs.append(f"hole diameters {sorted(set(holes))} (expected {sorted(hole_d)})")
        sizes = sorted({(round(b[2] - b[0], 2), round(b[3] - b[1], 2)) for b in parts})
        print(("PASS" if not errs else "FAIL"), name, f"{wmm:g}x{hmm:g} mm, {len(parts)} parts {sizes}, holes {sorted(set(holes))}", errs[:4])
        ok_all &= not errs
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
