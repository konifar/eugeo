"""Rounded tray case for eugeo (Mojo60-like pebble shape), for SLA resin printing.

    .venv/bin/python scripts/case.py      # -> case/eugeo-case.step, case/eugeo-case.stl

Coordinates: X/Y follow the PCB (centre of the board = origin, +Y = back / USB side),
Z = 0 is the underside of the PCB.

Assembly (no threaded inserts needed in resin):
  case boss (from below, M2x10 pan head) -> PCB -> M2 3.5 mm female-female standoff
  -> switch plate (optional M2x3 from the top)
"""
import math
import os
import sys

from build123d import (Align, Axis, BuildPart, BuildSketch, Circle, Cylinder, Keep, Locations, Mode,
                       Plane, Pos, RectangleRounded, SlotOverall, Text, export_step, export_stl,
                       extrude, fillet, insert, split)

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
FLOOR_TOP = -5.0         # space under the PCB for the USB-C receptacle / sockets / leads
FLOOR_T = 3.0
FRONT_BOTTOM = -10.0     # outer bottom at the front edge
ANGLE = 6.0              # typing angle (deg)
CORNER_R = 12.0          # plan-view outer corner radius
TOP_FILLET = 6.5
BOTTOM_FILLET = 4.5
RIM_FILLET = 1.0
BOTTOM_RIM = 6.0         # width of the ring the case stands on (bottom is hollowed out)

BOSS_D = design.CASE_BOSS_D
SCREW_D = 2.4            # M2 clearance
HEAD_D = 4.4             # M2 pan head counterbore
HEAD_SEAT = -6.4         # screw head seat: M2x10 then engages 2 mm of the 3.5 mm standoff
PILLARS = [(152.4, 68.0), (152.4, 125.5)]   # extra PCB supports (no screw), near the USB-C
USB_W, USB_H = 14.0, 8.5  # room for the plug overmold
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

        # hollow underside, leaving a floor and a ring to stand on
        with BuildSketch(Plane.XY.offset(back_bottom - 2)):
            RectangleRounded(outer_w - 2 * BOTTOM_RIM, outer_h - 2 * BOTTOM_RIM, CORNER_R - BOTTOM_RIM)
        extrude(amount=floor_bottom - (back_bottom - 2), mode=Mode.SUBTRACT)

        # screw bosses and support pillars standing on the floor up to the PCB
        holes = [to_case(x, y) for x, y in design.HOLES]
        with Locations(*[(x, y, FLOOR_TOP) for x, y in holes]):
            Cylinder(BOSS_D / 2, -FLOOR_TOP, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations(*[(*to_case(x, y), FLOOR_TOP) for x, y in PILLARS]):
            Cylinder(2.5, -FLOOR_TOP, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations(*[(x, y, floor_bottom - 1) for x, y in holes]):
            Cylinder(SCREW_D / 2, -floor_bottom + 2, align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
            Cylinder(HEAD_D / 2, HEAD_SEAT - floor_bottom + 1, align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)

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

    part = case.part
    os.makedirs(os.path.join(ROOT, "case"), exist_ok=True)
    export_cover()
    step = os.path.join(ROOT, "case", "eugeo-case.step")
    stl = os.path.join(ROOT, "case", "eugeo-case.stl")
    export_step(part, step)
    export_stl(part, stl, tolerance=0.02, angular_tolerance=0.1)
    bb = part.bounding_box()
    print(f"size {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
          f"volume {part.volume / 1000:.1f} cm3, valid={part.is_valid}")
    print("front height", round(Z_TOP - FRONT_BOTTOM, 1), "back height", round(Z_TOP - back_bottom, 1))
    print("wrote", step, stl)


if __name__ == "__main__":
    main()
