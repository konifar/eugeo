#!/usr/bin/env python3
"""Laser-cut SVGs for Yushakobo (https://yushakobo.jp/lasercut/) built on their official templates.

    python3 scripts/export_yushakobo_svg.py <template_dir>

<template_dir> holds the Inkscape templates from Yushakobo's Laser_Cut_template folder:
Laser_acrylic_template.svg, Laser_pom_template.svg, Laser_poron_template.svg.
Outlines are read from the KiCad Edge.Cuts of the plate / cover / foam boards, so they
are identical to the DXFs. Inner cut-outs use Cut1 (red) and outer outlines Cut2 (blue),
so the holes are cut before the part is released.
"""
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
import sexpr  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "lasercut", "yushakobo")
NS = {"svg": "http://www.w3.org/2000/svg",
      "inkscape": "http://www.inkscape.org/namespaces/inkscape",
      "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"}
for k, v in NS.items():
    ET.register_namespace("" if k == "svg" else k, v)
INK = "{%s}" % NS["inkscape"]
CUT1, CUT2 = "#ff0000", "#0000ff"
STROKE_MM = 0.001
MARGIN = 8.0      # from the sheet edge (template asks for >= 3 mm)
GAP = 5.0         # between parts (template asks for >= 2 mm)

JOBS = [
    # output name, template, size layer, sheet (w, h), [(board, copies)], material note
    ("eugeo-cover_acrylic-clear-2mm_115x300.svg", "Laser_acrylic_template.svg", "115x300", (115, 300),
     [("plates/eugeo-cover.kicad_pcb", 1)], "acrylic clear 2 mm"),
    ("eugeo-switch-plate_pom-1.5mm_245x245.svg", "Laser_pom_template.svg", "245x245", (245, 245),
     [("plates/eugeo-plate.kicad_pcb", 2)], "POM 1.5 mm"),
    ("eugeo-foam_poron-3mm_500x100.svg", "Laser_poron_template.svg", "500x100", (500, 100),
     [("foam/eugeo-plate-foam.kicad_pcb", 2), ("foam/eugeo-case-foam.kicad_pcb", 2)], "PORON 3 mm"),
]


def edge_loops(path):
    """Closed loops from Edge.Cuts lines / arcs / circles: list of loops, each a list of segments."""
    root = sexpr.parse(open(path).read())
    segs, loops = [], []
    xy = lambda n: (float(n.items[1]), float(n.items[2]))
    for n in root.children():
        if n.tag not in ("gr_line", "gr_arc", "gr_circle"):
            continue
        if n.child("layer").items[1] != "Edge.Cuts":
            continue
        if n.tag == "gr_circle":
            c, e = xy(n.child("center")), xy(n.child("end"))
            loops.append([("circle", c, math.dist(c, e))])
        elif n.tag == "gr_line":
            segs.append(("line", xy(n.child("start")), xy(n.child("end"))))
        else:
            segs.append(("arc", xy(n.child("start")), xy(n.child("end")), xy(n.child("mid"))))
    close = lambda a, b: math.dist(a, b) < 1e-4
    while segs:
        loop = [segs.pop(0)]
        while not close(loop[-1][2], loop[0][1]):
            end = loop[-1][2]
            for i, s in enumerate(segs):
                if close(s[1], end):
                    loop.append(segs.pop(i))
                    break
                if close(s[2], end):
                    s = segs.pop(i)
                    loop.append((s[0], s[2], s[1]) + s[3:])
                    break
            else:
                raise SystemExit(f"open outline in {path} near {end}")
        loops.append(loop)
    return loops


def bbox(loops):
    xs, ys = [], []
    for loop in loops:
        for s in loop:
            if s[0] == "circle":
                (cx, cy), r = s[1], s[2]
                xs += [cx - r, cx + r]
                ys += [cy - r, cy + r]
            else:
                xs += [s[1][0], s[2][0]]
                ys += [s[1][1], s[2][1]]
    return min(xs), min(ys), max(xs), max(ys)


def to_path(loop, f):
    """SVG path data; f maps board mm -> template units."""
    if loop[0][0] == "circle":
        (cx, cy), r = loop[0][1], loop[0][2]
        (ax, ay), (bx, by) = f((cx - r, cy)), f((cx + r, cy))
        rr = f((cx + r, cy))[0] - f((cx, cy))[0]
        return f"M {ax:.4f},{ay:.4f} A {rr:.4f},{rr:.4f} 0 1 1 {bx:.4f},{by:.4f} A {rr:.4f},{rr:.4f} 0 1 1 {ax:.4f},{ay:.4f} Z"
    x0, y0 = f(loop[0][1])
    d = [f"M {x0:.4f},{y0:.4f}"]
    for s in loop:
        ex, ey = f(s[2])
        if s[0] == "line":
            d.append(f"L {ex:.4f},{ey:.4f}")
        else:
            (sx, sy), (mx, my), (tx, ty) = s[1], s[3], s[2]
            # circle through start / mid / end
            a = 2 * (sx * (my - ty) + mx * (ty - sy) + tx * (sy - my))
            ux = ((sx * sx + sy * sy) * (my - ty) + (mx * mx + my * my) * (ty - sy) + (tx * tx + ty * ty) * (sy - my)) / a
            uy = ((sx * sx + sy * sy) * (tx - mx) + (mx * mx + my * my) * (sx - tx) + (tx * tx + ty * ty) * (mx - sx)) / a
            r = math.dist((ux, uy), (sx, sy))
            cross = (mx - sx) * (ty - my) - (my - sy) * (tx - mx)
            sweep = 1 if cross > 0 else 0          # y-down: positive cross = clockwise on screen
            rr = f((ux + r, uy))[0] - f((ux, uy))[0]
            d.append(f"A {rr:.4f},{rr:.4f} 0 0 {sweep} {ex:.4f},{ey:.4f}")
    d.append("Z")
    return " ".join(d)


def build(name, template, layer, sheet, boards, note, tdir):
    tree = ET.parse(os.path.join(tdir, template))
    svg = tree.getroot()
    vb = [float(v) for v in svg.get("viewBox").split()]
    k = vb[2] / float(svg.get("width").rstrip("mm"))          # template units per mm
    # keep only the chosen sheet size; drop its black size label (it would be engraved)
    for g in list(svg):
        label = g.get(INK + "label") or ""
        if g.tag.endswith("}g") and re.match(r"^\d+x\d+", label):
            if label != layer:
                svg.remove(g)
            else:
                for c in list(g):
                    if c.tag.endswith("}g"):
                        g.remove(c)
                    elif "fill:#000000" in (c.get("style") or ""):
                        # zero-area guide line, but never leave anything black (= engrave) on the sheet
                        c.set("style", c.get("style").replace("fill:#000000", "fill:none"))
    svg.set("width", f"{sheet[0]}mm")
    svg.set("height", f"{sheet[1]}mm")
    svg.set("viewBox", f"0 0 {sheet[0] * k:.4f} {sheet[1] * k:.4f}")

    layer_el = ET.SubElement(svg, "{%s}g" % NS["svg"], {INK + "groupmode": "layer", INK + "label": "cut", "id": "eugeo_cut"})
    style = "fill:none;stroke:{c};stroke-width:%.5f;stroke-opacity:1" % (STROKE_MM * k)
    x = y = MARGIN
    row_h, placed = 0.0, []
    for board, copies in boards:
        loops = edge_loops(os.path.join(ROOT, board))
        x1, y1, x2, y2 = bbox(loops)
        w, h = x2 - x1, y2 - y1
        outer = max(range(len(loops)), key=lambda i: (lambda b: (b[2] - b[0]) * (b[3] - b[1]))(bbox([loops[i]])))
        for _ in range(copies):
            if x + w > sheet[0] - MARGIN:                 # next row
                x, y = MARGIN, y + row_h + GAP
            f = lambda p, ox=x, oy=y: ((p[0] - x1 + ox) * k, (p[1] - y1 + oy) * k)
            for i, loop in enumerate(loops):
                ET.SubElement(layer_el, "{%s}path" % NS["svg"],
                              {"d": to_path(loop, f), "style": style.format(c=CUT2 if i == outer else CUT1)})
            placed.append((x, y, x + w, y + h))
            row_h = max(row_h, h)
            x += w + GAP
    for px1, py1, px2, py2 in placed:
        if px2 > sheet[0] - 3 or py2 > sheet[1] - 3:
            raise SystemExit(f"{name}: part outside the 3 mm margin")
    tree.write(os.path.join(OUT, name), xml_declaration=True, encoding="UTF-8")
    used = max(p[2] for p in placed), max(p[3] for p in placed)
    print(f"{name}: {len(placed)} parts, {note}, uses {used[0]:.1f} x {used[1]:.1f} mm of {sheet[0]} x {sheet[1]}")


def main(tdir):
    os.makedirs(OUT, exist_ok=True)
    for job in JOBS:
        build(*job, tdir)


if __name__ == "__main__":
    main(sys.argv[1])
