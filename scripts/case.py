"""Rounded gasket-mount case for eugeo (Mojo60-like pebble shape), for MJF nylon (PA12) printing.

    .venv/bin/python scripts/case.py      # -> case/eugeo-case-{bottom,top}.{step,stl}

Coordinates: X/Y follow the PCB (centre of the board = origin, +Y = back / USB side),
Z = 0 is the underside of the PCB.

Two pieces split at the middle of the switch plate:
  bottom tray : floor (raised under the key areas for the case foam), walls, USB-C opening,
                nameplate, lower half of the tab recesses
  top frame   : the rim above the plates, upper half of the tab recesses, M2 nut pockets
The switch plates (PCB hanging from them on M2 3.5 mm standoffs) rest on PORON pads in
the tab recesses and are clamped by pads in the top frame; nothing else touches the case.
The halves are joined by 8 x M2x10 pan heads from below into M2 nuts in the top frame
(no threaded inserts needed).

Clearances allow for MJF tolerances (+/-0.3 mm, +/-0.3 % over 100 mm: about 0.45 mm per end
over the 303 mm length) and for JLC3DP's spray paint inside and out (0.1-0.2 mm per surface).
"""
import math
import os
import sys

from build123d import (Align, Axis, BuildPart, BuildSketch, Circle, Cylinder, Keep, Locations, Mode,
                       Plane, Pos, Rectangle, RectangleRounded, RegularPolygon, SlotOverall, Text,
                       export_step, export_stl, extrude, fillet, insert, split)

sys.path.insert(0, os.path.dirname(__file__))
import design  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- board stack (mm) -----------------------------------------------------
X1, Y1, X2, Y2 = design.EDGE
PCB_W, PCB_H = X2 - X1, Y2 - Y1                      # 284.9 x 75.35
CX, CY = (X1 + X2) / 2, (Y1 + Y2) / 2
PCB_T = 1.6
PLATE_TOP = PCB_T + 5.0                              # MX: plate top is 5 mm above PCB top

# --- case parameters --------------------------------------------------------
CLEARANCE = design.CASE_CLEARANCE  # keycaps sit ~1.1 mm off the wall
WALL = 8.0               # pocket wall to outer surface (at the rim)
Z_TOP = PLATE_TOP + 6.5  # rim height: hides the switch housings, keycaps sit just above (high profile)
FLOOR_TOP = -5.0         # space under the PCB for the USB-C receptacle and the centre parts
KEY_FLOOR = -(design.CASE_FOAM_T - design.CASE_FOAM_PRELOAD)   # raised floor under the key areas: case foam touches the PCB
FLOOR_T = 3.0
FRONT_BOTTOM = -10.0     # outer bottom at the front edge
ANGLE = 6.0              # typing angle (deg)
CORNER_R = 12.0          # plan-view outer corner radius
TOP_FILLET = 6.5
BOTTOM_FILLET = 4.5
RIM_FILLET = 1.0
BOTTOM_RIM = 7.0         # width of the ring the case stands on (bottom is hollowed out)
HOLLOW_CORNER_R = 25.0   # big corner radius on the hollow leaves a flat land in each corner for a rubber foot

# gasket mount
PLATE_BOTTOM = PLATE_TOP - 1.5
Z_SPLIT = PLATE_TOP - 0.75                     # case halves meet at the middle of the plate
RECESS_Z = (PLATE_BOTTOM - design.GASKET_GAP, PLATE_TOP + design.GASKET_GAP)
RECESS_PAD = 0.5                               # recess larger than the tab on each side
RECESS_TIP = 1.0                               # ... and beyond the tab tip (MJF shrink over the long axis)
SCREW_D = 2.8            # M2 clearance (+0.2 mm paint on each side)
HEAD_D = 5.0             # M2 pan head counterbore (ISO 7045 head 4.0 mm, + paint)
SCREW_INSET = 4.2        # screw axis from the outer wall surface
HEAD_SEAT = Z_SPLIT - 7.6                      # M2x10: tip 2.4 mm above the split, through the nut
SCREW_BOSS_R = HEAD_D / 2 + 1.5                # solid column kept around each counterbore in the hollow underside
# ribs across the hollow underside: stiffen the floor (less drumming, less warping) and split the cavity
RIB_T = 2.0
RIB_X = (-108.0, -72.0, -36.0, 0.0, 36.0, 72.0, 108.0)   # front-to-back ribs
RIB_Y = (0.0,)                                            # left-to-right rib
NUT_AF, NUT_T = 4.7, 1.8                       # M2 nut pocket (4.0 mm AF, + paint); 1.8 deep so the painted ceiling (~1.6) clamps the 1.6 mm nut
USB_W, USB_H = 14.0, 9.5  # room for the plug overmold and the board moving on its gaskets
USB_Z = -1.63             # receptacle centre (TYPE-C-31-M-12 on the back side)

# nameplate on the back wall: a recessed pill the same height as the USB-C opening,
# with widely tracked capitals left standing at the wall surface
BADGE_TEXT = "EUGEO"
BADGE_FONT = "Futura"
BADGE_FONT_SIZE = 5.5     # cap height ~4.4 mm
BADGE_TRACKING = 2.4      # extra space between letters
BADGE_H = USB_H
BADGE_PAD = 8.5           # text end to pill end
BADGE_DEPTH = 0.6
BADGE_X = -100.0          # right-hand side when looking at the back
RIVET_D = 1.3


def to_case(x, y):
    return (x - CX, CY - y)


def wordmark():
    """Letters laid out one by one (Text has no tracking), centred on the origin."""
    letters, x = [], 0.0
    for ch in BADGE_TEXT:
        t = Text(ch, BADGE_FONT_SIZE, font=BADGE_FONT, align=(Align.MIN, Align.NONE))
        bb = t.bounding_box()
        letters.append(Pos(x - bb.min.X, 0) * t)
        x += bb.size.X + BADGE_TRACKING
    width = x - BADGE_TRACKING
    cap = max(l.bounding_box().max.Y for l in letters)
    return [Pos(-width / 2, -cap / 2) * l for l in letters], width


def cover_solid():
    """Centre cover in case coordinates (bottom face at PCB top + standoff)."""
    (x1, x2), (y1, y2) = design.COVER_X, design.COVER_Y
    z0 = PCB_T + design.COVER_STANDOFF
    with BuildPart() as cover:
        with BuildSketch(Plane.XY.offset(z0)):
            with Locations(to_case((x1 + x2) / 2, (y1 + y2) / 2)):
                RectangleRounded(x2 - x1, y2 - y1, design.COVER_R)
        extrude(amount=design.COVER_T)
        with Locations(*[(*to_case(x, y), z0 - 1) for x, y in design.COVER_HOLES]):
            Cylinder(1.1, design.COVER_T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    return cover.part


def export_cover():
    part = cover_solid()
    export_step(part, os.path.join(ROOT, "case", "eugeo-cover.step"))
    export_stl(part, os.path.join(ROOT, "case", "eugeo-cover.stl"), tolerance=0.02, angular_tolerance=0.1)
    bb = part.bounding_box()
    print(f"cover {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")


def main():
    pocket_w, pocket_h = PCB_W + 2 * CLEARANCE, PCB_H + 2 * CLEARANCE
    outer_w, outer_h = pocket_w + 2 * WALL, pocket_h + 2 * WALL
    t = math.tan(math.radians(ANGLE))
    back_bottom = FRONT_BOTTOM - outer_h * t
    floor_bottom = FLOOR_TOP - FLOOR_T

    letters, text_w = wordmark()      # build the text outside BuildPart

    with BuildPart() as case:
        # body: rounded slab, cut by the tilted bottom plane
        with BuildSketch(Plane.XY.offset(back_bottom - 1)):
            RectangleRounded(outer_w, outer_h, CORNER_R)
        extrude(amount=Z_TOP - back_bottom + 1)
        bottom = Plane(origin=(0, -outer_h / 2, FRONT_BOTTOM), z_dir=(0, t, 1))
        split(bisect_by=bottom, keep=Keep.TOP)
        top_face = case.faces().sort_by(Axis.Z)[-1]
        fillet(top_face.edges(), TOP_FILLET)
        bottom_face = case.faces().sort_by(Axis.Z)[0]
        fillet(bottom_face.edges(), BOTTOM_FILLET)

        # pocket for PCB + plates
        with BuildSketch(Plane.XY.offset(FLOOR_TOP)):
            RectangleRounded(pocket_w, pocket_h, 2.0)
        extrude(amount=Z_TOP - FLOOR_TOP + 1, mode=Mode.SUBTRACT)
        def inside_pocket(e):
            bb = e.bounding_box()
            return (max(abs(bb.min.X), abs(bb.max.X)) <= pocket_w / 2 + 0.01
                    and max(abs(bb.min.Y), abs(bb.max.Y)) <= pocket_h / 2 + 0.01)
        rim = [e for e in case.edges().filter_by_position(Axis.Z, Z_TOP - 0.01, Z_TOP + 0.01)
               if inside_pocket(e)]
        fillet(rim, RIM_FILLET)

        # hollow underside, leaving a floor, a ring to stand on, a boss around each screw and ribs
        screws = screw_points(outer_w, outer_h)

        def keep_solid():
            with Locations(*screws):
                Circle(SCREW_BOSS_R, mode=Mode.SUBTRACT)
            with Locations(*[(x, 0) for x in RIB_X]):
                Rectangle(RIB_T, outer_h, mode=Mode.SUBTRACT)
            with Locations(*[(0, y) for y in RIB_Y]):
                Rectangle(outer_w, RIB_T, mode=Mode.SUBTRACT)

        with BuildSketch(Plane.XY.offset(back_bottom - 2)):
            RectangleRounded(outer_w - 2 * BOTTOM_RIM, outer_h - 2 * BOTTOM_RIM, HOLLOW_CORNER_R)
            keep_solid()
        extrude(amount=floor_bottom - (back_bottom - 2), mode=Mode.SUBTRACT)

        # raised floor under both key areas (the centre keeps the deeper floor for USB-C etc.),
        # with the hollow underside raised by the same amount to keep the floor thickness
        for xa, xb in key_floor_x(pocket_w):
            with BuildSketch(Plane.XY.offset(FLOOR_TOP - 0.01)):
                with Locations(((xa + xb) / 2, 0)):
                    Rectangle(xb - xa, pocket_h)
            extrude(amount=KEY_FLOOR - FLOOR_TOP + 0.01)
            with BuildSketch(Plane.XY.offset(floor_bottom - 0.01)):
                RectangleRounded(outer_w - 2 * BOTTOM_RIM, outer_h - 2 * BOTTOM_RIM, HOLLOW_CORNER_R)
                with Locations(((xa + xb) / 2, 0)):
                    Rectangle(xb - xa, outer_h, mode=Mode.INTERSECT)
                keep_solid()
            extrude(amount=KEY_FLOOR - FLOOR_TOP + 0.01, mode=Mode.SUBTRACT)

        # tab recesses: the plates' gasket tabs and their PORON pads sit in these
        for x0, x1_, y0, y1_ in tab_recesses():
            with BuildSketch(Plane.XY.offset(RECESS_Z[0])):
                with Locations(((x0 + x1_) / 2, (y0 + y1_) / 2)):
                    Rectangle(x1_ - x0, y1_ - y0)
            extrude(amount=RECESS_Z[1] - RECESS_Z[0], mode=Mode.SUBTRACT)

        # USB-C opening in the back wall
        usb_plane = Plane(origin=(0, pocket_h / 2 - 1, USB_Z), x_dir=(1, 0, 0), z_dir=(0, 1, 0))
        with BuildSketch(usb_plane):
            SlotOverall(USB_W, USB_H)
        extrude(amount=WALL + 3, mode=Mode.SUBTRACT)

        # nameplate (reads left to right when viewed from behind)
        badge_w = text_w + 2 * BADGE_PAD
        badge = Plane(origin=(BADGE_X, outer_h / 2, USB_Z), x_dir=(-1, 0, 0), z_dir=(0, 1, 0))
        with BuildSketch(badge):
            SlotOverall(badge_w, BADGE_H)
        extrude(amount=-BADGE_DEPTH, mode=Mode.SUBTRACT)
        with BuildSketch(badge.offset(-BADGE_DEPTH)):
            for l in letters:
                insert(l)
            with Locations((-(badge_w / 2 - BADGE_H / 2), 0), (badge_w / 2 - BADGE_H / 2, 0)):
                Circle(RIVET_D / 2)
        extrude(amount=BADGE_DEPTH)

    body = case.part
    bottom = split(body, bisect_by=Plane.XY.offset(Z_SPLIT), keep=Keep.BOTTOM)
    top = split(body, bisect_by=Plane.XY.offset(Z_SPLIT), keep=Keep.TOP)
    # M2x10 from below: clearance hole + head counterbore in the tray, nut pocket in the frame
    for x, y in screw_points(outer_w, outer_h):
        bottom -= Pos(x, y, back_bottom - 2) * Cylinder(SCREW_D / 2, Z_SPLIT - back_bottom + 3,
                                                       align=(Align.CENTER, Align.CENTER, Align.MIN))
        bottom -= Pos(x, y, back_bottom - 2) * Cylinder(HEAD_D / 2, HEAD_SEAT - back_bottom + 2,
                                                       align=(Align.CENTER, Align.CENTER, Align.MIN))
        top -= Pos(x, y, Z_SPLIT - 0.1) * Cylinder(SCREW_D / 2, 3.4, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with BuildPart() as nut:
            with BuildSketch(Plane.XY.offset(Z_SPLIT - 0.1)):
                with Locations((x, y)):
                    RegularPolygon(NUT_AF / 2 / math.cos(math.radians(30)), 6)
            extrude(amount=NUT_T + 0.1)
        top -= nut.part

    os.makedirs(os.path.join(ROOT, "case"), exist_ok=True)
    export_cover()
    for name, part in (("bottom", bottom), ("top", top)):
        step = os.path.join(ROOT, "case", f"eugeo-case-{name}.step")
        stl = os.path.join(ROOT, "case", f"eugeo-case-{name}.stl")
        export_step(part, step)
        export_stl(part, stl, tolerance=0.02, angular_tolerance=0.1)
        bb = part.bounding_box()
        print(f"{name}: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
              f"volume {part.volume / 1000:.1f} cm3, valid={part.is_valid}")
    print("front height", round(Z_TOP - FRONT_BOTTOM, 1), "back height", round(Z_TOP - back_bottom, 1),
          "split at", round(Z_SPLIT, 2), "tab recesses", len(tab_recesses()))


def tab_recesses():
    """[(x0, x1, y0, y1)] in case coordinates for every plate tab (both plates)."""
    w, d, pad, tip = design.GASKET_TAB_W, design.GASKET_TAB_D, RECESS_PAD, RECESS_TIP
    hw, hh = PCB_W / 2, PCB_H / 2
    out = []
    for right in (False, True):
        for edge, pos in design.gasket_tabs(right):
            if edge in ("back", "front"):
                x = pos - CX
                y0, y1_ = hh - 0.1, hh + d + tip
                if edge == "front":
                    y0, y1_ = -y1_, -y0
                out.append((x - w / 2 - pad, x + w / 2 + pad, y0, y1_))
            else:
                y = CY - pos
                x0, x1_ = -(hw + d + tip), -hw + 0.1
                if right:
                    x0, x1_ = -x1_, -x0
                out.append((x0, x1_, y - w / 2 - pad, y + w / 2 + pad))
    return out


def key_floor_x(pocket_w):
    """[(x0, x1)] in case coordinates of the raised floor under the left and right key areas."""
    edge = design.LEFT_END - CX
    return [(-pocket_w / 2 - 0.5, edge), (-edge, pocket_w / 2 + 0.5)]


def screw_points(outer_w, outer_h):
    y = outer_h / 2 - SCREW_INSET
    xs = (outer_w / 2 - 22, 80.0)
    return [(sx * x, sy * y) for x in xs for sx in (-1, 1) for sy in (-1, 1)]


if __name__ == "__main__":
    main()
