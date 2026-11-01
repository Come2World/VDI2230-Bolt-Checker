import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_general_engine import b1_payload, b3_payload
from vdi2230.calculations.general import calculate_general
from vdi2230.domain.general_inputs import InputValidationError, default_input_json, parse_general_input
from vdi2230.domain.models import ProjectSnapshot
from vdi2230.infrastructure.project_file import (
    load_general_project, save_general_project, save_project, write_text_atomic,
)


class GeneralProjectTests(unittest.TestCase):
    def test_all_inputs_sources_and_results_round_trip(self):
        washer = default_input_json()
        washer["head_washer"]["enabled"] = washer["nut_washer"]["enabled"] = True
        tapped = b1_payload()
        tapped["tapped"].update(hole_type="through", thickness=15.0, thread_depth=12.0)
        for payload in (default_input_json(), washer, tapped, b3_payload()):
            with self.subTest(joint=payload["joint"]["type"]), tempfile.TemporaryDirectory() as directory:
                item = parse_general_input(payload)
                before = calculate_general(item)
                path = Path(directory) / "project.json"
                save_general_project(path, item)
                loaded = load_general_project(path)
                after = calculate_general(loaded)
                self.assertEqual(loaded, item)
                self.assertEqual(after.result.values, before.result.values)
                self.assertEqual(after.checks, before.checks)
                self.assertEqual(after.metrics, before.metrics)
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(document["inputs"], item.to_json())
                self.assertNotIn("results", document)

    def test_invalid_files_and_other_case_projects_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            save_general_project(path, parse_general_input(default_input_json()))
            baseline = json.loads(path.read_text(encoding="utf-8"))
            for mutation in (
                {"format": "unknown"}, {"schema_version": 99}, {"case_id": "B1"},
                {"title": "different"}, {"inputs": []},
            ):
                with self.subTest(mutation=mutation):
                    path.write_text(json.dumps({**baseline, **mutation}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_general_project(path)
            inputs = default_input_json()
            inputs["bolt"]["d"] = -1
            path.write_text(json.dumps({**baseline, "inputs": inputs}), encoding="utf-8")
            with self.assertRaises(InputValidationError):
                load_general_project(path)
            for content in ('{"invalid":', "[]", '{"format": NaN}'):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_general_project(path)

    def test_legacy_general_inputs_migrate_on_load(self):
        payload = default_input_json()
        payload["schema"] = "vdi2230.general/3"
        payload["bolt"].pop("fatigue_strength_amplitude")
        for name in ("head_diameter", "socket_size", "socket_depth", "head_width_across_flats"):
            payload["bolt"].pop(name)
        for name in ("hole_type", "thickness", "hole_depth", "thread_depth"):
            payload["tapped"].pop(name)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.json"
            save_project(path, ProjectSnapshot(case_id="GENERAL", title=payload["title"], inputs=payload))
            item = load_general_project(path)
            self.assertEqual(item.to_json()["schema"], "vdi2230.general/4")
            self.assertIsNone(item.bolt.head_diameter)

    def test_atomic_write_failure_preserves_file_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text("original", encoding="utf-8")
            for failure in ("fsync", "replace"):
                patch = mock.patch("vdi2230.infrastructure.project_file.os.fsync", side_effect=OSError("disk error")) \
                    if failure == "fsync" else mock.patch.object(Path, "replace", side_effect=OSError("replace failed"))
                with self.subTest(failure=failure), patch:
                    with self.assertRaises(OSError):
                        write_text_atomic(path, "new content")
                self.assertEqual(path.read_text(encoding="utf-8"), "original")
                self.assertEqual(list(Path(directory).iterdir()), [path])
            write_text_atomic(path, "complete")
            self.assertEqual(path.read_text(encoding="utf-8"), "complete")

    def test_nonfinite_snapshot_does_not_truncate_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text("original", encoding="utf-8")
            with self.assertRaises(ValueError):
                save_project(path, ProjectSnapshot(case_id="GENERAL", title="invalid", inputs={"d": float("nan")}))
            self.assertEqual(path.read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
