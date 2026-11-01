import copy
import json
import unittest

from vdi2230 import data as engineering_data
from vdi2230.domain.general_inputs import (
    FIELD_SPECS,
    LAYER_SPECS,
    LEGACY_SCHEMA_ID,
    MAX_LAYERS,
    SCHEMA_ID,
    GeneralInput,
    InputValidationError,
    default_input_json,
    default_layer,
    field_schema_json,
    parse_general_input,
)


def error_paths(payload: dict) -> set[str]:
    with unittest.TestCase().assertRaises(InputValidationError) as raised:
        parse_general_input(payload)
    return {error.path for error in raised.exception.errors}


class GeneralInputParsingTests(unittest.TestCase):
    def esv_payload(self):
        payload = default_input_json()
        payload["joint"]["type"] = "ESV"
        return payload

    def test_tapped_geometry_is_backward_compatible_and_round_trips(self):
        payload = self.esv_payload()
        for name in ("hole_type", "thickness", "hole_depth", "thread_depth"):
            payload["tapped"].pop(name)
        item = parse_general_input(payload)
        self.assertEqual(item.tapped.hole_type, "blind")
        self.assertEqual(item.tapped_geometry.engagement_length, 30.0)
        payload = item.to_json()
        payload["tapped"].update(thickness=45.0, hole_depth=38.0, thread_depth=20.0)
        item = parse_general_input(payload)
        self.assertEqual(item.tapped_geometry.engagement_length, 20.0)
        self.assertEqual(item.clamp_length, 40.0)
        self.assertEqual(parse_general_input(item.to_json()), item)

    def test_blind_depth_relations_reject_bottoming_and_thread_beyond_drill(self):
        for changes, path in (
            ({"thickness": 35, "hole_depth": 35}, "tapped.hole_depth"),
            ({"thickness": 40, "hole_depth": 32}, "bolt.length"),
            ({"thickness": 40, "hole_depth": 35, "thread_depth": 34}, "tapped.thread_depth"),
        ):
            with self.subTest(changes=changes):
                payload = self.esv_payload()
                payload["tapped"].update(changes)
                self.assertIn(path, error_paths(payload))
        payload = self.esv_payload()
        payload["tapped"]["hole_depth"] = 35.0
        cylinder = parse_general_input(payload).tapped_geometry.cylindrical_depth
        payload["bolt"]["length"] = 40.0 + cylinder
        self.assertIn("bolt.length", error_paths(payload))

    def test_through_hole_allows_protrusion_and_limits_threads_to_thickness(self):
        payload = self.esv_payload()
        payload["tapped"].update(hole_type="through", thickness=15.0)
        item = parse_general_input(payload)
        self.assertEqual(item.tapped_geometry.hole_depth, 15.0)
        self.assertEqual(item.tapped_geometry.thread_depth, 15.0)
        self.assertEqual(item.tapped_geometry.engagement_length, 15.0)
        payload["tapped"]["thread_depth"] = 16.0
        self.assertIn("tapped.thread_depth", error_paths(payload))

    def test_thread_overlap_respects_shank_start_and_manual_engagement_limit(self):
        payload = self.esv_payload()
        payload["bolt"]["thread_length"] = 20.0
        payload["tapped"].update(thread_depth=22.0, engagement_length=18.0)
        item = parse_general_input(payload)
        self.assertEqual(item.tapped_geometry.engagement_start, 10.0)
        self.assertEqual(item.tapped_geometry.engagement_length, 12.0)
        payload["tapped"]["engagement_length"] = 8.0
        self.assertEqual(parse_general_input(payload).tapped_geometry.engagement_length, 8.0)
        payload["tapped"]["thread_depth"] = 10.0
        self.assertIn("tapped.thread_depth", error_paths(payload))

    def test_tapped_dimensions_reject_invalid_values(self):
        for name in ("thickness", "hole_depth", "thread_depth"):
            for invalid in (0, -1, True, "nan", float("inf"), "invalid"):
                with self.subTest(field=name, value=invalid):
                    payload = self.esv_payload()
                    payload["tapped"][name] = invalid
                    self.assertIn(f"tapped.{name}", error_paths(payload))
        payload = self.esv_payload()
        payload["tapped"]["hole_type"] = "unknown"
        self.assertIn("tapped.hole_type", error_paths(payload))

    def test_default_round_trip(self) -> None:
        item = parse_general_input(default_input_json())
        self.assertIsInstance(item, GeneralInput)
        self.assertEqual(len(item.plates), 2)
        self.assertEqual(item.clamp_length, 40.0)
        self.assertTrue(item.is_through_bolt)
        again = GeneralInput.from_json(json.loads(json.dumps(item.to_json())))
        self.assertEqual(again, item)

    def test_schema_3_inputs_migrate_to_schema_4_without_reinterpreting_fatigue(self) -> None:
        payload = default_input_json()
        payload["schema"] = LEGACY_SCHEMA_ID
        del payload["bolt"]["fatigue_strength_amplitude"]
        item = parse_general_input(payload)
        self.assertIsNone(item.bolt.fatigue_strength_amplitude)
        self.assertEqual(item.to_json()["schema"], SCHEMA_ID)
        payload["bolt"]["fatigue_strength_amplitude"] = 50
        self.assertIn("bolt.fatigue_strength_amplitude", error_paths(payload))

    def test_default_values_come_from_catalog_and_materials(self) -> None:
        payload = default_input_json()
        catalog = engineering_data.bolt_catalog_values(
            payload["bolt"]["catalog_variant_id"],
            payload["bolt"]["length"],
            payload["bolt"]["property_class"],
        )
        for path, value in catalog.items():
            section, name = path.split(".")
            if path == "bolt.shank_diameter":
                continue
            self.assertEqual(payload[section][name], value, path)
        plate = engineering_data.material_values(payload["plates"][0]["material_id"])
        self.assertEqual(payload["plates"][0]["limiting_surface_pressure"], plate["limiting_surface_pressure"])
        self.assertEqual(payload["provenance"]["bolt.d"], "catalog:ISO4014-M12x1.75")
        self.assertEqual(payload["provenance"]["bolt.yield_strength"], "class:8.8")
        self.assertEqual(payload["provenance"]["plates[1].youngs_modulus"], "material:S355J0")

    def test_numeric_strings_and_blank_optionals(self) -> None:
        payload = default_input_json()
        payload["bolt"]["length"] = "70,0"
        payload["bolt"]["thread_length"] = ""
        item = parse_general_input(payload)
        self.assertEqual(item.bolt.length, 70.0)
        self.assertIsNone(item.bolt.thread_length)

    def test_a2_90_requires_product_specific_shear_ratio(self) -> None:
        payload = default_input_json()
        payload["bolt"].update(property_class="A2-90", shear_ratio=None)
        with self.assertRaises(InputValidationError) as raised:
            parse_general_input(payload)
        error = next(error for error in raised.exception.errors if error.path == "bolt.shear_ratio")
        self.assertIn("A2-90", error.message)
        self.assertIn("实际产品", error.message)
        payload["provenance"] = {}
        payload["bolt"]["shear_ratio"] = 0.7
        self.assertEqual(parse_general_input(payload).bolt.shear_ratio, 0.7)
        del payload["bolt"]["shear_ratio"]
        self.assertIn("bolt.shear_ratio", error_paths(payload))

    def test_a2_rejects_stale_strength_and_shear_provenance(self) -> None:
        payload = default_input_json()
        payload["bolt"]["property_class"] = "A2-70"
        self.assertTrue({"bolt.yield_strength", "bolt.tensile_strength", "bolt.shear_ratio"} <= error_paths(payload))
        payload["bolt"]["property_class"] = "A2-90"
        self.assertIn("bolt.shear_ratio", error_paths(payload))
        payload["bolt"]["property_class"] = "a2-90"
        payload["bolt"]["shear_ratio"] = None
        self.assertIn("bolt.shear_ratio", error_paths(payload))
        payload["bolt"]["property_class"] = "A2-70"
        del payload["bolt"]["shear_ratio"]
        self.assertIn("bolt.shear_ratio", error_paths(payload))

    def test_a2_rejects_mismatched_catalog_variant_sources(self) -> None:
        payload = default_input_json()
        payload["bolt"]["property_class"] = "A2-70"
        variant = "ISO4014-M12x1.75"
        for path, value in engineering_data.bolt_catalog_values(variant, 70, "A2-70").items():
            section, name = path.split(".")
            payload[section][name] = value
        payload["provenance"].update(engineering_data.catalog_value_sources(variant, "A2-70"))
        payload["bolt"]["catalog_variant_id"] = "ISO4017-M12x1.75"
        self.assertIn("bolt.catalog_variant_id", error_paths(payload))

    def test_fatigue_amplitude_is_optional_and_must_be_positive(self) -> None:
        payload = default_input_json()
        self.assertIsNone(parse_general_input(payload).bolt.fatigue_strength_amplitude)
        for invalid in (0, -1, True, "nan", float("inf")):
            with self.subTest(value=invalid):
                payload["bolt"]["fatigue_strength_amplitude"] = invalid
                self.assertIn("bolt.fatigue_strength_amplitude", error_paths(payload))
        payload["bolt"]["fatigue_strength_amplitude"] = "55.5"
        self.assertEqual(parse_general_input(payload).bolt.fatigue_strength_amplitude, 55.5)

    def test_field_errors_report_paths(self) -> None:
        payload = default_input_json()
        payload["bolt"]["d"] = "abc"
        payload["bolt"]["thread_friction"] = 2
        payload["load"]["slip_interfaces"] = 1.5
        payload["joint"]["type"] = "XYZ"
        payload["plates"][1]["thickness"] = -1
        payload["nut"]["standard_adequate"] = "yes"
        paths = error_paths(payload)
        self.assertTrue({
            "bolt.d",
            "bolt.thread_friction",
            "load.slip_interfaces",
            "joint.type",
            "plates[1].thickness",
            "nut.standard_adequate",
        } <= paths)

    def test_rejects_non_finite_and_boolean_numbers(self) -> None:
        payload = default_input_json()
        payload["bolt"]["d"] = float("inf")
        payload["bolt"]["pitch"] = True
        self.assertTrue({"bolt.d", "bolt.pitch"} <= error_paths(payload))

    def test_layer_count_limits(self) -> None:
        payload = default_input_json()
        payload["plates"] = []
        self.assertIn("plates", error_paths(payload))
        payload["plates"] = [default_layer(i) for i in range(MAX_LAYERS + 1)]
        self.assertIn("plates", error_paths(payload))

    def test_schema_and_provenance_are_checked(self) -> None:
        payload = default_input_json()
        payload["schema"] = "other"
        payload["provenance"] = {"bolt.d": 3}
        self.assertTrue({"schema", "provenance"} <= error_paths(payload))
        self.assertIn("", error_paths([]))

    def test_relation_rules(self) -> None:
        cases = {
            "bolt.d2": lambda p: p["bolt"].update(d2=13.0),
            "bolt.stress_area": lambda p: p["bolt"].update(stress_area=40.0),
            "bolt.yield_strength": lambda p: p["bolt"].update(yield_strength=900.0),
            "bolt.shank_diameter": lambda p: p["bolt"].update(shank_diameter=13.0),
            "bolt.bore_diameter": lambda p: p["bolt"].update(bore_diameter=8.0),
            "joint.hole_diameter": lambda p: p["joint"].update(hole_diameter=11.0),
            "bolt.head_bearing_diameter": lambda p: p["bolt"].update(head_bearing_diameter=13.0),
            "joint.outer_diameter": lambda p: p["joint"].update(outer_diameter=13.0),
            "load.axial_min": lambda p: p["load"].update(axial_min=20000.0),
            "load.friction_radius": lambda p: p["load"].update(torque=10.0),
            "load.sealing_area": lambda p: p["load"].update(sealing_pressure=1.0),
            "bolt.length": lambda p: p["bolt"].update(length=40.0, thread_length=20.0),
            "bolt.thread_length": lambda p: p["bolt"].update(thread_length=20.0),
        }
        for path, mutate in cases.items():
            with self.subTest(path=path):
                payload = default_input_json()
                mutate(payload)
                self.assertIn(path, error_paths(payload))

    def test_tapped_joint_rules(self) -> None:
        payload = default_input_json()
        payload["joint"]["type"] = "ESV"
        payload["assembly"]["tighten_side"] = "nut"
        payload["tapped"]["engagement_length"] = 50.0
        self.assertTrue({"assembly.tighten_side", "tapped.engagement_length"} <= error_paths(payload))
        payload = default_input_json()
        payload["joint"]["type"] = "ESV"
        payload["bolt"]["thread_length"] = None
        item = parse_general_input(payload)
        self.assertFalse(item.is_through_bolt)

    def test_input_is_not_mutated(self) -> None:
        payload = default_input_json()
        snapshot = copy.deepcopy(payload)
        parse_general_input(payload)
        self.assertEqual(payload, snapshot)


class GeneralSchemaTests(unittest.TestCase):
    def test_schema_is_json_serialisable_and_complete(self) -> None:
        schema = json.loads(json.dumps(field_schema_json(), ensure_ascii=False))
        self.assertEqual(schema["schema"], SCHEMA_ID)
        self.assertEqual(len(schema["fields"]), len(FIELD_SPECS))
        self.assertEqual(len(schema["layer_fields"]), len(LAYER_SPECS))
        groups = {field["group"] for field in schema["fields"]}
        self.assertEqual(groups, {"bolt", "plates", "load", "assembly"})
        joint_type = next(field for field in schema["fields"] if field["path"] == "joint.type")
        self.assertEqual([choice[0] for choice in joint_type["choices"]], ["DSV", "ESV"])

    def test_layer_fields_own_plate_properties(self) -> None:
        names = {spec.name for spec in LAYER_SPECS}
        self.assertTrue({"thickness", "roughness_rz", "interface_friction", "material_id"} <= names)
        self.assertNotIn("bearing_friction", names)
        bolt_paths = {spec.path for spec in FIELD_SPECS if spec.path.startswith("bolt.")}
        self.assertIn("bolt.thread_friction", bolt_paths)
        self.assertIn("bolt.bearing_friction", bolt_paths)
        payload = default_input_json()
        payload["bolt"].update(thread_friction=0.12, bearing_friction=0.10)
        item = parse_general_input(payload)
        self.assertEqual(item.bolt.bearing_friction, 0.10)
        self.assertEqual(item.bolt.thread_friction, 0.12)
        self.assertEqual(parse_general_input(item.to_json()), item)

    def test_bearing_friction_validates_independently(self):
        for invalid in (0, 2, float("nan"), True, "abc"):
            payload = default_input_json()
            payload["bolt"]["bearing_friction"] = invalid
            self.assertIn("bolt.bearing_friction", error_paths(payload))


class ProvenanceTests(unittest.TestCase):
    def test_source_is_provisional(self) -> None:
        self.assertFalse(engineering_data.source_is_provisional("catalog:ISO4014-M12x1.75"))
        self.assertFalse(engineering_data.source_is_provisional("material:S355J0"))
        self.assertFalse(engineering_data.source_is_provisional("table:embedding_um"))
        self.assertFalse(engineering_data.source_is_provisional("class:8.8"))
        self.assertTrue(engineering_data.source_is_provisional("catalog:unknown"))
        self.assertTrue(engineering_data.source_is_provisional("default:anything"))
        self.assertFalse(engineering_data.source_is_provisional("user"))
        self.assertFalse(engineering_data.source_is_provisional("user:measured"))

    def test_value_source_helpers(self) -> None:
        catalog = engineering_data.catalog_value_sources("ISO4017-M8x1.25", "12.9")
        self.assertEqual(catalog["nut.height"], "catalog:ISO4017-M8x1.25")
        self.assertEqual(catalog["bolt.tensile_strength"], "class:12.9")
        self.assertEqual(catalog["bolt.shear_ratio"], "table:shear_strength_ratio")
        self.assertEqual(
            set(engineering_data.material_value_sources("Cq45", "tapped")),
            {"tapped.youngs_modulus", "tapped.tensile_strength", "tapped.shear_strength"},
        )
        self.assertEqual(
            set(engineering_data.material_value_sources("GJL-250", "plates[3]")),
            {"plates[3].youngs_modulus", "plates[3].limiting_surface_pressure"},
        )


if __name__ == "__main__":
    unittest.main()
