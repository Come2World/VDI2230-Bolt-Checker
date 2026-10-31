# VDI 2230 Bolt Calculator

This local Python application (desktop and browser UI) has two modes:

- **General calculator** (default): a parameterized VDI 2230 Part 1:2015
  calculation for a concentric single-bolt joint — through bolt with nut (DSV)
  or tapped thread (ESV), 1–10 clamped layers, solid/hollow and reduced-shank
  bolts, concentric axial load, transverse load and torque. Inputs drive the
  calculation, the 2D section and the safety factors (FMzul, SF, SD, Sp, mges,
  FKR, SG, SA) live; the result is exported as a UTF-8 text report.
- **Reference verifier**: recalculates the fixed Appendix B cases B1–B5 and
  compares every safety factor with the printed values (all 12 within 3 %).

Eccentric clamping/loading, bending, thermal effects and multi-bolt load
distribution are outside the general model. All bundled catalog, material and
table data are still **provisional** (not yet checked against the primary
standards); every result based on them is therefore labelled
**需确认 · 数据待核验** and must not be used as a final verdict. The tool does
not replace the standard, engineering judgment, or design review.

### Ownership of inputs

Thread friction μG and bearing friction μK belong to the bolt: **μK = μG**
is enforced through one editable value. Thickness, material, roughness Rz and
interface friction μT belong to each plate layer,
ordered from the bolt head. Bolt data are chosen from the hex-bolt catalog
(ISO 4014/4017, M6–M30, 8.8/10.9/12.9) first; any catalog value can be
overridden, and the override is kept when the bolt length changes.

Optional head-side and nut-side **plain washers** are edited on the **板层**
tab. Nut-side washers apply only to DSV; their settings are retained but not
used when switching to ESV. Both washers are off by default. Initial dimensions
are empirical, not ISO catalog data: **di = 1.1d, Do = 2d, t = 0.16d** (mm;
M12: 13.2 / 24 / 1.92). Unmodified estimates follow nominal-diameter changes;
manual overrides remain unchanged. Material, modulus, limiting surface pressure
and roughness are also editable. S355J0 is only a provisional starting material,
not a claim about the grade of any purchased washer.

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
  **需确认** model flag even when all geometry is manually entered.

Regression against the source (same inputs as B1–B3): B1 SF +0.45 %,
Sp −0.18 %, MA +0.88 %; B2 SG +0.32 %, Sp −0.28 %, SA 0.00 %, MA +0.56 %;
B3 SG/Sp/FMzul 0.00 %. **B3 MA is now +8.63 %** (566.100 vs. 521.135 N·m):
the new μK = μG = 0.12 assumption differs from the example's μK = 0.10.
This intentional torque change is tested separately, not represented as a
safety-factor regression failure. The fixed reference verifier is unchanged.
The B1 Φ difference comes from the source mixing
w = 1 geometry with δPzu = δM; B3 R11 in the source uses FMzul and 1.2·P.

## Run from the repository root

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
vdi2230              # general calculator (Tkinter)
vdi2230 --reference  # B1–B5 reference verifier
```

Without installation: `PYTHONPATH=src python3 -m vdi2230 [--reference]`.
The desktop window uses the same three-pane layout as the browser UI; the
**参考算例 B1–B5** button opens the verifier in a second window.

### Browser UI

```sh
PYTHONPATH=src python3 -m vdi2230.web
# Or, after installation:
vdi2230-web
```

Open <http://127.0.0.1:8765> (general calculator) or
<http://127.0.0.1:8765/reference> (B1–B5 verifier) in a browser or VS Code's
integrated browser.
Use `--port 8766` if the default port is busy; stop the server with Ctrl+C.
The service binds only to the loopback interface, serves bundled local assets,
and requires no external network access. This is a local UI/test server, not
a production or shared-network service.

The general page is a compact single-viewport layout (12 px text, 24 px
controls; fits 1280×720 without page scrolling; stacks below 1080 px width):

- **Left** – inputs in four tabs (螺栓 / 板层 / 载荷 / 装配). Catalog and
  material values are marked (blue = catalog, amber = provisional source);
  irrelevant fields (nut vs. tapped part, table vs. manual modes) are hidden.
- **Center** – engineering-style SVG section: chamfered hex-head/nut profiles
  with curved face projections, unhatched bolt, fine thread-root lines,
  alternating plate/washer hatching, centerline and arrow dimensions
  (d, layer thickness, lK, l, DA). Click a bolt, nut, washer or plate to activate
  its input tab, reveal the relevant section and focus its field. The same
  interaction is available on the Tk canvas. **+ 板层** inserts a copy below the
  selected layer. The drawing remains schematic, not manufacturing-ready.
- **Right** – verdict, safety-factor table, filterable full results and the
  text report with **导出 TXT**.

Calculation runs automatically 300 ms after an edit. Invalid fields are
listed and marked on their tab; the last valid section stays visible with a
"剖面未更新" overlay and export is disabled until the input is fixed.

On `/reference`, select B1–B5 and click **计算**. The right column shows each available safety
factor's PDF reference, calculated value and relative error, expandable full
results and source details, and a TXT preview/download. Switching cases or a
failed calculation clears the previous result and disables export. B1 remains
**需确认** because of its unresolved additional-compliance source contradiction;
its report can be exported but explicitly retains the incomplete status.
The section is schematic, not a manufacturing drawing. JSON project save/load
is only available in the desktop reference verifier.

### Automated tests

The application uses only the Python standard library at runtime. Run calculation,
domain, desktop-contract and HTTP API tests without test dependencies:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

For real browser UI tests, install the optional test extra in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[ui-test]'
python -m playwright install chromium
PYTHONPATH=src python -m unittest discover -s tests/browser -v
```

On Windows, activate with `.venv\Scripts\Activate.ps1`; after the editable
installation, run the same `python -m unittest ...` commands without `PYTHONPATH`.
Browser tests start their own local server on an available port, launch Chromium,
and clean up both. For the general page they cover the single-viewport layout,
catalog selection, washer estimates/overrides, part clicks and field focus,
shared bolt friction, layer add/select via the section, field errors, stale
responses and TXT export; for `/reference` they cover all five cases and 12
safety-factor comparisons, read-only inputs, result invalidation, error/retry,
out-of-order responses, UTF-8 report downloads, and desktop/narrow layouts.
Tk window tests (`tests/test_general_desktop_window.py`) skip automatically
when no display is available.

In VS Code, select the environment with the test extra installed, then use
**Tasks: Run Task**: **VDI 2230: Web UI**, **VDI 2230: Unit and API tests**, or
**VDI 2230: Browser UI tests**. Stable selectors for browser automation:

- General page: `#project-title`, `#verdict`, `#tab-bolt` … `#tab-assembly`,
  field rows `.field[data-path="bolt.length"]` (layer fields:
  `.field[data-path="plates[0].thickness"]`), `#layers`, `#add-layer`,
  `#section rect[data-role="plate-0"]`, `#key-metrics`,
  `#section rect[data-role="washer-head"]`, `#section polygon[data-role="nut"]`,
  `.field[data-path="head_washer.enabled"]`,
  `#checks-table tr[data-symbol="SF"]`, `#values-table`, `#report-preview`,
  `#export`, `#error`.
- Reference page: the labels `计算实例`, `计算`, `导出 TXT`, and `#section`,
  `#safety-table tr[data-symbol="SF"]`, `#results-table`, `#status`, `#error`.

The general API (`GET /api/general/schema`, `GET /api/general/catalog`,
`GET /api/general/catalog-values?variant=…&length=…&class=…`,
`POST /api/general/calculate`) returns field-level errors as
`{"field_errors": [{"path", "message"}]}`.
The input schema is now `vdi2230.general/2`, adding `head_washer` and
`nut_washer` objects and removing `plates[].bearing_friction`. Only
`bolt.thread_friction` is submitted; μK is derived. Version 1 and legacy
bearing-friction fields are explicitly rejected to prevent silent changes to
old calculations. Restart running Python processes and reload the web page
after updating.
