from dataclasses import replace
from http.client import HTTPConnection
import json
import subprocess
import sys
from threading import Thread
import unittest
from unittest.mock import patch

from vdi2230.domain.models import ProjectSnapshot
from vdi2230.web.server import MAX_BODY_BYTES, ReferenceServer, reference_project


class WebUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ReferenceServer(0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def http(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.headers), response.read()
        finally:
            connection.close()

    def post(self, case_id: str, payload: object) -> tuple[int, dict[str, str], bytes]:
        return self.http(
            "POST", f"/api/cases/{case_id}/calculate",
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"},
        )

    def test_assets_and_case_discovery(self) -> None:
        for path, content_type in (
            ("/", "text/html"),
            ("/app.js", "text/javascript"),
            ("/styles.css", "text/css"),
            ("/reference", "text/html"),
            ("/reference.js", "text/javascript"),
            ("/reference.css", "text/css"),
        ):
            with self.subTest(path=path):
                status, headers, body = self.http("GET", path)
                self.assertEqual(status, 200)
                self.assertTrue(headers["Content-Type"].startswith(content_type))
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
                self.assertTrue(body)
        pages = {path: self.http("GET", path)[2].decode("utf-8") for path in ("/", "/reference")}
        self.assertIn('src="/app.js"', pages["/"])
        self.assertIn('href="/reference"', pages["/"])
        self.assertIn('src="/reference.js"', pages["/reference"])
        self.assertIn('href="/"', pages["/reference"])
        status, _, body = self.http("GET", "/api/cases")
        self.assertEqual(status, 200)
        self.assertEqual([case["case_id"] for case in json.loads(body)], list(self.server.cases))

    def test_all_cases_share_calculations_sections_and_report(self) -> None:
        expected_factors = {
            "B1": {"SF", "Sp"}, "B2": {"SG"}, "B3": {"Sp", "SG"},
            "B4": {"SD", "SpK", "SpMu", "SG"}, "B5": {"SF", "SD", "Sp"},
        }
        for case_id, case in self.server.cases.items():
            with self.subTest(case=case_id):
                status, _, body = self.http("GET", f"/api/cases/{case_id}")
                self.assertEqual(status, 200)
                data = json.loads(body)
                self.assertTrue(all(field["read_only"] for field in data["fields"]))
                self.assertTrue(data["section"])
                self.assertEqual(data["geometry"]["bolt_count"], 12 if case_id == "B2" else 15 if case_id == "B5" else 1)
                status, _, body = self.post(case_id, {"inputs": data["inputs"]})
                self.assertEqual(status, 200)
                result = json.loads(body)
                core = case.calculate(reference_project(case))
                self.assertEqual(result["case_id"], case_id)
                self.assertEqual(result["overall_status"], core.overall_status.value)
                self.assertEqual(result["is_fully_calculated"], case_id != "B1")
                self.assertEqual(
                    {value["symbol"]: value["value"] for value in result["values"]},
                    {value.symbol: value.value for value in core.values},
                )
                self.assertEqual(
                    {value["symbol"] for value in result["safety_factors"]},
                    expected_factors[case_id],
                )
                for value in result["safety_factors"]:
                    self.assertAlmostEqual(
                        value["relative_error_percent"],
                        abs(value["value"] - value["reference_value"])
                        / abs(value["reference_value"]) * 100,
                    )
                    self.assertLessEqual(value["relative_error_percent"], 3)
                    self.assertIn(f"{value['symbol']} (", result["report"])
                self.assertIn(f"计算案例：{case_id}", result["report"])
                self.assertIn("相对误差：", result["report"])
                self.assertIn(result["calculated_at"], result["report"])
                if case_id == "B1":
                    self.assertIn("计算完整性：不完整", result["report"])
                    self.assertIn("w=1", result["report"])
                    self.assertIn("w=2", result["report"])

    def test_changed_and_invalid_inputs_are_rejected(self) -> None:
        inputs = reference_project(self.server.cases["B1"]).inputs
        for value in (123456, True, None, "5.5", float("nan"), float("inf"), []):
            with self.subTest(value=value):
                status, _, body = self.post("B1", {"inputs": {**inputs, "pmax": value}})
                self.assertEqual(status, 400)
                self.assertTrue(json.loads(body)["error"])
        for payload in ([], {}, {"inputs": []}, {"inputs": inputs, "extra": 1}):
            with self.subTest(payload=payload):
                self.assertEqual(self.post("B1", payload)[0], 400)

    def test_malformed_requests_and_unknown_paths(self) -> None:
        path = "/api/cases/B1/calculate"
        self.assertEqual(self.http("POST", path, b"{", {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.http("POST", path, b"{}", {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.http("POST", path, b"x" * (MAX_BODY_BYTES + 1), {"Content-Type": "application/json"})[0], 413)
        for path in ("/api/cases/B9", "/../../pyproject.toml", "/api/cases/B1/extra"):
            self.assertEqual(self.http("GET", path)[0], 404)
        self.assertEqual(self.post("B9", {"inputs": {}})[0], 404)

    def test_external_hosts_and_origins_are_rejected(self) -> None:
        self.assertEqual(self.http("GET", "/api/cases", headers={"Host": "other.invalid"})[0], 403)
        self.assertEqual(self.http("GET", "/api/cases", headers={"Origin": "https://other.invalid"})[0], 403)

    def test_calculation_failure_is_explicit(self) -> None:
        case = self.server.cases["B1"]

        def fail(project: ProjectSnapshot) -> None:
            raise RuntimeError("deliberate calculation failure")

        with patch.dict(self.server.cases, {"B1": replace(case, calculate=fail)}):
            with self.assertLogs("vdi2230.web.server", level="ERROR"):
                status, _, body = self.post("B1", {"inputs": reference_project(case).inputs})
        self.assertEqual(status, 500)
        self.assertIn("计算失败", json.loads(body)["error"])

    def test_web_entry_does_not_import_tkinter(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.modules['tkinter'] = None; "
             "from vdi2230.web.server import build_reference_cases; "
             "assert len(build_reference_cases()) == 5"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
