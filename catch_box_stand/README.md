# Classification sampler catch box stand

Parametric build123d model and fabrication drawings (drawing CBS-001, 2 x A3 sheets)
for a free-standing galvanised stand that carries the new catch box and the sample tub.
It replaces the existing wall-mounted arrangement and bolts down to the Webforge
C325MPG grating.

## Inputs used

From the sketch and the fabricator's proposal email:

| Item | Value |
|---|---|
| Platform (shelf top) height above grating | 1050 |
| Catch box outlet above platform | 340 |
| Catch box body + hopper height | 390 + 110 = 500 (top of box at 1890) |
| Catch box mounting holes | 330 crs vertical, 315 crs horizontal (see assumptions) |
| Stand depth | 300 |
| Platform width | min 570 (tray clear width is 576) |
| Frame | Duragal SHS 40x40x2.0 |
| Catch box mounting angles | Duragal EA 40x40x5.0 |
| Shelf | 2.0 galvanised sheet, with sides and back |

## Design summary

- Four-leg SHS frame, 580 W x 300 D. The front legs stop at the shelf and the rear uprights run up to 1900.
- Base ring frame sits on the grating. Four Ø14 holes go through the bottom wall of the base side rails, with Ø25 socket access in the top wall, for M12 grating clamps.
- Side and back rails at 400 tie the legs together. The shelf frame has a centre bearer.
- Two horizontal EA 40x40x5 angles sit between the rear uprights, with the vertical leg flush with the uprights' front face. Each angle has two 14 x 40 slots at 315 crs (±13 adjustment) at heights 1545 and 1875.
- The tray is folded 2 mm sheet: a 580 x 260 base, tapered sides (80 high at the front, 200 at the back) and a 200 high back. It sits in front of the rear uprights, so the front of the tray stays open for the tub.
- Approximate mass is 32 kg per stand, excluding fasteners. 4 off required.

## Assumptions to confirm

1. The sketch reads **"31.5mm between centres"** for the horizontal hole spacing. This was taken as **315 mm**. Check it against the catch box brackets before fabrication.
2. The catch box envelope is drawn chain-dotted from the sketch dimensions, for reference only.
3. The grating clamp type is for the installer to confirm.
4. Rear upright stiffness: the box is cantilevered about 850 mm above the shelf on two 40x40x2 uprights, tied by the two angles. This is adequate for a light catch box. If the box is heavy or will be knocked, add knee braces.

## Files

- `model.py` builds the model (all parameters are at the top). Running it exports `output/catch_box_stand.step` and `.stl` and prints the BOM and masses.
- `drawing.py` projects the model with hidden-line removal and lays out the A3 sheets. It writes `output/CBS-001.pdf` (both sheets), plus SVG and PNG for each sheet.

```
pip install -r requirements.txt
python model.py
python drawing.py
```
