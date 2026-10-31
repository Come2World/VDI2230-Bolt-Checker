from http.client import HTTPConnection
import json
import math
import subprocess
import sys
from threading import Thread
import unittest
from unittest.mock import patch

from vdi2230.domain.general_inputs import default_input_json
from vdi2230.web import general_api
from vdi2230.web.general_api import (
    _json_safe,
    calculate_payload,
    catalog_payload,
    catalog_values_payload,
    schema_payload,
)
from vdi2230.web.server import MAX_BODY_BYTES, CalculatorServer

from test_general_engine import b1_payload, b2_payload, b3_payload


VALUES_QUERY = "variant=ISO4014-M12x1.75&length=70&class=8.8"


class GeneralApiFunctionTests(unittest.TestCase):
    def test_schema_exposes_fields_layers_and_defaults(self) -> None:
        status, payload = schema_payload()
        self.assertEqual(status, 200)
        self.assertEqual(payload["max_layers"], 10)
        paths = {field["path"] for field in payload["fields"]}
        self.assertTrue({"bolt.d", "bolt.thread_friction", "bolt.bearing_friction", "load.axial_max", "assembly.utilization"} <= paths)
        layer_paths = {field["path"] for field in payload["layer_fields"]}
        self.assertTrue({"thickness", "roughness_rz", "interface_friction"} <= layer_paths)
        self.assertNotIn("bearing_friction", layer_paths)
        self.assertTrue({"head_washer.enabled", "nut_washer.thickness"} <= paths)
        self.assertGreaterEqual(len(payload["defaults"]["plates"]), 1)

    def test_catalog_lists_bolts_materials_and_friction_classes(self) -> None:
        status, payload = catalog_payload()
        self.assertEqual(status, 200)
        for key in ("bolts", "property_classes", "lengths", "materials", "friction_classes"):
            with self.subTest(key=key):
                self.assertTrue(payload[key])
        self.assertEqual(payload["friction_classes"][0]["class"], "A")

    def test_catalog_values_fill_geometry_with_accepted_sources(self) -> None:
        status, payload = catalog_values_payload(VALUES_QUERY)
        self.assertEqual(status, 200)
        values = payload["values"]
        self.assertEqual(values["bolt.d"], 12.0)
        self.assertEqual(values["bolt.pitch"], 1.75)
        self.assertEqual(values["nut.width_across_flats"], 18.0)
        self.assertEqual(values["bolt.thread_length"], 30.0)
        self.assertEqual(payload["provisional"], [])
        self.assertEqual(payload["sources"]["bolt.d"], "catalog:ISO4014-M12x1.75")

    def test_catalog_values_reject_bad_queries(self) -> None:
        for query in (
            "",
            "variant=ISO4014-M12x1.75&length=70",
            VALUES_QUERY + "&extra=1",
            VALUES_QUERY + "&length=80",
            "variant=ISO4014-M12x1.75&length=-5&class=8.8",
            "variant=ISO4014-M12x1.75&length=nan&class=8.8",
            "variant=ISO4014-M12x1.75&length=abc&class=8.8",
            "variant=UNKNOWN&length=70&class=8.8",
            "variant=ISO4014-M12x1.75&length=70&class=99.9",
        ):
            with self.subTest(query=query):
                status, payload = catalog_values_payload(query)
                self.assertEqual(status, 400)
                self.assertTrue(payload["error"])

    def test_calculate_returns_checks_section_and_report(self) -> None:
        status, payload = calculate_payload({"input": default_input_json(), "view": {"width": 600, "height": 480}})
        self.assertEqual(status, 200)
        json.dumps(payload, allow_nan=False)
        self.assertEqual(payload["verdict"], "通过")
        self.assertEqual(payload["verdict_label"], "通过")
        symbols = {check["symbol"] for check in payload["checks"]}
        self.assertTrue({"SF", "SD", "FKR"} <= symbols)
        self.assertEqual((payload["section"]["width"], payload["section"]["height"]), (600, 480))
        roles = {shape["role"] for shape in payload["section"]["shapes"]}
        self.assertTrue({"plate-0", "plate-1", "bolt-head", "nut", "dim-lK"} <= roles)
        self.assertIn("总体判定：通过", payload["report"])
        self.assertIn(payload["calculated_at"], payload["report"])
        self.assertEqual(payload["provisional_sources"], [])

    def test_reference_payloads_calculate_through_the_api(self) -> None:
        for name, factory in (("B1", b1_payload), ("B2", b2_payload), ("B3", b3_payload)):
            with self.subTest(case=name):
                status, payload = calculate_payload({"input": factory()})
                self.assertEqual(status, 200, payload.get("error"))
                json.dumps(payload, allow_nan=False)

    def test_geometry_and_load_validation_remains_structured_in_both_languages(self):
        for joint in ("DSV", "ESV"):
            for language in ("zh", "en"):
                for section, name, invalid in (
                    ("bolt", "length", 10), ("joint", "hole_diameter", 5),
                    ("joint", "outer_diameter", 10), ("bolt", "bearing_friction", -1),
                    ("load", "axial_min", 100000), ("head_washer", "outer_diameter", 10),
                    ("plates", "thickness", 0), ("plates", "roughness_rz", 160),
                ):
                    with self.subTest(joint=joint, language=language, field=f"{section}.{name}"):
                        item = default_input_json()
                        item["joint"]["type"] = joint
                        item["head_washer"]["enabled"] = True
                        target = item["plates"][0] if section == "plates" else item[section]
                        target[name] = invalid
                        status, payload = calculate_payload({"input": item, "language": language})
                        self.assertEqual(status, 400, payload)
                        self.assertTrue(payload["error"])
                        self.assertIn("field_errors", payload)
                        self.assertNotIn("section", payload)
                        self.assertNotIn("report", payload)
                        if language == "en":
                            messages = payload["error"] + "".join(error["message"] for error in payload["field_errors"])
                            self.assertNotRegex(messages, r"[\u4e00-\u9fff]")

    def test_view_is_optional_and_clamped(self) -> None:
        status, payload = calculate_payload({"input": default_input_json()})
        self.assertEqual(status, 200)
        self.assertEqual((payload["section"]["width"], payload["section"]["height"]), general_api.DEFAULT_VIEW)
        status, payload = calculate_payload({"input": default_input_json(), "view": {"width": 50, "height": 99999}})
        self.assertEqual(status, 200)
        self.assertEqual((payload["section"]["width"], payload["section"]["height"]), (200, 2400))

    def test_invalid_field_reports_its_path(self) -> None:
        item = default_input_json()
        item["plates"][0]["thickness"] = -1
        status, payload = calculate_payload({"input": item})
        self.assertEqual(status, 400)
        self.assertIn("输入有误（1 项）", payload["error"])
        self.assertEqual([error["path"] for error in payload["field_errors"]], ["plates[0].thickness"])

    def test_clamp_length_must_fit_bolt_length(self) -> None:
        item = default_input_json()
        item["plates"].append({**item["plates"][-1], "thickness": item["bolt"]["length"]})
        status, payload = calculate_payload({"input": item})
        self.assertEqual(status, 400)
        self.assertIn("bolt.length", [error["path"] for error in payload["field_errors"]])

    def test_malformed_bodies_are_rejected(self) -> None:
        for body in (None, [], "x", {}, {"input": default_input_json(), "extra": 1}):
            with self.subTest(body=type(body).__name__):
                status, payload = calculate_payload(body)
                self.assertEqual(status, 400)
                self.assertEqual(payload["field_errors"], [])
        for view in ([], {"width": "a"}, {"width": True}, {"width": math.inf}, {"depth": 3}):
            with self.subTest(view=view):
                status, _ = calculate_payload({"input": default_input_json(), "view": view})
                self.assertEqual(status, 400)

    def test_engine_value_errors_become_400(self) -> None:
        with patch.object(general_api, "calculate_general", side_effect=ValueError("boom")):
            with self.assertLogs("vdi2230.web.general_api", level="WARNING"):
                status, payload = calculate_payload({"input": default_input_json()})
        self.assertEqual(status, 400)
        self.assertIn("计算无法完成", payload["error"])

    def test_non_finite_values_become_null(self) -> None:
        self.assertEqual(
            _json_safe({"a": [1.0, math.inf, (math.nan, "x")], "b": -math.inf, "c": True}),
            {"a": [1.0, None, [None, "x"]], "b": None, "c": True},
        )


class GeneralApiHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = CalculatorServer(0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def http(self, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.headers), response.read()
        finally:
            connection.close()

    def post(self, payload: object, content_type: str = "application/json"):
        return self.http("POST", "/api/general/calculate", json.dumps(payload).encode("utf-8"), {"Content-Type": content_type})

    def test_get_endpoints(self) -> None:
        for path in ("/api/general/schema", "/api/general/catalog", "/api/general/catalog-values?" + VALUES_QUERY):
            with self.subTest(path=path):
                status, headers, body = self.http("GET", path)
                self.assertEqual(status, 200)
                self.assertTrue(headers["Content-Type"].startswith("application/json"))
                self.assertTrue(json.loads(body))
        self.assertEqual(self.http("GET", "/api/general/catalog-values?variant=x")[0], 400)
        self.assertEqual(self.http("GET", "/api/general/unknown")[0], 404)

    def test_calculate_round_trip(self) -> None:
        status, _, body = self.post({"input": default_input_json(), "view": {"width": 500, "height": 400}})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["verdict_label"], "通过")
        self.assertTrue(payload["section"]["shapes"])

    def test_calculate_field_error_round_trip(self) -> None:
        item = default_input_json()
        item["bolt"]["d"] = "abc"
        status, _, body = self.post({"input": item})
        self.assertEqual(status, 400)
        self.assertIn("bolt.d", [error["path"] for error in json.loads(body)["field_errors"]])

    def test_transport_errors(self) -> None:
        path = "/api/general/calculate"
        self.assertEqual(self.post({"input": {}}, "text/plain")[0], 415)
        self.assertEqual(self.http("POST", path, b"", {"Content-Type": "application/json"})[0], 413)
        self.assertEqual(self.http("POST", path, b"x" * (MAX_BODY_BYTES + 1), {"Content-Type": "application/json"})[0], 413)
        self.assertEqual(self.http("POST", path, b"{", {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.http("POST", "/api/general/other", b"{}", {"Content-Type": "application/json"})[0], 404)

    def test_cross_origin_requests_are_rejected(self) -> None:
        body = json.dumps({"input": default_input_json()}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Origin": "https://other.invalid"}
        self.assertEqual(self.http("POST", "/api/general/calculate", body, headers)[0], 403)
        self.assertEqual(self.http("GET", "/api/general/schema", headers={"Host": "other.invalid"})[0], 403)

    def test_unexpected_engine_failure_is_500(self) -> None:
        with patch.object(general_api, "calculate_general", side_effect=RuntimeError("deliberate")):
            with self.assertLogs("vdi2230.web.server", level="ERROR"):
                status, _, body = self.post({"input": default_input_json()})
        self.assertEqual(status, 500)
        self.assertIn("计算失败", json.loads(body)["error"])

    def test_general_api_does_not_import_tkinter(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.modules['tkinter'] = None; "
             "from vdi2230.domain.general_inputs import default_input_json; "
             "from vdi2230.web.general_api import calculate_payload; "
             "assert calculate_payload({'input': default_input_json()})[0] == 200"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
