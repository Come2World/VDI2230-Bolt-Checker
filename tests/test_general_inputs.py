import copy
import json
import unittest

from vdi2230 import data as engineering_data
from vdi2230.domain.general_inputs import (
    FIELD_SPECS,
    LAYER_SPECS,
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
    def test_default_round_trip(self) -> None:
        item = parse_general_input(default_input_json())
        self.assertIsInstance(item, GeneralInput)
        self.assertEqual(len(item.plates), 2)
        self.assertEqual(item.clamp_length, 40.0)
        self.assertTrue(item.is_through_bolt)
        again = GeneralInput.from_json(json.loads(json.dumps(item.to_json())))
        self.assertEqual(again, item)

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
        item = parse_general_input(default_input_json())
        self.assertEqual(item.bolt.bearing_friction, item.bolt.thread_friction)


class ProvenanceTests(unittest.TestCase):
    def test_source_is_provisional(self) -> None:
        self.assertTrue(engineering_data.source_is_provisional("catalog:ISO4014-M12x1.75"))
        self.assertTrue(engineering_data.source_is_provisional("material:S355J0"))
        self.assertTrue(engineering_data.source_is_provisional("table:embedding_um"))
        self.assertTrue(engineering_data.source_is_provisional("class:8.8"))
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
