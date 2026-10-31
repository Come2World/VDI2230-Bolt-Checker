import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from playwright.sync_api import expect, sync_playwright

from vdi2230.web.server import ReferenceServer


REFERENCE_SAFETY = {
    "B1": {"SF": 1.15, "Sp": 1.8},
    "B2": {"SG": 1.26},
    "B3": {"Sp": 2.0, "SG": 1.31},
    "B4": {"SD": 2.02, "SpK": 1.64, "SpMu": 1.25, "SG": 1.12},
    "B5": {"SF": 1.16, "SD": 3.57, "Sp": 1.03},
}


class BrowserUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ReferenceServer(0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.stop_server)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch()
        cls.addClassCleanup(cls.browser.close)

    @classmethod
    def stop_server(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self) -> None:
        self.context = self.browser.new_context(
            accept_downloads=True, viewport={"width": 1440, "height": 1000},
        )
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page_errors: list[str] = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.goto(f"{self.base_url}/reference")
        expect(self.page.get_by_role("button", name="计算", exact=True)).to_be_enabled()

    def tearDown(self) -> None:
        self.assertEqual(self.page_errors, [])

    def select_case(self, case_id: str) -> None:
        self.page.get_by_label("计算实例").select_option(case_id)
        expect(self.page.locator("#case-title")).to_contain_text(case_id)
        expect(self.page.get_by_role("button", name="计算", exact=True)).to_be_enabled()

    def calculate(self) -> None:
        self.page.get_by_role("button", name="计算", exact=True).click()
        expect(self.page.get_by_role("button", name="导出 TXT")).to_be_enabled()

    def test_all_five_cases_safety_errors_and_sections(self) -> None:
        for case_id, factors in REFERENCE_SAFETY.items():
            with self.subTest(case=case_id):
                self.select_case(case_id)
                inputs = self.page.locator("#inputs input")
                self.assertGreater(inputs.count(), 0)
                self.assertEqual(inputs.count(), self.page.locator("#inputs input[readonly]").count())
                self.assertGreater(self.page.locator("#section rect").count(), 3)
                self.calculate()
                expect(self.page.get_by_role("status")).to_have_text(
                    "计算状态：需确认" if case_id == "B1" else "计算状态：通过",
                )
                expect(self.page.locator("#safety-table tbody tr")).to_have_count(len(factors))
                for symbol, reference in factors.items():
                    cells = self.page.locator(f'#safety-table tr[data-symbol="{symbol}"] td')
                    self.assertEqual(float(cells.nth(1).inner_text()), reference)
                    actual = float(cells.nth(2).inner_text())
                    error = float(cells.nth(3).inner_text().rstrip("%"))
                    self.assertAlmostEqual(error, abs(actual - reference) / abs(reference) * 100, delta=.001)
                    self.assertLessEqual(error, 3.0)
                if case_id == "B3":
                    expect(self.page.locator("#geometry")).to_contain_text("空心内径")
                elif case_id == "B4":
                    expect(self.page.locator("#geometry")).to_contain_text("缩颈直径")
                elif case_id == "B1":
                    expect(self.page.locator("#warnings")).to_contain_text("w=1")
                    expect(self.page.locator("#result-summary")).to_contain_text("不完整")

    def test_switching_clears_stale_results_and_details(self) -> None:
        self.calculate()
        self.page.locator("#safety-table").get_by_role("button", name="查看 SF 计算依据").click()
        expect(self.page.get_by_role("region", name="计算项详情")).to_contain_text("B1.2 R8")
        self.select_case("B5")
        expect(self.page.get_by_role("button", name="导出 TXT")).to_be_disabled()
        expect(self.page.locator("#safety-table tbody tr")).to_have_count(0)
        expect(self.page.locator("#result-details")).to_be_hidden()
        expect(self.page.locator("#report-preview")).to_have_text("")
        self.calculate()
        expect(self.page.locator("#result-summary")).to_contain_text("B5")

    def test_download_is_current_utf8_report_including_review_warning(self) -> None:
        for case_id in ("B1", "B5"):
            with self.subTest(case=case_id):
                self.select_case(case_id)
                self.calculate()
                with self.page.expect_download() as event:
                    self.page.get_by_role("button", name="导出 TXT").click()
                download = event.value
                self.assertEqual(download.suggested_filename, f"VDI2230-{case_id}.txt")
                with TemporaryDirectory() as directory:
                    path = Path(directory) / download.suggested_filename
                    download.save_as(path)
                    text = path.read_text(encoding="utf-8")
                self.assertEqual(text, self.page.locator("#report-preview").text_content())
                self.assertIn(f"计算案例：{case_id}", text)
                self.assertIn("相对误差：", text)
                if case_id == "B1":
                    self.assertIn("计算完整性：不完整", text)
                    self.assertIn("w=2", text)

    def test_failed_calculation_disables_export_and_can_retry(self) -> None:
        self.calculate()
        pattern = "**/api/cases/B1/calculate"
        self.page.route(pattern, lambda route: route.fulfill(
            status=500, content_type="application/json",
            body=json.dumps({"error": "测试计算失败"}, ensure_ascii=False),
        ))
        self.page.get_by_role("button", name="计算", exact=True).click()
        expect(self.page.get_by_role("alert")).to_contain_text("测试计算失败")
        expect(self.page.get_by_role("button", name="导出 TXT")).to_be_disabled()
        expect(self.page.locator("#safety-table tbody tr")).to_have_count(0)
        self.page.unroute(pattern)
        self.calculate()
        expect(self.page.get_by_role("alert")).to_be_hidden()

    def test_late_response_does_not_replace_new_case(self) -> None:
        data = self.page.request.get(f"{self.base_url}/api/cases/B5").json()
        pending = []
        self.page.route("**/api/cases/B5", lambda route: pending.append(route))
        with self.page.expect_request("**/api/cases/B5"):
            self.page.get_by_label("计算实例").select_option("B5")
        self.select_case("B3")
        self.assertEqual(len(pending), 1)
        with self.page.expect_response("**/api/cases/B5"):
            pending[0].fulfill(json=data)
        self.calculate()
        expect(self.page.locator("#case-title")).to_contain_text("B3")
        expect(self.page.locator("#result-summary")).to_contain_text("B3")

    def test_desktop_columns_and_narrow_viewport_remain_accessible(self) -> None:
        panels = [self.page.locator(f".{name}-panel").bounding_box() for name in ("input", "section", "result")]
        self.assertTrue(all(panel is not None for panel in panels))
        self.assertEqual(len({panel["y"] for panel in panels if panel is not None}), 1)
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            self.page.evaluate("window.innerWidth"),
        )
        self.calculate()
        expect(self.page.get_by_role("button", name="导出 TXT")).to_be_visible()
        expect(self.page.locator("#safety-table")).to_be_visible()


if __name__ == "__main__":
    unittest.main()
