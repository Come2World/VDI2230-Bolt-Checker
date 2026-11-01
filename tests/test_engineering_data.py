import math
import unittest

from vdi2230 import data


class PlateMaterialTests(unittest.TestCase):
    def test_table_a9_materials_are_unique_and_physically_plausible(self):
        records = data.materials()
        self.assertEqual(len(records), 36)
        self.assertEqual(len({row.material_id for row in records}), len(records))
        for row in records:
            self.assertGreater(row.youngs_modulus, 40_000)
            self.assertGreater(row.limiting_surface_pressure, 0)
            self.assertGreaterEqual(row.tensile_strength, row.yield_strength)
            self.assertEqual(row.verification_status, "accepted_baseline")

    def test_known_table_a9_rows(self):
        steel = data.material("S235JRG1")
        self.assertEqual(
            (steel.youngs_modulus, steel.tensile_strength, steel.limiting_surface_pressure),
            (205_000.0, 340.0, 490.0),
        )
        self.assertEqual(data.material("S355J0").name, "S355 J0")
        self.assertEqual(data.material_values("GJL-250")["youngs_modulus"], 110_000.0)
        with self.assertRaises(KeyError):
            data.material("unknown")


class VdiTableTests(unittest.TestCase):
    def test_bundled_tables_and_derived_bolt_variants_are_accepted(self):
        for row in data.bolt_variants():
            self.assertEqual(row.verification_status, "accepted_baseline")
            self.assertFalse(data.source_is_provisional(f"catalog:{row.variant_id}"))
        for key in ("load_introduction_factor_n", "embedding_um", "shear_strength_ratio",
                    "friction_classes", "tightening_factor_alpha_a"):
            self.assertEqual(data.table_status(key), "accepted_baseline")
            self.assertFalse(data.source_is_provisional(f"table:{key}"))
        self.assertEqual(data.catalog_summary()["status"], "accepted_baseline")

    def test_table_2_grid_points_and_bilinear_interpolation(self):
        self.assertEqual(data.load_introduction_factor("SV1", 0, 0), 0.7)
        self.assertEqual(data.load_introduction_factor("SV6", 0.3, 0.5), 0.03)
        self.assertTrue(math.isclose(
            data.load_introduction_factor("SV2", 0.05, 0.2), 0.3325,
        ))
        self.assertEqual(data.load_introduction_factor("SV3", 2.0, 9.0), 0.04)
        with self.assertRaises(KeyError):
            data.load_introduction_factor("SV7", 0, 0)
        with self.assertRaises(ValueError):
            data.load_introduction_factor("SV1", -0.1, 0)

    def test_table_5_embedding_rows(self):
        self.assertEqual(data.embedding_values(5, shear=False), (3.0, 2.5, 1.5))
        self.assertEqual(data.embedding_values(16, shear=False), (3.0, 3.0, 2.0))
        self.assertEqual(data.embedding_values(16, shear=True), (3.0, 4.5, 2.5))
        with self.assertRaises(ValueError):
            data.embedding_values(160, shear=False)

    def test_table_7_and_presets(self):
        self.assertEqual(data.shear_strength_ratio("10.9"), 0.62)
        self.assertEqual(data.shear_strength_ratio("8.8"), 0.65)
        self.assertEqual(data.shear_strength_ratio("A2-70"), 0.72)
        self.assertEqual(data.shear_strength_ratio("A2-80"), 0.68)
        self.assertIsNone(data.shear_strength_ratio("A2-90"))
        self.assertIsNone(data.shear_strength_ratio("unknown"))
        self.assertEqual(len(data.tightening_factor_presets()), 4)
        self.assertEqual(
            [row["class"] for row in data.friction_classes()],
            ["A", "B", "C", "D", "E"],
        )


class CatalogLookupTests(unittest.TestCase):
    def test_geometry_lookup_is_shared_by_all_strength_classes(self):
        geometry = data.bolt_geometry_values("ISO4762-M12x1.75", 70)
        self.assertNotIn("bolt.yield_strength", geometry)
        self.assertNotIn("bolt.youngs_modulus", geometry)
        for grade in ("8.8", "10.9", "12.9", "A2-70", "A2-80", "A2-90"):
            catalog = data.bolt_catalog_values("ISO4762-M12x1.75", 70, grade)
            self.assertEqual({path: catalog[path] for path in geometry}, geometry)

    def test_variant_values_are_catalog_first(self):
        values = data.bolt_catalog_values("ISO4014-M12x1.75", 60, "10.9")
        self.assertEqual(values["bolt.d"], 12.0)
        self.assertEqual(values["bolt.pitch"], 1.75)
        self.assertEqual(values["bolt.thread_length"], 30.0)
        self.assertEqual(values["bolt.yield_strength"], 940.0)
        self.assertEqual(values["bolt.shear_ratio"], 0.62)
        self.assertEqual(values["joint.hole_diameter"], 13.5)
        self.assertEqual(values["nut.width_across_flats"], 18.0)
        self.assertEqual(
            set(data.catalog_value_sources("ISO4014-M12x1.75", "10.9")),
            set(values),
        )
        self.assertEqual(values["bolt.head_type"], "hex")
        self.assertEqual(values["bolt.head_width_across_flats"], 18.0)
        self.assertIsNone(values["bolt.head_diameter"])
        self.assertEqual(
            data.bolt_catalog_values("ISO4017-M12x1.75", 60, "8.8")["bolt.thread_length"],
            None,
        )

    def test_iso4014_thread_length_selects_b_by_length(self):
        variant = data.bolt_variant("ISO4014-M12x1.75")
        self.assertEqual(variant.thread_length_for(125), variant.thread_lengths[0])
        self.assertEqual(variant.thread_length_for(150), variant.thread_lengths[1])

    def test_iso4762_socket_values_use_own_dw_and_hex_nut(self):
        values = data.bolt_catalog_values("ISO4762-M12x1.75", 60, "12.9")
        self.assertEqual(values["bolt.head_type"], "socket")
        self.assertEqual(values["bolt.head_bearing_diameter"], 17.23)
        self.assertEqual(values["bolt.head_height"], 12.0)
        self.assertEqual(values["bolt.head_diameter"], 18.0)
        self.assertEqual(values["bolt.socket_size"], 10.0)
        self.assertEqual(values["bolt.socket_depth"], 6.0)
        self.assertIsNone(values["bolt.head_width_across_flats"])
        # The nut stays an ISO 4032 hexagon nut, never the 10 mm socket key size.
        self.assertEqual(values["nut.width_across_flats"], 18.0)
        self.assertEqual(values["nut.bearing_diameter"], data.bolt_catalog_values("ISO4014-M12x1.75", 60, "12.9")["nut.bearing_diameter"])

    def test_iso4762_thread_length_is_full_up_to_tabulated_limit(self):
        variant = data.bolt_variant("ISO4762-M12x1.75")
        self.assertIsNone(variant.thread_length_for(50))
        self.assertEqual(variant.thread_length_for(55), 36.0)
        self.assertEqual(variant.thread_length_for(200), 36.0)

    def test_property_class_ranges_and_summary(self):
        self.assertEqual(data.property_class_record("8.8", 16).tensile_strength, 800)
        self.assertEqual(data.property_class_record("8.8", 20).tensile_strength, 830)
        with self.assertRaises(KeyError):
            data.property_class_record("8.8", 36)
        summary = data.catalog_summary()
        self.assertEqual(summary["property_classes"], ["8.8", "10.9", "12.9", "A2-70", "A2-80", "A2-90"])
        self.assertEqual(len(summary["bolts"]), 33)
        self.assertEqual(sum(bolt["head_type"] == "socket" for bolt in summary["bolts"]), 9)
        self.assertEqual(len(summary["materials"]), 36)

    def test_a2_catalog_values_and_sources_cover_catalog_sizes(self):
        for variant in data.bolt_variants():
            for grade, tensile, proof, ratio in (
                ("A2-70", 700, 450, 0.72),
                ("A2-80", 800, 600, 0.68),
                ("A2-90", 900, 700, None),
            ):
                with self.subTest(variant=variant.variant_id, grade=grade):
                    values = data.bolt_catalog_values(variant.variant_id, 70, grade)
                    sources = data.catalog_value_sources(variant.variant_id, grade)
                    self.assertEqual(values["bolt.tensile_strength"], tensile)
                    self.assertEqual(values["bolt.yield_strength"], proof)
                    self.assertEqual(values["bolt.shear_ratio"], ratio)
                    self.assertEqual(values["bolt.youngs_modulus"], data.material("X5CrNi18-10").youngs_modulus)
                    self.assertEqual(sources["bolt.youngs_modulus"], "material:X5CrNi18-10")
                    self.assertEqual(sources["bolt.tensile_strength"], f"class:{grade}")
                    if ratio is None:
                        self.assertNotIn("bolt.shear_ratio", sources)
                    else:
                        self.assertEqual(sources["bolt.shear_ratio"], "table:shear_strength_ratio")
                    self.assertFalse(data.source_is_provisional(f"class:{grade}"))
        with self.assertRaises(KeyError):
            data.property_class_record("A2-70", 31)
        reference = data.property_class_record("A2-90", 30)
        self.assertEqual(reference.source_ids, ("tomita_a2_90_supplier",))
        self.assertIn("supplier", reference.applicability_note)


if __name__ == "__main__":
    unittest.main()
