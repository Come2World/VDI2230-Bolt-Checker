import json
import math
import unittest
from pathlib import Path


CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "vdi2230"
    / "data"
    / "bolt_catalog"
    / "catalog.json"
)


class BoltCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    def test_scope_and_thread_size_references_are_complete(self):
        sizes = self.catalog["thread_sizes"]
        expected = [6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 27, 30]
        self.assertEqual(
            [row["nominal_diameter_mm"] for row in sizes],
            expected,
        )
        self.assertEqual(
            len({row["size_id"] for row in sizes}),
            len(sizes),
        )
        for row in sizes:
            self.assertGreater(row["pitch_mm"], 0)
            self.assertGreater(row["pitch_diameter_d2_mm"], 0)
            self.assertGreater(row["external_thread_minor_diameter_d3_mm"], 0)
            self.assertGreater(row["tensile_stress_area_as_mm2"], 0)
            self.assertIsNone(row["area_a0_mm2"])
            self.assertEqual(row["verification_status"], "provisional")

    def test_bolt_variants_have_uniform_shape_and_valid_thread_fields(self):
        variants = self.catalog["bolt_geometries"]
        self.assertEqual(len(variants), 24)
        self.assertEqual(
            len({row["variant_id"] for row in variants}),
            len(variants),
        )
        thread_size_ids = {
            row["size_id"] for row in self.catalog["thread_sizes"]
        }
        expected_keys = set(variants[0])

        for row in variants:
            self.assertEqual(set(row), expected_keys)
            self.assertIn(row["thread_size_id"], thread_size_ids)
            self.assertIn(row["standard"], {"ISO 4014", "ISO 4017"})
            self.assertGreater(row["head_height_k_mm"], 0)
            self.assertGreater(row["width_across_flats_s_mm"], 0)
            self.assertIn(row["verification_status"], {
                "provisional",
                "provisional_conflict",
            })
            if row["standard"] == "ISO 4014":
                self.assertEqual(row["threading"], "partial")
                self.assertIsNone(row["unthreaded_shank_length_h_mm"])
                self.assertGreater(row["thread_length_b1_mm"], 0)
                self.assertGreater(row["thread_length_b2_mm"], 0)
            else:
                self.assertEqual(row["threading"], "full")
                self.assertIsNone(row["thread_length_b1_mm"])
                self.assertIsNone(row["thread_length_b2_mm"])
                self.assertGreater(row["unthreaded_shank_length_h_mm"], 0)

    def test_provisional_values_are_usable_but_force_review(self):
        policy = self.catalog["selection_policy"]
        self.assertTrue(policy["provisional_values_are_calculation_eligible"])
        self.assertTrue(policy["provisional_values_force_review_status"])

    def test_property_data_and_length_candidates_are_not_authoritative(self):
        classes = self.catalog["property_class_records"]
        self.assertEqual(
            {row["property_class"] for row in classes},
            {"8.8", "10.9", "12.9"},
        )
        for row in classes:
            self.assertTrue(row["calculation_eligible"])
            self.assertTrue(row["requires_review_warning"])
            self.assertEqual(
                row["verification_status"],
                "secondary_reference_only",
            )
            self.assertIsInstance(row["diameter_min_inclusive"], bool)
            self.assertIsInstance(row["diameter_max_inclusive"], bool)

        class_88 = [row for row in classes if row["property_class"] == "8.8"]
        at_16 = [
            row for row in class_88
            if (
                row["diameter_min_mm"] < 16
                or (
                    row["diameter_min_mm"] == 16
                    and row["diameter_min_inclusive"]
                )
            )
            and (
                row["diameter_max_mm"] > 16
                or (
                    row["diameter_max_mm"] == 16
                    and row["diameter_max_inclusive"]
                )
            )
        ]
        self.assertEqual(len(at_16), 1)
        self.assertEqual(at_16[0]["tensile_strength_min_mpa"], 800)

        length_catalog = self.catalog["length_catalog"]
        lengths = length_catalog["candidate_nominal_lengths_mm"]
        self.assertEqual(lengths, sorted(set(lengths)))
        self.assertEqual(
            length_catalog["verification_status"],
            "not_approved_for_standard_auto_selection",
        )

    def test_catalog_source_references_and_derivation_values(self):
        source_ids = {
            row["source_id"] for row in self.catalog["sources"]
        }
        for variant in self.catalog["bolt_geometries"]:
            self.assertTrue(set(variant["source_ids"]) <= source_ids)
        for joint in self.catalog["joint_dimension_records"]:
            self.assertTrue(set(joint["source_ids"]) <= source_ids)

        for row in self.catalog["thread_sizes"]:
            d = row["nominal_diameter_mm"]
            pitch = row["pitch_mm"]
            self.assertTrue(
                math.isclose(
                    row["pitch_diameter_d2_mm"],
                    d - 0.64951905 * pitch,
                    abs_tol=0.000001,
                )
            )
            self.assertTrue(
                math.isclose(
                    row["external_thread_minor_diameter_d3_mm"],
                    d - 1.226869 * pitch,
                    abs_tol=0.000001,
                )
            )

    def test_joint_dimension_records_cover_every_size_consistently(self):
        sizes = {
            row["size_id"]: row["nominal_diameter_mm"]
            for row in self.catalog["thread_sizes"]
        }
        joints = self.catalog["joint_dimension_records"]
        self.assertEqual([row["thread_size_id"] for row in joints], list(sizes))
        for row in joints:
            d = row["nominal_diameter_mm"]
            self.assertEqual(d, sizes[row["thread_size_id"]])
            self.assertLess(d, row["clearance_hole_fine_mm"])
            self.assertLess(
                row["clearance_hole_fine_mm"],
                row["clearance_hole_medium_mm"],
            )
            self.assertLess(
                row["clearance_hole_medium_mm"],
                row["clearance_hole_coarse_mm"],
            )
            self.assertGreater(
                row["head_bearing_diameter_dw_min_mm"],
                row["clearance_hole_coarse_mm"],
            )
            self.assertGreater(
                row["nut_iso4032_bearing_diameter_dw_min_mm"],
                row["clearance_hole_coarse_mm"],
            )
            self.assertGreater(row["nut_iso4032_height_m_max_mm"], 0.75 * d)
            self.assertEqual(row["verification_status"], "provisional")


if __name__ == "__main__":
    unittest.main()
