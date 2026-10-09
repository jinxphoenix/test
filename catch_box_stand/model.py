"""Classification sampler catch box stand - build123d model.

Coordinate system (mm):
    X  width, centred on the stand
    Y  depth, Y=0 at the front (open/access side), Y=D at the back
    Z  height, Z=0 on top of the floor grating

Run directly to export STEP/STL files to ./output.
"""

from dataclasses import dataclass, field
from pathlib import Path

from build123d import (
    Align,
    Box,
    Cylinder,
    Location,
    Part,
    Polyline,
    Pos,
    Compound,
    export_step,
    export_stl,
    extrude,
    make_face,
    loft,
    Rectangle,
    Plane,
    Axis,
)

# ---------------------------------------------------------------- parameters
W = 580.0  # overall width  (sketch: platform width min 570)
D = 300.0  # overall depth  (sketch: 300)
H = 1900.0  # overall height (top of rear uprights)

SHS = 40.0  # Duragal SHS 40 x 40 x 2
SHS_T = 2.0
EA = 40.0  # Duragal EA 40 x 40 x 5
EA_T = 5.0
SHEET_T = 2.0  # galvanised sheet tray

PLATFORM_Z = 1050.0  # top of shelf tray (sketch: 1050)
SHELF_FRAME_TOP = PLATFORM_Z - SHEET_T
MID_RAIL_Z = 400.0  # underside of mid-height rails
OUTLET_Z = PLATFORM_Z + 340.0  # catch box outlet (sketch: 340 above platform)
BOX_TOP_Z = OUTLET_Z + 500.0  # top of catch box (sketch: 110 hopper + 390 body)

HOLE_PITCH_Z = 330.0  # catch box mounting hole centres, vertical (sketch)
HOLE_PITCH_X = 315.0  # catch box mounting hole centres, horizontal (sketch "31.5")
HOLE_TOP_Z = BOX_TOP_Z - 15.0  # upper hole row
HOLE_BOT_Z = HOLE_TOP_Z - HOLE_PITCH_Z  # lower hole row
SLOT_W = 14.0  # M12 bolts
SLOT_L = 40.0  # horizontal slots, +/-13 mm adjustment
EA_GAUGE = 22.5  # hole centre from heel of angle

TRAY_SIDE_H_BACK = 200.0
TRAY_SIDE_H_FRONT = 80.0
TRAY_BACK_H = 200.0
TRAY_D = D - SHS  # tray stops at the front face of the rear uprights

FIX_HOLE_D = 14.0  # floor fixing holes through base side rails (M12)
FIX_ACCESS_D = 25.0  # access hole in top wall for socket
FIX_HOLE_Y = (SHS + 40.0, D - SHS - 40.0)

STEEL_DENSITY = 7.85e-6  # kg/mm^3

XL = -W / 2  # left face
XR = W / 2  # right face
X_IN = W / 2 - SHS  # inner face of legs
RAIL_L_X = W - 2 * SHS  # rails between legs, along X
RAIL_L_Y = D - 2 * SHS  # rails between legs, along Y


@dataclass
class Item:
    """A bill-of-materials line: one or more identical parts."""

    mark: str
    description: str
    material: str
    length: float | None
    parts: list = field(default_factory=list)
    finish: str = "Galv"

    @property
    def qty(self):
        return len(self.parts)

    @property
    def mass_each(self):
        return self.parts[0].volume * STEEL_DENSITY


# ---------------------------------------------------------------- primitives
def shs(length: float, axis: str, x: float, y: float, z: float) -> Part:
    """SHS 40x40x2 of given length along axis, (x, y, z) = min corner."""
    size = {"X": (length, SHS, SHS), "Y": (SHS, length, SHS), "Z": (SHS, SHS, length)}[axis]
    inner = [s - 2 * SHS_T if i != "XYZ".index(axis) else s for i, s in enumerate(size)]
    outer = Box(*size, align=Align.MIN)
    hole = Pos(*[SHS_T if i != "XYZ".index(axis) else 0 for i in range(3)]) * Box(*inner, align=Align.MIN)
    return Pos(x, y, z) * (outer - hole)


def ea_horizontal(length: float, x: float, y_face: float, z_heel: float) -> Part:
    """EA 40x40x5 along X. Vertical leg face on plane Y=y_face facing -Y,
    toe leg pointing +Y (rearwards) at the bottom (heel at z_heel)."""
    prof = Polyline(
        (0, 0), (EA, 0), (EA, EA_T), (EA_T, EA_T), (EA_T, EA), (0, EA), (0, 0)
    )  # (y, z) local: y rearward, z up
    face = make_face(prof)
    face = Plane.YZ * face  # local x->Y, local y->Z
    angle = extrude(face, amount=length)
    return Pos(x, y_face, z_heel) * angle


def slot_cutter(xc: float, y0: float, zc: float, depth: float) -> Part:
    """Horizontal slot (SLOT_L x SLOT_W) through a plate normal to Y."""
    r = SLOT_W / 2
    body = Box(SLOT_L - SLOT_W, depth, SLOT_W, align=(Align.CENTER, Align.MIN, Align.CENTER))
    ends = [
        Pos(dx, 0, 0) * Cylinder(r, depth, rotation=(-90, 0, 0), align=(Align.CENTER, Align.CENTER, Align.MIN))
        for dx in (-(SLOT_L - SLOT_W) / 2, (SLOT_L - SLOT_W) / 2)
    ]
    return Pos(xc, y0, zc) * (body + ends[0] + ends[1])


def sheet_poly_x(points_yz, x0: float) -> Part:
    """Sheet plate in a YZ plane, thickness SHEET_T in +X from x0."""
    face = Plane.YZ * make_face(Polyline(*points_yz, points_yz[0]))
    return Pos(x0, 0, 0) * extrude(face, amount=SHEET_T)


# ---------------------------------------------------------------- assembly
def build():
    items: list[Item] = []

    def add(mark, desc, material, length, *parts, finish="Galv"):
        items.append(Item(mark, desc, material, length, list(parts), finish))

    # 1 rear uprights
    add(
        "1", "Rear upright", "SHS 40x40x2.0 Duragal", H,
        shs(H, "Z", XL, D - SHS, 0), shs(H, "Z", X_IN, D - SHS, 0),
    )
    # 2 front legs
    add(
        "2", "Front leg", "SHS 40x40x2.0 Duragal", SHELF_FRAME_TOP,
        shs(SHELF_FRAME_TOP, "Z", XL, 0, 0), shs(SHELF_FRAME_TOP, "Z", X_IN, 0, 0),
    )
    # 3 long rails between legs (X direction)
    long_rails = [
        shs(RAIL_L_X, "X", XL + SHS, 0, 0),  # base front
        shs(RAIL_L_X, "X", XL + SHS, D - SHS, 0),  # base back
        shs(RAIL_L_X, "X", XL + SHS, D - SHS, MID_RAIL_Z),  # mid back
        shs(RAIL_L_X, "X", XL + SHS, 0, SHELF_FRAME_TOP - SHS),  # shelf front
        shs(RAIL_L_X, "X", XL + SHS, D - SHS, SHELF_FRAME_TOP - SHS),  # shelf back
    ]
    add("3", "Cross rail", "SHS 40x40x2.0 Duragal", RAIL_L_X, *long_rails)

    # 4 base side rails with floor fixing holes
    base_sides = []
    for x0 in (XL, X_IN):
        rail = shs(RAIL_L_Y, "Y", x0, SHS, 0)
        for yh in FIX_HOLE_Y:
            rail -= Pos(x0 + SHS / 2, yh, -1) * Cylinder(FIX_HOLE_D / 2, SHS_T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
            rail -= Pos(x0 + SHS / 2, yh, SHS - SHS_T - 1) * Cylinder(FIX_ACCESS_D / 2, SHS_T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
        base_sides.append(rail)
    add("4", "Base side rail (drilled)", "SHS 40x40x2.0 Duragal", RAIL_L_Y, *base_sides)

    # 5 side rails (mid + shelf) and shelf centre bearer
    side_rails = [
        shs(RAIL_L_Y, "Y", XL, SHS, MID_RAIL_Z),
        shs(RAIL_L_Y, "Y", X_IN, SHS, MID_RAIL_Z),
        shs(RAIL_L_Y, "Y", XL, SHS, SHELF_FRAME_TOP - SHS),
        shs(RAIL_L_Y, "Y", X_IN, SHS, SHELF_FRAME_TOP - SHS),
        shs(RAIL_L_Y, "Y", -SHS / 2, SHS, SHELF_FRAME_TOP - SHS),
    ]
    add("5", "Side rail / shelf bearer", "SHS 40x40x2.0 Duragal", RAIL_L_Y, *side_rails)

    # 6 catch box mounting angles (slotted), between rear uprights,
    #   vertical leg flush with the front face of the uprights
    angles = []
    for z_hole in (HOLE_TOP_Z, HOLE_BOT_Z):
        a = ea_horizontal(RAIL_L_X, XL + SHS, D - SHS, z_hole - EA_GAUGE)
        for xs in (-HOLE_PITCH_X / 2, HOLE_PITCH_X / 2):
            a -= slot_cutter(xs, D - SHS - 1, z_hole, EA_T + 2)
        angles.append(a)
    add("6", "Catch box mounting angle (slotted)", "EA 40x40x5.0 Duragal", RAIL_L_X, *angles)

    # 7 shelf tray - single folded 2 mm sheet: base + 2 sides + back
    y_b = TRAY_D
    base = Pos(XL, 0, SHELF_FRAME_TOP) * Box(W, TRAY_D, SHEET_T, align=Align.MIN)
    side_pts = [
        (0, PLATFORM_Z),
        (y_b, PLATFORM_Z),
        (y_b, PLATFORM_Z + TRAY_SIDE_H_BACK),
        (0, PLATFORM_Z + TRAY_SIDE_H_FRONT),
    ]
    side_l = sheet_poly_x(side_pts, XL)
    side_r = sheet_poly_x(side_pts, XR - SHEET_T)
    back = Pos(XL + SHEET_T, y_b - SHEET_T, PLATFORM_Z) * Box(W - 2 * SHEET_T, SHEET_T, TRAY_BACK_H, align=Align.MIN)
    tray = base + side_l + side_r + back
    add("7", "Shelf tray (base, sides & back)", "2.0 galvanised sheet", None, tray)

    return items


def catch_box_phantom() -> Part:
    """Approximate envelope of the catch box, for context only (not supplied)."""
    body_w, body_d = 250.0, 200.0
    y0 = D - SHS - 30.0 - body_d  # 30 mm bracket stand-off
    body = Pos(-body_w / 2, y0, OUTLET_Z + 110) * Box(body_w, body_d, 390, align=Align.MIN)
    top = Plane.XY.offset(OUTLET_Z + 110) * Rectangle(body_w, body_d)
    bot = Plane.XY.offset(OUTLET_Z) * Rectangle(90, 70)
    hopper = Pos(0, y0 + body_d / 2, 0) * loft([top, bot])
    flanges = [
        Pos(xs - 25, D - SHS - 30, HOLE_BOT_Z - 15) * Box(50, 30, HOLE_PITCH_Z + 30, align=Align.MIN)
        for xs in (-HOLE_PITCH_X / 2, HOLE_PITCH_X / 2)
    ]
    return body + hopper + flanges[0] + flanges[1]


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
        print(f"{it.mark:>2} {it.qty:>2} x {it.description:<38} {it.material:<24} L={it.length}  {m:6.2f} kg")
    print(f"total {total:.1f} kg")
    print("bbox", asm.bounding_box())
