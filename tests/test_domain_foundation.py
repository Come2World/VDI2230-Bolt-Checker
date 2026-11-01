import json
import tempfile
import unittest
from pathlib import Path

from vdi2230.domain.models import (
    CalculationResult,
    CalculationValue,
    ProjectSnapshot,
    ResultStatus,
)
from vdi2230.domain.validation import (
    matches_reference,
    relative_error_percent,
    require_finite,
    within_relative_tolerance,
)
from vdi2230.infrastructure.project_file import (
    FORMAT_ID,
    SCHEMA_VERSION,
    load_project,
    save_project,
)
from vdi2230.infrastructure.report import render_text_report


class DomainFoundationTests(unittest.TestCase):
    def test_calculation_step_metadata_is_optional_and_validated(self):
        value = CalculationValue(symbol="d", label="Diameter", value=12, unit="mm", formula_reference="input")
        self.assertIsNone(value.calculation_step)
        for invalid in (0, 14, True, 1.5, "R3"):
            with self.subTest(step=invalid), self.assertRaises(ValueError):
                CalculationValue(symbol="d", label="Diameter", value=12, unit="mm",
                                 formula_reference="input", calculation_step=invalid)

    def test_numeric_validation_and_reference_tolerance(self):
        self.assertEqual(require_finite("length", 1.25), 1.25)
        self.assertAlmostEqual(relative_error_percent(103, 100), 3)
        self.assertTrue(within_relative_tolerance(103, 100))
        self.assertFalse(within_relative_tolerance(103.01, 100))
        self.assertTrue(matches_reference(0.004, 0, absolute_tolerance=0.005))
        self.assertFalse(matches_reference(0.006, 0, absolute_tolerance=0.005))

        for invalid in (float("nan"), float("inf"), True, "2"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    require_finite("input", invalid)
        with self.assertRaises(ValueError):
            relative_error_percent(1, 0)
        with self.assertRaisesRegex(ValueError, "absolute_tolerance"):
            matches_reference(0, 0)

    def test_project_file_round_trip_and_schema_rejection(self):
        project = ProjectSnapshot(
            case_id="B1",
            title="Hydraulic cylinder",
            inputs={"d_mm": 12, "load_n": 24900},
            assumptions=("Reference example input",),
            metadata={"source": "VDI 2230 Part 1:2015"},
            input_units={"d_mm": "mm", "load_n": "N"},
            input_sources={"d_mm": "B1 table", "load_n": "B1.1"},
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "project.json"
            save_project(path, project)
            self.assertEqual(load_project(path), project)

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["schema_version"] = SCHEMA_VERSION + 1
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema version"):
                load_project(path)

    def test_report_contains_sources_status_and_reference_comparison(self):
        project = ProjectSnapshot(
            case_id="B1",
            title="Hydraulic cylinder",
            inputs={"FAmax": 24900},
            assumptions=("Concentric axial loading",),
            input_units={"FAmax": "N"},
            input_sources={"FAmax": "VDI 2230 Part 1:2015, B1.1"},
        )
        result = CalculationResult(
            case_id="B1",
            model_name="Axial concentric case",
            source_reference="VDI 2230 Part 1:2015, Appendix B1",
            values=(
                CalculationValue(
                    symbol="FA",
                    label="maximum axial load",
                    value=24900.0,
                    unit="N",
                    formula_reference="B1.1",
                    reference_value=24900.0,
                    relative_error_percent=0.0,
                ),
                CalculationValue(
                    symbol="SF",
                    label="safety factor",
                    value=None,
                    unit="",
                    formula_reference="not calculated",
                    status=ResultStatus.NOT_CALCULATED,
                    note="Required input missing",
                ),
                CalculationValue(
                    symbol="FQ",
                    label="transverse force",
                    value=0.0,
                    unit="N",
                    formula_reference="B1.1",
                    reference_value=0,
                    absolute_error=0,
                    absolute_tolerance=0.05,
                ),
            ),
            warnings=("Reference case verification is pending.",),
        )
        report = render_text_report(project, result)
        self.assertIn("VDI 2230 Part 1:2015, Appendix B1", report)
        self.assertIn(
            "FAmax = 24900 N [VDI 2230 Part 1:2015, B1.1]",
            report,
        )
        self.assertIn("计算时间（UTC）：", report)
        self.assertIn("整体判定：未计算", report)
        self.assertIn("计算完整性：不完整", report)
        self.assertIn("相对误差：0.000%", report)
        self.assertIn("状态：未计算", report)
        self.assertIn("绝对容差：0.05 N", report)
        self.assertIn("Required input missing", report)

    def test_project_rejects_wrong_format(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "wrong.json"
            path.write_text(
                json.dumps(
                    {
                        "format": "other",
                        "schema_version": SCHEMA_VERSION,
                        "case_id": "B1",
                        "title": "wrong",
                        "inputs": {},
                        "assumptions": [],
                        "metadata": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "format"):
                load_project(path)

    def test_project_rejects_non_finite_numbers(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "non-finite.json"
            path.write_text(
                '{"format":"vdi2230-bolt-project","schema_version":1,'
                '"case_id":"B1","title":"invalid","inputs":{"x":NaN},'
                '"assumptions":[],"metadata":{}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "non-finite"):
                load_project(path)

    def test_empty_result_is_not_a_complete_calculation(self):
        result = CalculationResult(
            case_id="B1",
            model_name="Axial concentric case",
            source_reference="VDI 2230 Part 1:2015",
            values=(),
        )
        self.assertFalse(result.is_fully_calculated)
        self.assertEqual(result.overall_status, ResultStatus.NOT_CALCULATED)

    def test_calculation_results_reject_non_finite_values(self):
        with self.assertRaisesRegex(ValueError, "must be finite"):
            CalculationValue(
                symbol="δS",
                label="bolt resilience",
                value=float("nan"),
                unit="mm/N",
                formula_reference="B1 R3",
            )
        with self.assertRaisesRegex(ValueError, "absolute comparison"):
            CalculationValue(
                symbol="FQ",
                label="transverse force",
                value=0.1,
                unit="N",
                formula_reference="B2 R0",
                reference_value=0,
                relative_error_percent=1,
            )

    def test_overall_status_never_hides_a_failed_check(self):
        result = CalculationResult(
            case_id="B1",
            model_name="Axial concentric case",
            source_reference="VDI 2230 Part 1:2015",
            values=(
                CalculationValue(
                    symbol="SF",
                    label="safety factor",
                    value=0.8,
                    unit="",
                    formula_reference="B1",
                    status=ResultStatus.FAIL,
                ),
                CalculationValue(
                    symbol="δP",
                    label="part resilience",
                    value=None,
                    unit="mm/N",
                    formula_reference="B1",
                    status=ResultStatus.NOT_CALCULATED,
                ),
            ),
        )
        self.assertEqual(result.overall_status, ResultStatus.FAIL)
        self.assertFalse(result.is_fully_calculated)

if __name__ == "__main__":
    unittest.main()
