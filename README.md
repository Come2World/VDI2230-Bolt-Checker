# VDI 2230 Bolt Calculator

This local Python desktop application recalculates the five fixed Appendix B
reference cases (B1–B5) from VDI 2230 Part 1:2015, compares reported quantities
with the printed values, displays a schematic 2D section, and exports a UTF-8
text report.

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

The application uses only the Python standard library at runtime. Run tests
without installing test dependencies:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
