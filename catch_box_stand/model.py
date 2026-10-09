"""Classification sampler catch box stand - build123d model (rev B).

Coordinate system (mm):
    X  width, centred on the stand
    Y  depth, Y=0 at the front (operator side), +Y towards the back
    Z  height, Z=0 on top of the floor grating

Run directly to export STEP/STL files to ./output and print the BOM.
Values marked MEASURE are assumptions to be confirmed on site / from the
catch box and sample tub before fabrication.
"""

import math
from dataclasses import dataclass, field
from pathlib import Path

from build123d import (
    Align,
    Box,
    Compound,
    Cylinder,
    Keep,
    Part,
    Plane,
    Polyline,
    Pos,
    Rectangle,
    Rot,
    export_step,
    export_stl,
    extrude,
    loft,
    make_face,
)

# ---------------------------------------------------------------- parameters
# sections
SHS = 40.0  # Duragal SHS 40 x 40 x 2
SHS_T = 2.0
EA = 40.0  # Duragal EA 40 x 40 x 5
EA_T = 5.0
SHEET_T = 2.0  # galvanised sheet tray
CAP_T = 3.0  # welded cap plates on open SHS ends
FOOT_T = 6.0  # foot plates

# sample tub (MEASURE) - drives tray clear width check and outlet alignment
TUB_L = 560.0  # across the stand (X)
TUB_W = 300.0  # front to back (Y)
TUB_H = 200.0
TUB_TAPER = 30.0  # rim to base, each side
HAND_GAP = 35.0  # min finger gap each end of tub

# main frame
W = 580.0  # overall frame width (sketch: platform width min 570)
D = 300.0  # main frame depth (sketch: 300)
BASE_EXT_REAR = 250.0  # rear outrigger behind the rear uprights
D_BASE = D + BASE_EXT_REAR

PLATFORM_Z = 1050.0  # top of shelf tray base (sketch: 1050)
SHELF_FRAME_TOP = PLATFORM_Z - SHEET_T
MID_RAIL_Z = 400.0  # underside of mid-height rails
BASE_Z = FOOT_T  # underside of base frame (frame sits on foot plates)

# catch box interface (sketch + MEASURE)
OUTLET_Z = PLATFORM_Z + 340.0  # catch box outlet (sketch: 340 above platform)
BOX_TOP_Z = OUTLET_Z + 500.0  # top of catch box (sketch: 110 hopper + 390 body)
BOX_W, BOX_D = 250.0, 200.0  # body envelope (MEASURE)
BOX_STANDOFF = 30.0  # rear face of box body to front face of angles (MEASURE)
BRKT_LOW_ABOVE_OUTLET = 155.0  # lower bracket hole above outlet (MEASURE)
HOLE_PITCH_Z = 330.0  # mounting hole centres, vertical (sketch)
HOLE_PITCH_X = 315.0  # mounting hole centres, horizontal (sketch "31.5", MEASURE)
HOLE_BOT_Z = OUTLET_Z + BRKT_LOW_ABOVE_OUTLET
HOLE_TOP_Z = HOLE_BOT_Z + HOLE_PITCH_Z
SLOT_W = 14.0  # M12 bolts
SLOT_L = 40.0  # horizontal slots, +/-13 adjustment
EA_GAUGE = 22.5  # hole centre from heel of angle

# rear uprights stop just above the upper angle (heel is at the top)
H = 5.0 * -(-(HOLE_TOP_Z + EA_GAUGE + CAP_T) // 5.0)

# raking strut from rear upright to outrigger
STRUT_TOP_Z = 1400.0  # strut centreline meets upright back face
STRUT_BOT_Y = D_BASE - 30.0  # strut centreline meets outrigger top

# shelf tray
TRAY_D = D - SHS  # tray stops at the front face of the rear uprights
TRAY_SIDE_H_BACK = 200.0
TRAY_SIDE_H_FRONT = 80.0
TRAY_BACK_H = 200.0
TRAY_LIP_H = 15.0  # front upstand
TRAY_FLANGE = 15.0  # side plate bottom flange, lapped on the base
DRAIN_D = 10.0
DRAIN_XY = [(x, 60.0) for x in (-200.0, -70.0, 70.0, 200.0)]

# foot plates: outboard tab with a slot for the grating fixing
FOOT_X, FOOT_Y = 100.0, 80.0
FOOT_SLOT_W, FOOT_SLOT_L = 14.0, 40.0  # slot runs in Y

# cable tie tabs on right rear upright (side TBC)
CABLE_TAB_Z = (700.0, 1100.0, 1400.0)

STEEL_DENSITY = 7.85e-6  # kg/mm^3

XL = -W / 2  # left face
XR = W / 2  # right face
X_IN = W / 2 - SHS  # inner face of legs
RAIL_L_X = W - 2 * SHS  # rails between legs, along X
RAIL_L_Y = D - 2 * SHS  # rails between legs, along Y
TRAY_CLEAR_W = W - 2 * SHEET_T


@dataclass
class Item:
    """A bill-of-materials line: one or more identical parts."""

    mark: str
    description: str
    material: str
    length: float | None
    parts: list = field(default_factory=list)

    @property
    def qty(self):
        return len(self.parts)

    @property
    def mass_each(self):
        return self.parts[0].volume * STEEL_DENSITY


# ---------------------------------------------------------------- primitives
def shs(length: float, axis: str, x: float, y: float, z: float) -> Part:
    """SHS 40x40x2 of given length along axis, (x, y, z) = min corner."""
    ax = "XYZ".index(axis)
    size = [SHS, SHS, SHS]
    size[ax] = length
    inner = [s - 2 * SHS_T if i != ax else s for i, s in enumerate(size)]
    outer = Box(*size, align=Align.MIN)
    hole = Pos(*[SHS_T if i != ax else 0 for i in range(3)]) * Box(*inner, align=Align.MIN)
    return Pos(x, y, z) * (outer - hole)


def plate(sx, sy, sz, x, y, z) -> Part:
    return Pos(x, y, z) * Box(sx, sy, sz, align=Align.MIN)


def ea_horizontal(length: float, x: float, y_face: float, z_heel: float) -> Part:
    """EA 40x40x5 along X. Vertical leg face on plane Y=y_face facing -Y,
    toe leg pointing +Y (rearwards) at the TOP, heel at z_heel (top edge).
    Toe-up so there is no upward-facing ledge to hold water or grain."""
    prof = Polyline(
        (0, 0), (EA_T, 0), (EA_T, EA - EA_T), (EA, EA - EA_T), (EA, EA), (0, EA), (0, 0)
    )  # (y, z) local, z measured from the bottom of the vertical leg
    angle = extrude(Plane.YZ * make_face(prof), amount=length)
    return Pos(x, y_face, z_heel - EA) * angle


def slot_y_normal(xc, y0, zc, depth, length=SLOT_L, width=SLOT_W) -> Part:
    """Horizontal slot through a plate normal to Y."""
    r = width / 2
    body = Box(length - width, depth, width, align=(Align.CENTER, Align.MIN, Align.CENTER))
    for dx in (-(length - width) / 2, (length - width) / 2):
        body += Pos(dx, 0, 0) * Cylinder(r, depth, rotation=(-90, 0, 0), align=(Align.CENTER, Align.CENTER, Align.MIN))
    return Pos(xc, y0, zc) * body


def slot_z_normal(xc, yc, z0, depth, length, width) -> Part:
    """Slot running in Y through a plate normal to Z."""
    r = width / 2
    body = Box(width, length - width, depth, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for dy in (-(length - width) / 2, (length - width) / 2):
        body += Pos(0, dy, 0) * Cylinder(r, depth, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return Pos(xc, yc, z0) * body


def sheet_poly_x(points_yz, x0: float) -> Part:
    """Sheet plate in a YZ plane, thickness SHEET_T in +X from x0."""
    face = Plane.YZ * make_face(Polyline(*points_yz, points_yz[0]))
    return Pos(x0, 0, 0) * extrude(face, amount=SHEET_T)


def strut(x0: float) -> Part:
    """Raking SHS from rear upright back face down to the outrigger top,
    square tube trimmed by the two contact planes."""
    p_top = (D, STRUT_TOP_Z)
    p_bot = (STRUT_BOT_Y, BASE_Z + SHS)
    dy, dz = p_bot[0] - p_top[0], p_bot[1] - p_top[1]
    L = (dy**2 + dz**2) ** 0.5
    ang = math.degrees(math.atan2(dy, -dz))  # from vertical
    long = L + 200
    tube = Pos(0, 0, -long / 2) * (
        Box(SHS, SHS, long, align=(Align.MIN, Align.CENTER, Align.MIN))
        - Pos(SHS_T, 0, 0) * Box(SHS - 2 * SHS_T, SHS - 2 * SHS_T, long, align=(Align.MIN, Align.CENTER, Align.MIN))
    )
    mid = ((p_top[0] + p_bot[0]) / 2, (p_top[1] + p_bot[1]) / 2)
    tube = Pos(x0, *mid) * Rot(ang, 0, 0) * tube
    tube = tube.split(Plane((0, D, 0), z_dir=(0, 1, 0)), keep=Keep.TOP)
    tube = tube.split(Plane.XY.offset(BASE_Z + SHS), keep=Keep.TOP)
    return tube, L, ang


# ---------------------------------------------------------------- assembly
def build():
    items: list[Item] = []

    def add(mark, desc, material, length, *parts):
        items.append(Item(mark, desc, material, length, list(parts)))

    leg_r = H - CAP_T - BASE_Z
    leg_f = SHELF_FRAME_TOP - CAP_T - BASE_Z
    add(
        "1", "Rear upright", "SHS 40x40x2.0 Duragal", leg_r,
        shs(leg_r, "Z", XL, D - SHS, BASE_Z), shs(leg_r, "Z", X_IN, D - SHS, BASE_Z),
    )
    add(
        "2", "Front leg", "SHS 40x40x2.0 Duragal", leg_f,
        shs(leg_f, "Z", XL, 0, BASE_Z), shs(leg_f, "Z", X_IN, 0, BASE_Z),
    )
    add(
        "3", "Cross rail", "SHS 40x40x2.0 Duragal", RAIL_L_X,
        shs(RAIL_L_X, "X", XL + SHS, 0, BASE_Z),  # base front
        shs(RAIL_L_X, "X", XL + SHS, D - SHS, BASE_Z),  # base back
        shs(RAIL_L_X, "X", XL + SHS, D - SHS, MID_RAIL_Z),  # mid back
        shs(RAIL_L_X, "X", XL + SHS, 0, SHELF_FRAME_TOP - SHS),  # shelf front
        shs(RAIL_L_X, "X", XL + SHS, D - SHS, SHELF_FRAME_TOP - SHS),  # shelf back
    )
    add(
        "4", "Side rail / shelf bearer", "SHS 40x40x2.0 Duragal", RAIL_L_Y,
        *[shs(RAIL_L_Y, "Y", x0, SHS, z0) for z0 in (BASE_Z, MID_RAIL_Z, SHELF_FRAME_TOP - SHS) for x0 in (XL, X_IN)],
        shs(RAIL_L_Y, "Y", -SHS / 2, SHS, SHELF_FRAME_TOP - SHS),
    )
    out_l = BASE_EXT_REAR - CAP_T
    add(
        "5", "Rear outrigger", "SHS 40x40x2.0 Duragal", out_l,
        shs(out_l, "Y", XL, D, BASE_Z), shs(out_l, "Y", X_IN, D, BASE_Z),
    )
    s_l, s_r = strut(XL), strut(X_IN)
    strut_len = max(e.length for e in s_l[0].edges() if abs(e.tangent_at(0).Z) > 0.5)  # long point
    add("6", f"Raking strut, ends cut {s_l[2]:.1f}°", "SHS 40x40x2.0 Duragal", strut_len, s_l[0], s_r[0])

    # catch box mounting angles between rear uprights, face flush with uprights'
    # front; upper and lower are the same part with two 14 x 40 slots
    angles = []
    for z_hole in (HOLE_TOP_Z, HOLE_BOT_Z):
        a = ea_horizontal(RAIL_L_X, XL + SHS, D - SHS, z_hole + EA_GAUGE)
        for xs in (-HOLE_PITCH_X / 2, HOLE_PITCH_X / 2):
            a -= slot_y_normal(xs, D - SHS - 1, z_hole, EA_T + 2)
        angles.append(a)
    add("7", "Catch box mounting angle (slotted)", "EA 40x40x5.0 Duragal", RAIL_L_X, *angles)

    # tray 9: base + back + front lip, one blank with two folds
    base = plate(W, TRAY_D, SHEET_T, XL, 0, SHELF_FRAME_TOP)
    for x, y in DRAIN_XY:
        base -= Pos(x, y, SHELF_FRAME_TOP - 1) * Cylinder(DRAIN_D / 2, SHEET_T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    back = plate(W, SHEET_T, TRAY_BACK_H, XL, TRAY_D - SHEET_T, PLATFORM_Z)
    lip = plate(W - 2 * (SHEET_T + TRAY_FLANGE), SHEET_T, TRAY_LIP_H, XL + SHEET_T + TRAY_FLANGE, 0, PLATFORM_Z)
    add("8", "Tray base, back & front lip", "2.0 galvanised sheet", None, base + back + lip)

    # tray 10: tapered side plates with bottom return flange lapped on base
    def side(x_plate, x_flange):
        pts = [
            (0, PLATFORM_Z),
            (TRAY_D - SHEET_T, PLATFORM_Z),
            (TRAY_D - SHEET_T, PLATFORM_Z + TRAY_SIDE_H_BACK),
            (0, PLATFORM_Z + TRAY_SIDE_H_FRONT),
        ]
        return sheet_poly_x(pts, x_plate) + plate(TRAY_FLANGE, TRAY_D - SHEET_T, SHEET_T, x_flange, 0, PLATFORM_Z)

    add(
        "9", "Tray side plate", "2.0 galvanised sheet", None,
        side(XL, XL + SHEET_T), side(XR - SHEET_T, XR - SHEET_T - TRAY_FLANGE),
    )

    # 11 foot plates, outboard tab carries the fixing slot
    feet = []
    for y0 in (0.0, D - SHS - 20, D_BASE - FOOT_Y):
        for side_ in (-1, 1):
            x0 = XL - (FOOT_X - SHS) if side_ < 0 else XR - SHS
            xs = XL - (FOOT_X - SHS) / 2 if side_ < 0 else XR + (FOOT_X - SHS) / 2
            p = plate(FOOT_X, FOOT_Y, FOOT_T, x0, y0, 0)
            p -= slot_z_normal(xs, y0 + FOOT_Y / 2, -1, FOOT_T + 2, FOOT_SLOT_L, FOOT_SLOT_W)
            feet.append(p)
    add("10", "Foot plate, slotted", "PL 6 galv (HDG)", None, *feet)

    # 12 cap plates on open SHS ends
    caps = [plate(SHS, SHS, CAP_T, x0, D - SHS, H - CAP_T) for x0 in (XL, X_IN)]
    caps += [plate(SHS, SHS, CAP_T, x0, 0, SHELF_FRAME_TOP - CAP_T) for x0 in (XL, X_IN)]
    caps += [plate(SHS, CAP_T, SHS, x0, D_BASE - CAP_T, BASE_Z) for x0 in (XL, X_IN)]
    add("11", "Cap plate 40x40", "PL 3 galv", None, *caps)

    # 13 cable tie tabs, outboard face of right rear upright
    tabs = []
    for z in CABLE_TAB_Z:
        t = plate(25, 25, 3, XR, D - SHS + 7.5, z)
        t -= Pos(XR + 15, D - SHS + 20, z - 1) * Cylinder(3.25, 5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        tabs.append(t)
    add("12", "Cable tie tab 25x25, Ø6.5 hole", "PL 3 galv", None, *tabs)

    return items


def box_outlet_y():
    y0 = D - SHS - BOX_STANDOFF - BOX_D
    return y0 + BOX_D / 2


def catch_box_phantom() -> Part:
    """Approximate envelope of the catch box, for context only (not supplied)."""
    y0 = D - SHS - BOX_STANDOFF - BOX_D
    body = Pos(-BOX_W / 2, y0, OUTLET_Z + 110) * Box(BOX_W, BOX_D, 390, align=Align.MIN)
    top = Plane.XY.offset(OUTLET_Z + 110) * Rectangle(BOX_W, BOX_D)
    bot = Plane.XY.offset(OUTLET_Z) * Rectangle(90, 70)
    hopper = Pos(0, y0 + BOX_D / 2, 0) * loft([top, bot])
    brackets = [
        Pos(xs - 25, D - SHS - BOX_STANDOFF, HOLE_BOT_Z - 15) * Box(50, BOX_STANDOFF, HOLE_PITCH_Z + 30, align=Align.MIN)
        for xs in (-HOLE_PITCH_X / 2, HOLE_PITCH_X / 2)
    ]
    return body + hopper + brackets[0] + brackets[1]


def tub_y0():
    """Tub pushed against the tray back."""
    return TRAY_D - SHEET_T - TUB_W


def tub_phantom() -> Part:
    """Tapered tub, rim against the tray back."""
    yc = tub_y0() + TUB_W / 2
    bot = Plane.XY.offset(PLATFORM_Z) * Rectangle(TUB_L - 2 * TUB_TAPER, TUB_W - 2 * TUB_TAPER)
    top = Plane.XY.offset(PLATFORM_Z + TUB_H) * Rectangle(TUB_L, TUB_W)
    return Pos(0, yc - TUB_TAPER, 0) * loft([bot, top]).moved(Pos(0, TUB_TAPER, 0))


def checks():
    """Design checks on the parameters. Returns list of (ok, message)."""
    out = []
    tub_cy = tub_y0() + TUB_W / 2
    dy = box_outlet_y() - tub_cy
    out.append((abs(dy) <= 30, f"outlet {dy:+.0f} mm from tub centre (limit 30)"))
    gap = (TRAY_CLEAR_W - TUB_L) / 2
    out.append((gap >= HAND_GAP, f"hand gap each end {gap:.0f} mm (min {HAND_GAP:.0f}); W for min gap = {TUB_L + 2 * HAND_GAP + 2 * SHEET_T:.0f}"))
    out.append((HOLE_TOP_Z + EA_GAUGE <= H - CAP_T, f"upper angle heel {HOLE_TOP_Z + EA_GAUGE:.0f} below upright top {H:.0f}"))
    need = TUB_W - TUB_TAPER  # rim against back, base front edge must clear the lip
    room = TRAY_D - 2 * SHEET_T
    out.append((need <= room, f"tub rim-to-base-front {need:.0f} vs clear tray depth {room:.0f}"))
    clear = OUTLET_Z - (PLATFORM_Z + TUB_H)
    out.append((clear >= 100, f"drop from outlet to tub rim {clear:.0f} mm (min 100 for tub removal)"))
    return out


def assembly(items):
    return Compound([p for it in items for p in it.parts])


if __name__ == "__main__":
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    items = build()
    asm = assembly(items)
    export_step(asm, str(out / "catch_box_stand.step"))
    export_stl(asm, str(out / "catch_box_stand.stl"))
    total = 0.0
    for it in items:
        m = it.mass_each * it.qty
        total += m
        L = f"L={it.length:.0f}" if it.length else ""
        print(f"{it.mark:>2} {it.qty:>2} x {it.description:<36} {it.material:<22} {L:<7} {m:6.2f} kg")
    print(f"total {total:.1f} kg   H={H:.0f}")
    for ok, msg in checks():
        print("OK  " if ok else "WARN", msg)
    print("bbox", asm.bounding_box())
