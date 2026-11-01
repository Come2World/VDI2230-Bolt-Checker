# VDI 2230 Bolt Calculator — 0.0.1

Tk-only release on branch `VDI2230_BOLT_CHECKER_RELEASE_0.0.1`.

A local Python desktop calculator for a **concentric single-bolt joint** under
VDI 2230 Part 1:2015: through bolt with nut (DSV) or tapped thread (ESV),
1–10 clamped plates, solid/hollow and reduced-shank bolts, concentric axial load,
transverse load and torque. Inputs drive the calculation, interactive 2D section
and checks (FMzul, SF, SD, Sp, mges, FKR, SG, SA). Results can be exported as a
UTF-8 plain-text report.

**Not covered:** eccentric clamping/loading, bending, thermal effects, bolt-group
load distribution, 3D/CAD or finite-element analysis. Loads must already be
expressed for the single bolt being checked. The drawing is schematic, not a
manufacturing drawing or a stress plot.

Bundled bolt, material and table records are **accepted as the project's
calculation baseline** (`accepted_baseline`). Values, sources and audit notes
are retained. This policy is not independent certification. Empirical dimensions,
unverified model assumptions and unknown source records still require review;
failed checks remain failures. This tool does not replace the official standard,
engineering judgment or design review.

## Install and start

Python **3.10 or newer**, with **Tkinter/Tcl/Tk** and a graphical desktop, is
required. Runtime calculations and tests use the Python standard library.
Tkinter is supplied by the Python distribution or operating system, not by pip.
`python -m tkinter` opens a small window to check its availability.

From the repository root on macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
vdi2230
```

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
vdi2230
```

After installation, `python -m vdi2230` also starts the same Tk window.
`vdi2230 --version` prints `vdi2230 0.0.1`; `vdi2230 --help` lists supported
options. Without installation on macOS, use:

```sh
PYTHONPATH=src python3 -m vdi2230
```

After switching branches or updating the installation, rerun
`python -m pip install -e .` to refresh command entry points. Restart an already
running Tk window to load the new code. No local server or browser is required.

## Desktop workflow

The window opens in **English** and uses a compact three-pane layout:

- **Left:** Bolt / Plates / Loads / Assembly tabs. Choose catalog geometry and
  materials, then adjust values as needed. Cyan markers identify accepted
  catalog values; amber marks estimates/review sources. Irrelevant fields are
  hidden for the selected joint or calculation mode.
- **Center:** the section and key metrics. Click a bolt, nut, washer or plate
  to activate the corresponding input tab and focus its field. Add, remove,
  select and move plates; adding inserts a copy below the selected plate.
- **Right:** overall verdict, individual checks, filterable full results and
  report preview. **Export TXT** saves the report currently displayed.

Calculation runs automatically about **300 ms** after an edit. An edit
immediately disables export. Invalid inputs clear the results/report, identify
the errors and visibly mark the last valid section as stale. Correcting the
inputs restores calculation and drawing updates.

In particular, increasing plate or washer thickness can make the grip too long
for the bolt. Correct the length/engagement or stack geometry; the program
never silently lengthens the bolt or labels old geometry with new dimensions.

The cyberpunk palette uses deep navy, cyan and purple. Pass/fail/review have
both distinct colors and text. The section includes chamfers, hex-face curves,
thread-root lines, alternate plate/washer hatching, a centerline and dimensions.
Compression cones have **no fill and dashed outlines**, so plates remain visible.
These display choices do not change calculations.

The initial window is 1440×860, reduced and centered to fit smaller screens.
Operating-system window decorations and file-dialog controls remain native.
This release exports TXT reports; it does **not** provide design-project
save/load controls.

## Inputs and washers

Thread friction **μG** and bearing friction **μK** belong to the bolt and are
**independently editable**. Both start at 0.12; changing one never changes the
other. μK describes the rotating head/nut bearing contact. Plate thickness,
material, roughness Rz and interface friction μT belong to each ordered plate.

The hex-bolt catalog covers ISO 4014/4017, M6–M30 coarse threads and
8.8/10.9/12.9 property classes. Catalog values may be overridden; overrides
survive bolt-length changes. Suggested lengths do not guarantee commercial
availability for every standard/diameter combination.

Optional head-side and nut-side **plain washers** are on the **Plates** tab.
Both are off by default. ESV retains but does not use nut-side washer settings.
Initial estimates are **di = 1.1d, Do = 2d, t = 0.16d**, in mm
(M12: 13.2 / 24 / 1.92). These are empirical, not ISO catalog dimensions.
Unmodified estimates follow diameter changes; manual overrides remain unchanged.
Material, elastic modulus, limiting surface pressure and roughness are editable.
S355J0 is an initial selection, not a claim about any purchased washer.

### Calculation assumptions

- Working bearing pressure uses **FVmax = FMzul − FZ**.
- DSV deformation cones start at the respective head and nut bearing diameters.
- The R11 shear area uses **A0 = min(AS, AT)** minus the bore.
- ISO 965 thread tolerances for engagement are approximated.
- Washers use a **conservative plain-washer model**, not a spring/Belleville
  model. Their thickness contributes to grip length, bolt compliance,
  engagement and shear-plane position. Plate cones use the plate-stack length.
- Washer annular compliance is added in series with plate compliance:
  `Deff = min(dW, Do, DA)`, `di,eff = max(di, dh, dha)`,
  `Aeff = π/4(Deff² − di,eff²)`, `δW = t/(EW·Aeff)`.
  No load spreading across the washer is assumed. Adjacent plate compliance
  uses the larger of its hole and washer bore.
- Both washer contact faces are checked. Sp,K / Sp,M use the minimum of the
  washer and adjacent plate factors; components appear in the full results.
  Washer interfaces contribute to table-based embedding, not automatically to
  the user-specified slip-interface count. Manual fZ/interface overrides must
  include washer effects.
- Torque uses the rotating head/nut-to-washer contact annulus, not the full
  washer OD, and assumes a stationary washer. Washer bending, local yielding
  and actual contact/load distribution require separate verification.
  Enabled washers retain a **Review** model flag even with manual dimensions.

## Chinese / English

The **中文 / English** selector changes labels/options, section annotations,
checks, warnings, field errors and the TXT report together. Numerical values,
units, source identifiers and input schema `vdi2230.general/3` do not change.
Translation is fully offline.

Switching preserves entered text (including `0.10`), overrides, selected plate
and input tab. Untouched generated titles/names follow the language:
**General bolt joint**, **clamped plate 1, 2, …** or **通用螺栓连接**,
**板 1、2、…**. User-edited or programmatically loaded names remain unchanged,
even if they match a generated name. New plates use the current language.
Invalid inputs remain invalid after switching; export stays disabled and the
old section remains visibly stale.

Programmatic inputs use separate `bolt.thread_friction` and
`bolt.bearing_friction` fields. Schema versions 1/2 and
`plates[].bearing_friction` are rejected rather than silently reinterpreted.
Application version, input schema and engineering-data versions are independent.

## Tests and development

After installation:

```sh
python -m unittest discover -s tests -v
```

Or, from the source tree on macOS:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The suite covers calculations, engineering data, internal standard-example
regressions, field validation, washers, bilingual reports and actual Tk widgets.
It exercises real debounce callbacks, part clicks, layer edits, stale drawings,
failure recovery and TXT export. Tests need no third-party test packages.
Tk window tests skip when no display is available; such a run is **not** desktop
release acceptance. Run the suite with Tk and a display for GUI validation.

In VS Code, select the project Python environment, then use **Tasks: Run Task**:
**VDI 2230: Tk UI** or **VDI 2230: All tests**.

The current validation environment is macOS. Windows remains a target platform;
Windows installation, native dialogs and display behavior require validation
on that operating system before claiming platform acceptance.

See the [requirements](./SOFTWARE_REQUIREMENTS_SPECIFICATION.md),
[architecture and release checks](./SOFTWARE_ARCHITECTURE_AND_BUILD_PLAN.md)
and [catalog sources/licenses](./src/vdi2230/data/bolt_catalog/README.md).
