# VDI 2230 Bolt Checker 0.0.1

This local Python desktop application (Tkinter, standard library only) performs a
parameterized VDI 2230 Part 1:2015 calculation for a concentric single-bolt joint:
through bolt with nut (DSV) or tapped thread (ESV), 1–10 clamped layers,
solid/hollow and reduced-shank bolts, concentric axial load, transverse load and
torque. Inputs drive the calculation, the 2D section and the safety factors
(FMzul, SF, SD, Sp, mges, FKR, SG, SA) live; the result is exported as a UTF-8
text report.

Release 0.0.1 contains **only the Tk desktop UI**. The browser UI, its HTTP API
and the separate B1–B5 reference-verifier window are not part of this release.
The VDI 2230 Appendix B cases B1–B5 remain **internal automated regression
tests** (see [Automated tests](#automated-tests)); they are not a user mode.

Eccentric clamping/loading, bending, thermal effects and multi-bolt load
distribution are outside the general model. Bundled bolt, material and table
data are **accepted as the project's calculation baseline** (`accepted_baseline`).
Their values and source records are retained; using the database no longer
forces a review verdict. This is a project acceptance policy, not a claim of
independent certification. Empirical washer dimensions, unverified model
assumptions and unknown source records still require review; failed checks
remain failures. The tool does not replace the standard, engineering judgment,
or design review.

### Ownership of inputs

Thread friction μG and bearing friction μK belong to the bolt and are
**independently editable**; changing one never changes the other. μK applies
to the rotating head/nut bearing contact. Thickness, material, roughness Rz and
interface friction μT belong to each plate layer,
ordered from the bolt head. Bolt data are chosen from the hex-bolt catalog
(ISO 4014/4017, M6–M30, 8.8/10.9/12.9) first; any catalog value can be
overridden, and the override is kept when the bolt length changes.

Optional head-side and nut-side **plain washers** are edited on the
**Plates / 板层** tab. Nut-side washers apply only to DSV; their settings are
retained but not used when switching to ESV. Both washers are off by default.
Initial dimensions are empirical, not ISO catalog data: **di = 1.1d, Do = 2d,
t = 0.16d** (mm; M12: 13.2 / 24 / 1.92). Unmodified estimates follow
nominal-diameter changes; manual overrides remain unchanged. Material, modulus,
limiting surface pressure and roughness are also editable. S355J0 is only the
initial material selection, not a claim about the grade of any purchased washer.

### General-model assumptions

- FVmax = FMzul − FZ is used for the bearing-pressure check under service load.
- DSV deformation cones use the head bearing diameter on the head side and the
  nut bearing diameter on the nut side.
- The R11 shear area uses A0 = min(AS, AT) minus the bore.
- ISO 965 thread tolerances for the engagement check are approximated.
- Washers use a **conservative plain-washer model**, not a spring/Belleville
  model. Grip length includes their thickness; washer annular compression
  compliance is added in series with the plate compliance. Plate cones use
  only the plate-stack length. No load spreading across the washer is assumed:
  `Deff = min(dW, Do, DA)`, `di,eff = max(di, dh, dha)`,
  `Aeff = π/4(Deff² − di,eff²)`, `δW = t/(EW·Aeff)`.
  Adjacent plate compliance uses the larger of its hole and washer bore.
- Both washer contact faces are checked; Sp,K / Sp,M report the minimum of
  the washer and adjacent plate safety factors (components appear in the full
  results). Washer interfaces contribute to table-based embedding, not to the
  user-specified slip-interface count. Manual fZ or interface-count overrides
  must include washer effects.
- Torque uses the rotating head/nut-to-washer contact annulus, not the full
  washer OD, and assumes the washer stays stationary. Washer bending and actual
  contact/load distribution are unverified; enabled washers retain a
  **review required / 需确认** model flag even when all geometry is manually
  entered.

Regression of the general engine against the source (same inputs as B1–B3):
B1 SF +0.45 %, Sp −0.18 %, MA +0.88 %; B2 SG +0.32 %, Sp −0.28 %, SA 0.00 %,
MA +0.56 %; B3 SG/Sp/FMzul/MA 0.00 %. **B3 uses μG = 0.12 and μK = 0.10**,
reproducing the source tightening torque of **521.135 N·m**. No shared-friction
assumption or special torque correction is used. The B1 Φ difference comes
from the source mixing w = 1 geometry with δPzu = δM; B3 R11 in the source uses
FMzul and 1.2·P.

## Run from the repository root

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
vdi2230              # Tk desktop calculator
vdi2230 --version    # prints "vdi2230 0.0.1" without opening a window
```

Without installation: `PYTHONPATH=src python3 -m vdi2230`.
On Windows, activate with `.venv\Scripts\Activate.ps1`.
After updating the code, close and restart any running window.

### Desktop window

The window uses a compact three-pane layout with a dark cyberpunk palette
(standard-library `clam` ttk theme). Pass/fail/review keep distinct
green/red/amber colors and text labels.

- **Left** – inputs in four tabs (Bolt / Plates / Loads / Assembly). Catalog and
  material values are marked (cyan = accepted catalog, amber = estimate/review);
  irrelevant fields (nut vs. tapped part, table vs. manual modes) are hidden.
- **Center** – engineering-style Canvas section: chamfered hex-head/nut
  profiles, unhatched bolt, thread-root lines, alternating plate/washer
  hatching, centerline and dimensions (d, layer thickness, lK, l, DA). Click a
  bolt, nut, washer or plate to activate its input tab and focus its field.
  **+ Plate** inserts a copy below the selected layer. Tk Canvas has no true
  alpha compositing, so the compression cone is a transparent, unfilled dashed
  outline that keeps the plates behind it visible. The drawing is schematic,
  not manufacturing-ready.
- **Right** – verdict, safety-factor table, filterable full results and the
  text report with **Export TXT**.

Calculation runs automatically 300 ms after an edit. Invalid fields are
listed and marked on their tab; the last valid section stays visible with a
"Section not updated" overlay and export is disabled until the input is fixed.
If a thickness edit makes the clamped stack too long for the selected bolt,
the input is invalid: results are cleared and export is disabled. Correct the
bolt length/engagement or the stack geometry to resume updating; the program
never silently lengthens the bolt.

### English / Chinese

A new window **defaults to English**. The **中文 / English** selector in the
toolbar changes the input labels/options, drawing annotations, checks,
warnings, field errors and TXT report of the current window together. The
preview and exported UTF-8 TXT use the same language. Numerical values, units,
provenance and input schema `vdi2230.general/3` are unchanged.

Switching retains parameters (including their entered text), plate selection
and user overrides. Untouched application-generated titles and plate names
follow the language: **General bolt joint** and **clamped plate 1, 2, …** in
English, **通用螺栓连接** and **板 1、2、…** in Chinese. Newly added plates use
the current language. Once edited, names are user text and are **not
translated**, even if they match a default name. Operating-system file-dialog
controls follow the OS language. Translation uses a bundled offline catalog,
not a network service; programmatic report rendering accepts
`render_general_report(result, language="en")` or `"zh"`.

Input schema `vdi2230.general/3` uses independent `bolt.thread_friction` and
`bolt.bearing_friction` values (both default to 0.12, not linked) plus
`head_washer` and `nut_washer` objects. Versions 1/2 and
`plates[].bearing_friction` are explicitly rejected, so older inputs must be
reviewed and both bolt friction values confirmed.

## Automated tests

The application uses only the Python standard library at runtime and the
tests need no extra dependencies:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The suite covers:

- General engine, catalog/material data, washers, reports and both languages
  through the toolkit-neutral `GeneralFormModel` and the Canvas section model.
- Tk window behavior (`tests/test_general_desktop_window.py`): input-driven
  redraws, part clicks and field focus, language switching, stale sections,
  TXT export, `--version` and the removed `--reference` option. These tests
  skip automatically when no display is available.
- **Internal B1–B5 regression** (`tests/test_reference_cases.py`): the fixed
  Appendix B cases are recalculated and each of the 12 printed safety factors
  (B1 SF/Sp; B2 SG; B3 Sp/SG; B4 SD/SpK/SpMu/SG; B5 SF/SD/Sp) must stay within
  3 %. B1 keeps its documented additional-compliance source contradiction.
- Release boundaries (`tests/test_release_structure.py`): version 0.0.1, a
  single `vdi2230` entry point, no Web/reference UI modules, and calculation
  without Tk or HTTP server modules.

In VS Code, use **Tasks: Run Task** → **VDI 2230: Tk UI** or
**VDI 2230: All tests**.
