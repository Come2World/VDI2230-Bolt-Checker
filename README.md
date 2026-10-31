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

Thread friction μG belongs to the bolt. Thickness, material, roughness Rz,
interface friction μT and bearing friction μK belong to each plate layer,
ordered from the bolt head. Bolt data are chosen from the hex-bolt catalog
(ISO 4014/4017, M6–M30, 8.8/10.9/12.9) first; any catalog value can be
overridden, and the override is kept when the bolt length changes.

### General-model assumptions

- FVmax = FMzul − FZ is used for the bearing-pressure check under service load.
- DSV deformation cones use the head bearing diameter on the head side and the
  nut bearing diameter on the nut side.
- The R11 shear area uses A0 = min(AS, AT) minus the bore.
- ISO 965 thread tolerances for the engagement check are approximated.

Regression against the source (same inputs as B1–B3): B1 SF +0.45 %,
Sp −0.18 %, MA +0.88 %; B2 SG +0.32 %, Sp −0.28 %, SA 0.00 %, MA +0.56 %;
B3 SG/Sp/FMzul/MA 0.00 %. The B1 Φ difference comes from the source mixing
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
- **Center** – SVG section with lK, l, b, DA and the deformation cone. Click a
  plate to edit it; **+ 板层** inserts a copy below the selected layer.
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
catalog selection, layer add/select via the section, field errors, stale
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
  `#checks-table tr[data-symbol="SF"]`, `#values-table`, `#report-preview`,
  `#export`, `#error`.
- Reference page: the labels `计算实例`, `计算`, `导出 TXT`, and `#section`,
  `#safety-table tr[data-symbol="SF"]`, `#results-table`, `#status`, `#error`.

The general API (`GET /api/general/schema`, `GET /api/general/catalog`,
`GET /api/general/catalog-values?variant=…&length=…&class=…`,
`POST /api/general/calculate`) returns field-level errors as
`{"field_errors": [{"path", "message"}]}`.
