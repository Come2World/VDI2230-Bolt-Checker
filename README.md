# VDI 2230 Bolt Calculator

This local Python application (desktop and browser UI) recalculates the five fixed Appendix B
reference cases (B1–B5) from VDI 2230 Part 1:2015, compares reported quantities
with the printed values, displays a schematic 2D section, and exports a UTF-8
text report.

The browser UI has three columns: read-only reference inputs, an SVG joint
section, and results with individual safety-factor comparisons. It shares the
desktop calculation, geometry and report code; it does not require Tkinter.

The current release is a **reference-case verifier**, not a general-purpose
parameterized design calculator. The displayed source inputs are read-only;
changing a design parameter does not drive the calculation. Any result marked
for review or not calculated must be resolved against the source before use.
The tool does not replace the standard, engineering judgment, or design review.

## Run from the repository root

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
vdi2230
```

### Browser UI

```sh
PYTHONPATH=src python3 -m vdi2230.web
# Or, after installation:
vdi2230-web
```

Open <http://127.0.0.1:8765> in a browser or VS Code's integrated browser.
Use `--port 8766` if the default port is busy; stop the server with Ctrl+C.
The service binds only to the loopback interface, serves bundled local assets,
and requires no external network access. This is a local UI/test server, not
a production or shared-network service.

Select B1–B5 and click **计算**. The right column shows each available safety
factor's PDF reference, calculated value and relative error, expandable full
results and source details, and a TXT preview/download. Switching cases or a
failed calculation clears the previous result and disables export. B1 remains
**需确认** because of its unresolved additional-compliance source contradiction;
its report can be exported but explicitly retains the incomplete status.
The section is schematic, not a manufacturing drawing. The browser UI does not
yet expose the desktop application's custom project-title/JSON save/load controls.

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
and clean up both. They cover all five cases and 12 safety-factor comparisons,
read-only inputs, SVG sections, result invalidation, error/retry, out-of-order
responses, UTF-8 report downloads, and desktop/narrow layouts.

In VS Code, select the environment with the test extra installed, then use
**Tasks: Run Task**: **VDI 2230: Web UI**, **VDI 2230: Unit and API tests**, or
**VDI 2230: Browser UI tests**. Browser automation can use the accessible labels
`计算实例`, `计算`, `导出 TXT`, and the stable selectors `#section`,
`#safety-table tr[data-symbol="SF"]`, `#results-table`, `#status`, and `#error`.
