import unittest
from dataclasses import replace

from vdi2230.domain.section import SectionGeometry, section_primitives


class SectionDrawingTests(unittest.TestCase):
    def setUp(self):
        self.geometry = SectionGeometry(
            outer_diameter_mm=80,
            hole_diameter_mm=13.5,
            head_diameter_mm=18,
            head_height_mm=10,
            shank_diameter_mm=12,
            threaded_diameter_mm=9.85,
            shank_length_mm=60,
            clamp_layer_thicknesses_mm=(20, 22),
            threaded_length_mm=18,
            nut_height_mm=0,
        )

    def test_section_contains_layers_and_fastener(self):
        primitives = section_primitives(600, 500, self.geometry)
        rectangles = [item for item in primitives if item.kind == "rectangle"]
        labels = [item.text for item in primitives if item.kind == "text"]
        self.assertGreaterEqual(len(rectangles), 5)
        self.assertIn("Layer 1: 20 mm", labels)
        self.assertIn("Layer 2: 22 mm", labels)

    def test_multi_bolt_and_eccentric_features_are_labeled(self):
        geometry = replace(
            self.geometry,
            bolt_count=15,
            pitch_circle_diameter_mm=175,
            load_offset_mm=15.5,
        )
        primitives = section_primitives(600, 500, geometry)
        labels = [item.text for item in primitives if item.kind == "text"]
        self.assertTrue(any("15 bolts" in label for label in labels))
        self.assertTrue(any("Load offset" in label for label in labels))

    def test_invalid_geometry_is_rejected(self):
        invalid = SectionGeometry(
            outer_diameter_mm=20,
            hole_diameter_mm=22,
            head_diameter_mm=18,
            head_height_mm=10,
            shank_diameter_mm=12,
            threaded_diameter_mm=9,
            shank_length_mm=40,
            clamp_layer_thicknesses_mm=(10,),
        )
        with self.assertRaisesRegex(ValueError, "hole diameter"):
            section_primitives(500, 400, invalid)

    def test_invalid_multibolt_count_is_rejected(self):
        geometry = replace(self.geometry, bolt_count=1.5)
        with self.assertRaisesRegex(ValueError, "bolt_count"):
            section_primitives(500, 400, geometry)

    def test_reduced_shank_and_hollow_bore_are_drawn_from_dimensions(self):
        geometry = replace(
            self.geometry,
            neck_diameter_mm=5.82,
            neck_length_mm=15,
            hollow_diameter_mm=4,
        )
        primitives = section_primitives(600, 500, geometry)
        rectangles = [item for item in primitives if item.kind == "rectangle"]
        self.assertEqual(len(rectangles), 9)

    def test_external_thread_can_be_larger_than_hollow_shank(self):
        geometry = replace(
            self.geometry,
            shank_diameter_mm=24,
            threaded_diameter_mm=27,
            hollow_diameter_mm=16,
        )
        primitives = section_primitives(600, 500, geometry)
        rectangles = [item for item in primitives if item.kind == "rectangle"]
        self.assertTrue(rectangles)

    def test_large_eccentricity_stays_inside_the_viewport(self):
        geometry = replace(self.geometry, load_offset_mm=500)
        primitives = section_primitives(600, 500, geometry)
        load_arrow = next(
            item
            for item in primitives
            if item.kind == "line" and item.outline == "#c0392b"
        )
        self.assertLessEqual(max(load_arrow.coordinates[::2]), 564)


if __name__ == "__main__":
    unittest.main()
