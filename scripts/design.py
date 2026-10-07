"""eugeo: 6x4x2 (48 key) through-hole ortholinear keyboard derived from Lumberjack.

Single source of truth for parts, nets and placement. Used by gen_schematic.py
(system python) and build_pcb.py (KiCad bundled python).
"""

PROJECT = "eugeo"
REV = "1.0"

U = 19.05
ROWS = 4
COLS = 12
# Key centres follow Lumberjack's grid; only the bottom row is removed.
X_LEFT = [19.05 + U * c for c in range(6)]           # 19.05 .. 114.30
X_RIGHT = [190.5 + U * c for c in range(6)]          # 190.50 .. 285.75
KEY_X = X_LEFT + X_RIGHT
KEY_Y = [64.294 + U * r for r in range(ROWS)]        # 64.294 .. 121.444

EDGE = (9.95, 55.194, 294.85, 130.544)               # x1, y1, x2, y2
CENTER_X = (KEY_X[5] + KEY_X[6]) / 2                 # 152.4
LEFT_END = 124.3                                     # column buses join here
RIGHT_END = 180.5

# Electrical matrix is 8 rows x 6 cols (14 I/O):
#   left block  key (r, c)   -> ROW r,     COL c
#   right block key (r, 6+j) -> ROW r + 4, COL 5 - j   (mirrored, so both halves
#   share one straight column bus along the bottom edge)
# Rows stay on their own side of the MCU; nothing has to cross the DIP.
MATRIX_ROWS = 8
MATRIX_COLS = 6
ROW_PINS = {0: ("PD0", 2), 1: ("PD1", 3), 2: ("PD4", 6), 3: ("PD5", 11),
            4: ("PC5", 28), 5: ("PC1", 24), 6: ("PB5", 19), 7: ("PB1", 15)}
COL_PINS = {0: ("PB4", 18), 1: ("PB3", 17), 2: ("PB2", 16),
            3: ("PB0", 14), 4: ("PD7", 13), 5: ("PD6", 12)}
LED_PINS = {"LED1": ("PC4", 27), "LED2": ("PC3", 26)}

FP_MX = "eugeo:MX_Hotswap_Kailh"
FP_D = "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal"
FP_R = "Resistor_THT:R_Axial_DIN0204_L3.6mm_D1.6mm_P7.62mm_Horizontal"
FP_HOLE = "eugeo:MountingHole_M2_NPTH"


def key_ref(r, c):
    return r * COLS + c + 1


def matrix_pos(r, c):
    """Physical (row, col) -> electrical (row, col)."""
    return (r, c) if c < 6 else (r + 4, 11 - c)


def key_net(n):
    """Switch-to-diode net; matches the name KiCad derives from the schematic."""
    return f"Net-(D{n}-A)"


DIODE_ANODE_X = (128.5, 176.3)    # left / right stack, anode side faces the keys
DIODE_CATHODE_X = (136.12, 168.68)


def diode_stack_y(k):
    """24 diodes per side at 2.55 mm pitch (y = 64.0 .. 122.65).

    Group r (6 diodes) starts no higher than 11.6 mm above key row r, so the
    fan-out of row r never meets the tracks of row r-1 (see build_pcb.py).
    """
    return round(64.0 + 2.55 * k, 3)


def parts():
    """Return list of dicts: ref, value, symbol, footprint, pins{pin: net}, pos(x, y, rot, side)."""
    P = []

    def add(ref, value, symbol, footprint, pins, pos=None, **kw):
        d = dict(ref=ref, value=value, symbol=symbol, footprint=footprint, pins=pins, pos=pos)
        d.update(kw)
        P.append(d)

    # --- key matrix -------------------------------------------------------
    for r in range(ROWS):
        for c in range(COLS):
            n = key_ref(r, c)
            add(f"MX{n}", "MX", "eugeo:SW_Push", FP_MX,
                {"1": key_net(n), "2": f"COL{matrix_pos(r, c)[1]}"}, (KEY_X[c], KEY_Y[r], 0, "F"),
                row=r, col=c)
    for side in ("L", "R"):
        for k in range(24):
            r, j = divmod(k, 6)
            c = 5 - j if side == "L" else 6 + j
            n = key_ref(r, c)
            y = diode_stack_y(k)
            if side == "L":
                pos = (DIODE_CATHODE_X[0], y, 180, "F")   # cathode right, anode left (towards keys)
            else:
                pos = (DIODE_CATHODE_X[1], y, 0, "F")
            add(f"D{n}", "1N4148", "eugeo:D_Small_ALT", FP_D,
                {"1": f"ROW{matrix_pos(r, c)[0]}", "2": key_net(n)}, pos, row=r, col=c)

    # --- MCU --------------------------------------------------------------
    u1 = {str(i): None for i in range(1, 29)}
    u1.update({"1": "RESET", "4": "USB_D+", "5": "USB_D-", "7": "+5V", "8": "GND",
               "9": "XTAL1", "10": "XTAL2", "20": "+5V", "22": "GND",
               })
    for name, (_, pin) in LED_PINS.items():
        u1[str(pin)] = name
    for r, (_, pin) in ROW_PINS.items():
        u1[str(pin)] = f"ROW{r}"
    for c, (_, pin) in COL_PINS.items():
        u1[str(pin)] = f"COL{c}"
    add("U1", "ATMEGA328P-PU", "eugeo:ATmega328P-PU",
        "Package_DIP:DIP-28_W7.62mm", u1, (154.781, 71.596, 0, "F"))
    add("Y1", "16MHz", "eugeo:Crystal_Small", "Crystal:Crystal_HC49-4H_Vertical",
        {"1": "XTAL1", "2": "XTAL2"}, (148.828, 89.892, -90, "F"))
    add("C1", "22p", "eugeo:C_Small", "Capacitor_THT:C_Disc_D3.0mm_W1.6mm_P2.50mm",
        {"1": "XTAL2", "2": "GND"}, (144.066, 94.059, -90, "F"))
    add("C2", "22p", "eugeo:C_Small", "Capacitor_THT:C_Disc_D3.0mm_W1.6mm_P2.50mm",
        {"1": "XTAL1", "2": "GND"}, (144.066, 88.702, -90, "F"))
    add("C3", "4.7u", "eugeo:CP1_Small", "Capacitor_THT:CP_Radial_D4.0mm_P1.50mm",
        {"1": "+5V", "2": "GND"}, (149.0, 112.6, 180, "F"))
    add("C4", "100n", "eugeo:C_Small", "Capacitor_THT:C_Disc_D4.3mm_W1.9mm_P5.00mm",
        {"1": "+5V", "2": "GND"}, (155.0, 121.6, 0, "F"))
    add("C5", "100n", "eugeo:C_Small", "Capacitor_THT:C_Disc_D4.3mm_W1.9mm_P5.00mm",
        {"1": "+5V", "2": "GND"}, (143.5, 117.2, 0, "F"))
    add("R4", "10k", "eugeo:R_Small", FP_R, {"1": "+5V", "2": "RESET"}, (162.401, 109.1, 180, "F"))
    add("SW1", "RESET", "eugeo:SW_Push", "Button_Switch_THT:SW_PUSH_6mm",
        {"1": "RESET", "2": "GND"}, (144.066, 75.605, 90, "F"))
    add("SW2", "BOOT", "eugeo:SW_Push", "Button_Switch_THT:SW_PUSH_6mm",
        {"1": "ROW3", "2": "GND"}, (144.066, 107.156, 90, "F"))   # bootloader jumper on PD5
    add("J2", "AVR_ISP", "eugeo:Conn_02x03_Odd_Even",
        "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical",
        {"1": "GND", "2": "RESET", "3": "COL1", "4": "ROW6", "5": "+5V", "6": "COL0"},  # MOSI/SCK/MISO
        (144.066, 82.749, 90, "F"))

    # --- status LEDs ------------------------------------------------------
    add("R7", "1.5k", "eugeo:R_Small", FP_R, {"1": "LED1", "2": "LED1_A"}, (162.401, 111.84, 180, "F"))
    add("R8", "1.5k", "eugeo:R_Small", FP_R, {"1": "LED2", "2": "LED2_A"}, (162.401, 114.58, 180, "F"))
    add("LED1", "RED", "eugeo:LED_Small", "LED_THT:LED_D3.0mm", {"1": "GND", "2": "LED1_A"}, (154.9, 118.0, 0, "F"))
    add("LED2", "GREEN", "eugeo:LED_Small", "LED_THT:LED_D3.0mm", {"1": "GND", "2": "LED2_A"}, (159.9, 118.0, 0, "F"))

    # --- USB (V-USB) ------------------------------------------------------
    j1 = {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "S1": "GND",
          "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
          "A5": "CC1", "B5": "CC2", "A6": "CONN_D+", "B6": "CONN_D+",
          "A7": "CONN_D-", "B7": "CONN_D-", "A8": None, "B8": None}
    add("J1", "USB-C", "eugeo:USB_C_Receptacle_USB2.0", "eugeo:TYPE-C-31-M-12",
        j1, (CENTER_X, 62.106, 0, "B"))
    add("F1", "100mA", "eugeo:Polyfuse_Small", "Fuse:Fuse_Bourns_MF-RHT100",
        {"1": "VBUS", "2": "+5V"}, (158.6, 65.4, 0, "F"))
    add("R5", "5.1k", "eugeo:R_Small", FP_R, {"1": "GND", "2": "CC1"}, (138.6, 57.2, 0, "F"))
    add("R6", "5.1k", "eugeo:R_Small", FP_R, {"1": "GND", "2": "CC2"}, (138.6, 59.8, 0, "F"))
    add("R2", "75R", "eugeo:R_Small", FP_R, {"1": "CONN_D+", "2": "USB_D+"}, (138.6, 62.4, 0, "F"))
    add("R3", "75R", "eugeo:R_Small", FP_R, {"1": "CONN_D-", "2": "USB_D-"}, (158.6, 59.8, 0, "F"))
    add("R1", "1.5k", "eugeo:R_Small", FP_R, {"1": "CONN_D-", "2": "+5V"}, (158.6, 57.2, 0, "F"))
    add("D49", "3.6V", "eugeo:D_Zener_Small_ALT", FP_D,
        {"1": "CONN_D+", "2": "GND"}, (138.6, 65.0, 0, "F"))
    add("D50", "3.6V", "eugeo:D_Zener_Small_ALT", FP_D,
        {"1": "CONN_D-", "2": "GND"}, (158.6, 62.4, 0, "F"))

    # --- mounting holes (between keys, for plate/bottom sandwich) --------
    holes = [(28.575, 73.819), (28.575, 111.919), (104.775, 73.819), (104.775, 111.919),
             (200.025, 73.819), (200.025, 111.919), (276.225, 73.819), (276.225, 111.919)]
    for i, (x, y) in enumerate(holes, 1):
        add(f"H{i}", "M2", "eugeo:MountingHole", FP_HOLE, {}, (x, y, 0, "F"))
    # centre component cover (as on Lumberjack): 4 standoff holes around the MCU area
    for i, (x, y) in enumerate(COVER_HOLES, len(holes) + 1):
        add(f"H{i}", "M2", "eugeo:MountingHole", FP_HOLE, {}, (x, y, 0, "F"))
    return P


HOLES = [(28.575, 73.819), (28.575, 111.919), (104.775, 73.819), (104.775, 111.919),
         (200.025, 73.819), (200.025, 111.919), (276.225, 73.819), (276.225, 111.919)]

POWER_NETS = ("+5V", "GND", "VBUS")

# Centre cover: 2 mm acrylic on 10 mm M2 standoffs over the diodes / MCU / USB area.
# Top holes sit above the diode stacks, bottom ones inside the stacks because the
# column buses run along the bottom edge.
COVER_HOLES = [(131.5, 59.4), (173.3, 59.4), (139.4, 121.6), (165.4, 121.6)]
COVER_X = (124.3, 180.5)          # clear of the inner keycaps (x <= 123.3 / >= 181.5)
COVER_Y = (EDGE[1], EDGE[3])
COVER_R = 3.0
COVER_T = 2.0
COVER_STANDOFF = 10.0             # above the PCB top surface

# shared by case.py and build_foams.py
CASE_CLEARANCE = 1.0     # PCB edge to case pocket wall
CASE_BOSS_D = 5.5        # screw boss under each mounting hole
