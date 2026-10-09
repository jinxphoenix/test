"""Drawing sheets for the catch box stand.

Projects the build123d model with hidden-line removal (project_to_viewport),
then lays the views out on A3 sheets with dimensions, item balloons,
bill of materials and title block. Outputs SVG and a combined PDF.
"""

import datetime
import math
from pathlib import Path

import cairosvg
from build123d import Compound, GeomType

import model as m

OUT = Path(__file__).parent / "output"
SHEET_W, SHEET_H = 420.0, 297.0  # A3 landscape
FONT = "DejaVu Sans, Arial, Helvetica, sans-serif"
DRG_NO = "CBS-001"
REV = "A"
DATE = datetime.date(2026, 10, 9).strftime("%d/%m/%Y")

LW_THICK = 0.5
LW_THIN = 0.25
TXT = 2.5  # dimension / note text height

VIEW_DIRS = {
    # name: (viewport origin, up) ; u,v of each view in model axes
    "front": ((0, -10000, 0), (0, 0, 1)),  # u=X, v=Z
    "plan": ((0, 0, 10000), (0, 1, 0)),  # u=X, v=Y
    "side": ((10000, 0, 0), (0, 0, 1)),  # u=Y, v=Z  (right side, third angle)
    "iso": ((6000, -8000, 5000), (0, 0, 1)),
}


def _edge_points(edge, scale):
    if edge.geom_type == GeomType.LINE:
        pts = [edge.position_at(0), edge.position_at(1)]
    else:
        n = max(8, int(edge.length * scale / 0.5))
        pts = [edge.position_at(i / n) for i in range(n + 1)]
    return [(p.X, p.Y) for p in pts]


class Sheet:
    def __init__(self, number, of, title2, scale_txt):
        self.els = []
        self.number, self.of, self.title2, self.scale_txt = number, of, title2, scale_txt

    # ------------------------------------------------------------ primitives
    def line(self, p1, p2, w=LW_THIN, dash=None, color="#000"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.els.append(
            f'<line x1="{p1[0]:.3f}" y1="{p1[1]:.3f}" x2="{p2[0]:.3f}" y2="{p2[1]:.3f}" '
            f'stroke="{color}" stroke-width="{w}" stroke-linecap="round"{d}/>'
        )

    def poly(self, pts, w=LW_THICK, dash=None, color="#000"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        s = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
        self.els.append(
            f'<polyline points="{s}" fill="none" stroke="{color}" stroke-width="{w}" '
            f'stroke-linecap="round" stroke-linejoin="round"{d}/>'
        )

    def rect(self, x, y, w, h, lw=LW_THIN, fill="none"):
        self.els.append(
            f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" fill="{fill}" stroke="#000" stroke-width="{lw}"/>'
        )

    def circle(self, c, r, lw=LW_THIN, fill="none"):
        self.els.append(
            f'<circle cx="{c[0]:.3f}" cy="{c[1]:.3f}" r="{r:.3f}" fill="{fill}" stroke="#000" stroke-width="{lw}"/>'
        )

    def text(self, p, s, h=TXT, anchor="middle", rot=0, bold=False, color="#000"):
        s = s.replace("&", "&amp;").replace("  ", "\u00a0\u00a0").replace("<", "&lt;").replace(">", "&gt;")
        wt = ' font-weight="bold"' if bold else ""
        tr = f' transform="rotate({rot} {p[0]:.3f} {p[1]:.3f})"' if rot else ""
        self.els.append(
            f'<text x="{p[0]:.3f}" y="{p[1]:.3f}" font-family="{FONT}" font-size="{h * 1.4:.2f}" '
            f'text-anchor="{anchor}" fill="{color}"{wt}{tr}>{s}</text>'
        )

    def arrow(self, tip, direction, size=2.5):
        dx, dy = direction
        n = math.hypot(dx, dy)
        dx, dy = dx / n, dy / n
        bx, by = tip[0] - dx * size, tip[1] - dy * size
        px, py = -dy * size / 3.5, dx * size / 3.5
        self.els.append(
            f'<polygon points="{tip[0]:.3f},{tip[1]:.3f} {bx + px:.3f},{by + py:.3f} {bx - px:.3f},{by - py:.3f}" fill="#000"/>'
        )

    # ------------------------------------------------------------ drafting
    def dim(self, p1, p2, at, orient, text=None, side_text=None):
        """Linear dimension between sheet points p1, p2.
        orient 'h': measures x, dimension line at y=at.
        orient 'v': measures y, dimension line at x=at."""
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
        tw = 0.62 * TXT * len(txt)
        if length > 7:
            self.line(a, b)
            self.arrow(a, (a[0] - b[0], a[1] - b[1]))
            self.arrow(b, (b[0] - a[0], b[1] - a[1]))
        else:  # arrows outside
            u = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
            self.line((a[0] - u[0] * 5, a[1] - u[1] * 5), (b[0] + u[0] * 5, b[1] + u[1] * 5))
            self.arrow(a, u)
            self.arrow(b, (-u[0], -u[1]))
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if side_text == "out" or (length < tw + 6):
            # text beyond the far end
            if orient == "h":
                self.text((b[0] + 6 + tw / 2, at - 1), txt)
            else:
                self.text((at - 1, a[1] - 6 - tw / 2), txt, rot=-90)
        elif orient == "h":
            self.text((mid[0], at - 1), txt)
        else:
            self.text((at - 1, mid[1]), txt, rot=-90)

    def balloon(self, target, at, label):
        r = 3.5
        dx, dy = target[0] - at[0], target[1] - at[1]
        n = math.hypot(dx, dy)
        self.line((at[0] + dx / n * r, at[1] + dy / n * r), target)
        self.circle(target, 0.6, fill="#000")
        self.circle(at, r)
        self.text((at[0], at[1] + 1.25), label, h=TXT * 1.0)

    def note(self, p, lines, h=TXT, bold_first=False, spacing=1.7):
        for i, s in enumerate(lines):
            self.text((p[0], p[1] + i * h * spacing), s, h=h, anchor="start", bold=bold_first and i == 0)

    def table(self, x, y, cols, rows, row_h=5.5, h=2.2):
        """cols: list of (header, width, anchor)."""
        total_w = sum(c[1] for c in cols)
        all_rows = [[c[0] for c in cols]] + rows
        for r, row in enumerate(all_rows):
            yy = y + r * row_h
            self.rect(x, yy, total_w, row_h, fill="#eee" if r == 0 else "none")
            cx = x
            for (hdr, wdt, anc), val in zip(cols, row):
                tx = {"start": cx + 1.5, "middle": cx + wdt / 2, "end": cx + wdt - 1.5}[anc]
                self.text((tx, yy + row_h / 2 + h * 0.5), str(val), h=h, anchor=anc, bold=r == 0)
                cx += wdt
        cx = x
        for c in cols[:-1]:
            cx += c[1]
            self.line((cx, y), (cx, y + row_h * len(all_rows)))
        return y + row_h * len(all_rows)

    # ------------------------------------------------------------ views
    def view(self, shape, direction, scale, origin, uv0=(0, 0), hidden=False, style="solid"):
        """Project shape and place model point uv0 at sheet point origin.
        Returns a mapping function model(u, v) -> sheet (x, y)."""
        vp, up = VIEW_DIRS[direction]
        vis, hid = shape.project_to_viewport(vp, up, (0, 0, 0))

        def tf(u, v):
            return (origin[0] + (u - uv0[0]) * scale, origin[1] - (v - uv0[1]) * scale)

        if hidden:
            for e in hid:
                self.poly([tf(*p) for p in _edge_points(e, scale)], w=LW_THIN, dash="1.5,1")
        for e in vis:
            pts = [tf(*p) for p in _edge_points(e, scale)]
            if style == "phantom":
                self.poly(pts, w=LW_THIN, dash="6,1,1,1", color="#666")
            else:
                self.poly(pts, w=LW_THICK)
        tf.scale = scale
        return tf

    def fit_view(self, shape, direction, box, phantom=None):
        """Projected view scaled to fit box=(x0, y0, x1, y1). Used for the iso."""
        vp, up = VIEW_DIRS[direction]
        allsh = Compound([shape] + ([phantom] if phantom else []))
        vis, _ = allsh.project_to_viewport(vp, up, (0, 0, 0))
        bb = Compound(vis).bounding_box()
        s = min((box[2] - box[0]) / bb.size.X, (box[3] - box[1]) / bb.size.Y)
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        uc, vc = bb.center().X, bb.center().Y
        origin = (cx, cy)
        if phantom is not None:
            self.view(phantom, direction, s, origin, (uc, vc), style="phantom")
        self.view(shape, direction, s, origin, (uc, vc))
        return s

    def label(self, p, title, scale_txt):
        self.text(p, title, h=3.5, bold=True)
        self.line((p[0] - 0.31 * 3.5 * len(title), p[1] + 1.2), (p[0] + 0.31 * 3.5 * len(title), p[1] + 1.2), w=LW_THIN)
        self.text((p[0], p[1] + 5.5), scale_txt, h=2.5)

    # ------------------------------------------------------------ frame
    def frame(self):
        self.rect(10, 10, SHEET_W - 20, SHEET_H - 20, lw=0.7)
        # zone ticks
        for i in range(1, 8):
            x = 10 + i * (SHEET_W - 20) / 8
            self.line((x, 10), (x, 15))
            self.line((x, SHEET_H - 10), (x, SHEET_H - 15))
        # title block 180 x 52 bottom right
        x0, y0 = SHEET_W - 10 - 180, SHEET_H - 10 - 52
        self.rect(x0, y0, 180, 52, lw=0.5)
        self.line((x0, y0 + 16), (x0 + 180, y0 + 16))
        self.line((x0, y0 + 34), (x0 + 180, y0 + 34))
        self.text((x0 + 3, y0 + 6.5), "TITLE", h=1.8, anchor="start")
        self.text((x0 + 102, y0 + 9.5), "CLASSIFICATION SAMPLER CATCH BOX STAND", h=3.4, bold=True)
        self.text((x0 + 102, y0 + 14.2), self.title2, h=2.8)
        cells = [
            (0, 16, 45, "DRAWN", "CLAUDE (DRAFT)"),
            (45, 16, 45, "CHECKED", ""),
            (90, 16, 45, "APPROVED", ""),
            (135, 16, 45, "DATE", DATE),
            (0, 34, 40, "SCALE @ A3", self.scale_txt),
            (40, 34, 30, "UNITS", "mm"),
            (70, 34, 25, "SHEET", f"{self.number} OF {self.of}"),
            (95, 34, 55, "DRAWING No.", DRG_NO),
            (150, 34, 30, "REV", REV),
        ]
        for cx, cy, w, k, v in cells:
            if cx:
                self.line((x0 + cx, y0 + cy), (x0 + cx, y0 + cy + 18))
            self.text((x0 + cx + 1.5, y0 + cy + 4), k, h=1.8, anchor="start")
            self.text((x0 + cx + w / 2, y0 + cy + 12.5), v, h=3.2 if k != "DRAWING No." else 4, bold=k in ("DRAWING No.", "REV"))
        # third angle projection symbol in the title area
        sx, sy = x0 + 6, y0 + 10.5
        self.circle((sx + 13, sy), 3.2)
        self.circle((sx + 13, sy), 1.6)
        self.poly([(sx, sy - 1.6), (sx + 7, sy - 3.2), (sx + 7, sy + 3.2), (sx, sy + 1.6), (sx, sy - 1.6)], w=LW_THIN)
        self.line((sx - 1.5, sy), (sx + 18, sy), dash="3,0.8,0.8,0.8")
        self.line((sx + 13, sy - 4.5), (sx + 13, sy + 4.5), dash="3,0.8,0.8,0.8")
        # status stamp
        self.rect(x0, y0 - 8, 180, 8, lw=0.5)
        self.text((x0 + 90, y0 - 2.4), "PRELIMINARY - FOR REVIEW - NOT FOR CONSTRUCTION", h=3, bold=True, color="#b00")

    def svg(self):
        body = "\n".join(self.els)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_W}mm" height="{SHEET_H}mm" '
            f'viewBox="0 0 {SHEET_W} {SHEET_H}">\n<rect width="100%" height="100%" fill="#fff"/>\n{body}\n</svg>\n'
        )


def by_mark(items, mark):
    return next(it for it in items if it.mark == mark)


# ======================================================================= SHEET 1
def sheet1(items):
    s = Sheet(1, 2, "GENERAL ARRANGEMENT", "1:10")
    sc = 0.1
    s.cur_scale = sc
    stand = m.assembly(items)
    ph = m.catch_box_phantom()

    # --- front view (u = X, v = Z)
    F = s.view(stand, "front", sc, (85, 254))
    s.view(ph, "front", sc, (85, 254), style="phantom")
    # --- plan view above (u = X, v = Y; front edge at bottom)
    P = s.view(stand, "plan", sc, (85, 50))
    s.view(ph, "plan", sc, (85, 50), style="phantom")
    # --- right side view (u = Y; front on the left)
    S = s.view(stand, "side", sc, (152, 254))
    s.view(ph, "side", sc, (152, 254), style="phantom")

    # centre lines on front view
    s.line(F(0, -60), F(0, 1960), dash="6,1,1,1")
    s.line(P(0, -50), P(0, 350), dash="6,1,1,1")

    # front view dimensions
    s.dim(F(-290, 0), F(290, 0), F(0, 0)[1] + 9, "h")
    s.dim(F(-250, 1008), F(250, 1008), F(0, 0)[1] + 15, "h", text="500 CLEAR")
    s.dim(F(-290, 0), F(-290, m.MID_RAIL_Z), F(-290, 0)[0] - 8, "v")
    s.dim(F(-290, 0), F(-290, m.PLATFORM_Z), F(-290, 0)[0] - 16, "v")
    s.dim(F(-290, 0), F(-290, m.H), F(-290, 0)[0] - 24, "v")
    s.dim(F(-m.HOLE_PITCH_X / 2, m.HOLE_TOP_Z), F(m.HOLE_PITCH_X / 2, m.HOLE_TOP_Z), F(0, m.H)[1] - 7, "h",
          text=f"{m.HOLE_PITCH_X:.0f} SLOT CRS")
    s.dim(F(-288, m.PLATFORM_Z + 60), F(288, m.PLATFORM_Z + 60), F(0, m.PLATFORM_Z)[1] - 2.5, "h", text="576 TRAY CLEAR")

    # side view dimensions (u = Y)
    s.dim(S(0, 0), S(m.D, 0), S(0, 0)[1] + 9, "h")
    s.dim(S(0, m.PLATFORM_Z), S(m.TRAY_D, m.PLATFORM_Z), S(0, m.PLATFORM_Z)[1] + 6, "h", side_text="out")
    s.dim(S(0, m.PLATFORM_Z), S(0, m.PLATFORM_Z + m.TRAY_SIDE_H_FRONT), S(0, 0)[0] - 7, "v", side_text="out")
    xr = S(m.D, 0)[0]
    s.dim(S(m.TRAY_D, m.PLATFORM_Z), S(m.TRAY_D, m.PLATFORM_Z + m.TRAY_SIDE_H_BACK), xr + 7, "v")
    s.dim(S(m.D, 0), S(m.D, m.OUTLET_Z), xr + 14, "v", text=f"{m.OUTLET_Z:.0f} OUTLET (REF)")
    s.dim(S(m.D, 0), S(m.D, m.HOLE_BOT_Z), xr + 21, "v")
    s.dim(S(m.D, 0), S(m.D, m.HOLE_TOP_Z), xr + 28, "v")
    s.dim(S(m.D, m.PLATFORM_Z), S(m.D, m.OUTLET_Z), xr + 7, "v", text="340 (REF)", side_text="out")
    # plan dimension
    s.dim(P(290, 0), P(290, m.D), P(290, 0)[0] + 8, "v")

    # balloons
    s.balloon(F(-270, 1700), (F(-290, 0)[0] - 12, F(0, 1700)[1]), "1")
    s.balloon(F(270, 700), (F(290, 0)[0] + 10, F(0, 700)[1]), "2")
    s.balloon(F(100, 20), (F(150, 0)[0], F(0, 260)[1]), "3")
    s.balloon(F(200, m.HOLE_BOT_Z - 10), (F(290, 0)[0] + 10, F(0, m.HOLE_BOT_Z - 60)[1]), "6")
    s.balloon(F(200, m.PLATFORM_Z + 150), (F(290, 0)[0] + 10, F(0, m.PLATFORM_Z + 250)[1]), "7")
    s.balloon(S(150, 20), (S(150, 0)[0], S(0, 250)[1]), "4")
    s.balloon(S(150, m.MID_RAIL_Z + 20), (S(150, 0)[0], S(0, 650)[1]), "5")

    # view labels
    s.label((F(0, 0)[0], 278.5), "FRONT VIEW", "SCALE 1:10")
    s.label((S(150, 0)[0], 278.5), "RIGHT SIDE VIEW", "SCALE 1:10")
    s.text((P(0, 0)[0] - 34, P(0, 300)[1] - 2), "PLAN", h=3.5, bold=True)
    s.text((S(150, 0)[0], S(0, m.BOX_TOP_Z)[1] - 12), "CATCH BOX (REF ONLY,", h=2.0, color="#555")
    s.text((S(150, 0)[0], S(0, m.BOX_TOP_Z)[1] - 9), "NOT SUPPLIED)", h=2.0, color="#555")

    # --- isometric
    s.fit_view(stand, "iso", (235, 20, 405, 150), phantom=ph)
    s.text((320, 160), "ISOMETRIC VIEW (NTS)", h=3.5, bold=True)

    # --- bill of materials
    rows, total = [], 0.0
    for it in items:
        mass = it.mass_each * it.qty
        total += mass
        rows.append([it.mark, it.qty, it.description, it.material,
                     f"{it.length:.0f}" if it.length else "-", f"{mass:.1f}"])
    rows.append(["", "", "TOTAL (APPROX., EXCL. FIXINGS)", "", "", f"{total:.1f}"])
    cols = [("ITEM", 10, "middle"), ("QTY", 9, "middle"), ("DESCRIPTION", 58, "start"),
            ("MATERIAL", 48, "start"), ("LENGTH", 25, "middle"), ("kg", 15, "middle")]
    s.table(SHEET_W - 10 - 180 + 7, 172, cols, rows, row_h=5.0)

    s.frame()
    return s


# ======================================================================= SHEET 2
def sheet2(items):
    s = Sheet(2, 2, "FABRICATION DETAILS & NOTES", "AS SHOWN")
    sc = 0.2
    s.cur_scale = sc

    # --- plan on base frame (items 1, 2, 3, 4 below Z 300) with fixing holes
    base = Compound([p for it in items for p in it.parts if p.bounding_box().min.Z < 1 and it.mark in "1234"])
    B = s.view(base, "plan", sc, (75, 85), hidden=True)
    s.dim(B(-290, 0), B(290, 0), B(0, 0)[1] + 9, "h")
    s.dim(B(-270, m.FIX_HOLE_Y[0]), B(270, m.FIX_HOLE_Y[0]), B(0, 300)[1] - 7, "h", text="540 HOLE CRS")
    s.dim(B(290, 0), B(290, m.D), B(290, 0)[0] + 18, "v")
    s.dim(B(290, m.FIX_HOLE_Y[0]), B(290, m.FIX_HOLE_Y[1]), B(290, 0)[0] + 10, "v", text="140 CRS")
    s.dim(B(-290, 0), B(-270, m.FIX_HOLE_Y[0]), B(-290, 0)[0] - 8, "v", text="80")
    for y in m.FIX_HOLE_Y:
        for x in (-270, 270):
            c = B(x, y)
            s.line((c[0] - 4, c[1]), (c[0] + 4, c[1]), dash="2,0.6,0.6,0.6")
            s.line((c[0], c[1] - 4), (c[0], c[1] + 4), dash="2,0.6,0.6,0.6")
    lc = B(270, m.FIX_HOLE_Y[1])
    s.line(lc, (lc[0] + 30, lc[1] - 20))
    s.line((lc[0] + 30, lc[1] - 20), (lc[0] + 38, lc[1] - 20))
    s.note((lc[0] + 39, lc[1] - 22), ["4 x Ø14 THRU BOTTOM WALL", "Ø25 ACCESS IN TOP WALL"], h=2.2)
    s.label((B(0, 0)[0], 103), "PLAN ON BASE FRAME", "SCALE 1:5")

    # --- item 6 mounting angle: elevation from front 1:5 and end section 1:2
    ang = by_mark(items, "6").parts[1]  # lower angle
    zc = m.HOLE_BOT_Z
    A = s.view(ang, "front", sc, (75, 127), uv0=(0, zc), hidden=True)
    s.dim(A(-250, zc + 17.5), A(250, zc + 17.5), A(0, zc)[1] - 10, "h")
    s.dim(A(-m.HOLE_PITCH_X / 2, zc), A(m.HOLE_PITCH_X / 2, zc), A(0, zc)[1] - 5, "h", text=f"{m.HOLE_PITCH_X:.0f} SLOT CRS")
    s.dim(A(-250, zc), A(-m.HOLE_PITCH_X / 2, zc), A(0, zc)[1] + 8, "h", text=f"{250 - m.HOLE_PITCH_X / 2:.1f}")
    sc2 = 0.5
    s.cur_scale = sc2
    E = s.view(ang, "side", sc2, (163, 127), uv0=(m.D - m.SHS, zc), hidden=True)
    y0 = m.D - m.SHS
    s.dim(E(y0, zc - m.EA_GAUGE), E(y0, zc), E(y0, zc)[0] - 6, "v", text="22.5", side_text="out")
    s.dim(E(y0, zc - m.EA_GAUGE), E(y0 + m.EA, zc - m.EA_GAUGE), E(0, zc - m.EA_GAUGE)[1] + 7, "h")
    s.dim(E(y0, zc - m.EA_GAUGE), E(y0, zc - m.EA_GAUGE + m.EA), E(y0 + m.EA, zc)[0] + 7, "v")
    s.cur_scale = sc
    c = A(m.HOLE_PITCH_X / 2, zc)
    s.line(c, (c[0] + 8, c[1] + 8))
    s.line((c[0] + 8, c[1] + 8), (c[0] + 12, c[1] + 8))
    s.note((c[0] + 13, c[1] + 9), ["2 x SLOT 14 x 40"], h=2.2)
    s.label((A(0, zc)[0], 152), "ITEM 6 - MOUNTING ANGLE (2 OFF)", "SCALE 1:5")
    s.label((E(y0 + 20, zc)[0] + 3, 152), "END VIEW", "SCALE 1:2")

    # --- item 7 tray: front, plan, side at 1:5
    tray = by_mark(items, "7").parts[0]
    z0 = m.PLATFORM_Z
    TF = s.view(tray, "front", sc, (268, 150), uv0=(0, z0))
    TP = s.view(tray, "plan", sc, (268, 100), uv0=(0, 0))
    TS = s.view(tray, "side", sc, (345, 150), uv0=(0, z0))
    s.dim(TF(-290, z0), TF(290, z0), TF(0, z0)[1] + 6, "h", text="580 O/A")
    s.dim(TF(-290, z0 + 80), TF(-290, z0 + m.TRAY_BACK_H), TF(-290, z0)[0] - 7, "v", text="200")
    s.dim(TP(290, 0), TP(290, m.TRAY_D), TP(290, 0)[0] + 7, "v")
    s.dim(TS(0, z0), TS(0, z0 + m.TRAY_SIDE_H_FRONT), TS(0, z0)[0] - 6, "v", side_text="out")
    s.dim(TS(m.TRAY_D, z0), TS(m.TRAY_D, z0 + m.TRAY_SIDE_H_BACK), TS(m.TRAY_D, z0)[0] + 6, "v")
    s.dim(TS(0, z0), TS(m.TRAY_D, z0), TS(0, z0)[1] + 6, "h")
    s.label((TF(0, z0)[0], 167), "ITEM 7 - SHELF TRAY, 2.0 GALV SHEET", "SCALE 1:5")
    s.note((205, 185), [
        "Tray folded/welded from 2.0 galvanised sheet: base, two",
        "tapered sides and back. Corners seam welded. Base plug or",
        "stitch welded to shelf frame; back fixed to rear uprights.",
        "Drill 4 x Ø8 drain holes in base corners.",
    ], h=2.2)

    # --- cut list
    rows = []
    for it in items:
        if it.length:
            rows.append([it.mark, it.material, f"{it.length:.0f}", it.qty, f"{it.length * it.qty / 1000:.2f}"])
    shs_total = sum(it.length * it.qty for it in items if it.length and "SHS" in it.material) / 1000
    ea_total = sum(it.length * it.qty for it in items if it.length and "EA" in it.material) / 1000
    rows.append(["", f"TOTAL SHS {shs_total:.2f} m, EA {ea_total:.2f} m (PER STAND)", "", "", ""])
    cols = [("ITEM", 10, "middle"), ("SECTION", 72, "start"), ("CUT L", 20, "middle"), ("QTY", 12, "middle"), ("m", 15, "middle")]
    s.text((20, 164), "CUT LIST (PER STAND, SQUARE CUT)", h=3, anchor="start", bold=True)
    s.table(20, 167, cols, rows, row_h=4.6, h=2.0)

    # --- general notes
    s.note((20, 212), [
        "GENERAL NOTES",
        "1. Dimensions in mm. Do not scale. Third angle projection.",
        "2. SHS 40x40x2.0 Duragal C450L0 to AS/NZS 1163; EA 40x40x5.0 Duragal angle.",
        "3. Welds: 3 mm continuous fillet all round to AS/NZS 1554.1 (SP) unless noted.",
        "    Tray 2.0 sheet to frame: 25 long stitch welds @ 150 crs.",
        "4. Wire-wheel all welds; touch up with cold galvanising coating, 2 coats.",
        "5. Cap open SHS ends at tops of uprights with plastic end caps.",
        "6. Fix to Webforge C325MPG grating with 4 x M12 galv grating clamps through",
        "    base rail holes (fixing type to be confirmed by installer).",
        "7. Catch box mounting holes taken from sketch: 330 crs vertical, 315 crs",
        "    horizontal (sketch reads \"31.5\"). CONFIRM AGAINST CATCH BOX BRACKETS",
        "    BEFORE FABRICATION. Slots give ±13 horizontal adjustment.",
        "8. Shelf top (platform) 1050 above grating; catch box outlet 340 above",
        "    platform. Catch box shown chain-dotted for reference only.",
        "9. Quantity required: 4 off.",
        "10. Bolts by others: 4 x M12 catch box (with washers), 4 x M12 grating clamps.",
    ], h=2.1, bold_first=True, spacing=1.65)

    s.frame()
    return s


def main():
    OUT.mkdir(exist_ok=True)
    items = m.build()
    sheets = [sheet1(items), sheet2(items)]
    pdfs = []
    for sh in sheets:
        svg = sh.svg()
        stem = OUT / f"{DRG_NO}_sheet{sh.number}"
        stem.with_suffix(".svg").write_text(svg)
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(stem.with_suffix(".png")), output_width=3300)
        pdf = cairosvg.svg2pdf(bytestring=svg.encode())
        pdfs.append(pdf)
        stem.with_suffix(".pdf").write_bytes(pdf)
    from pypdf import PdfWriter

    writer = PdfWriter()
    for sh in sheets:
        writer.append(str(OUT / f"{DRG_NO}_sheet{sh.number}.pdf"))
    writer.write(str(OUT / f"{DRG_NO}.pdf"))
    for sh in sheets:
        (OUT / f"{DRG_NO}_sheet{sh.number}.pdf").unlink()
    print("written", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
