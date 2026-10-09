# Classification sampler catch box stand

This is a parametric build123d model and an A1 fabrication drawing set (2 sheets) for a free-standing galvanised stand. The stand carries the new catch box and the sample tub. It replaces the existing wall-mounted arrangement and bolts down to Webforge C325MPG grating.

## Inputs used

From the sketch and the fabricator's proposal email:

| Item | Value |
|---|---|
| Platform (shelf top) height above grating | 1050 |
| Catch box outlet above platform | 340 |
| Catch box body + hopper height | 390 + 110 = 500 |
| Catch box mounting holes | 330 crs vertical, 315 crs horizontal (see open items) |
| Stand depth | 300 (main frame) |
| Platform width | min 570 (tray clear width is 576) |
| Frame | Duragal SHS 40x40x2.0 |
| Catch box mounting angles | Duragal EA 40x40x5.0 |
| Shelf | 2.0 galvanised sheet, with sides and back |
| Finish | Welds wire-wheeled and cold galvanised |

## Design (rev A)

- **Frame:**
  - SHS frame, 580 W x 300 D. Rear uprights are 1905 high; front legs stop at the shelf.
  - Rails at the base, at 400 and at the shelf. The shelf has a centre bearer.
  - All open SHS ends are capped with seal-welded PL 3 plates.
- **Rear outrigger and struts:**
  - The base side rails continue 250 behind the rear uprights.
  - A raking SHS strut runs from each upright at 1400 down to the outrigger end.
  - Overall base is 700 W x 550 D.
- **Fixing to the grating:**
  - Six slotted PL 6 foot plates (14 x 40 slots). They sit outboard of the frame, so the M12 fixings can be placed in bar gaps on site.
  - Clamp plates go under the grating, and shim packs are used for levelling.
- **Catch box mounting:**
  - Two EA 40x40x5 angles between the rear uprights, with the toe leg at the top pointing back so no ledge holds water.
  - The upper angle has 40-wide open-top hang-on notches, so the box can hang on pre-fitted bolts while the lower bolts go in.
  - The lower angle has 14 x 40 slots. Slots and notches give ±13 horizontal adjustment.
- **Tray:**
  - Two-part 2.0 sheet. Item 9 is the base, back and 15 front lip in one blank. Item 10 is the two tapered side plates, each with a bottom return flange.
  - The sides are riveted and sealed to the base; there are no fusion welds on the sheet.
  - Hemmed top edges.
  - Four Ø10 drain holes, placed clear of the frame members.
  - The tray is held to the frame by rivnuts, so it can be removed.
- **Mass:** about 42 kg per stand.

### Structural checks

These are hand checks. Assumptions: catch box 20 kg, full tub 15 kg, a 0.3 kN service push at the top (0.45 kN ULS), outdoor C3 exposure.

| Check | Without outrigger and struts | Rev A |
|---|---|---|
| Fore-aft deflection at top under 0.3 kN | 3.2 mm | 1.4 mm |
| Fore-aft natural frequency (20 kg box) | ~10 Hz | ~15 Hz |
| ULS uplift per rear grating fixing | 1.4 kN | 0.75 kN |
| Rear upright bending utilisation | ~0.12 | < 0.12 |

The stand depends on its grating fixings to stay upright. Unfixed, it would tip under about 5 kg pushed at the top.

Duragal plus cold galv gives a design life of about 10 years in C3 exposure. Hot-dip galvanising after fabrication was considered and not adopted; the client is to confirm.

## Open items (confirm before fabrication)

1. **Catch box brackets:**
   - Horizontal hole centres: the sketch reads "31.5mm", taken here as 315.
   - Stand-off: assumed 30.
   - Lower hole height above the outlet: assumed 155.
   - These are the parameters `HOLE_PITCH_X`, `BOX_STANDOFF` and `BRKT_LOW_ABOVE_OUTLET`. The slot heights and upright length follow from them.
2. **Sample tub size:**
   - Assumed 560 x 300 x 200 (`TUB_L`, `TUB_W`, `TUB_H`).
   - Running `model.py` flags two problems with this assumption:
     - The hand gap is only 8 mm each end. A 35 mm gap needs W = tub length + 74.
     - A 300 deep tub rim does not fit the 256 clear tray depth.
3. **Site layout:**
   - Which way the grating bearing bars run at each location.
   - 300 clear behind each stand for the outrigger and for catch box bolt access.
4. **Box details:** which side the sensor cable exits (tabs are drawn on the right upright), and which side the catch box door is hinged.
5. **Client acceptance:** Duragal plus cold galv (about 10 year life).

## Files

- `model.py` builds the model. All parameters are at the top. Running it exports `output/catch_box_stand.step` and `.stl`, then prints the BOM and the parameter checks.
- `drawing.py` projects the model with hidden-line removal and draws the two sheets into paper-space layouts of the company A1 title block DXF:
  - Sheet 001: general arrangement, BOM, parameter checks, open items.
  - Sheet 002: base plan, foot plate, angles, tray, cut list, general notes.
  - It fills in the title block attributes and writes a DXF (one layout per sheet), a multi-page PDF and PNG previews to `output/a1/`.

The title block template and everything generated from it are not committed, because this repository is public. Run with the template path:

```
pip install -r requirements.txt
python model.py
python drawing.py path/to/Ammjohn_A1_Title_Block.dxf   # or set CBS_TEMPLATE
```

Drawing numbers use the placeholder `AJXXX-0000-ME-DWG-001/002` until a project number is assigned (`DRG_PREFIX` in `drawing.py`).
