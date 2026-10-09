"""Drawing sheets for the catch box stand, on the company A1 title block.

Projects the build123d model with hidden-line removal (project_to_viewport)
and draws the views, dimensions, balloons, BOM and notes directly in paper
space (mm, views pre-scaled) of a copy of the A1 title block DXF. Each sheet
is a paper-space layout in one DXF; a multi-page PDF and PNG previews are
rendered from it with ezdxf.

    python drawing.py path/to/A1_title_block.dxf

The template is not stored in this repository. Its path can also be given in
the CBS_TEMPLATE environment variable. Outputs go to ./output/a1 (git-ignored).
"""

import math
import os
import sys
from pathlib import Path

import ezdxf
from build123d import Compound, GeomType
from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, pymupdf
from ezdxf.enums import TextEntityAlignment

import model as m

OUT = Path(__file__).parent / "output" / "a1"
TEMPLATE_LAYOUT = "A1 TEMPLATE"
TITLE_BLOCK = "AMMJOHN A1 TITLE BLOCK 2025-07-01"
QA_BLOCK = "AJ QA"
QA_LINES_LAYER = "G-ANNO-TTLB"  # QA stamp checkbox lines drawn loose in the template
PAPER = (841.0, 594.0)

DRG_PREFIX = "AJXXX-0000-ME-DWG-"  # project number to be assigned
REV = "A"
DATE = "09-10-26"

# drawing area inside the title block border, above the title strip (paper mm)
AREA = (12.0, 61.0, 816.0, 570.0)

TXT = 2.5  # dimension / note text height
STYLE = "Arial Narrow"
STYLE_B = "Arial Narrow_B"

LAYERS = {
    # name: (colour, linetype, lineweight 1/100 mm)
    "CBS-VISIBLE": (7, "Continuous", 50),
    "CBS-HIDDEN": (7, "CBS_HIDDEN", 25),
    "CBS-PHANTOM": (8, "CBS_PHANTOM", 18),
    "CBS-CENTRE": (7, "CBS_CENTRE", 18),
    "CBS-DIM": (7, "Continuous", 18),
    "CBS-TEXT": (7, "Continuous", 25),
    "CBS-TABLE": (7, "Continuous", 25),
}

VIEW_DIRS = {
    # name: (viewport origin, up) ; u,v of each view in model axes
    "front": ((0, -10000, 0), (0, 0, 1)),  # u=X, v=Z
    "plan": ((0, 0, 10000), (0, 1, 0)),  # u=X, v=Y
    "side": ((10000, 0, 0), (0, 0, 1)),  # u=Y, v=Z (right side, third angle)
    "iso": ((6000, -8000, 5000), (0, 0, 1)),
}


def _edge_points(edge, scale):
    if edge.geom_type == GeomType.LINE:
        pts = [edge.position_at(0), edge.position_at(1)]
    else:
        n = max(8, int(edge.length * scale / 0.5))
        pts = [edge.position_at(i / n) for i in range(n + 1)]
    return [(p.X, p.Y) for p in pts]


# ======================================================================= DXF document
def prepare_document(template_path):
    doc = ezdxf.readfile(template_path)
    for name, pattern in {
        "CBS_HIDDEN": [2.5, 1.5, -1.0],
        "CBS_PHANTOM": [12.0, 8.0, -1.0, 0.5, -1.0, 0.5, -1.0],
        "CBS_CENTRE": [10.0, 7.0, -1.0, 1.0, -1.0],
    }.items():
        if name not in doc.linetypes:
            doc.linetypes.add(name, pattern=pattern, description=name)
    for name, (col, lt, lw) in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=col, linetype=lt, lineweight=lw)

    tpl = doc.layouts.get(TEMPLATE_LAYOUT)
    # remove the template's model viewport (paper-space viewport id 1 stays),
    # the internal review (QA) stamp and its loose checkbox lines
    for e in list(tpl):
        if e.dxftype() == "VIEWPORT" and e.dxf.id != 1:
            tpl.delete_entity(e)
        elif e.dxftype() == "INSERT" and e.dxf.name == QA_BLOCK:
            tpl.delete_entity(e)
        elif e.dxftype() == "LINE" and e.dxf.layer == QA_LINES_LAYER:
            tpl.delete_entity(e)
    return doc


def new_sheet_layout(doc, name, source=None):
    """First sheet: rename the template layout. Later sheets: copy the page
    setup and title block insert from the source layout."""
    if source is None:
        doc.layouts.rename(TEMPLATE_LAYOUT, name)
        return doc.layouts.get(name)
    tpl = doc.layouts.get(source)
    lay = doc.layouts.new(name)
    skip = {"handle", "owner", "name", "block_record_handle", "taborder", "viewport_handle"}
    for k, v in tpl.dxf_layout.dxfattribs().items():
        if k not in skip:
            lay.dxf_layout.dxf.set(k, v)
    # copy the title block insert with its attribute values
    for e in tpl.query("INSERT"):
        ref = lay.add_blockref(e.dxf.name, e.dxf.insert, dxfattribs={"layer": e.dxf.layer})
        ref.add_auto_attribs({a.dxf.tag: a.dxf.text for a in e.attribs})
    return lay


def fill_title_block(lay, values):
    for e in lay.query("INSERT"):
        if e.dxf.name == TITLE_BLOCK:
            for a in e.attribs:
                if a.dxf.tag in values:
                    a.dxf.text = values[a.dxf.tag]


# ======================================================================= sheet drawing API
class Sheet:
    """Paper-space drawing helpers. Coordinates in paper mm, y up."""

    def __init__(self, lay):
        self.lay = lay
        self.cur_scale = 1.0

    # ------------------------------------------------------------ primitives
    def line(self, p1, p2, layer="CBS-DIM"):
        self.lay.add_line(p1, p2, dxfattribs={"layer": layer})

    def poly(self, pts, layer="CBS-VISIBLE"):
        if len(pts) == 2:
            self.line(pts[0], pts[1], layer)
        else:
            self.lay.add_lwpolyline(pts, dxfattribs={"layer": layer})

    def rect(self, x, y, w, h, layer="CBS-TABLE"):
        self.lay.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": layer})

    def circle(self, c, r, layer="CBS-DIM", fill=False):
        self.lay.add_circle(c, r, dxfattribs={"layer": layer})
        if fill:
            h = self.lay.add_hatch(dxfattribs={"layer": layer})
            h.paths.add_edge_path().add_arc(c, r, 0, 360)

    def text(self, p, s, h=TXT, align="BOTTOM_CENTER", rot=0.0, bold=False, layer="CBS-TEXT"):
        t = self.lay.add_text(s, height=h, rotation=rot, dxfattribs={"layer": layer, "style": STYLE_B if bold else STYLE})
        t.set_placement(p, align=TextEntityAlignment[align])
        return t

    def arrow(self, tip, direction, size=3.0):
        dx, dy = direction
        n = math.hypot(dx, dy)
        dx, dy = dx / n, dy / n
        bx, by = tip[0] - dx * size, tip[1] - dy * size
        px, py = -dy * size / 3.5, dx * size / 3.5
        self.lay.add_solid([tip, (bx + px, by + py), (bx - px, by - py)], dxfattribs={"layer": "CBS-DIM"})

    # ------------------------------------------------------------ drafting
    def dim(self, p1, p2, at, orient, text=None, side_text=None):
        """Linear dimension between paper points p1, p2.
        orient 'h' measures x with the dimension line at y=at;
        orient 'v' measures y with the dimension line at x=at."""
        gap, ext = 1.0, 2.0
        if orient == "h":
            val = abs(p2[0] - p1[0])
            for p in (p1, p2):
                s = 1 if at > p[1] else -1
                self.line((p[0], p[1] + s * gap), (p[0], at + s * ext))
            a, b = (min(p1[0], p2[0]), at), (max(p1[0], p2[0]), at)
        else:
            val = abs(p2[1] - p1[1])
            for p in (p1, p2):
                s = 1 if at > p[0] else -1
                self.line((p[0] + s * gap, p[1]), (at + s * ext, p[1]))
            a, b = (at, min(p1[1], p2[1])), (at, max(p1[1], p2[1]))
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        txt = text if text is not None else f"{round(val / self.cur_scale):d}"
        tw = 0.6 * TXT * len(txt)
        if length > 8:
            self.line(a, b)
            self.arrow(a, (a[0] - b[0], a[1] - b[1]))
            self.arrow(b, (b[0] - a[0], b[1] - a[1]))
        else:
            u = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
            self.line((a[0] - u[0] * 6, a[1] - u[1] * 6), (b[0] + u[0] * 6, b[1] + u[1] * 6))
            self.arrow(a, u)
            self.arrow(b, (-u[0], -u[1]))
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if side_text == "out" or length < tw + 7:
            if orient == "h":
                self.text((b[0] + 7, at + 1), txt, align="BOTTOM_LEFT")
            else:
                self.text((at - 1, b[1] + 7), txt, rot=90, align="BOTTOM_LEFT")
        elif orient == "h":
            self.text((mid[0], at + 1), txt)
        else:
            self.text((at - 1, mid[1]), txt, rot=90)

    def balloon(self, target, at, label):
        r = 4.0
        dx, dy = target[0] - at[0], target[1] - at[1]
        n = math.hypot(dx, dy)
        self.line((at[0] + dx / n * r, at[1] + dy / n * r), target)
        self.circle(target, 0.7, fill=True)
        self.circle(at, r)
        self.text(at, label, h=3.0, align="MIDDLE_CENTER")

    def leader_note(self, target, at, lines, h=TXT):
        self.line(target, at)
        self.circle(target, 0.6, fill=True)
        right = at[0] >= target[0]
        x2 = at[0] + (4 if right else -4)
        self.line(at, (x2, at[1]))
        self.note((x2 + (1 if right else -1), at[1] + h * 0.5 + (len(lines) - 1) * h * 1.7), lines, h=h,
                  align="BOTTOM_LEFT" if right else "BOTTOM_RIGHT")

    def note(self, p, lines, h=TXT, bold_first=False, spacing=1.7, align="BOTTOM_LEFT"):
        for i, s in enumerate(lines):
            self.text((p[0], p[1] - i * h * spacing), s, h=h, align=align, bold=bold_first and i == 0)

    def table(self, x, y_top, cols, rows, row_h=6.0, h=2.5, title=None):
        """cols: list of (header, width, align). Draws downward from y_top."""
        if title:
            self.text((x, y_top + 2), title, h=3.5, align="BOTTOM_LEFT", bold=True)
        total_w = sum(c[1] for c in cols)
        all_rows = [[c[0] for c in cols]] + rows
        for r, row in enumerate(all_rows):
            yy = y_top - (r + 1) * row_h
            self.rect(x, yy, total_w, row_h)
            cx = x
            for (hdr, wdt, anc), val in zip(cols, row):
                tx = {"LEFT": cx + 1.5, "CENTER": cx + wdt / 2, "RIGHT": cx + wdt - 1.5}[anc]
                self.text((tx, yy + row_h / 2), str(val), h=h, align=f"MIDDLE_{anc}", bold=r == 0)
                cx += wdt
        cx = x
        for c in cols[:-1]:
            cx += c[1]
            self.line((cx, y_top), (cx, y_top - row_h * len(all_rows)), layer="CBS-TABLE")
        return y_top - row_h * len(all_rows)

    def label(self, p, title, scale_txt):
        t = self.text(p, title, h=5.0, bold=True)
        w = 0.55 * 5.0 * len(title)
        self.line((p[0] - w / 2, p[1] - 1.5), (p[0] + w / 2, p[1] - 1.5), layer="CBS-TEXT")
        self.text((p[0], p[1] - 7), scale_txt, h=3.5)
        return t

    # ------------------------------------------------------------ views
    def view(self, shape, direction, scale, origin, uv0=(0, 0), hidden=False, style="visible"):
        """Project shape and place model point uv0 at paper point origin.
        Returns mapping function model (u, v) -> paper (x, y)."""
        vp, up = VIEW_DIRS[direction]
        vis, hid = shape.project_to_viewport(vp, up, (0, 0, 0))

        def tf(u, v):
            return (origin[0] + (u - uv0[0]) * scale, origin[1] + (v - uv0[1]) * scale)

        if hidden:
            for e in hid:
                self.poly([tf(*p) for p in _edge_points(e, scale)], layer="CBS-HIDDEN")
        layer = "CBS-PHANTOM" if style == "phantom" else "CBS-VISIBLE"
        for e in vis:
            self.poly([tf(*p) for p in _edge_points(e, scale)], layer=layer)
        return tf

    def fit_view(self, shape, direction, box, phantoms=()):
        vp, up = VIEW_DIRS[direction]
        allsh = Compound([shape, *phantoms])
        vis, _ = allsh.project_to_viewport(vp, up, (0, 0, 0))
        bb = Compound(vis).bounding_box()
        s = min((box[2] - box[0]) / bb.size.X, (box[3] - box[1]) / bb.size.Y)
        origin = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        uv0 = (bb.center().X, bb.center().Y)
        for ph in phantoms:
            self.view(ph, direction, s, origin, uv0, style="phantom")
        self.view(shape, direction, s, origin, uv0)
        return s


def by_mark(items, mark):
    return next(it for it in items if it.mark == mark)


# ======================================================================= SHEET 1
def sheet1(s: Sheet, items):
    sc = 0.2
    s.cur_scale = sc
    stand = m.assembly(items)
    ph = m.catch_box_phantom()
    tub = m.tub_phantom()

    # --- front view 1:5 (u = X, v = Z)
    fo = (125, 112)
    F = s.view(stand, "front", sc, fo)
    s.view(ph, "front", sc, fo, style="phantom")
    s.view(tub, "front", sc, fo, style="phantom")
    s.line(F(0, -40), F(0, m.H + 40), layer="CBS-CENTRE")

    xl = F(-350, 0)[0]
    y0 = F(0, 0)[1]
    s.dim(F(-350, 0), F(350, 0), y0 - 10, "h", text="700 OVER FEET")
    s.dim(F(-290, m.BASE_Z), F(290, m.BASE_Z), y0 - 19, "h")
    s.dim(F(-250, m.BASE_Z), F(250, m.BASE_Z), y0 - 28, "h", text="500 CLEAR")
    s.dim(F(-290, 0), F(-290, m.MID_RAIL_Z), xl - 10, "v")
    s.dim(F(-290, 0), F(-290, m.PLATFORM_Z), xl - 19, "v", text=f"{m.PLATFORM_Z:.0f} PLATFORM")
    s.dim(F(-290, 0), F(-290, m.H), xl - 28, "v")
    s.dim(F(-m.HOLE_PITCH_X / 2, m.HOLE_TOP_Z), F(m.HOLE_PITCH_X / 2, m.HOLE_TOP_Z), F(0, m.H)[1] + 9, "h",
          text=f"{m.HOLE_PITCH_X:.0f} SLOT CRS")
    s.dim(F(-288, m.PLATFORM_Z + 230), F(288, m.PLATFORM_Z + 230), F(0, m.PLATFORM_Z + 230)[1], "h",
          text=f"{m.TRAY_CLEAR_W:.0f} TRAY CLEAR")

    s.balloon(F(-270, 1700), (xl - 40, F(0, 1700)[1]), "1")
    s.balloon(F(270, 700), (F(350, 0)[0] + 12, F(0, 700)[1]), "2")
    s.balloon(F(120, m.BASE_Z + 20), (F(150, 0)[0], F(0, 230)[1]), "3")
    s.balloon(F(-200, m.HOLE_TOP_Z + 10), (F(350, 0)[0] + 12, F(0, m.HOLE_TOP_Z + 60)[1]), "7")
    s.balloon(F(200, m.HOLE_BOT_Z + 10), (F(350, 0)[0] + 12, F(0, m.HOLE_BOT_Z - 60)[1]), "7")
    s.balloon(F(-150, m.PLATFORM_Z + 190), (F(350, 0)[0] + 12, F(0, m.PLATFORM_Z + 140)[1]), "8")
    s.balloon(F(-289, m.PLATFORM_Z + 60), (xl - 40, F(0, m.PLATFORM_Z + 60)[1]), "9")
    s.balloon(F(-320, 3), (xl - 40, F(0, 120)[1]), "10")
    s.balloon(F(-270, m.H - 1), (xl - 40, F(0, m.H + 40)[1]), "11")
    s.label((F(0, 0)[0], AREA[1] + 12), "FRONT VIEW", "SCALE 1:5")

    # --- right side view 1:5 (u = Y, front on the left)
    so = (225, 112)
    S = s.view(stand, "side", sc, so)
    s.view(ph, "side", sc, so, style="phantom")
    s.view(tub, "side", sc, so, style="phantom")
    xr = S(m.D_BASE, 0)[0]
    s.dim(S(0, 0), S(m.D, 0), y0 - 10, "h")
    s.dim(S(m.D, 0), S(m.D_BASE, 0), y0 - 10, "h")
    s.dim(S(0, 0), S(m.D_BASE, 0), y0 - 19, "h", text=f"{m.D_BASE:.0f} OVERALL BASE")
    s.dim(S(0, m.PLATFORM_Z), S(m.TRAY_D, m.PLATFORM_Z), S(0, m.PLATFORM_Z)[1] - 12, "h", text=f"{m.TRAY_D:.0f} TRAY")
    s.dim(S(0, m.PLATFORM_Z), S(0, m.PLATFORM_Z + m.TRAY_SIDE_H_FRONT), S(0, 0)[0] - 8, "v", side_text="out")
    s.dim(S(m.D, m.PLATFORM_Z), S(m.D, m.OUTLET_Z), xr + 8, "v", text="340 (REF)")
    s.dim(S(m.D, 0), S(m.D, m.STRUT_TOP_Z), xr + 16, "v", text=f"{m.STRUT_TOP_Z:.0f} STRUT")
    s.dim(S(m.D, 0), S(m.D, m.OUTLET_Z), xr + 24, "v", text=f"{m.OUTLET_Z:.0f} OUTLET (REF)")
    s.dim(S(m.D, 0), S(m.D, m.HOLE_BOT_Z), xr + 32, "v")
    s.dim(S(m.D, 0), S(m.D, m.HOLE_TOP_Z), xr + 40, "v")
    s.balloon(S(150, m.BASE_Z + 20), (S(150, 0)[0], S(0, 260)[1]), "4")
    s.balloon(S(400, m.BASE_Z + 20), (S(430, 0)[0], S(0, 260)[1]), "5")
    s.balloon(S(m.D + 60, 1000), (S(m.D + 160, 0)[0], S(0, 1000)[1]), "6")
    s.balloon(S(m.D + 2, 1250), (S(m.D + 160, 0)[0], S(0, 1250)[1]), "12")
    s.text((S(130, 0)[0], S(0, m.BOX_TOP_Z)[1] + 6), "CATCH BOX & TUB SHOWN", h=2.5)
    s.text((S(130, 0)[0], S(0, m.BOX_TOP_Z)[1] + 2), "CHAIN-DOTTED, NOT SUPPLIED", h=2.5)
    s.label((S(m.D_BASE / 2, 0)[0], AREA[1] + 12), "RIGHT SIDE VIEW", "SCALE 1:5")

    # --- isometric
    s.fit_view(stand, "iso", (405, 250, 625, 560), phantoms=(ph, tub))
    s.label((515, 238), "ISOMETRIC VIEW", "NOT TO SCALE")

    # --- bill of materials
    rows, total = [], 0.0
    for it in items:
        mass = it.mass_each * it.qty
        total += mass
        rows.append([it.mark, it.qty, it.description, it.material,
                     f"{it.length:.0f}" if it.length else "-", f"{mass:.1f}"])
    rows.append(["", "", "TOTAL PER STAND (APPROX., EXCL. FIXINGS)", "", "", f"{total:.1f}"])
    cols = [("ITEM", 11, "CENTER"), ("QTY", 10, "CENTER"), ("DESCRIPTION", 66, "LEFT"),
            ("MATERIAL", 44, "LEFT"), ("LENGTH", 16, "CENTER"), ("kg", 14, "CENTER")]
    s.table(AREA[2] - 4 - sum(c[1] for c in cols), AREA[3] - 8, cols, rows, row_h=6.0, h=2.4,
            title="BILL OF MATERIALS (PER STAND)")

    # --- design checks from the model parameters
    chk = [["OK" if ok else "CHECK", msg.upper()] for ok, msg in m.checks()]
    s.table(AREA[2] - 4 - 161, 395, [("", 14, "CENTER"), ("DESIGN CHECK (MODEL PARAMETERS)", 147, "LEFT")],
            chk, row_h=6.0, h=2.3, title="PARAMETER CHECKS")

    # --- open items
    s.note((405, 215), [
        "OPEN ITEMS - TO BE CONFIRMED BEFORE FABRICATION",
        f"1. CATCH BOX BRACKETS: HORIZONTAL HOLE CRS (SKETCH \"31.5\", TAKEN AS {m.HOLE_PITCH_X:.0f}), VERTICAL",
        f"    CRS {m.HOLE_PITCH_Z:.0f}, STAND-OFF (ASSUMED {m.BOX_STANDOFF:.0f}) AND LOWER HOLE HEIGHT ABOVE OUTLET",
        f"    (ASSUMED {m.BRKT_LOW_ABOVE_OUTLET:.0f}). SLOT HEIGHTS AND UPRIGHT LENGTH FOLLOW FROM THESE.",
        f"2. SAMPLE TUB SIZE (ASSUMED {m.TUB_L:.0f} x {m.TUB_W:.0f} x {m.TUB_H:.0f}). TRAY CLEAR {m.TRAY_CLEAR_W:.0f} x {m.TRAY_D - 2 * m.SHEET_T:.0f};",
        f"    {m.HAND_GAP:.0f} MIN HAND GAP EACH END NEEDS FRAME WIDTH = TUB LENGTH + {2 * m.HAND_GAP + 2 * m.SHEET_T:.0f}.",
        "3. GRATING BEARING BAR DIRECTION AT EACH LOCATION; 300 CLEAR BEHIND STAND FOR OUTRIGGER",
        "    AND CATCH BOX BOLT ACCESS.",
        "4. SENSOR CABLE EXIT SIDE (TABS SHOWN ON RIGHT UPRIGHT) AND CATCH BOX DOOR HINGE SIDE.",
        "5. CLIENT TO CONFIRM DURAGAL + COLD GALV (DESIGN LIFE ~10 YRS, C3) IS ACCEPTABLE.",
    ], h=2.6, bold_first=True, spacing=1.75)


# ======================================================================= SHEET 2
def sheet2(s: Sheet, items):
    sc = 0.2
    s.cur_scale = sc

    # --- plan on base frame 1:5 (all members with underside at base level)
    base = Compound([p for it in items for p in it.parts
                     if it.mark in ("1", "2", "3", "4", "5", "6", "10", "11") and p.bounding_box().min.Z < m.BASE_Z + 1])
    bo = (110, 400)
    B = s.view(base, "plan", sc, bo, hidden=True)
    xs = m.XL - (m.FOOT_X - m.SHS) / 2
    feet_y = [y0 + m.FOOT_Y / 2 for y0 in (0.0, m.D - m.SHS - 20, m.D_BASE - m.FOOT_Y)]
    for y in feet_y:
        for x in (xs, -xs):
            c = B(x, y)
            s.line((c[0] - 6, c[1]), (c[0] + 6, c[1]), layer="CBS-CENTRE")
            s.line((c[0], c[1] - 9), (c[0], c[1] + 9), layer="CBS-CENTRE")
    s.dim(B(xs, 0), B(-xs, 0), B(0, 0)[1] - 10, "h", text=f"{-2 * xs:.0f} SLOT CRS")
    s.dim(B(-350, 0), B(350, 0), B(0, 0)[1] - 19, "h")
    s.dim(B(-xs, feet_y[0]), B(-xs, feet_y[1]), B(350, 0)[0] + 10, "v")
    s.dim(B(-xs, feet_y[1]), B(-xs, feet_y[2]), B(350, 0)[0] + 10, "v")
    s.dim(B(350, 0), B(350, m.D_BASE), B(350, 0)[0] + 19, "v")
    s.dim(B(-350, 0), B(-350, feet_y[0]), B(-350, 0)[0] - 8, "v", side_text="out")
    s.text(B(0, 80), "FRONT OF STAND (BELOW)", h=2.5, align="MIDDLE_CENTER")
    s.label((B(0, 0)[0], B(0, 0)[1] - 38), "PLAN ON BASE FRAME", "SCALE 1:5")

    # --- foot plate detail 1:2
    sc2 = 0.5
    s.cur_scale = sc2
    foot = by_mark(items, "10").parts[0]
    fx0, fy0 = m.XL - (m.FOOT_X - m.SHS), 0.0
    P = s.view(foot, "plan", sc2, (240, 478), uv0=(fx0, fy0))
    s.dim(P(fx0, fy0), P(fx0 + m.FOOT_X, fy0), P(0, fy0)[1] - 8, "h")
    s.dim(P(fx0 + m.FOOT_X, fy0), P(fx0 + m.FOOT_X, fy0 + m.FOOT_Y), P(fx0 + m.FOOT_X, 0)[0] + 8, "v")
    s.dim(P(fx0, fy0 + 20), P(xs, fy0 + 20), P(0, fy0 + m.FOOT_Y)[1] + 8, "h", side_text="out")
    s.leader_note(P(xs, fy0 + m.FOOT_Y / 2 + 13), (P(fx0 + m.FOOT_X, 0)[0] + 18, P(0, fy0 + m.FOOT_Y)[1] + 6),
                  ["SLOT 14 x 40", "(M12 FIXING)"])
    s.note((P(fx0 + 60, 0)[0] - 8, P(0, fy0 + 70)[1]), ["LEG / BASE", "RAIL OVER"], h=2.2)
    s.text((P(fx0 + 50, 0)[0], P(0, fy0)[1] - 20), "ITEM 10 - FOOT PLATE, 6 OFF  (SCALE 1:2)", h=3.5, bold=True)

    # --- catch box angle (2 off, identical): elevation 1:5 and end view 1:2
    s.cur_scale = sc
    zc, ytop = m.HOLE_BOT_Z, 300
    ang = by_mark(items, "7").parts[1]
    A = s.view(ang, "front", sc, (110, ytop), uv0=(0, zc), hidden=True)
    s.dim(A(-250, zc + m.EA_GAUGE), A(250, zc + m.EA_GAUGE), A(0, zc)[1] + 15, "h")
    s.dim(A(-m.HOLE_PITCH_X / 2, zc), A(m.HOLE_PITCH_X / 2, zc), A(0, zc)[1] + 9, "h",
          text=f"{m.HOLE_PITCH_X:.0f} SLOT CRS")
    s.dim(A(-250, zc), A(-m.HOLE_PITCH_X / 2, zc), A(0, zc)[1] - 9, "h", text=f"{250 - m.HOLE_PITCH_X / 2:.1f}")
    s.leader_note(A(m.HOLE_PITCH_X / 2 + 13, zc), (A(250, 0)[0] + 8, A(0, zc)[1] + 20),
                  [f"2 x SLOT {m.SLOT_W:.0f} WIDE x {m.SLOT_L:.0f} LONG", "ROUND ENDS, ON GAUGE LINE"])
    s.text((A(0, 0)[0], A(0, zc)[1] - 20), "ITEM 7 - CATCH BOX MOUNTING ANGLE, 2 OFF  (SCALE 1:5)", h=3.5, bold=True)
    s.cur_scale = sc2
    y0 = m.D - m.SHS
    E = s.view(ang, "side", sc2, (275, ytop), uv0=(y0, zc), hidden=True)
    s.dim(E(y0, zc), E(y0, zc + m.EA_GAUGE), E(y0, 0)[0] - 8, "v", text="22.5", side_text="out")
    s.dim(E(y0, zc + m.EA_GAUGE), E(y0 + m.EA, zc + m.EA_GAUGE), E(0, zc + m.EA_GAUGE)[1] + 8, "h")
    s.dim(E(y0 + m.EA, zc + m.EA_GAUGE - m.EA), E(y0 + m.EA, zc + m.EA_GAUGE), E(y0 + m.EA, 0)[0] + 8, "v")
    s.text((E(y0 + 20, 0)[0], E(0, zc)[1] - 20), "END VIEW 1:2", h=3.5, bold=True)
    s.cur_scale = sc

    # --- tray 1:5: front, plan above, side to right
    tray = Compound(by_mark(items, "8").parts + by_mark(items, "9").parts)
    z0 = m.PLATFORM_Z
    TF = s.view(tray, "front", sc, (420, 400), uv0=(0, z0))
    TP = s.view(tray, "plan", sc, (420, 465), uv0=(0, 0), hidden=True)
    TS = s.view(tray, "side", sc, (505, 400), uv0=(0, z0))
    s.dim(TF(-290, z0), TF(290, z0), TF(0, z0)[1] - 8, "h", text="580 O/A")
    s.dim(TF(-290, z0), TF(-290, z0 + m.TRAY_BACK_H), TF(-290, z0)[0] - 8, "v")
    s.dim(TF(290, z0), TF(290, z0 + m.TRAY_LIP_H), TF(290, z0)[0] + 8, "v", side_text="out")
    s.dim(TP(290, 0), TP(290, m.TRAY_D), TP(290, 0)[0] + 8, "v")
    for x, y in m.DRAIN_XY:
        c = TP(x, y)
        s.line((c[0] - 3, c[1]), (c[0] + 3, c[1]), layer="CBS-CENTRE")
        s.line((c[0], c[1] - 3), (c[0], c[1] + 3), layer="CBS-CENTRE")
    s.leader_note(TP(m.DRAIN_XY[-1][0], m.DRAIN_XY[-1][1]), (TP(290, 0)[0] + 20, TP(0, 200)[1]),
                  [f"4 x Ø{m.DRAIN_D:.0f} DRAIN", "Y = 60, X = ±70, ±200"])
    s.dim(TS(0, z0), TS(0, z0 + m.TRAY_SIDE_H_FRONT), TS(0, z0)[0] - 7, "v", side_text="out")
    s.dim(TS(m.TRAY_D, z0), TS(m.TRAY_D, z0 + m.TRAY_SIDE_H_BACK), TS(m.TRAY_D, z0)[0] + 7, "v")
    s.dim(TS(0, z0), TS(m.TRAY_D, z0), TS(0, z0)[1] - 8, "h")
    s.text((TF(0, z0)[0] + 40, TF(0, z0)[1] - 22), "ITEMS 8 & 9 - SHELF TRAY  (SCALE 1:5)", h=3.5, bold=True)
    s.note((345, 345), [
        "TRAY CONSTRUCTION",
        "ITEM 8: ONE BLANK, BASE + BACK (90°) + 15 FRONT LIP (90°), INSIDE BEND RADIUS 2.",
        "ITEM 9: 2 OFF TAPERED SIDES, 15 RETURN FLANGE FOLDED ALONG BOTTOM EDGE, LAPPED ON BASE.",
        "FIX SIDES TO BASE WITH 4 x Ø5 GALV BLIND RIVETS EACH + SEALANT; CORNERS SEALED.",
        "NO FUSION SEAM WELDS ON SHEET. SLOPED TOP EDGES 180° SAFE-EDGE HEM; FRONT TOP CORNERS R15.",
        "BACK PLATE: 2 x Ø5 RIVETS INTO EACH REAR UPRIGHT. BASE: 6 x M6 RIVNUTS INTO SHELF RAILS",
        "(TRAY REMOVABLE). CORNER RELIEF Ø6 AT FOLD INTERSECTIONS.",
    ], h=2.5, bold_first=True)

    # --- cut list and order
    rows = []
    for it in items:
        if it.length:
            rows.append([it.mark, it.description, it.material, f"{it.length:.0f}", it.qty,
                         f"{it.length * it.qty / 1000:.2f}"])
    shs_total = sum(it.length * it.qty for it in items if it.length and "SHS" in it.material) / 1000
    ea_total = sum(it.length * it.qty for it in items if it.length and "EA" in it.material) / 1000
    rows.append(["", f"PER STAND: SHS {shs_total:.2f} m, EA {ea_total:.2f} m", "", "", "", ""])
    rows.append(["", f"4 STANDS: SHS {4 * shs_total:.1f} m, EA {4 * ea_total:.1f} m", "", "", "", ""])
    cols = [("ITEM", 11, "CENTER"), ("DESCRIPTION", 62, "LEFT"), ("SECTION", 44, "LEFT"),
            ("CUT L", 16, "CENTER"), ("QTY", 11, "CENTER"), ("m", 14, "CENTER")]
    s.table(AREA[2] - 4 - sum(c[1] for c in cols), AREA[3] - 8, cols, rows, row_h=6.0, h=2.4,
            title="CUT LIST (PER STAND, SQUARE CUT -1/+0 UNLESS NOTED)")

    # --- general notes
    s.note((345, 300), [
        "GENERAL NOTES",
        "1.  DIMENSIONS IN mm. DO NOT SCALE. THIRD ANGLE PROJECTION. QUANTITY REQUIRED: 4 OFF.",
        "2.  SHS 40x40x2.0 DURAGAL C450L0 TO AS/NZS 1163. EA 40x40x5.0 DURAGAL (CONFIRM AVAILABILITY, ELSE",
        "     300PLUS HDG). PLATE 3 & 6 HDG TO AS/NZS 4680. SHEET 2.0 G300 Z275 TO AS 1397.",
        "3.  WELDING: GMAW SHORT-ARC, 0.9 WIRE, SP TO AS/NZS 1554.1 (AS/NZS 4600 FOR t < 3). SHS TO SHS 2.5 FW ALL",
        "     ROUND (LEG NOT LESS THAN WALL). EA TO SHS 4 FW ALL ROUND. WELD WITH LOCAL FUME EXTRACTION (ZINC).",
        "4.  CORROSION: WIRE-WHEEL ALL WELDS, CUT ENDS, HOLES AND SHEET EDGES; ZINC-RICH COLD GALV TO AS/NZS 3750.9,",
        "     2 COATS, MIN 100 µm DFT. DURAGAL + COLD GALV: DESIGN LIFE APPROX. 10 YEARS IN C3 EXPOSURE.",
        "5.  ALL OPEN SHS ENDS CAPPED: ITEM 11 PL 40x40x3 SEAL WELDED (UPRIGHT TOPS, FRONT LEG TOPS, OUTRIGGER ENDS).",
        "6.  BUILD SEQUENCE: SIDE FRAMES (LEG, UPRIGHT, SIDE RAILS, OUTRIGGER, STRUT) FLAT IN A TABLE JIG; JOIN WITH",
        "     CROSS RAILS IN A SQUARING JIG; FIT ITEM 7 ANGLES BOLTED TO A SLOT TEMPLATE. BALANCE WELDS SIDE TO SIDE.",
        "7.  TOLERANCES: FRAME 580 ±2, 300 ±2, DIAGONALS WITHIN 3, UPRIGHTS PLUMB WITHIN 2 OVER FULL HEIGHT.",
        "     DATUM A = UNDERSIDE OF FOOT PLATES. SLOT CENTRE HEIGHTS ±2 FROM A; 330 ±1 BETWEEN ROWS; 315 ±1.",
        "8.  STRUT ITEM 6: TOP END CUT TO SUIT UPRIGHT BACK FACE (LONG SNIPE), FILLET WELD ALL ROUND, SEAL.",
        "9.  CATCH BOX FIXING: 4 x M12 HDG 8.8/S BOLTS, HDG 50x50x5 SQUARE PLATE WASHERS OVER SLOTS, NYLOC NUTS,",
        "     40 Nm, RE-CHECK 1 MONTH AFTER INSTALL. SUPPORT BOX ON A PROP WHILE FITTING BOLTS.",
        "10. GRATING FIXING: 6 x M12 HDG 8.8 BOLTS THROUGH FOOT SLOTS, HDG 100x50x6 CLAMP PLATE UNDER GRATING",
        "     SPANNING MIN 3 BEARING BARS, NYLOC NUTS. DESIGN TENSION 0.8 kN ULS PER FIXING. LOCATE NEAR A GRATING",
        "     SUPPORT; CONFIRM GRATING PANEL CLIPS. LEVEL ±2 WITH GALV SHIM PACKS UNDER FEET (8 PER STAND).",
        "11. SAMPLE HOSE AND SENSOR CABLE TO BE FLEXIBLE AND SUPPORTED INDEPENDENTLY; NO RIGID CONNECTION",
        "     BETWEEN SAMPLER AND STAND. ROUTE SENSOR CABLE VIA ITEM 12 TABS, CLEAR OF TUB OPENING.",
        "12. HARD-STAMP UNIT No. CBS-1 TO CBS-4 ON FRONT BASE RAIL. ALL EXPOSED EDGES DEBURRED, NO SHARP CORNERS.",
        "13. MATERIAL ORDER (4 STANDS): 8 x 6.5 m SHS 40x40x2 DURAGAL (INCL. 1 SPARE), 1 x 6.5 m EA 40x40x5.",
    ], h=2.4, bold_first=True, spacing=1.75)


# ======================================================================= main
def render(doc, names, pdf_path, png_stem):
    import pymupdf as fitz

    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        color_policy=config.ColorPolicy.COLOR,
        lineweight_policy=config.LineweightPolicy.ABSOLUTE,
    )
    page = layout.Page(*PAPER, layout.Units.mm)
    out = fitz.open()
    for i, name in enumerate(names, 1):
        be = pymupdf.PyMuPdfBackend()
        fe = Frontend(RenderContext(doc), be, config=cfg)
        fe.draw_layout(doc.layouts.get(name), filter_func=lambda e: e.dxftype() != "OLE2FRAME")
        out.insert_pdf(fitz.open("pdf", be.get_pdf_bytes(page)))
        Path(f"{png_stem}{i}.png").write_bytes(be.get_pixmap_bytes(page, fmt="png", dpi=110))
    out.save(str(pdf_path))


def main():
    template = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CBS_TEMPLATE")
    if not template:
        sys.exit("usage: python drawing.py path/to/A1_title_block.dxf")
    OUT.mkdir(parents=True, exist_ok=True)
    items = m.build()
    doc = prepare_document(template)

    common = {
        "DRAWING_TITLE": "CLASSIFICATION SAMPLER CATCH BOX STAND",
        "REV": REV, "SIZE": "A1", "DATE": DATE, "DRAWN_BY": "-", "CHECKED_BY": "-", "SCALE": "1:5",
        "CLIENT": "CLIENT TBC", "PROJECT_TITLE_LINE1": "CLASSIFICATION SAMPLER",
        "PROJECT_TITLE_LINE2": "CATCH BOX STAND (4 OFF)",
        "REV1": REV, "DESCRIPTION1": "PRELIMINARY - ISSUED FOR INTERNAL REVIEW", "BY1": "-", "IR1": "-",
        "DATE1": DATE, "CHKD1": "-",
        "DRAWING_STATUS": "PRELIMINARY - NOT FOR CONSTRUCTION",
        "REFERENCE_DRAWING_NUMBER1": "UEMS PROPOSAL",
        "REFERENCE_DRAWING_DESCRIPTION1": "FABRICATOR PROPOSAL SKETCH 07-10-26",
    }
    sheets = [
        ("001", "GENERAL ARRANGEMENT", sheet1, "002", "FABRICATION DETAILS & NOTES"),
        ("002", "FABRICATION DETAILS & NOTES", sheet2, "001", "GENERAL ARRANGEMENT"),
    ]
    names = []
    for i, (num, subtitle, fn, ref_num, ref_desc) in enumerate(sheets):
        name = f"{DRG_PREFIX}{num}"
        lay = new_sheet_layout(doc, name, source=names[0] if names else None)
        fill_title_block(lay, {
            **common, "DRAWING_NUMBER": name, "DRAWING_SUBTITLE": subtitle,
            "REFERENCE_DRAWING_NUMBER2": f"{DRG_PREFIX}{ref_num}", "REFERENCE_DRAWING_DESCRIPTION2": ref_desc,
        })
        fn(Sheet(lay), items)
        names.append(name)

    stem = f"{DRG_PREFIX}001-002_rev{REV}"
    doc.saveas(OUT / f"{stem}.dxf")
    render(doc, names, OUT / f"{stem}.pdf", OUT / "sheet")
    print("written", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
