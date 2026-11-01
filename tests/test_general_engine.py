"""Regression of the general engine against VDI 2230 Appendix B examples B1–B3.

The worked examples carry rounded inputs and a few example-specific shortcuts
(Table A1 preload, chart readings). The general engine computes everything from
the inputs, so results are compared with a 3 % tolerance.
"""
from __future__ import annotations

import copy
import unittest

from vdi2230 import data as engineering_data
from vdi2230.calculations.b1 import calculate_b1
from vdi2230.calculations.b2 import calculate_b2
from vdi2230.calculations.b3 import calculate_b3
from vdi2230.calculations.general import (
    GeneralCalculationResult,
    calculate_general,
    iso965_tolerances,
)
from vdi2230.domain.general_inputs import InputValidationError, default_input_json, default_layer, parse_general_input
from vdi2230.domain.models import ResultStatus


TOLERANCE = 0.03


def _layer(index: int, **values: object) -> dict[str, object]:
    layer = default_layer(index)
    layer["material_id"] = None
    layer.update(values)
    return layer


def b1_payload() -> dict:
    payload = default_input_json()
    payload["provenance"] = {}
    payload["joint"].update(type="ESV", hole_diameter=13.5, chamfer_diameter=None, outer_diameter=80.0, substitute_diameter=80.0)
    payload["bolt"].update(
        catalog_variant_id=None, property_class="10.9", head_type="socket",
        d=12.0, pitch=1.75, d2=10.863, d3=9.85, stress_area=84.3,
        head_bearing_diameter=17.23, head_height=12.0, length=60.0, thread_length=36.0,
        yield_strength=940.0, tensile_strength=1040.0, shear_ratio=0.62, thread_friction=0.10, bearing_friction=0.10,
    )
    payload["tapped"].update(material_id=None, youngs_modulus=205000.0, tensile_strength=700.0, shear_strength=460.0)
    payload["plates"] = [_layer(0, thickness=42.0, limiting_surface_pressure=1300.0, roughness_rz=16.0)]
    payload["load"].update(axial_max=24946.2, axial_min=0.0, residual_clamp=1000.0)
    payload["load_introduction"].update(mode="manual", n=0.35)
    payload["assembly"].update(tightening_factor=1.8)
    payload["advanced"].update(w="1", cone="TBJ", cone_start_diameter=21.115)
    return payload


def b2_payload() -> dict:
    payload = default_input_json()
    payload["provenance"] = {}
    payload["joint"].update(type="DSV", hole_diameter=17.0, chamfer_diameter=17.7, outer_diameter=99.044, substitute_diameter=None)
    payload["bolt"].update(
        catalog_variant_id=None, property_class="10.9", head_type="hex",
        d=16.0, pitch=2.0, d2=14.701, d3=13.546, stress_area=157.0,
        head_bearing_diameter=22.5, head_height=10.0, length=80.0, thread_length=38.0,
        yield_strength=940.0, tensile_strength=1000.0, shear_ratio=0.62, thread_friction=0.12, bearing_friction=0.12,
    )
    payload["nut"].update(height=14.1, bearing_diameter=22.5)
    payload["plates"] = [
        _layer(index, thickness=30.0, youngs_modulus=110000.0, limiting_surface_pressure=850.0, interface_friction=0.15)
        for index in range(2)
    ]
    payload["load"].update(axial_max=0.0, transverse=8397.93)
    payload["assembly"].update(tightening_factor=1.6)
    payload["embedding"].update(mode="manual", fz_um=11.0)
    return payload


def b3_payload() -> dict:
    payload = default_input_json()
    payload["provenance"] = {}
    payload["joint"].update(type="ESV", hole_diameter=29.0, chamfer_diameter=28.0, outer_diameter=48.0, substitute_diameter=72.0)
    payload["bolt"].update(
        catalog_variant_id=None, property_class=None, head_type="hex",
        d=27.0, pitch=2.0, d2=25.7, d3=24.54, stress_area=495.6,
        head_bearing_diameter=36.0, head_height=10.0, length=40.0, thread_length=24.0,
        shank_diameter=24.0, bore_diameter=16.0,
        yield_strength=660.0, tensile_strength=830.0, shear_ratio=0.65, thread_friction=0.12, bearing_friction=0.10,
    )
    payload["tapped"].update(material_id=None, tensile_strength=1000.0, shear_strength=600.0, engagement_length=18.5, outer_diameter=50.0)
    payload["plates"] = [
        _layer(index, thickness=thickness, limiting_surface_pressure=710.0, roughness_rz=16.0, interface_friction=0.10)
        for index, thickness in enumerate((1.5, 7.0, 7.5))
    ]
    payload["load"].update(axial_max=0.0, torque=110.0, friction_radius=19.5)
    payload["assembly"].update(tightening_factor=1.6)
    payload["embedding"].update(mode="table", interface_count=2)
    return payload


def a2_payload(grade: str) -> dict:
    payload = default_input_json()
    variant = payload["bolt"]["catalog_variant_id"]
    values = engineering_data.bolt_catalog_values(variant, payload["bolt"]["length"], grade)
    for path, value in values.items():
        section, name = path.split(".")
        payload[section][name] = value
    payload["bolt"]["property_class"] = grade
    payload["provenance"].update(engineering_data.catalog_value_sources(variant, grade))
    if grade == "A2-90":
        payload["bolt"]["shear_ratio"] = 0.7
        payload["provenance"].pop("bolt.shear_ratio", None)
    return payload


def run(payload: dict) -> GeneralCalculationResult:
    return calculate_general(parse_general_input(payload))


def reference(result, symbol: str) -> float:
    return float(next(item.value for item in result.values if item.symbol == symbol))


class GeneralRegressionTests(unittest.TestCase):
    def assert_close(self, actual: float, expected: float, label: str) -> None:
        deviation = abs(actual - expected) / abs(expected)
        self.assertLessEqual(deviation, TOLERANCE, f"{label}: {actual:.6g} vs {expected:.6g} ({deviation:.2%})")

    def test_b1_tapped_thread_joint(self) -> None:
        source = calculate_b1()
        result = run(b1_payload())
        self.assert_close(result.check("SF").value, reference(source, "SF"), "B1 SF")
        self.assert_close(result.check("Sp,K").value, reference(source, "Sp"), "B1 Sp")
        self.assert_close(result.value("FMzul"), 64_800, "B1 FMzul vs Table A1")
        self.assert_close(result.value("MA"), 108, "B1 MA")
        self.assert_close(result.value("fZ"), 0.008, "B1 fZ")
        self.assert_close(result.value("δS"), reference(source, "dS"), "B1 δS")
        self.assert_close(result.value("δP"), reference(source, "dP"), "B1 δP")
        self.assert_close(result.value("tanφ"), reference(source, "tanPhiD"), "B1 tanφ")
        self.assert_close(result.value("FMmin") - result.value("FZ"), 1000 + (1 - result.value("Φn")) * 24946.2, "B1 FMmin")
        self.assert_close(result.value("mges,min") - 2 * 1.75, reference(source, "meff"), "B1 meff")
        self.assertEqual(result.check("mges").status, ResultStatus.PASS)
        self.assertEqual(result.check("SD").status, ResultStatus.PASS)
        # Documented deviation: the source combines w = 1 cone geometry with the
        # ESV term δPzu = δM, so its Φ is about 1.46 × the consistent w = 1 value.
        source_phi = reference(source, "PhiEn")
        self.assertGreater(abs(result.value("Φn") - source_phi) / source_phi, 0.25)

    def test_b1_source_load_factor_is_reproduced_with_w_2_compliance_term(self) -> None:
        source = calculate_b1()
        result = run(b1_payload())
        reconstructed = 0.35 * (result.value("δP") + result.value("δM")) / (result.value("δS") + result.value("δP"))
        self.assert_close(reconstructed, reference(source, "PhiEn"), "B1 Φ with δPzu = δM")

    def test_b2_through_bolt_with_transverse_load(self) -> None:
        source = calculate_b2()
        result = run(b2_payload())
        self.assert_close(result.check("SG").value, reference(source, "SG"), "B2 SG")
        self.assert_close(result.value("FKRmin"), reference(source, "FKRmin"), "B2 FKRmin")
        self.assert_close(result.value("FMzul"), reference(source, "FMzul"), "B2 FMzul")
        self.assert_close(result.value("MA"), reference(source, "MA"), "B2 MA")
        self.assert_close(result.value("δS"), reference(source, "dS"), "B2 δS")
        self.assert_close(result.value("δP"), reference(source, "dP"), "B2 δP")
        self.assert_close(result.value("FZ"), reference(source, "FZ"), "B2 FZ")
        self.assert_close(result.value("FKerf"), reference(source, "FKerf"), "B2 FKerf")
        self.assert_close(result.value("τB"), reference(source, "tauB"), "B2 τB")
        self.assert_close(result.value("τQmax"), reference(source, "tauQmax"), "B2 τQmax")
        source_sp = reference(source, "pG") / reference(source, "pMmax")
        self.assert_close(result.check("Sp,K").value, source_sp, "B2 Sp")
        self.assertEqual(result.check("SD").status, ResultStatus.NOT_APPLICABLE)
        self.assertEqual(result.check("SA").status, ResultStatus.PASS)

    def test_b3_hollow_reduced_shank_bolt_with_torque(self) -> None:
        source = calculate_b3()
        result = run(b3_payload())
        self.assert_close(result.value("FMzul"), reference(source, "FMzul"), "B3 FMzul")
        self.assert_close(result.check("SG").value, reference(source, "SG"), "B3 SG")
        self.assert_close(result.check("Sp,K").value, reference(source, "Sp"), "B3 Sp")
        self.assert_close(result.value("MA"), reference(source, "MA"), "B3 MA")
        self.assertAlmostEqual(result.value("μK"), 0.10)
        self.assertAlmostEqual(result.input.bolt.thread_friction, 0.12)
        self.assert_close(result.value("A0"), reference(source, "A0"), "B3 A0")
        self.assert_close(result.value("δS"), reference(source, "dS"), "B3 δS")
        self.assert_close(result.value("δP"), reference(source, "dP"), "B3 δP")
        self.assert_close(result.value("δPzu"), reference(source, "dPzu"), "B3 δPzu")
        self.assert_close(result.value("fZ"), reference(source, "fZ"), "B3 fZ")
        self.assert_close(result.value("FZ"), reference(source, "FZ"), "B3 FZ")
        self.assert_close(result.value("RS"), reference(source, "RS"), "B3 RS")
        self.assert_close(result.value("C1"), reference(source, "C1"), "B3 C1")
        self.assert_close(result.value("C2"), reference(source, "C2"), "B3 C2")
        self.assertEqual(result.check("mges").status, ResultStatus.PASS)
        # Documented deviation: the B3 source uses FMzul and mZu = 1.2P instead of
        # Rm,max·A0 and 2P (eq. 210/213), so the general engine is more conservative.
        self.assertGreater(result.check("mges").required, reference(source, "mgesmin"))
        self.assertEqual(result.check("SA").status, ResultStatus.NOT_APPLICABLE)


class GeneralEngineBehaviourTests(unittest.TestCase):
    def test_tapped_thread_depth_changes_r11_but_not_clamp_or_compliance(self):
        payload = b1_payload()
        original = run(payload)
        payload["tapped"]["thread_depth"] = 4.0
        shorter = run(payload)
        self.assertEqual(original.check("mges").status, ResultStatus.PASS)
        self.assertEqual(shorter.check("mges").status, ResultStatus.FAIL)
        self.assertEqual(shorter.check("mges").value, 4.0)
        self.assertEqual(shorter.metrics.engagement_length, 4.0)
        self.assertEqual(shorter.value("mvorh"), 4.0)
        self.assertEqual(original.check("mges").required, shorter.check("mges").required)
        for symbol in ("lK", "δS", "δP", "FMzul", "MA"):
            self.assertEqual(original.value(symbol), shorter.value(symbol))

    def test_bearing_friction_changes_only_bearing_torque_not_thread_stress(self):
        payload = default_input_json()
        baseline = run(payload)
        payload["bolt"]["bearing_friction"] = 0.10
        result = run(payload)
        self.assertEqual(result.value("μK"), 0.10)
        self.assertEqual(result.input.bolt.thread_friction, 0.12)
        expected_change = baseline.value("FMzul") * baseline.value("DKm") / 2 * 0.02 / 1000
        self.assertAlmostEqual(baseline.value("MA") - result.value("MA"), expected_change)
        for symbol in ("FMzul", "MG", "SF", "SD", "Sp,K", "Sp,M"):
            self.assertEqual(result.value(symbol), baseline.value(symbol), symbol)

    def test_default_input_uses_accepted_catalog_data_without_forced_review(self) -> None:
        result = run(default_input_json())
        self.assertEqual(result.verdict, ResultStatus.PASS)
        self.assertEqual(result.verdict_label, "通过")
        self.assertEqual(result.provisional_sources, ())
        self.assertEqual(result.warnings, ())
        self.assertEqual(result.input.provenance["bolt.d"], "catalog:ISO4014-M12x1.75")
        self.assertNotIn(ResultStatus.FAIL, {check.status for check in result.checks})

    def test_accepting_database_keeps_estimates_and_model_limitations_under_review(self):
        payload = default_input_json()
        payload["head_washer"]["enabled"] = True
        result = run(payload)
        self.assertEqual(result.verdict, ResultStatus.NEEDS_REVIEW)
        self.assertEqual(len(result.provisional_sources), 4)
        self.assertTrue(all(" ← default:" in source for source in result.provisional_sources))
        self.assertTrue(any("head_washer.model" in source for source in result.provisional_sources))
        self.assertTrue(any("局部屈服" in warning for warning in result.warnings))

    def test_user_values_with_manual_tables_can_pass(self) -> None:
        result = run(b2_payload())
        self.assertEqual(result.check("mges").status, ResultStatus.NOT_APPLICABLE)
        self.assertEqual(result.provisional_sources, ())
        self.assertEqual(result.verdict, ResultStatus.PASS)
        self.assertEqual(result.verdict_label, "通过")

    def test_r11_tolerance_approximation_is_flagged(self) -> None:
        result = run(b3_payload())
        self.assertIn("R11.tolerances ← default:ISO 965-1 6g/6H 公差公式近似", result.provisional_sources)
        self.assertEqual(result.verdict, ResultStatus.NEEDS_REVIEW)

    def test_failure_has_priority_over_review(self) -> None:
        payload = default_input_json()
        for layer in payload["plates"]:
            layer["limiting_surface_pressure"] = 200.0
        result = run(payload)
        self.assertEqual(result.check("Sp,K").status, ResultStatus.FAIL)
        self.assertEqual(result.verdict, ResultStatus.FAIL)
        self.assertEqual(result.verdict_label, "不通过")

    def test_plate_modulus_is_integrated_per_layer(self) -> None:
        stiff = default_input_json()
        soft = copy.deepcopy(stiff)
        soft["plates"][1]["youngs_modulus"] = 70000.0
        stiff_delta = run(stiff).value("δP")
        soft_delta = run(soft).value("δP")
        all_soft = copy.deepcopy(soft)
        all_soft["plates"][0]["youngs_modulus"] = 70000.0
        self.assertGreater(soft_delta, stiff_delta)
        self.assertAlmostEqual(run(all_soft).value("δP"), stiff_delta * 205000 / 70000, delta=stiff_delta * 1e-9)

    def test_splitting_a_layer_does_not_change_compliance(self) -> None:
        single = default_input_json()
        split = copy.deepcopy(single)
        split["plates"] = [dict(single["plates"][0], thickness=10.0), dict(single["plates"][0], thickness=10.0), single["plates"][1]]
        split["embedding"].update(mode="manual")
        single["embedding"].update(mode="manual")
        self.assertAlmostEqual(run(split).value("δP"), run(single).value("δP"), delta=1e-15)

    def test_sleeve_region_used_when_outer_diameter_is_small(self) -> None:
        payload = default_input_json()
        payload["joint"]["outer_diameter"] = 24.0
        result = run(payload)
        note = next(item.note for item in result.result.values if item.symbol == "DA,Gr")
        self.assertIn("套筒", note)
        self.assertIn("纯锥体", next(item.note for item in run(default_input_json()).result.values if item.symbol == "DA,Gr"))

    def test_reduced_shank_controls_critical_section(self) -> None:
        payload = default_input_json()
        payload["bolt"]["shank_diameter"] = 9.0
        result = run(payload)
        self.assertAlmostEqual(result.metrics.critical_diameter, 9.0)
        self.assertAlmostEqual(result.value("A0"), 3.141592653589793 / 4 * 81)
        self.assertLess(result.value("FMzul"), run(default_input_json()).value("FMzul"))

    def test_hollow_bolt_reduces_areas(self) -> None:
        payload = default_input_json()
        payload["bolt"]["bore_diameter"] = 4.0
        self.assertLess(run(payload).value("A0"), run(default_input_json()).value("A0"))

    def test_full_thread_bolt_has_no_shank_in_grip(self) -> None:
        payload = default_input_json()
        payload["bolt"]["thread_length"] = None
        result = run(payload)
        self.assertEqual(result.value("l1"), 0.0)
        self.assertEqual(result.value("lGew"), result.value("lK"))

    def test_preload_override_is_used(self) -> None:
        payload = default_input_json()
        payload["advanced"]["preload_override"] = 40000.0
        result = run(payload)
        self.assertEqual(result.value("FMzul"), 40000.0)
        self.assertTrue(any("覆盖" in warning for warning in result.warnings))

    def test_finite_life_raises_fatigue_strength(self) -> None:
        payload = default_input_json()
        payload["load"]["cycles"] = 1e5
        finite = run(payload)
        self.assertGreater(finite.check("SD").value, run(default_input_json()).check("SD").value)

    def test_rolled_after_heat_treatment_uses_sg_limit(self) -> None:
        payload = default_input_json()
        payload["bolt"]["rolling"] = "SG"
        self.assertGreater(run(payload).check("SD").value, run(default_input_json()).check("SD").value)

    def test_nut_short_protrusion_fails_engagement(self) -> None:
        payload = default_input_json()
        payload["bolt"]["length"] = 45.0
        payload["bolt"]["thread_length"] = 30.0
        result = run(payload)
        self.assertEqual(result.check("mges").status, ResultStatus.FAIL)

    def test_non_standard_nut_runs_r11(self) -> None:
        payload = default_input_json()
        payload["nut"]["standard_adequate"] = False
        result = run(payload)
        self.assertIn(result.check("mges").status, {ResultStatus.PASS, ResultStatus.FAIL})
        self.assertIsNotNone(result.check("mges").required)

    def test_table_embedding_counts_interfaces(self) -> None:
        payload = default_input_json()
        two = run(payload).value("fZ")
        payload["plates"].append(default_layer(2))
        payload["bolt"]["length"] = 90.0
        payload["bolt"]["thread_length"] = 40.0
        three = run(payload).value("fZ")
        self.assertAlmostEqual(three - two, 0.002)

    def test_iso965_tolerances_match_b3_values(self) -> None:
        tolerances = iso965_tolerances(27, 2, 25.7)
        # ISO 965-1 tabulates rounded deviations; the formula is within 3 µm.
        self.assertAlmostEqual(tolerances["d2_min"], 25.493, delta=0.003)
        self.assertAlmostEqual(tolerances["D1_max"], 25.21, delta=0.003)
        self.assertAlmostEqual(tolerances["d_min"], 26.682, delta=0.003)


class AusteniticBoltTests(unittest.TestCase):
    def test_a2_fatigue_requires_product_data_without_iso898_estimates(self) -> None:
        for grade in ("A2-70", "A2-80", "A2-90"):
            with self.subTest(grade=grade):
                result = run(a2_payload(grade))
                self.assertEqual(result.check("SD").status, ResultStatus.NEEDS_REVIEW)
                self.assertIsNone(result.check("SD").value)
                self.assertNotEqual(result.verdict, ResultStatus.PASS)
                self.assertTrue(any("疲劳" in warning for warning in result.warnings))
                with self.assertRaises(KeyError):
                    result.value("σASV")
                with self.assertRaises(KeyError):
                    result.value("SD")

    def test_product_fatigue_amplitude_is_used_directly_for_the_specified_life(self) -> None:
        payload = a2_payload("A2-80")
        payload["bolt"]["fatigue_strength_amplitude"] = 50
        payload["load"]["cycles"] = 100_000
        for rolling in ("SV", "SG"):
            with self.subTest(rolling=rolling):
                payload["bolt"]["rolling"] = rolling
                result = run(payload)
                self.assertAlmostEqual(result.check("SD").value, 50 / result.value("σa"))
                self.assertEqual(result.value("σA,input"), 50)
                with self.assertRaises(KeyError):
                    result.value("σASV")
        payload["bolt"]["fatigue_strength_amplitude"] = 0.01
        failed = run(payload)
        self.assertEqual(failed.check("SD").status, ResultStatus.FAIL)
        self.assertEqual(failed.verdict, ResultStatus.FAIL)

    def test_product_fatigue_check_uses_the_required_threshold(self) -> None:
        payload = a2_payload("A2-70")
        stress = run(payload).value("σa")
        required = payload["requirements"]["SD"]
        for multiplier, status in ((0.999, ResultStatus.FAIL), (1.0, ResultStatus.PASS), (1.001, ResultStatus.PASS)):
            with self.subTest(multiplier=multiplier):
                payload["bolt"]["fatigue_strength_amplitude"] = stress * required * multiplier
                self.assertEqual(run(payload).check("SD").status, status)

    def test_no_alternating_load_needs_no_fatigue_data(self) -> None:
        payload = a2_payload("A2-70")
        payload["load"]["axial_min"] = payload["load"]["axial_max"]
        result = run(payload)
        self.assertEqual(result.check("SD").status, ResultStatus.NOT_APPLICABLE)
        self.assertFalse(any("疲劳强度" in warning for warning in result.warnings))
        with self.assertRaises(KeyError):
            result.value("σASV")

    def test_a2_r11_requires_maximum_tensile_strength(self) -> None:
        for joint_type in ("ESV", "DSV"):
            with self.subTest(joint_type=joint_type):
                payload = a2_payload("A2-70")
                payload["joint"]["type"] = joint_type
                payload["nut"]["standard_adequate"] = False
                result = run(payload)
                self.assertEqual(result.check("mges").status, ResultStatus.NEEDS_REVIEW)
                self.assertIsNone(result.check("mges").required)
                self.assertTrue(any("Rm,max" in warning for warning in result.warnings))
                with self.assertRaises(KeyError):
                    result.value("mges,min")
                payload["bolt"]["tensile_strength_max"] = 850
                if joint_type == "DSV":
                    missing_nut = run(payload)
                    self.assertEqual(missing_nut.check("mges").status, ResultStatus.NEEDS_REVIEW)
                    payload["nut"].update(tensile_strength=900, shear_ratio=0.7)
                result = run(payload)
                self.assertIn(result.check("mges").status, {ResultStatus.PASS, ResultStatus.FAIL})
                self.assertGreater(result.value("mges,min"), 0)

    def test_a2_90_supplier_reference_requires_product_applicability_review(self) -> None:
        payload = a2_payload("A2-90")
        payload["load"].update(axial_min=0, axial_max=0)
        result = run(payload)
        self.assertEqual(result.verdict, ResultStatus.NEEDS_REVIEW)
        self.assertTrue(any("A2-90" in source for source in result.provisional_sources))
        self.assertTrue(any("厂商" in warning for warning in result.warnings))

    def test_a2_catalog_strengths_are_rejected_outside_catalog_diameters(self) -> None:
        payload = a2_payload("A2-70")
        payload["bolt"]["d"] = 31
        with self.assertRaises(InputValidationError) as raised:
            parse_general_input(payload)
        self.assertTrue(any(error.path == "bolt.d" and "目录 A2" in error.message for error in raised.exception.errors))

    def test_standard_nut_setting_requires_product_confirmation(self) -> None:
        result = run(a2_payload("A2-70"))
        self.assertEqual(result.check("mges").status, ResultStatus.NOT_APPLICABLE)
        self.assertTrue(any("螺母" in warning for warning in result.warnings))

    def test_user_supplied_shear_ratio_is_not_attributed_to_table_7(self) -> None:
        payload = a2_payload("A2-90")
        payload["load"]["transverse"] = 500
        result = run(payload)
        shear = next(value for value in result.result.values if value.symbol == "τB")
        self.assertIn("螺栓输入", shear.formula_reference)
        self.assertNotIn("表 7", shear.formula_reference)

    def test_failure_overrides_supplier_reference_review(self) -> None:
        payload = a2_payload("A2-90")
        payload["bolt"]["fatigue_strength_amplitude"] = 0.01
        result = run(payload)
        self.assertTrue(result.provisional_sources)
        self.assertEqual(result.check("SD").status, ResultStatus.FAIL)
        self.assertEqual(result.verdict, ResultStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
