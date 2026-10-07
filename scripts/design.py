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

# Electrical matrix is 8 rows x 6 cols (14 GPIO):
#   left block  key (r, c)   -> ROW r,     COL c
#   right block key (r, 6+j) -> ROW r + 4, COL 5 - j   (mirrored, so both halves
#   share one straight column bus along the bottom edge)
# Rows and columns leave the RP2040 sideways: left rows/columns on its left pins,
# right ones on its right pins. The bottom edge carries the crystal, RUN and
# the two LEDs; the top edge the QSPI flash and USB.
MATRIX_ROWS = 8
MATRIX_COLS = 6
# RP2040 (QFN-56) GPIO -> package pin
GPIO_PIN = {0: 2, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 11, 9: 12, 10: 13, 11: 14,
            12: 15, 13: 16, 14: 17, 15: 18, 16: 27, 17: 28, 18: 29, 19: 30, 20: 31, 21: 32,
            22: 34, 23: 35, 24: 36, 25: 37, 26: 38, 27: 39, 28: 40, 29: 41}
ROW_GPIO = {0: 1, 1: 3, 2: 5, 3: 6, 4: 28, 5: 26, 6: 24, 7: 23}
COL_GPIO = {0: 9, 1: 10, 2: 11, 3: 20, 4: 19, 5: 18}
LED_GPIO = {"LED1": 16, "LED2": 17}

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
ZIGZAG = 2.38                     # every other diode steps towards the centre (as on Lumberjack)


def diode_x(side, k):
    """(anode x, cathode x) of diode k (0..23) in the left (0) / right (1) stack."""
    step = ZIGZAG if k % 2 else 0.0
    if side == 0:
        return DIODE_ANODE_X[0] + step, DIODE_CATHODE_X[0] + step
    return DIODE_ANODE_X[1] - step, DIODE_CATHODE_X[1] - step


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
            kx = diode_x(0 if side == "L" else 1, k)[1]
            if side == "L":
                pos = (kx, y, 180, "F")   # cathode right, anode left (towards keys)
            else:
                pos = (kx, y, 0, "F")
            add(f"D{n}", "1N4148", "eugeo:D_Small_ALT", FP_D,
                {"1": f"ROW{matrix_pos(r, c)[0]}", "2": key_net(n)}, pos, row=r, col=c)

    # --- MCU: RP2040 + QSPI flash (SMD, assembled by JLCPCB) ---------------
    u1 = {str(i): None for i in range(1, 58)}
    for pin in (1, 10, 22, 33, 42, 49, 43, 44, 48):      # IOVDD, ADC_AVDD, VREG_VIN, USB_VDD
        u1[str(pin)] = "+3V3"
    u1.update({"45": "+1V1", "23": "+1V1", "50": "+1V1",  # VREG_VOUT -> DVDD
               "19": "GND", "57": "GND",                 # TESTEN, exposed pad
               "20": "XIN", "21": "XOUT", "26": "RUN",           # SWCLK / SWDIO (24, 25) unused
               "46": "USB_D-", "47": "USB_D+",
               "51": "QSPI_SD3", "52": "QSPI_SCLK", "53": "QSPI_SD0", "54": "QSPI_SD2",
               "55": "QSPI_SD1", "56": "QSPI_SS"})
    for r, g in ROW_GPIO.items():
        u1[str(GPIO_PIN[g])] = f"ROW{r}"
    for c, g in COL_GPIO.items():
        u1[str(GPIO_PIN[g])] = f"COL{c}"
    for name, g in LED_GPIO.items():
        u1[str(GPIO_PIN[g])] = name
    add("U1", "RP2040", "eugeo:RP2040", "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm",
        u1, (152.4, 77.0, 0, "F"), lcsc="C2040")
    add("U2", "W25Q16JVSSIQ", "eugeo:W25Q16JVSS", "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
        {"1": "QSPI_SS", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": "GND", "5": "QSPI_SD0",
         "6": "QSPI_SCLK", "7": "QSPI_SD3", "8": "+3V3"}, (145.2, 69.6, 180, "F"), lcsc="C131025")
    # decoupling (0402). All +3V3 pins are tied by a copper ring inside the pin
    # ring (build_pcb.py), so each capacitor sits on the outer end of one pin.
    # C12 / C13 sit on the back, right under the vias of pins 22 / 23.
    smd_c = "Capacitor_SMD:C_0402_1005Metric"
    decaps = [  # ref, value, supply net, (x, y, rot, side)
        ("C10", "100n", "+3V3", (147.12, 74.4, 180, "F")),   # IOVDD 1
        ("C11", "100n", "+3V3", (147.12, 78.0, 180, "F")),   # IOVDD 10
        ("C12", "100n", "+3V3", (151.3, 80.6, 180, "B")),      # IOVDD 22
        ("C13", "100n", "+1V1", (154.5, 80.6, 0, "B")),      # DVDD 23
        ("C14", "100n", "+3V3", (157.68, 78.0, 0, "F")),     # IOVDD 33
        ("C15", "100n", "+3V3", (157.68, 74.4, 0, "F")),     # IOVDD 42
        ("C17", "1u", "+3V3", (156.3, 72.7, 0, "F")),        # VREG_VIN 44 / ADC_AVDD 43
        ("C18", "1u", "+1V1", (154.45, 70.7, 90, "F")),      # VREG_VOUT 45
        ("C20", "100n", "+1V1", (152.75, 70.6, 90, "F")),    # DVDD 50
        ("C22", "100n", "+3V3", (141.612, 73.2, 270, "F")),  # flash VCC
    ]
    for ref, value, net, pos in decaps:
        add(ref, value, "eugeo:C_Small", smd_c, {"1": net, "2": "GND"}, pos,
            lcsc="C1525" if value == "100n" else "C52923")
    add("R11", "1k", "eugeo:R_Small", "Resistor_SMD:R_0402_1005Metric", {"1": "XOUT", "2": "XOUT_X"},
        (152.6, 82.5, 270, "F"), lcsc="C11702")

    # --- clock, reset, bootloader (through-hole, on show) --------------------
    add("Y1", "12MHz", "eugeo:Crystal_Small", "Crystal:Crystal_HC49-4H_Vertical",
        {"1": "XIN", "2": "XOUT_X"}, (151.4, 88.0, 0, "F"))
    add("C1", "22p", "eugeo:C_Small", "Capacitor_THT:C_Disc_D3.0mm_W1.6mm_P2.50mm",
        {"1": "XIN", "2": "GND"}, (150.0, 92.6, 0, "F"))
    add("C2", "22p", "eugeo:C_Small", "Capacitor_THT:C_Disc_D3.0mm_W1.6mm_P2.50mm",
        {"1": "XOUT_X", "2": "GND"}, (155.0, 92.6, 0, "F"))
    add("SW1", "RESET", "eugeo:SW_Push", "Button_Switch_THT:SW_PUSH_6mm",
        {"1": "RUN", "2": "GND"}, (143.0, 105.0, 90, "F"))
    add("SW2", "BOOT", "eugeo:SW_Push", "Button_Switch_THT:SW_PUSH_6mm",
        {"1": "BOOTSEL", "2": "GND"}, (143.0, 115.0, 90, "F"))
    add("R9", "10k", "eugeo:R_Small", FP_R, {"1": "+3V3", "2": "RUN"}, (150.2, 103.2, 90, "F"))
    add("R10", "1k", "eugeo:R_Small", FP_R, {"1": "QSPI_SS", "2": "BOOTSEL"}, (152.6, 103.2, 90, "F"))

    # --- power: VBUS -> polyfuse -> +5V -> MCP1700 -> +3V3 ---------------------
    add("F1", "100mA", "eugeo:Polyfuse_Small", "Fuse:Fuse_Bourns_MF-RHT100",
        {"1": "VBUS", "2": "+5V"}, (155.0, 101.8, 90, "F"))
    add("U3", "MCP1700-3302E", "eugeo:MCP1700-3302E_TO", "Package_TO_SOT_THT:TO-92_Inline_Wide",
        {"1": "GND", "2": "+5V", "3": "+3V3"}, (145.6, 90.2, 90, "F"))
    add("C6", "1u", "eugeo:C_Small", "Capacitor_THT:C_Disc_D3.0mm_W2.0mm_P2.50mm",
        {"1": "+5V", "2": "GND"}, (143.4, 95.6, 0, "F"))
    add("C7", "1u", "eugeo:C_Small", "Capacitor_THT:C_Disc_D3.0mm_W2.0mm_P2.50mm",
        {"1": "+3V3", "2": "GND"}, (143.4, 92.8, 0, "F"))
    add("C3", "10u", "eugeo:CP1_Small", "Capacitor_THT:CP_Radial_D4.0mm_P1.50mm",
        {"1": "+5V", "2": "GND"}, (156.25, 118.0, 180, "F"))

    # --- status LEDs ------------------------------------------------------
    add("R7", "1k", "eugeo:R_Small", FP_R, {"1": "LED1", "2": "LED1_A"}, (159.6, 96.4, 270, "F"))
    add("R8", "1k", "eugeo:R_Small", FP_R, {"1": "LED2", "2": "LED2_A"}, (161.8, 96.4, 270, "F"))
    add("LED1", "RED", "eugeo:LED_Small", "LED_THT:LED_D3.0mm", {"1": "GND", "2": "LED1_A"}, (159.6, 109.5, 90, "F"))
    add("LED2", "GREEN", "eugeo:LED_Small", "LED_THT:LED_D3.0mm", {"1": "GND", "2": "LED2_A"}, (161.8, 114.6, 90, "F"))

    # --- USB ------------------------------------------------------------------
    j1 = {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "S1": "GND",
          "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
          "A5": "CC1", "B5": "CC2", "A6": "CONN_D+", "B6": "CONN_D+",
          "A7": "CONN_D-", "B7": "CONN_D-", "A8": None, "B8": None}
    add("J1", "USB-C", "eugeo:USB_C_Receptacle_USB2.0", "eugeo:TYPE-C-31-M-12",
        j1, (CENTER_X, 62.106, 0, "B"))
    add("U4", "USBLC6-2SC6", "eugeo:USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
        {"1": "CONN_D+", "6": "CONN_D+", "3": "CONN_D-", "4": "CONN_D-", "5": "VBUS", "2": "GND"},
        (152.4, 65.6, 0, "B"), lcsc="C7519")
    add("R5", "5.1k", "eugeo:R_Small", FP_R, {"1": "GND", "2": "CC1"}, (138.6, 57.0, 0, "F"))
    add("R6", "5.1k", "eugeo:R_Small", FP_R, {"1": "GND", "2": "CC2"}, (138.6, 59.5, 0, "F"))
    add("R2", "27R", "eugeo:R_Small", FP_R, {"1": "CONN_D+", "2": "USB_D+"}, (158.6, 57.0, 0, "F"))
    add("R3", "27R", "eugeo:R_Small", FP_R, {"1": "CONN_D-", "2": "USB_D-"}, (158.6, 59.5, 0, "F"))

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

POWER_NETS = ("+5V", "+3V3", "GND", "VBUS")

# Centre cover: 2 mm acrylic on 10 mm M2 standoffs over the diodes / MCU / USB area.
# Top holes sit above the diode stacks, bottom ones inside the stacks because the
# column buses run along the bottom edge.
# extra PCB supports in the case (no screw): below the USB-C, clear of the back-side U4,
# and at the bottom edge
PILLARS = [(152.4, 70.2), (152.4, 125.5)]
COVER_HOLES = [(131.5, 59.4), (173.3, 59.4), (142.6, 118.8), (162.2, 118.8)]
COVER_X = (124.3, 180.5)          # clear of the inner keycaps (x <= 123.3 / >= 181.5)
COVER_Y = (EDGE[1], EDGE[3])
COVER_R = 3.0
COVER_T = 2.0
COVER_STANDOFF = 10.0             # above the PCB top surface

# shared by case.py and build_foams.py
CASE_CLEARANCE = 1.0     # PCB edge to case pocket wall
CASE_BOSS_D = 5.5        # screw boss under each mounting hole
