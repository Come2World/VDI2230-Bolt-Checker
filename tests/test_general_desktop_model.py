import math
import unittest

from vdi2230.infrastructure.general_section import Shape
from vdi2230.ui.general_model import (
    CATALOG_PATHS,
    GeneralFormModel,
    canvas_item,
    coerce,
    entry_text,
    fmt,
    plate_index,
    relevant,
    subsection_of,
)

FLOAT = {"kind": "float"}


class FormattingTests(unittest.TestCase):
    def test_fmt_uses_four_significant_digits(self):
        self.assertEqual(fmt(None), "—")
        self.assertEqual(fmt(math.nan), "—")
        self.assertEqual(fmt(0), "0")
        self.assertEqual(fmt(1.155234), "1.155")
        self.assertEqual(fmt(43109.4), "43109")
        self.assertEqual(fmt(2.5e-4), "2.500e-04")
        self.assertEqual(fmt("DSV"), "DSV")

    def test_entry_text_is_lossless(self):
        self.assertEqual(entry_text(None), "")
        self.assertEqual(entry_text(12.0), "12")
        self.assertEqual(entry_text(10.863342), "10.863342")
        self.assertEqual(entry_text("S355J0"), "S355J0")

    def test_coerce_keeps_unparsable_text_for_validation(self):
        self.assertIsNone(coerce(FLOAT, "  "))
        self.assertEqual(coerce(FLOAT, "1,5"), 1.5)
        self.assertEqual(coerce(FLOAT, "abc"), "abc")
        self.assertEqual(coerce(FLOAT, "inf"), "inf")
        self.assertEqual(coerce({"kind": "text"}, " 板 1 "), "板 1")
        self.assertIs(coerce({"kind": "bool"}, 1), True)


class RelevanceTests(unittest.TestCase):
    def test_joint_type_and_modes_hide_fields(self):
        dsv = {"joint.type": "DSV", "load_introduction.mode": "manual", "embedding.mode": "table"}
        esv = {**dsv, "joint.type": "ESV"}
        self.assertTrue(relevant("nut.height", dsv))
        self.assertFalse(relevant("nut.height", esv))
        self.assertTrue(relevant("tapped.youngs_modulus", esv))
        self.assertFalse(relevant("tapped.youngs_modulus", dsv))
        self.assertTrue(relevant("load_introduction.n", dsv))
        self.assertFalse(relevant("load_introduction.joint_class", dsv))
        self.assertTrue(relevant("embedding.interface_count", dsv))
        self.assertFalse(relevant("embedding.fz_um", dsv))
        self.assertTrue(relevant("bolt.d", esv))

    def test_subsections_split_bolt_geometry_and_material(self):
        model = GeneralFormModel()
        self.assertEqual(subsection_of(model.specs["joint.type"]), "连接与目录")
        self.assertEqual(subsection_of(model.specs["bolt.d"]), "螺栓几何")
        self.assertEqual(subsection_of(model.specs["bolt.thread_friction"]), "螺栓材料与摩擦")
        self.assertEqual(subsection_of(model.specs["nut.height"]), "螺母（DSV）")


class CanvasItemTests(unittest.TestCase):
    def test_plate_rectangle_gets_selectable_tags(self):
        kind, points, options = canvas_item(Shape("rect", (1, 2, 3, 4), fill="#dde", stroke="#333", role="plate-2"))
        self.assertEqual((kind, points), ("rectangle", (1, 2, 3, 4)))
        self.assertEqual(options["tags"], ("plate-2", "plate"))
        self.assertEqual(plate_index(options["tags"]), 2)
        self.assertIsNone(plate_index(("bolt",)))

    def test_polygon_opacity_is_blended_with_white(self):
        _, _, options = canvas_item(Shape("polygon", (0, 0, 1, 0, 1, 1), fill="#000000", opacity=0.5, dash=True))
        self.assertEqual(options["fill"], "#808080")
        self.assertEqual(options["dash"], (4, 3))
        self.assertEqual(options["tags"], ())

    def test_text_maps_anchor_size_and_rotation(self):
        kind, points, options = canvas_item(Shape("text", (5, 6), text="lK 40", anchor="middle", size=10, rotate=-90))
        self.assertEqual((kind, points), ("text", (5, 6)))
        self.assertEqual(options["anchor"], "center")
        self.assertEqual(options["font"], ("Helvetica", -10))
        self.assertEqual(options["angle"], 90)

    def test_unknown_shape_kind_raises(self):
        with self.assertRaises(ValueError):
            canvas_item(Shape("circle", (0, 0)))


class GeneralFormModelTests(unittest.TestCase):
    def setUp(self):
        self.model = GeneralFormModel()

    def test_defaults_come_from_the_catalog(self):
        model = self.model
        self.assertEqual(len(model.layers), 2)
        self.assertEqual(model.selected, 0)
        self.assertEqual(model.values["bolt.catalog_variant_id"], "ISO4014-M12x1.75")
        self.assertEqual(model.values["bolt.d"], 12)
        self.assertEqual(model.source_for("bolt.d"), "catalog:ISO4014-M12x1.75")
        self.assertEqual(model.source_for("plates[0].youngs_modulus"), "material:S355J0")
        self.assertIsNone(model.source_for("plates[9].thickness"))
        self.assertEqual(model.label_for("plates[1].thickness"), "板层 2 · 厚度 h")

    def test_new_variant_overwrites_catalog_values(self):
        model = self.model
        model.set_value("bolt.head_bearing_diameter", 17.0)
        self.assertIsNone(model.set_value("bolt.catalog_variant_id", "ISO4014-M16x2.0"))
        self.assertEqual(model.values["bolt.d"], 16)
        self.assertNotEqual(model.values["bolt.head_bearing_diameter"], 17.0)
        self.assertEqual(model.source_for("bolt.head_bearing_diameter"), "catalog:ISO4014-M16x2.0")

    def test_property_class_updates_strength(self):
        self.model.set_value("bolt.property_class", "10.9")
        self.assertEqual(self.model.values["bolt.yield_strength"], 940)
        self.assertEqual(self.model.source_for("bolt.yield_strength"), "class:10.9")

    def test_length_change_keeps_user_overrides(self):
        model = self.model
        model.set_value("bolt.head_bearing_diameter", 17.0)
        model.set_value("bolt.length", 80.0)
        self.assertEqual(model.values["bolt.head_bearing_diameter"], 17.0)
        self.assertIsNone(model.source_for("bolt.head_bearing_diameter"))
        self.assertEqual(model.source_for("bolt.d2"), "catalog:ISO4014-M12x1.75")

    def test_unknown_catalog_combination_reports_message(self):
        message = self.model.set_value("bolt.catalog_variant_id", "ISO4014-M99x9")
        self.assertIn("目录中没有", message)
        with self.assertRaises(KeyError):
            self.model.set_value("bolt.unknown", 1)

    def test_material_selection_fills_plate_properties(self):
        model = self.model
        record = model.materials["42CrMo4"]
        model.set_layer_value(1, "material_id", "42CrMo4")
        layer = model.layers[1]
        self.assertEqual(layer.values["youngs_modulus"], record["youngs_modulus"])
        self.assertEqual(layer.values["limiting_surface_pressure"], record["limiting_surface_pressure"])
        self.assertEqual(model.source_for("plates[1].youngs_modulus"), "material:42CrMo4")
        model.set_layer_value(1, "youngs_modulus", 200000.0)
        self.assertIsNone(model.source_for("plates[1].youngs_modulus"))
        with self.assertRaises(KeyError):
            model.set_layer_value(0, "unknown", 1)

    def test_tapped_material_fills_tapped_part(self):
        record = self.model.materials["GJS-400"]
        self.model.set_value("tapped.material_id", "GJS-400")
        self.assertEqual(self.model.values["tapped.youngs_modulus"], record["youngs_modulus"])
        self.assertEqual(self.model.source_for("tapped.shear_strength"), "material:GJS-400")

    def test_add_remove_and_move_layers(self):
        model = self.model
        self.assertTrue(model.add_layer())
        self.assertEqual(model.selected, 1)
        self.assertEqual([model.layer_name(i) for i in range(3)], ["板 1", "板 3", "板 2"])
        self.assertEqual(model.layers[1].values["thickness"], model.layers[0].values["thickness"])
        self.assertEqual(model.layer_summary(1), "2. 板 3 · S355J0 · h 20")

        self.assertTrue(model.move_layer(1, 1))
        self.assertEqual(model.selected, 2)
        self.assertEqual(model.layer_name(2), "板 3")
        self.assertFalse(model.move_layer(2, 1))

        self.assertTrue(model.remove_layer(2))
        self.assertEqual(model.selected, 1)
        self.assertTrue(model.remove_layer(0))
        self.assertEqual(model.selected, 0)
        self.assertFalse(model.remove_layer(0))
        with self.assertRaises(IndexError):
            model.select_layer(5)

    def test_layer_count_is_limited(self):
        model = self.model
        while model.add_layer():
            pass
        self.assertEqual(len(model.layers), model.max_layers)

    def test_input_json_carries_layer_provenance(self):
        model = self.model
        model.add_layer()
        model.set_layer_value(2, "material_id", "E295")
        model.title = "  "
        item = model.to_input_json()
        self.assertEqual(item["title"], "通用螺栓连接")
        self.assertEqual(len(item["plates"]), 3)
        self.assertEqual(item["bolt"]["catalog_variant_id"], "ISO4014-M12x1.75")
        self.assertEqual(item["provenance"]["plates[2].youngs_modulus"], "material:E295")
        self.assertEqual(item["provenance"]["bolt.d"], "catalog:ISO4014-M12x1.75")

    def test_calculate_default_case_needs_confirmation(self):
        outcome = self.model.calculate()
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.result.verdict_label, "需确认 · 数据待核验")
        self.assertIn("bolt.d", self.model.provisional)
        self.assertIn("通用螺栓连接", outcome.report)
        self.assertIn("SF", {check.symbol for check in outcome.result.checks})

    def test_calculate_reports_field_errors(self):
        self.model.set_layer_value(0, "thickness", "abc")
        outcome = self.model.calculate()
        self.assertFalse(outcome.ok)
        self.assertIn("输入有误", outcome.error)
        self.assertEqual([error.path for error in outcome.field_errors], ["plates[0].thickness"])

    def test_catalog_paths_are_choice_fields(self):
        for path in CATALOG_PATHS:
            self.assertIn(path, self.model.specs)


if __name__ == "__main__":
    unittest.main()
