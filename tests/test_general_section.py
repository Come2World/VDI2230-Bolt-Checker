import unittest

from test_general_engine import b1_payload, b2_payload, b3_payload
from vdi2230.calculations.general import calculate_general
from vdi2230.domain.general_inputs import default_input_json, default_layer, parse_general_input
from vdi2230.infrastructure.general_section import general_section_shapes


def shapes_for(payload, width=640, height=560):
    item = parse_general_input(payload)
    result = calculate_general(item)
    return item, result, general_section_shapes(item, result.metrics, width, height)


def roles(shapes):
    return {shape.role for shape in shapes}


class GeneralSectionTests(unittest.TestCase):
    def test_through_bolt_has_nut_and_no_tapped_part(self) -> None:
        _, _, shapes = shapes_for(default_input_json())
        self.assertIn("nut", roles(shapes))
        self.assertIn("label-nut", roles(shapes))
        self.assertNotIn("tapped", roles(shapes))

    def test_tapped_joint_has_tapped_part_and_no_nut(self) -> None:
        _, _, shapes = shapes_for(b1_payload())
        self.assertIn("tapped", roles(shapes))
        self.assertNotIn("nut", roles(shapes))

    def test_every_layer_is_drawn_and_labelled(self) -> None:
        payload = default_input_json()
        payload["plates"] = [default_layer(i) for i in range(4)]
        for layer in payload["plates"]:
            layer["thickness"] = 12.0
        _, _, shapes = shapes_for(payload)
        for index in range(4):
            rects = [s for s in shapes if s.role == f"plate-{index}" and s.kind == "rect"]
            texts = [s for s in shapes if s.role == f"plate-{index}" and s.kind == "text"]
            self.assertEqual(len(rects), 2)
            self.assertEqual(len(texts), 2)

    def test_slip_interfaces_follow_joint_type(self) -> None:
        _, _, dsv = shapes_for(b2_payload())
        _, _, esv = shapes_for(b3_payload())
        self.assertEqual({r for r in roles(dsv) if r.startswith("interface-")}, {"interface-0"})
        self.assertEqual(
            {r for r in roles(esv) if r.startswith("interface-")},
            {"interface-0", "interface-1", "interface-2"},
        )

    def test_plates_stack_to_clamp_length(self) -> None:
        item, result, shapes = shapes_for(b3_payload())
        tops = sorted({s.points[1] for s in shapes if s.role.startswith("plate-") and s.kind == "rect"})
        bottoms = sorted({s.points[3] for s in shapes if s.role.startswith("plate-") and s.kind == "rect"})
        self.assertEqual(len(tops), len(item.plates))
        self.assertEqual(tops[1:], bottoms[:-1])
        scale = (bottoms[-1] - tops[0]) / result.metrics.clamp_length
        for layer, top, bottom in zip(item.plates, tops, bottoms):
            self.assertAlmostEqual((bottom - top) / scale, layer.thickness, places=6)

    def test_cone_stays_inside_outer_diameter_and_clamp(self) -> None:
        _, _, shapes = shapes_for(default_input_json())
        plates = [s for s in shapes if s.role.startswith("plate-") and s.kind == "rect"]
        left = min(s.points[0] for s in plates)
        right = max(s.points[2] for s in plates)
        top = min(s.points[1] for s in plates)
        bottom = max(s.points[3] for s in plates)
        cones = [s for s in shapes if s.role == "cone"]
        self.assertEqual(len(cones), 2)
        for cone in cones:
            self.assertEqual(cone.kind, "polygon")
            for x in cone.points[0::2]:
                self.assertGreaterEqual(x, left - 1e-6)
                self.assertLessEqual(x, right + 1e-6)
            for y in cone.points[1::2]:
                self.assertGreaterEqual(y, top - 1e-6)
                self.assertLessEqual(y, bottom + 1e-6)

    def test_hollow_bolt_draws_bore(self) -> None:
        _, _, solid = shapes_for(default_input_json())
        _, _, hollow = shapes_for(b3_payload())
        self.assertNotIn("bolt-bore", roles(solid))
        self.assertIn("bolt-bore", roles(hollow))

    def test_full_thread_has_no_shank(self) -> None:
        payload = default_input_json()
        payload["bolt"]["thread_length"] = None
        _, _, shapes = shapes_for(payload)
        self.assertNotIn("bolt-shank", roles(shapes))
        self.assertIn("bolt-thread", roles(shapes))

    def test_shapes_fit_view_and_labels_do_not_overlap(self) -> None:
        payload = default_input_json()
        payload["plates"] = [default_layer(i) for i in range(10)]
        for layer in payload["plates"]:
            layer["thickness"] = 3.0
        payload["bolt"]["thread_length"] = None
        for width, height in ((640, 560), (420, 320), (1200, 900)):
            with self.subTest(size=(width, height)):
                _, _, shapes = shapes_for(payload, width, height)
                for shape in shapes:
                    for x in shape.points[0::2]:
                        self.assertTrue(0 <= x <= width, shape)
                    for y in shape.points[1::2]:
                        self.assertTrue(0 <= y <= height, shape)
                labels = sorted(
                    (s for s in shapes if s.kind == "text" and s.role != "title" and not s.role.startswith("dim-")),
                    key=lambda s: s.points[1],
                )
                self.assertEqual(len({s.role for s in labels}), 12)
                for upper, lower in zip(labels, labels[1:]):
                    self.assertGreaterEqual(lower.points[1] - upper.points[1], max(upper.size, lower.size) - 1e-6)

    def test_crowded_view_uses_single_line_labels(self) -> None:
        payload = default_input_json()
        payload["plates"] = [default_layer(i) for i in range(10)]
        for layer in payload["plates"]:
            layer["thickness"] = 3.0
        payload["bolt"]["thread_length"] = None
        _, _, roomy = shapes_for(payload, 640, 900)
        _, _, crowded = shapes_for(payload, 640, 300)
        self.assertEqual(len([s for s in roomy if s.role == "plate-9" and s.kind == "text"]), 2)
        compact = [s for s in crowded if s.role == "plate-9" and s.kind == "text"]
        self.assertEqual(len(compact), 1)
        self.assertIn("板 10", compact[0].text)
        self.assertIn("h 3", compact[0].text)

    def test_title_mentions_bolt_and_joint_type(self) -> None:
        _, _, shapes = shapes_for(default_input_json())
        title = next(s for s in shapes if s.role == "title")
        self.assertIn("DSV", title.text)
        self.assertIn("M12×1.75", title.text)
        self.assertIn("8.8", title.text)

    def test_rejects_view_out_of_range(self) -> None:
        item = parse_general_input(default_input_json())
        metrics = calculate_general(item).metrics
        with self.assertRaises(ValueError):
            general_section_shapes(item, metrics, 50, 400)


if __name__ == "__main__":
    unittest.main()
