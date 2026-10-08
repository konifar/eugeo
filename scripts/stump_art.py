"""Back-side artwork: a frozen tree stump (run with KiCad's python, after routing).

    $KP scripts/stump_art.py eugeo.kicad_pcb

Tree rings, a bark rim and drying cracks sit in the middle of the back, frost ferns
creep out towards both ends and snowflakes are scattered over the keys. Everything
is B.Silkscreen, clipped around every exposed pad, hole and existing text, except a
few large snowflakes that are B.Mask openings on the GND pour (bare, tin-plated copper
under a blue mask reads as ice). Those are only placed where the pour is solid GND
with no track or via underneath. Re-running replaces the previous artwork.
"""
import json
import math
import os
import random
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import design  # noqa: E402

ART = "stump-art"            # group name; the previous run's group is removed first
CX, CY = design.CENTER_X, (design.EDGE[1] + design.EDGE[3]) / 2
W_RING, W_BARK, W_FROST = 0.15, 0.2, 0.15
# logo: Futura "EUGEO" (scripts/logo_eugeo.json) in the free band between key rows 1
# and 2 of the right-hand block (front view), i.e. on the left when the board is turned over
LOGO_C = ((design.KEY_X[6] + design.KEY_X[11]) / 2, (design.KEY_Y[1] + design.KEY_Y[2]) / 2 - 1.8)
LOGO_RULE = (5.0, 20.0)      # gap after the text, rule length

PAD_MARGIN = 0.35            # silk to mask opening
EDGE_MARGIN = 0.8
STEP = 0.25                  # clipping resolution (mm)

P = lambda x, y: pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
mm = pcbnew.ToMM


# ---- drawing ----------------------------------------------------------------------
def ring(r, rng, sx=1.12, wob=0.035, n=None):
    """Closed wobbly ring around the pith (a bit wider than tall, like a sawn log)."""
    n = n or max(48, int(r * 9))
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        k = (1 + wob * math.sin(3 * t + ph[0]) + wob * 0.6 * math.sin(5 * t + ph[1])
             + wob * 0.4 * math.sin(9 * t + ph[2]) + 0.02 * math.sin(2 * t + ph[3]))
        pts.append((CX + sx * r * k * math.cos(t), CY + r * k * math.sin(t)))
    return pts


def bark(r, rng):
    """Jagged rim: small random bites out of the outer ring."""
    n = int(r * 14)
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        rr = r + (rng.uniform(-0.9, 0.2) if i % 3 == 0 else rng.uniform(-0.25, 0.25))
        if i == n:
            pts.append(pts[0])
            break
        pts.append((CX + 1.12 * rr * math.cos(t), CY + rr * math.sin(t)))
    return pts


def crack(angle, r_out, depth, rng):
    """Drying check: a narrow V from the rim towards the pith, slightly kinked."""
    out = []
    for side in (-1, 1):
        pts = []
        for i in range(9):
            f = i / 8
            r = r_out - depth * f
            a = angle + side * 0.035 * (1 - f) + 0.02 * math.sin(f * 7 + angle)
            pts.append((CX + 1.12 * r * math.cos(a), CY + r * math.sin(a)))
        out.append(pts)
    return out


def fern(x, y, ang, length, rng, depth=0):
    """Frost fern: a gently curving stem with sparse 60 degree side branches."""
    segs = []
    pts = [(x, y)]
    n = max(3, int(length / 1.6))
    bend = rng.uniform(-0.03, 0.03)
    for i in range(1, n + 1):
        f = i / n
        ang += bend
        x += (length / n) * math.cos(ang)
        y += (length / n) * math.sin(ang)
        pts.append((x, y))
        if depth == 0 and i % 2 == 0 and i < n - 1:
            bl = length * 0.32 * (1 - f) + 1.0
            for s in (-1, 1):
                if rng.random() < 0.8:
                    segs += fern(x, y, ang + s * math.radians(60), bl, rng, 1)
        elif depth == 1 and i % 2 == 1 and i < n and length > 4:
            for s in (-1, 1):
                b = ang + s * math.radians(60)
                bl = 0.9 * (1 - f) + 0.4
                segs.append([(x, y), (x + bl * math.cos(b), y + bl * math.sin(b))])
    segs.append(pts)
    return segs


def flake(x, y, r, rot=0.0):
    """Six-armed snowflake with two pairs of barbs per arm (list of polylines)."""
    out = []
    for k in range(6):
        a = rot + k * math.pi / 3
        ex, ey = x + r * math.cos(a), y + r * math.sin(a)
        out.append([(x, y), (ex, ey)])
        for f, bl in ((0.45, 0.35), (0.72, 0.25)):
            bx, by = x + f * r * math.cos(a), y + f * r * math.sin(a)
            for s in (-1, 1):
                b = a + s * math.radians(55)
                out.append([(bx, by), (bx + bl * r * math.cos(b), by + bl * r * math.sin(b))])
    return out


# ---- obstacles ------------------------------------------------------------------------
class Keepout:
    """Fast 'is this point too close to an exposed pad / hole / silk text / edge?'."""

    def __init__(self, board, extra=(), boxes=()):
        self.cell = 4.0
        self.grid = {}
        self.items = []
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(pcbnew.B_Mask) or p.GetDrillSize().x > 0:
                    self.add(p.GetBoundingBox(), ("pad", p))
            for t in [fp.Reference(), fp.Value()] + [g for g in fp.GraphicalItems() if g.GetClass() == "PCB_TEXT"]:
                if t.IsVisible() and t.GetLayer() == pcbnew.B_SilkS:
                    self.add(t.GetBoundingBox(), ("box", t.GetBoundingBox()))
        for d in board.GetDrawings():
            if d.GetLayer() == pcbnew.B_SilkS and isinstance(d, pcbnew.PCB_TEXT):
                self.add(d.GetBoundingBox(), ("box", d.GetBoundingBox()))
        for (x1, y1, x2, y2) in boxes:
            bb = pcbnew.BOX2I(P(x1, y1), P(x2 - x1, y2 - y1))
            self.add(bb, ("box", bb))
        for (x, y, r) in extra:
            bb = pcbnew.BOX2I(P(x - r, y - r), P(2 * r, 2 * r))
            self.add(bb, ("circle", (x, y, r)))
        self.acc = pcbnew.FromMM(PAD_MARGIN)
        x1, y1, x2, y2 = design.EDGE
        self.edge = (x1 + EDGE_MARGIN, y1 + EDGE_MARGIN, x2 - EDGE_MARGIN, y2 - EDGE_MARGIN)

    def add(self, bb, item):
        self.items.append(item)
        i = len(self.items) - 1
        m = PAD_MARGIN + 0.5
        gx1, gy1 = int((mm(bb.GetLeft()) - m) // self.cell), int((mm(bb.GetTop()) - m) // self.cell)
        gx2, gy2 = int((mm(bb.GetRight()) + m) // self.cell), int((mm(bb.GetBottom()) + m) // self.cell)
        for gx in range(gx1, gx2 + 1):
            for gy in range(gy1, gy2 + 1):
                self.grid.setdefault((gx, gy), []).append(i)

    def blocked(self, x, y, w):
        e = self.edge
        if not (e[0] < x < e[2] and e[1] < y < e[3]):
            return True
        pt = P(x, y)
        acc = self.acc + pcbnew.FromMM(w / 2)
        for i in self.grid.get((int(x // self.cell), int(y // self.cell)), ()):
            kind, it = self.items[i]
            if kind == "pad":
                if it.HitTest(pt, acc):
                    return True
            elif kind == "box":
                bb = pcbnew.BOX2I(it.GetOrigin(), it.GetSize())
                bb.Inflate(acc)
                if bb.Contains(pt):
                    return True
            else:
                cx, cy, r = it
                if math.hypot(x - cx, y - cy) < r + PAD_MARGIN + w / 2:
                    return True
        return False


def clip(polyline, keep, w):
    """Split a polyline into the runs that stay clear of every keepout."""
    runs, cur = [], []
    for (x1, y1), (x2, y2) in zip(polyline, polyline[1:]):
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) / STEP))
        for i in range(n + 1):
            f = i / n
            x, y = x1 + (x2 - x1) * f, y1 + (y2 - y1) * f
            if keep.blocked(x, y, w):
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
            elif not cur or math.hypot(x - cur[-1][0], y - cur[-1][1]) > 1e-6:
                cur.append((x, y))
    if len(cur) > 1:
        runs.append(cur)
    out = []
    for r in runs:                       # thin the samples back to the original vertices
        if math.hypot(r[-1][0] - r[0][0], r[-1][1] - r[0][1]) < 0.4:
            continue
        slim = [r[0]]
        for p in r[1:-1]:
            if math.hypot(p[0] - slim[-1][0], p[1] - slim[-1][1]) >= 0.6:
                slim.append(p)
        slim.append(r[-1])
        out.append(slim)
    return out


# ---- mask snowflakes ----------------------------------------------------------------------
def solid_gnd(board, zone, x, y, r):
    """True if a disc of radius r is pure GND pour: filled everywhere, no via / track / pad inside."""
    for k in range(25):
        rr = r * math.sqrt(k / 24) if k else 0
        a = k * 2.399
        if not zone.HitTestFilledArea(pcbnew.B_Cu, P(x + rr * math.cos(a), y + rr * math.sin(a)), 0):
            return False
    for k in range(16):
        a = k * math.pi / 8
        if not zone.HitTestFilledArea(pcbnew.B_Cu, P(x + r * math.cos(a), y + r * math.sin(a)), 0):
            return False
    c = P(x, y)
    reach = pcbnew.FromMM(r + 0.6)
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            if (t.GetPosition() - c).EuclideanNorm() < reach:
                return False
        elif t.GetLayer() == pcbnew.B_Cu and t.HitTest(c, reach):
            return False
    for hx, hy in design.HOLES + design.COVER_HOLES + design.PILLARS:
        if math.hypot(x - hx, y - hy) < r + 4.5:
            return False
    return True


def logo(board, group):
    """Filled Futura letters with a rule and a dot on each side; returns the bounding box."""
    d = json.load(open(os.path.join(os.path.dirname(__file__), "logo_eugeo.json")))
    cx, cy = LOGO_C
    to_board = lambda u, v: (cx - u, cy - v)          # read from the back: mirror x, y up
    for pts in d["polygons"]:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
        s.SetPolyPoints([P(*to_board(u, v)) for u, v in pts])
        s.SetLayer(pcbnew.B_SilkS)
        s.SetFilled(True)
        s.SetWidth(0)
        board.Add(s)
        group.AddItem(s)
    half = d["width"] / 2
    gap, rule = LOGO_RULE
    for sx in (-1, 1):
        a, b = to_board(sx * (half + gap), 0), to_board(sx * (half + gap + rule), 0)
        line = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(P(*a))
        line.SetEnd(P(*b))
        line.SetLayer(pcbnew.B_SilkS)
        line.SetWidth(pcbnew.FromMM(0.3))
        board.Add(line)
        group.AddItem(line)
        dot = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
        dot.SetCenter(P(*b))
        dot.SetEnd(P(b[0] + 0.7, b[1]))
        dot.SetLayer(pcbnew.B_SilkS)
        dot.SetFilled(True)
        dot.SetWidth(0)
        board.Add(dot)
        group.AddItem(dot)
    w = half + gap + rule + 0.7
    return (cx - w, cy - d["height"] / 2, cx + w, cy + d["height"] / 2)


def main(path):
    board = pcbnew.LoadBoard(path)
    old = [g for g in board.Groups() if g.GetName() == ART]
    if old:
        doomed = [d for d in board.GetDrawings()
                  if d.GetParentGroup() and d.GetParentGroup().GetName() == ART]
        for g in old:
            g.RemoveAll()
            board.Remove(g)
        for d in doomed:
            board.Remove(d)
    zones = [board.GetArea(i) for i in range(board.GetAreaCount())]
    zone = [z for z in zones if z.GetNetname() == "GND" and z.IsOnLayer(pcbnew.B_Cu)][0]
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    group = pcbnew.PCB_GROUP(board)
    group.SetName(ART)
    board.Add(group)
    rng = random.Random(20261007)

    def seg(a, b, layer, w):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*b))
        s.SetLayer(layer)
        s.SetWidth(pcbnew.FromMM(w))
        board.Add(s)
        group.AddItem(s)

    # 0. the logo, kept clear of everything else drawn below
    lx1, ly1, lx2, ly2 = logo(board, group)
    near_logo = lambda x, y, m: lx1 - m < x < lx2 + m and ly1 - m < y < ly2 + m

    # 1. ice: a few big snowflakes of bare copper on the GND pour (B.Mask openings)
    ice = []
    candidates = [(CX + dx, CY + dy) for dx in range(-128, 129, 3) for dy in range(-30, 31, 3)]
    rng.shuffle(candidates)
    for x, y in candidates:
        if len(ice) >= 7:
            break
        r = 2.4
        if any(math.hypot(x - a, y - b) < 22 for a, b, _ in ice) or near_logo(x, y, 6):
            continue
        if solid_gnd(board, zone, x, y, r + 0.4):
            ice.append((x, y, r))
    for x, y, r in ice:
        for a, b in flake(x, y, r, rng.uniform(0, math.pi / 3)):
            seg(a, b, pcbnew.B_Mask, 0.35)

    keep = Keepout(board, extra=[(x, y, r + 0.6) for x, y, r in ice],
                   boxes=[(lx1 - 2.0, ly1 - 1.6, lx2 + 2.0, ly2 + 1.6)])
    lines = []                                   # (polyline, width)

    # 2. the stump: pith, rings, bark, checks
    lines.append((ring(0.6, rng, wob=0.1, n=24), W_RING))
    r = 2.2
    while r < 31:
        lines.append((ring(r, rng), W_RING))
        r += rng.uniform(1.6, 2.8)
    lines.append((bark(33.5, rng), W_BARK))
    lines.append((bark(34.6, rng), W_BARK))
    for a in (0.35, 1.9, 2.75, 4.1, 5.3):
        for pts in crack(a + rng.uniform(-0.1, 0.1), 34.0, rng.uniform(9, 17), rng):
            lines.append((pts, W_RING))

    # 3. frost ferns creeping from the rim towards both ends of the board
    for side in (-1, 1):
        for t in (math.radians(a + rng.uniform(-6, 6)) for a in (-48, -20, 8, 34, 55)):
            sx = CX + side * 1.12 * 34.6 * math.cos(t)
            sy = CY + 34.6 * math.sin(t)
            ang = (0 if side > 0 else math.pi) + side * t * 0.6 + rng.uniform(-0.25, 0.25)
            for pts in fern(sx, sy, ang, rng.uniform(16, 34), rng):
                lines.append((pts, W_FROST))

    # 4. silk snowflakes drifting over the key area
    for k in range(70):
        x = rng.uniform(design.EDGE[0] + 4, design.EDGE[2] - 4)
        y = rng.uniform(design.EDGE[1] + 4, design.EDGE[3] - 4)
        if (abs(x - CX) < 1.12 * 37 and abs(y - CY) < 37) or near_logo(x, y, 4):
            continue
        for pts in flake(x, y, rng.uniform(0.9, 2.2), rng.uniform(0, math.pi / 3)):
            lines.append((pts, W_FROST))

    n = 0
    for pts, w in lines:
        for run in clip(pts, keep, w):
            for a, b in zip(run, run[1:]):
                seg(a, b, pcbnew.B_SilkS, w)
                n += 1
    board.Save(path)
    print(f"stump art: {n} silk segments, {len(ice)} bare-copper snowflakes")


if __name__ == "__main__":
    main(sys.argv[1])
