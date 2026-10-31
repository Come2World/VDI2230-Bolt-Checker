import math
import unittest

from vdi2230.calculations.general import calculate_general, deformation_diameter
from vdi2230.domain.general_inputs import default_input_json, parse_general_input
from vdi2230.domain.models import ResultStatus
from vdi2230.infrastructure.general_report import render_general_report
from vdi2230.infrastructure.general_section import general_section_shapes
from vdi2230.ui.general_model import GeneralFormModel, canvas_item
from vdi2230.web.general_api import calculate_payload

from test_general_inputs import error_paths


def calculate(payload):
    return calculate_general(parse_general_input(payload))


class WasherInputTests(unittest.TestCase):
    def test_defaults_are_optional_and_estimated_from_nominal_diameter(self):
        payload = default_input_json()
        item = parse_general_input(payload)
        self.assertFalse(item.head_washer.enabled)
        self.assertFalse(item.nut_washer.enabled)
        self.assertEqual(item.head_washer.inner_diameter, 13.2)
        self.assertEqual(item.head_washer.outer_diameter, 24)
        self.assertEqual(item.head_washer.thickness, 1.92)
        model = GeneralFormModel()
        model.set_value("bolt.catalog_variant_id", "ISO4014-M16x2.0")
        for side in ("head_washer", "nut_washer"):
            self.assertEqual(model.values[f"{side}.inner_diameter"], 17.6)
            self.assertEqual(model.values[f"{side}.outer_diameter"], 32)
            self.assertEqual(model.values[f"{side}.thickness"], 2.56)

    def test_manual_washer_dimensions_survive_diameter_and_catalog_changes(self):
        model = GeneralFormModel()
        model.set_value("head_washer.outer_diameter", 30)
        model.set_value("head_washer.thickness", 3)
        model.set_value("bolt.d", 14)
        self.assertEqual(model.values["head_washer.inner_diameter"], 15.4)
        model.set_value("bolt.catalog_variant_id", "ISO4014-M16x2.0")
        self.assertEqual(model.values["head_washer.outer_diameter"], 30)
        self.assertEqual(model.values["head_washer.thickness"], 3)
        self.assertIsNone(model.source_for("head_washer.thickness"))

    def test_washer_material_fields_are_filled_and_editable(self):
        model = GeneralFormModel()
        model.set_value("head_washer.material_id", "42CrMo4")
        self.assertEqual(model.values["head_washer.limiting_surface_pressure"], model.materials["42CrMo4"]["limiting_surface_pressure"])
        model.set_value("head_washer.youngs_modulus", 200000)
        self.assertIsNone(model.source_for("head_washer.youngs_modulus"))
        self.assertIn("头侧垫片", model.label_for("head_washer.thickness"))

    def test_washer_geometry_validation(self):
        for field, value in (("inner_diameter", 12), ("outer_diameter", 10), ("thickness", 0),
                             ("inner_diameter", 20), ("youngs_modulus", -1), ("roughness_rz", "abc")):
            with self.subTest(field=field, value=value):
                payload = default_input_json()
                payload["head_washer"].update(enabled=True, **{field: value})
                self.assertIn(f"head_washer.{field}", error_paths(payload))

    def test_washer_dimensions_round_trip(self):
        payload = default_input_json()
        payload["head_washer"].update(enabled=True, inner_diameter=14, outer_diameter=30, thickness=3.3)
        item = parse_general_input(payload)
        self.assertEqual(parse_general_input(item.to_json()), item)
        self.assertAlmostEqual(item.clamp_length, 43.3)

    def test_rejects_legacy_friction_instead_of_silently_ignoring_it(self):
        payload = default_input_json()
        payload["schema"] = "vdi2230.general/1"
        self.assertIn("schema", error_paths(payload))
        payload = default_input_json()
        payload["plates"][0]["bearing_friction"] = 0.1
        self.assertIn("plates[0].bearing_friction", error_paths(payload))
        payload = default_input_json()
        payload["bolt"]["bearing_friction"] = 0.1
        self.assertIn("bolt.thread_friction", error_paths(payload))

    def test_advanced_cone_cannot_enlarge_the_washer_contact(self):
        payload = default_input_json()
        payload["head_washer"]["enabled"] = True
        for diameter in (30, 13.1):
            payload["advanced"]["cone_start_diameter"] = diameter
            self.assertIn("advanced.cone_start_diameter", error_paths(payload))


class WasherCalculationTests(unittest.TestCase):
    def test_all_end_combinations_and_esv_excludes_nut_washer(self):
        for joint in ("DSV", "ESV"):
            for head in (False, True):
                for nut in (False, True):
                    with self.subTest(joint=joint, head=head, nut=nut):
                        payload = default_input_json()
                        payload["joint"]["type"] = joint
                        baseline = calculate(payload)
                        payload["head_washer"]["enabled"] = head
                        payload["nut_washer"]["enabled"] = nut
                        result = calculate(payload)
                        count = int(head) + int(nut and joint == "DSV")
                        self.assertAlmostEqual(result.value("lK"), 40 + count * 1.92)
                        self.assertAlmostEqual(result.value("fZ") - baseline.value("fZ"), count * 0.002)
                        if joint == "ESV":
                            self.assertFalse(any("nut_washer" in source for source in result.provisional_sources))

    def test_washer_compliances_are_in_series_and_bolt_grip_increases(self):
        payload = default_input_json()
        baseline = calculate(payload)
        payload["head_washer"]["enabled"] = payload["nut_washer"]["enabled"] = True
        result = calculate(payload)
        for side, suffix in (("head", "K"), ("nut", "M")):
            item = result.input
            area = math.pi / 4 * (item.bearing_outer(side) ** 2 - item.bearing_inner(side) ** 2)
            self.assertAlmostEqual(result.value(f"δW,{suffix}"), 1.92 / (205000 * area))
        self.assertAlmostEqual(result.value("δP,plates"), baseline.value("δP"))
        self.assertAlmostEqual(result.value("δP"), baseline.value("δP") + result.value("δW,K") + result.value("δW,M"))
        self.assertAlmostEqual(result.value("δS") - baseline.value("δS"), 3.84 / (205000 * math.pi / 4 * result.input.bolt.d3 ** 2))
        self.assertEqual(result.verdict, ResultStatus.NEEDS_REVIEW)

    def test_unequal_support_diameters_have_continuous_cones_and_correct_compliance(self):
        payload = default_input_json()
        payload["head_washer"].update(enabled=True, outer_diameter=15)
        result = calculate(payload)
        m = result.metrics
        length = result.input.plate_length
        tangent = m.tan_phi
        meet = length / 2 + (m.cone_start_nut - m.cone_start_head) / (4 * tangent)
        diameter = lambda z: deformation_diameter(z, length, 40, 1, tangent, m.cone_start_head, m.cone_start_nut)
        self.assertAlmostEqual(diameter(meet - 1e-8), diameter(meet + 1e-8), places=6)
        step = length / 10000
        numerical = sum(step / (205000 * math.pi / 4 * (diameter((i + 0.5) * step) ** 2 - 13.5 ** 2))
                        for i in range(10000))
        self.assertAlmostEqual(result.value("δP,plates"), numerical, delta=numerical * 1e-6)

    def test_large_washer_outer_diameter_does_not_inflate_contact_area(self):
        payload = default_input_json()
        payload["head_washer"]["enabled"] = True
        small = calculate(payload)
        payload["head_washer"]["outer_diameter"] = 100
        large = calculate(payload)
        for symbol in ("Ap,K", "Sp,K", "δW,K", "δP", "DKm", "MA"):
            self.assertAlmostEqual(small.value(symbol), large.value(symbol), msg=symbol)

    def test_soft_washer_governs_bearing_check_and_failure(self):
        payload = default_input_json()
        payload["head_washer"].update(enabled=True, limiting_surface_pressure=100)
        result = calculate(payload)
        self.assertEqual(result.check("Sp,K").value, result.value("Sp,W,K"))
        self.assertLess(result.value("Sp,W,K"), result.value("Sp,P,K"))
        self.assertEqual(result.check("Sp,K").status, ResultStatus.FAIL)
        self.assertEqual(result.verdict, ResultStatus.FAIL)
        self.assertAlmostEqual(result.value("Sp,W,K"), 100 / result.value("pmax,W,K"))

    def test_tightening_torque_uses_rotating_contact_not_washer_outer_diameter(self):
        for side in ("head", "nut"):
            with self.subTest(side=side):
                payload = default_input_json()
                payload[f"{side}_washer"].update(enabled=True, inner_diameter=14, outer_diameter=32)
                payload["bolt"]["thread_friction"] = 0.18
                payload["assembly"]["tighten_side"] = side
                result = calculate(payload)
                bearing = result.input.bolt.head_bearing_diameter if side == "head" else result.input.nut.bearing_diameter
                dkm = (bearing + 14) / 2
                self.assertAlmostEqual(result.value("DKm"), dkm)
                self.assertAlmostEqual(result.value("μK"), 0.18)
                expected = result.value("FMzul") * (0.16 * 1.75 + 0.58 * result.input.bolt.d2 * 0.18 + dkm / 2 * 0.18) / 1000
                self.assertAlmostEqual(result.value("MA"), expected)

    def test_washer_thickness_reduces_engagement(self):
        payload = default_input_json()
        payload["head_washer"].update(enabled=True, thickness=12)
        payload["nut_washer"].update(enabled=True, thickness=12)
        result = calculate(payload)
        self.assertEqual(result.value("mvorh"), 6)
        self.assertEqual(result.check("mges").status, ResultStatus.FAIL)
        payload["head_washer"]["thickness"] = 30
        self.assertIn("bolt.length", error_paths(payload))

    def test_washer_offset_changes_shear_plane_from_shank_to_thread(self):
        payload = default_input_json()
        payload["bolt"]["thread_length"] = 49
        payload["load"]["transverse"] = 1000
        baseline = calculate(payload)
        payload["head_washer"].update(enabled=True, thickness=3)
        result = calculate(payload)
        self.assertAlmostEqual(baseline.value("Aτ"), math.pi / 4 * 12 ** 2)
        self.assertAlmostEqual(result.value("Aτ"), math.pi / 4 * result.input.bolt.d3 ** 2)

    def test_roughness_error_points_to_washer(self):
        payload = default_input_json()
        payload["head_washer"].update(enabled=True, roughness_rz=1000)
        status, response = calculate_payload({"input": payload})
        self.assertEqual(status, 400)
        self.assertIn("head_washer.roughness_rz", [error["path"] for error in response["field_errors"]])

    def test_washer_bore_cannot_exceed_opposite_cone_in_a_single_plate(self):
        payload = default_input_json()
        payload["plates"] = [dict(payload["plates"][0], thickness=40)]
        payload["bolt"]["head_bearing_diameter"] = 25
        payload["head_washer"].update(enabled=True, inner_diameter=20, outer_diameter=30)
        status, response = calculate_payload({"input": payload})
        self.assertEqual(status, 400)
        self.assertIn("head_washer.inner_diameter", [error["path"] for error in response["field_errors"]])

    def test_report_and_api_include_washers_assumptions_and_click_targets(self):
        payload = default_input_json()
        payload["head_washer"]["enabled"] = payload["nut_washer"]["enabled"] = True
        result = calculate(payload)
        report = render_general_report(result)
        for text in ("头侧垫片", "螺母侧垫片", "43.84", "μG = μK", "δW", "Sp,W,K", "不计载荷扩散"):
            self.assertIn(text, report)
        status, response = calculate_payload({"input": payload})
        self.assertEqual(status, 200)
        for role, target in (("washer-head", "head_washer.thickness"), ("washer-nut", "nut_washer.thickness"),
                             ("bolt-head", "bolt.head_height"), ("nut", "nut.height")):
            shapes = [s for s in response["section"]["shapes"] if s["role"] == role]
            self.assertTrue(shapes, role)
            self.assertTrue(all(s["target"] == target for s in shapes))


class WasherDrawingTests(unittest.TestCase):
    def test_washers_stack_without_gaps_or_overlap(self):
        payload = default_input_json()
        payload["head_washer"]["enabled"] = payload["nut_washer"]["enabled"] = True
        result = calculate(payload)
        shapes = general_section_shapes(result.input, result.metrics, 640, 560)
        rect = lambda role: next(s for s in shapes if s.role == role and s.kind == "rect")
        head, nut = rect("washer-head"), rect("washer-nut")
        self.assertEqual(head.points[3], rect("plate-0").points[1])
        self.assertEqual(rect("plate-1").points[3], nut.points[1])
        self.assertAlmostEqual(head.points[3] - head.points[1], nut.points[3] - nut.points[1])
        self.assertIn("target:head_washer.thickness", canvas_item(head)[2]["tags"])

    def test_engineering_detail_has_curves_chamfers_hatching_and_foreground_axis(self):
        result = calculate(default_input_json())
        shapes = general_section_shapes(result.input, result.metrics, 640, 560)
        for role in ("bolt-head", "nut"):
            self.assertTrue(any(s.role == role and s.kind == "line" and len(s.points) > 4 for s in shapes))
        self.assertTrue(any(s.role == "bolt-thread" and s.kind == "polygon" for s in shapes))
        self.assertTrue(any(s.role == "plate-0" and s.kind == "line" for s in shapes))
        axis = next(i for i, s in enumerate(shapes) if s.role == "axis")
        self.assertTrue(shapes[axis].dash_pattern)
        self.assertGreater(axis, max(i for i, s in enumerate(shapes) if s.role in ("nut", "bolt-head")))
        self.assertTrue(any(s.role == "dim-d" and s.kind == "polygon" for s in shapes))

    def test_washer_drawing_coordinates_fit_small_and_large_views(self):
        payload = default_input_json()
        payload["head_washer"]["enabled"] = payload["nut_washer"]["enabled"] = True
        result = calculate(payload)
        for width, height in ((200, 200), (420, 320), (640, 560), (2400, 2400)):
            with self.subTest(view=(width, height)):
                for shape in general_section_shapes(result.input, result.metrics, width, height):
                    self.assertTrue(all(0 <= x <= width for x in shape.points[::2]), shape)
                    self.assertTrue(all(0 <= y <= height for y in shape.points[1::2]), shape)


if __name__ == "__main__":
    unittest.main()
