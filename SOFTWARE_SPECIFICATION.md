# VDI 2230 Bolt Checker: Requirements, Architecture and Release Validation

| Item | Value |
|---|---|
| Document version | 2.0 |
| Date | 2026-11-03 |
| Application | VDI 2230 Bolt Calculator 0.0.1 |
| Release baseline | `VDI2230_BOLT_CHECKER_RELEASE_0.0.1` |
| Engineering scope | VDI 2230 Part 1:2015, concentric single-bolt joints |
| Interface | Tkinter / ttk desktop window with a 2D Canvas section |
| Outputs | UTF-8 Markdown reports and JSON design projects |

This English document consolidates requirements version 1.9 and architecture
version 0.15. Duplicate material is combined without expanding the application
scope. See the [README](./README.md) for setup and a short project overview.

> This application supports engineering calculations. It does not replace the
> official standard, engineering judgment or design review. Accepting bundled
> data as a project baseline is not independent certification. Product release
> still requires verification of inputs, formula applicability, assumptions
> and results.

## 1. Purpose and release scope

The application serves mechanical designers and reviewers familiar with bolted
joints and mechanics of materials. The normal workflow is to select geometry
and materials, enter single-bolt loads, review the section and checks, adjust
inputs, and save a design or export a report.

Only one general-purpose Tk calculation interface is delivered.
`vdi2230` and `python -m vdi2230` launch that interface; `--help` lists options
and `--version` prints `vdi2230 0.0.1`.
There is no Web service, HTTP API, static Web interface, browser test dependency,
reference-case window or reference-case button. Removed entry points
`vdi2230-web`, `python -m vdi2230.web` and `--reference` are not supported.

Internal B1–B5 calculators and their engineering data remain for numerical
regression. They are not user modes, and their eccentric or multi-bolt examples
do not extend the general model's capabilities. Removing older interfaces must
not change the general formulas, input format, engineering values or retained
Tk interactions. Standalone installers and platform signing are outside this
release.

### Supported cases

- Concentric single-bolt through joints with a nut (DSV) and tapped joints (ESV).
- One to ten clamped plates, ordered from the bolt head downward.
- Solid, hollow and reduced-shank bolts, with explicit manual input where
  catalog data are unavailable.
- Concentric axial load, transverse load and torque for the individual bolt.
- Optional head-side and nut-side plain washers; ESV ignores the nut-side washer.
- Compliance, load sharing, embedding, preload, and applicable strength,
  fatigue, bearing, slip, shear and engagement checks.
- Interactive 2D sections, English/Chinese application display, Markdown reports,
  and JSON project save/load.

### Exclusions

Eccentric clamping/loading, bending, bolt-group load distribution, thermal loads,
temperature-dependent properties, creep/relaxation prediction, nonlinear load
redistribution after partial separation, contact FEA, spring/Belleville washer
models, washer bending and actual local load distribution are excluded.
The application provides no 3D/CAD editing, manufacturing drawings, stress plots
or automatic certification.

Unsupported inputs must produce explicit errors or limitations, not be silently
ignored. Internal test coverage must not be presented as product support for
excluded cases.

## 2. Engineering basis and data policy

The official VDI 2230 Part 1:2015 standard takes precedence over supporting
reference material. Results retain relevant section, formula and table sources.

| Topic | Main standard reference |
|---|---|
| Bolt axial compliance | 5.1.1.1 |
| Concentric clamped-part compliance | 5.1.2.1 |
| Load introduction and sharing | 5.2.2, R3 |
| Embedding and preload | 5.4.2.1, Table 5, R2/R4–R6 |
| Assembly and working stress | 5.5.1, 5.5.2.1, R7/R8 |
| Fatigue | 5.5.3, R9 |
| Bearing pressure | 5.5.4, R10 |
| Engagement, shear and tightening torque | Applicable R11–R13 relationships |

Bundled bolt, property-class, material and table records use `accepted_baseline`.
Derived specifications retain this status. Using bundled data alone must not
force a Review verdict. Values, versions, original discrepancies, sources and
licenses remain traceable; this policy does not certify the records.
Unknown sources, empirical dimensions and unverified assumptions still require
review. Internal names such as `provisional_sources` refer to these remaining
unaccepted sources, not to all bundled data.

### Catalog and head geometry

The catalog contains ISO 4014/4017 hexagon bolts and ISO 4762 socket head cap
screws at M6–M16, M20, M24 and M30, coarse threads, and property classes
8.8/10.9/12.9 and A2-70/80/90. Suggested lengths and class/geometry combinations
do not guarantee commercial availability.

Head geometry is independent of property class. ISO 4762 selections set socket
head type, diameter `dk`, height `k`, socket size `s`, depth `t`, and their own
bearing diameter `dW`. Nuts retain ISO 4032 hexagon geometry and their own width
across flats, not the socket size.

`dW` determines R10 bearing area `Ap = pi/4 * (dW^2 - dha^2)`, deformation-cone
start diameter and the R13 bearing friction diameter. The section shows the
`dW` bearing face, dimension and effective contact annulus. Hexagon heads are
drawn at width across corners `e = 2s/sqrt(3)`. Head width, diameter and socket
dimensions are drawing-only; missing or inconsistent values are estimated
from `dW`.

Catalog version 0.5.0 added nine socket-head geometries with `head_type` and
per-geometry `head_bearing_diameter_dw_mm`, taking precedence over shared
hexagon-head values. Lengths within `full_thread_max_length_mm` are fully
threaded; longer lengths use the reference thread length `b`.
`joint_dimension_records` supplies the nut width across flats.
Optional `bolt.head_type`, `head_width_across_flats`, `head_diameter`,
`socket_size` and `socket_depth` remain compatible with input schema 4;
missing dimensions are estimated for drawing.

### Stainless-steel references

| Class | Minimum Rm / Rp0.2 | Shear-strength ratio |
|---|---|---|
| A2-70 | 700 / 450 MPa | 0.72, Table 7 |
| A2-80 | 800 / 600 MPa | 0.68, Table 7 |
| A2-90 | 900 / 700 MPa | Actual product input required |

A2-90 is an editable supplier-specific reference, not a universal ISO property
class. The supplier's listed sizes and JIS geometry do not verify all catalog
M6–M30 ISO combinations. Catalog A2-90 strengths retain a product-applicability
Review flag. No default shear-strength ratio is supplied.
Catalog version 0.4.0 introduced these A2 classes. Their representative editable
modulus is 200000 MPa from `material:X5CrNi18-10`; nut modulus is independent.
See the [catalog sources and licenses](./src/vdi2230/data/bolt_catalog/README.md).

## 3. Functional requirements

### FR-01: Inputs, ownership and catalog overrides

| Object / tab | Inputs |
|---|---|
| Project | Report title |
| Bolt | Catalog, class, thread/length/bore/reduced shank, material, independent thread and bearing friction |
| Joint | DSV/ESV, hole and clamped-part diameters, nut or tapped-part properties |
| Plates | Ordered names, thickness, material, modulus, limiting bearing pressure, Rz and interface friction |
| Washers, on Plates tab | Enable flags, diameters, thickness, material, modulus, bearing limit and roughness |
| Loads | Single-bolt axial limits, transverse load, torque, residual clamp demand and load introduction |
| Assembly | Tightening factor, utilization, embedding mode, process and required safety factors |

`bolt.thread_friction` (muG) and `bolt.bearing_friction` (muK) both default to
0.12 but are independently editable. Plate interface friction muT replaces
neither. Friction depends on contact conditions, surface finish and lubrication.

Catalog/material selection fills fields with provenance; manual edits make
them custom. Changing head type matches geometry at the current diameter/pitch,
even without a selected property class, while retaining manual strength and
non-head geometry. No match clears catalog geometry provenance and explicitly
requests custom dimensions. `bolt_geometry_values()` shares this geometry logic.
A length-only change updates catalog-managed values without overwriting manual
overrides. The Tk view must synchronize both values and visibility.

Irrelevant fields are hidden, but switching DSV/ESV preserves unused settings.
Changing catalog variant, class or nominal diameter clears product-specific
fatigue amplitude; when A2 is involved it also clears maximum tensile strength
and requests confirmation of new values. Length-only edits retain them.
Validation rejects stale A2 strength sources, incorrect table values and
catalog strengths outside the supported diameter range.

#### Tapped-part geometry

The ESV Bolt section accepts blind/through hole type, part thickness `H`,
drilled depth `Lh` and complete internal-thread depth `Lt`, in mm from the
contact face. `H` is not part of grip length `lK`; DSV hides these fields.

- Blind `Lh` includes an estimated 118-degree drill tip; cylindrical depth
  excludes it. Require `Lh < H`, `Lt <= cylindrical depth` and bolt insertion
  strictly less than cylindrical depth. Bottoming is an error.
- Through holes use `Lh = H`, hide its input and allow bolt protrusion;
  require `Lt <= H`.
- Blank blind dimensions use `Lh = l - lK + 0.4d` and
  `H = max(l - lK + d, Lh + 0.5d)`. Blank through `H = l - lK + 0.5d`.
  Blank `Lt` is the lesser of insertion and available cylindrical depth.
  Older files lacking these fields retain their previous engagement.
- Engagement is actual internal/external thread overlap, limited by optional
  `mges`, not unthreaded shank length. Zero overlap is rejected; `Lt` affects R11.
- Draw the part boundary, hole/tip, thread limit and H/Lh/Lt/mges dimensions.
  Red engaged threads and the mges dimension must match R11; clicking either
  focuses the relevant field. Reports disclose resolved dimensions and estimates.

### FR-02: Washer estimates and overrides

Both washers default off and do not count toward the ten-plate limit.
Initial empirical dimensions are `di = 1.1d`, `Do = 2d`, `t = 0.16d` mm,
not ISO catalog values. Only untouched estimates follow diameter changes.
Material, modulus, bearing limit and roughness are editable; S355J0 is merely
the initial material selection.

### FR-03: Validation and input compatibility

Reject missing required values, invalid text, NaN and infinity. Geometry and
modulus must be positive, friction nonnegative, tightening factor at least 1,
and utilization greater than 0 and at most 1. Require `FAmin <= FAmax`.
Users must supply individual-bolt loads, not a bolt-group total.

Validate threads, bearing annuli, bores, washer contact, lengths and engagement.
If a thicker stack exceeds usable bolt length, report the error; never
automatically lengthen the bolt. Stop dependent calculations for invalid areas,
logarithms, roots or denominators. Give field paths where possible and explicit
reasons for other calculation rejections.

Internal units are N, mm, MPa and N·mm; displayed N·m requires explicit conversion.
The format is `vdi2230.general/4`, with optional product fatigue amplitude.
Schema 3 without that field is accepted and re-emitted as 4; the new field
in schema 3 is rejected. Schemas 1/2 and legacy plate `bearing_friction` are
rejected rather than silently merging or reinterpreting friction.

### FR-04: Compliance, load sharing and preload

Calculate bolt-segment, head/thread-end, plate and washer compliance for the
applicable geometry, retaining intermediate values and sources. Integrate each
plate material over its segment; do not treat a cone/cylinder combination as
a complete cone. Disclose load introduction, additional compliance, embedding
table lookups and manual overrides.

Embedding loss, minimum/maximum assembly preload and working clamp force must
come from the same input snapshot with individual contributions retained.
Manual embedding/interface counts must account for actual washer contacts.
Thermal loads and multi-bolt distribution are not calculated.

### FR-05: Checks and verdicts

Show values, requirements, units, formula sources and statuses for:

- Assembly capability `FMzul >= FMmax`.
- Working yield `SF` and fatigue `SD`.
- Head/nut bearing `Sp`, including enabled washer components.
- Engagement `mges`, residual clamp force `FKR`, slip `SG` and shear `SA`.
- Tightening torque `MA` and associated intermediate results.

Do not conflate allowable assembly preload, utilization and safety factors.
Not Applicable is not Pass. Overall priority is **Fail** for any applicable
failed check, otherwise **Review** for pending checks/sources, otherwise
**Pass** when all criteria are satisfied. Review must never hide a failure.

### FR-06: Mandatory model disclosures

- Working bearing pressure uses `FVmax = FMzul - FZ`.
- DSV deformation cones start at the respective head/nut bearing diameters.
- R11 uses `A0 = min(AS, AT)` minus the central bore; ISO 965 thread tolerances
  are approximated.
- Fatigue amplitude sigmaA defaults blank. For 8.8/10.9/12.9, VDI R9 provides
  sigmaASV/sigmaASG and finite-life sigmaAZS, shown under R9.
- A2 identified by class or retained source must not use the ISO 898-1
  steel-bolt fatigue reference formula. Under alternating axial load, require
  actual product fatigue amplitude for the applicable life and conditions.
  Calculate `SD = sigmaA / sigmaa` directly, without further rolling/life scaling.
  Missing amplitude gives Review with no fabricated SD; no alternating load
  gives Not Applicable. Manual amplitude overrides the estimate for other
  classes too. Unidentified fully manual materials require user-supplied data.
- A2 ESV/nonstandard-nut R11 requires actual `Rm,max`, not a silent `1.2 * Rm`.
  Nonstandard nuts also require their tensile strength and shear ratio.
  Missing data gives Review. The matching-standard-nut waiver is a user
  assumption, not automatic selection or certification.
- Washer thickness contributes to grip, bolt compliance, engagement and shear
  position; plate-cone length excludes washers.
- Washer annular compliance is in series with plate compliance:
  `Deff = min(dW, Do, DA)`, `di,eff = max(di, dh, dha)`,
  `Aeff = pi/4 * (Deff^2 - di,eff^2)`, `deltaW = t/(EW * Aeff)`.
  Do not assume spreading across the full outer diameter. Adjacent plates use
  the larger applicable bore.
- Check both washer faces and adjacent plates; `Sp,K` / `Sp,M` take the minimum.
  Washer contacts contribute to table-based embedding, not automatically to
  a manually specified slip-interface count.
- Torque uses the rotating fastener's contact annulus and assumes a stationary
  washer. Washer bending, local yielding and actual load distribution remain
  unverified, so enabled washers retain a model Review flag.

### FR-07: Desktop layout

Open at 1440×860, reduced and centered to fit the screen, with scrollable inputs
and results. Use three columns: Bolt/Plates/Loads/Assembly tabs; section, plate
operations and key metrics; overall verdict, safety factors, filterable results,
report preview and export.

Use the standard-library clam theme with deep navy, cyan and purple styling.
Primary text/status contrast targets at least 4.5:1. Statuses require text as
well as color. Retain native window decorations and file dialogs.

### FR-08: Live updates and error recovery

Edits immediately disable export, cancel the pending timer and schedule
recalculation after approximately 300 ms. Results, report and section share
one snapshot. Invalid input clears results/report, disables export, shows
field-localized errors and marks the last valid drawing stale.
Errors can focus fields and mark tabs; corrections restore calculation.
Explicit numerical/domain failures produce error outcomes, not successful
defaults. Closing cancels pending calculation/drawing callbacks.

English dynamic templates match more-specific, longer fixed text first to
avoid shorter templates swallowing suffixes and breaking callbacks. Missing
registered messages remain explicit errors, not hidden by broad catches.

### FR-09: Section drawing and interaction

Show the head, shank/threads, plates, holes, washers and nut/tapped end,
including chamfers, hex-face arcs, fine thread lines, alternating plate
hatching, centerline and dimension arrows. Longitudinal fasteners are not
hatched. The section is schematic, not a stress or manufacturing drawing.

Clicking a part activates its input tab and field. Adding a plate copies the
selected plate and inserts after it; support selection, deletion and reordering
up to ten plates. Compression cones are unfilled dashed outlines, never
opaque overlays. Drawing coordinates, colors and scaling cannot affect results.

### FR-10: Application language behavior

New windows default to English. The English/Chinese selector changes labels,
options, annotations, results, warnings, errors and reports together, without
changing numbers, units, provenance identifiers or schemas. Translation is
offline; native dialog controls follow the operating-system language.

Preserve raw input text, overrides, selected plate, tab and filter. Untouched
generated titles and plate names follow the selected language; user-edited
or loaded names never translate, even if identical to defaults. New names
avoid existing default numbering in either language; naming flags move with
plates and remain UI state, not engineering input.

Language changes cannot clear errors or stale state. Cached valid geometry may
be redrawn in the other language, but the report stays empty and export disabled
while inputs are invalid. Do not translate by replacing text across a whole report.

### FR-11: Markdown reports

UTF-8 `.md` reports include software version, calculation time, title, standard
and scope, all inputs/sources, intermediate values, formula references, checks
and requirements, pending sources, assumptions and disclaimers.
Preview and export must match the current window language and valid calculation.
Valid Fail/Review results may be exported with their actual verdicts.
Preview shows Markdown source; use an external Markdown viewer for formatting.

Escape special characters in user text, sources and formulas to prevent broken
tables, forged headings or raw HTML. Cancellation writes nothing; failures are
explicitly reported, never shown as success.

Report section 3 groups every result exactly once, in R1–R13 order:
tightening factor, required clamp force, compliance/load factor, preload loss,
minimum preload, maximum preload, assembly strength, working strength, fatigue,
bearing pressure, engagement, slip/shear and tightening torque.
Geometry helpers belong to R3, existing engagement to R11 and SD to R9 even
when evaluated later. Keep Not Applicable/Review statuses and reasons in their
steps. R1 records the selected tightening factor, not automatic bolt sizing.

### FR-12: Project save/load

Top-bar Save/Load uses JSON dialogs; Save allows another filename.
Save the title, all inputs including hidden joint settings, ordered plates,
washers and provenance. Validate/recalculate before saving; valid Fail/Review
verdicts do not block saving, but invalid inputs must not overwrite a file.

Use envelope `vdi2230-bolt-project` version 1, `case_id = GENERAL`, and nested
schema 4 inputs. Schema 3 migrates under the existing rules. Do not cache
results; recalculate with the installed application. Reject B1–B5 internal
snapshots as general projects.

Validate format, version, inputs and calculability before replacing the current
design. Corrupt, unsupported or failed loads preserve current edits and show
errors. Retain the current language; loaded names are user text.
Refresh visibility, section, results and report after a successful load.

Unsaved edits trigger Save/Discard/Cancel before loading or closing. Cancelled
or failed saves preserve the design. Atomic replacement follows a complete
write; failed writes preserve the old file. Markdown reports are records,
not loadable designs.

## 4. Software architecture

### Modules and dependency boundaries

Paths below are relative to `src/vdi2230/`.

| Layer | Module | Responsibility |
|---|---|---|
| Entry | `__main__.py` | CLI parsing, version and Tk root creation |
| Window | `ui/general_window.py` | ttk forms, Canvas, results/report, errors and timers |
| Form state | `ui/general_model.py` | Catalogs, overrides, plates, provenance, snapshots and Outcome |
| Inputs | `domain/general_inputs.py` | Schema, immutable inputs, defaults and validation |
| Calculation | `calculations/general.py` | Orchestration, metrics, checks and verdict |
| Data | `data/` | Versioned bolt, material and table records/licenses |
| Geometry | `infrastructure/general_section.py` | Window-independent Shape geometry and part roles |
| Report | `infrastructure/general_report.py` | Same-snapshot Markdown in R1–R13 order |
| Projects | `infrastructure/project_file.py` | Validation, serialization and atomic file writing |
| Translation | `i18n.py` | Offline messages, full templates and source labels |
| Internal regression | `calculations/b1.py` through `b5.py` | Independent fixed-example recalculation |
| Shared foundation | `domain/models.py`, `domain/validation.py` | Results, statuses, sources and error criteria |

`infrastructure/report.py` remains an internal reference-result audit tool.
`ProjectSnapshot` and project-file utilities serve internal and general projects;
the general loader rejects non-GENERAL cases. Legacy `domain/section.py` and
reference UI adapters are removed; current drawing uses general Shapes only.

```text
__main__ -> GeneralWindow -> GeneralFormModel
                              |-> parse_general_input -> calculate_general
                              |-> render_general_report
             |-> general_section_shapes -> canvas_item -> Tk Canvas
             |-> save_general_project / load_general_project -> ProjectSnapshot JSON

tests -> general model / report / shapes / Tk widgets
test_reference_cases -> internal standard-example calculators
```

Calculations must not depend on Tk, dialogs or UI events. Graphics consume
inputs/metrics but cannot change engineering results. Runtime and tests use
the standard library; setuptools is the declared build dependency.

### Shared calculation state

`GeneralFormModel.to_input_json()` emits schema 4 and provenance.
`parse_general_input()` validates it before `calculate_general()` returns
`GeneralCalculationResult`: inputs, metrics, checks, raw calculation results,
warnings and sources. `Outcome` represents a valid result or an explicit error.
Keep full numerical precision; only display/report formatting rounds values.
Application, input-schema and database versions are independent.

`TappedInput` holds `hole_type` and optional thickness/hole/thread depths.
`GeneralInput.tapped_geometry` resolves one immutable `TappedGeometry`, including
the drill tip, cylindrical depth, external-thread start and overlap.
Input validation rejects bottoming, blind-hole breakthrough, excessive thread
depth and zero overlap. Existing engagement `mvorh`, R11,
`SectionMetrics.engagement_length`, red `engaged-thread` and `dim-mges` all
consume the same resolved length. Hole-type edits use the existing debounce
path and toggle `Lh`; reports disclose estimates without adding H to lK.

### Persistence and report implementation

Project `inputs` contains complete `GeneralInput.to_json()` and `metadata`
records the application version, not UI language or cached results.
Loading builds and calculates a candidate model before replacing the current one.
`_saved_inputs` detects unsaved edits. If saving before loading overwrites the
pending load path, reread it instead of using a pre-save cached candidate.

Load and language switching reuse `_rebuild()`. Loading cancels old timers and
clears cached geometry before generating the new views.
`write_text_atomic()` writes and synchronizes a temporary file in the target
directory, then replaces the target; failures clean up the temporary file.
Both projects and reports use this mechanism.

`CalculationValue.calculation_step` is optional metadata in the range 1–13;
legacy internal results may leave it unset. General `_Values` assigns steps
without changing formulas, including early engagement as R11 and late SD as R9.
The report groups by metadata and explicitly rejects missing steps rather than
guessing from formula text.

### Canvas adaptation

Each Shape contains coordinates, style, text and role. `section_target(role)`
resolves a field; `canvas_item()` creates Canvas items with `target:<path>` tags.
Centerlines and cones must not block part clicks. Basic drawing primitives
implement arcs, threads and dimensions without extra dependencies.
Polygons with opacity below 1 map to empty fill/dashed outlines in Tk.

## 5. Nonfunctional requirements

- Python 3.10+ and usable Tcl/Tk for the desktop; no runtime/test third-party
  dependencies or external service requirement.
- Headless testing of the calculation layer, form model, geometry and reports.
- Full-precision calculations, explicit errors and no success-shaped defaults
  for invalid inputs, limitations or unfinished work.
- Local design processing and traceable values, sources, licenses and assumptions.
- Separate macOS and Windows acceptance; macOS results do not certify Windows.

## 6. Tests and acceptance

After installation:

```sh
python -m unittest discover -s tests -v
```

From the source tree on macOS:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

VS Code tasks are **VDI 2230: Tk UI** and **VDI 2230: All tests**.

| Test group | Coverage |
|---|---|
| `test_bolt_catalog`, `test_engineering_data` | Values, sources, baseline acceptance and unknown sources |
| `test_general_inputs`, `test_general_engine` | Boundaries, formulas, statuses and general-model regressions |
| `test_general_washers` | Geometry, series compliance, bearing, torque, ESV and click targets |
| `test_general_section`, `test_general_report` | Shapes, dimensions, scope, sources, reports and verdicts |
| `test_i18n` | Numeric/check/coordinate invariance, templates, user text and model-language isolation |
| `test_general_desktop_model` | Catalog overrides, plate operations, snapshots and bilingual DSV/ESV errors |
| `test_general_desktop_window` | Real Tk widgets, timers, redraw, clicks, export, theme and entry points |
| `test_release_structure` | Modules, metadata, documentation links and CLI, no legacy modes or Tk/HTTP dependency in the model |
| `test_reference_cases`, `test_domain_foundation` | Internal examples, tolerances, provenance, serialization and audits |

Only tests specific to removed HTTP/DOM/browser/reference UI surfaces are
removed. Their engineering coverage remains in direct model/geometry tests,
including washer errors, bilingual consistency, short-bolt errors after plate
edits, invalid-input recovery and English-template callback regressions.

### Internal B1–B5 numerical criteria

Retain original example inputs and formula sources. Explicit reference values
use the existing 3% relative-error threshold; zero references use explicit
absolute comparisons. Assert all twelve safety factors individually, not only
the maximum aggregate error.

| Case | Individually checked factors |
|---|---|
| B1 | SF, Sp |
| B2 | SG |
| B3 | Sp, SG |
| B4 | SD, SpK, SpMu, SG |
| B5 | SF, SD, Sp |

Keep the unresolved B1 additional-compliance discrepancy and Review/Incomplete
status; do not reverse-fit formulas to pass. Retain general-model B1–B3
regressions with equivalent inputs. B3 uses muG = 0.12, muK = 0.10 and
MA = 521.135 N·m. Passing regressions is not database certification or support
for eccentric joints/bolt groups.

### Release acceptance checklist

1. Installation, sole application entry point and consistent version information.
2. Catalog fill/override, DSV/ESV, plates, both washers and independent friction.
3. Field ranges, nonfinite values, geometry/domain errors and correction recovery.
4. Individual safety factors, example regressions and retained source conflicts.
5. Language-invariant values/coordinates, user text, real Tk timers and click focus.
6. Matching report preview/export, stale-export prevention and explicit errors.
7. Packaged engineering data/licenses and no removed interfaces/resources.
8. Project round trips, recalculation consistency, and no data loss on cancel/error.
9. Valid Markdown, ordered R1–R13, each result once, and retained check reasons.

Tk window tests explicitly skip when Tk or a display is unavailable.
Desktop acceptance requires a display-equipped machine and disclosure of every
skip; core-only success is not GUI acceptance. Windows needs its own native
window, dialog and font-layout validation.

## 7. Build and release procedure

Run in the configured project environment:

```sh
python -m pip wheel --no-deps --wheel-dir dist .
python -m pip install -e .
vdi2230 --version
python -m unittest discover -s tests -v
```

pip's isolated build installs declared build dependencies; runtime remains
standard-library-only. `--no-build-isolation` requires a prepared setuptools
environment. Namespace scanning is disabled so leftover non-package directories
are not shipped.

Before release:

1. Match package metadata, `__version__`, CLI and report versions.
2. Ship only the `vdi2230` console script, no Web/reference UI or static pages.
3. Retain all three engineering JSON datasets, source/license records and
   internal regression calculators.
4. Load data, calculate and render a report from an independently installed
   wheel, so editable source paths cannot hide missing resources.
5. Pass all applicable tests and per-factor thresholds; disclose platform/display
   limitations.
6. Review the diff, remove temporary build outputs and create a rollback-ready
   commit after obtaining required approval, without changing unrelated versions.

Reinstall editable packages after switching releases to refresh entry points.
Close/restart old processes; a branch switch does not hot-reload a running window.
A wheel is a Python package, not a standalone macOS/Windows application.
Native installers, signing/notarization and Windows hardware acceptance remain
separate distribution work.
