import unittest

from vdi2230.domain.models import ProjectSnapshot
from vdi2230.domain.section import section_primitives
from vdi2230.ui.reference_cases import build_reference_cases


class ReferenceCaseUiTests(unittest.TestCase):
    def test_all_reference_cases_are_read_only_and_renderable(self):
        cases = build_reference_cases()
        self.assertEqual([case.case_id for case in cases], ["B1", "B2", "B3", "B4", "B5"])

        for case in cases:
            with self.subTest(case=case.case_id):
                self.assertTrue(case.fields)
                self.assertTrue(all(field.read_only for field in case.fields))
                inputs = {
                    field.key: field.default_value for field in case.fields
                }
                geometry = case.geometry(inputs)
                self.assertTrue(
                    section_primitives(600, 500, geometry)
                )
                result = case.calculate(
                    ProjectSnapshot(
                        case_id=case.case_id,
                        title=case.title,
                        inputs=inputs,
                    )
                )
                self.assertEqual(result.case_id, case.case_id)
                self.assertTrue(result.values)

    def test_reference_calculation_rejects_modified_inputs(self):
        case = build_reference_cases()[0]
        inputs = {
            field.key: field.default_value for field in case.fields
        }
        inputs[next(iter(inputs))] = 123.0
        with self.assertRaisesRegex(ValueError, "fixed PDF reference"):
            case.calculate(
                ProjectSnapshot(
                    case_id=case.case_id,
                    title=case.title,
                    inputs=inputs,
                )
            )


if __name__ == "__main__":
    unittest.main()
