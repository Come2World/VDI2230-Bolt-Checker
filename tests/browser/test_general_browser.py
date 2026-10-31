from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from playwright.sync_api import expect, sync_playwright

from vdi2230.web.server import CalculatorServer


CALCULATE = "**/api/general/calculate"


class GeneralBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = CalculatorServer(0)
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
        self.context = self.browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 900})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page_errors: list[str] = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.goto(self.base_url)
        self.export = self.page.get_by_role("button", name="导出 TXT")
        expect(self.export).to_be_enabled()

    def tearDown(self) -> None:
        self.assertEqual(self.page_errors, [])

    def metric(self, term: str):
        return self.page.locator(f"xpath=//dl[@id='key-metrics']//dt[normalize-space()='{term}']/following-sibling::dd[1]")

    def wait_until(self, predicate, timeout_ms: int = 5000) -> None:
        for _ in range(timeout_ms // 20):
            if predicate():
                return
            self.page.wait_for_timeout(20)
        self.fail("condition not reached in time")

    def plate_rects(self, index: int):
        return self.page.locator(f'#section rect[data-role="plate-{index}"]')

    def test_page_fits_viewport_with_compact_controls(self) -> None:
        page = self.page
        self.assertLessEqual(page.evaluate("document.documentElement.scrollHeight"), page.evaluate("innerHeight"))
        boxes = [page.locator(selector).bounding_box() for selector in (".input-pane", ".section-pane", ".result-pane")]
        self.assertTrue(all(boxes))
        self.assertEqual(len({round(box["y"]) for box in boxes if box}), 1)
        self.assertLess(boxes[0]["x"], boxes[1]["x"])
        self.assertLess(boxes[1]["x"], boxes[2]["x"])
        self.assertEqual(page.evaluate("getComputedStyle(document.body).fontSize"), "12px")
        self.assertLessEqual(page.locator("#f-bolt-d").bounding_box()["height"], 26)
        expect(page.locator("#verdict")).to_have_text("需确认 · 数据待核验")
        expect(page.locator("#checks-table tbody tr[data-symbol='SF']")).to_be_visible()
        expect(self.plate_rects(0).first).to_be_attached()
        expect(self.plate_rects(1).first).to_be_attached()
        expect(self.metric("lK")).to_have_text("40 mm")

    def test_input_and_result_tabs_switch_panels(self) -> None:
        page = self.page
        page.get_by_role("tab", name="载荷").click()
        expect(page.locator("#panel-load")).to_be_visible()
        expect(page.locator("#panel-bolt")).to_be_hidden()
        page.get_by_role("tab", name="报告").click()
        expect(page.locator("#report-preview")).to_contain_text("数据待核验")
        expect(page.locator("#checks-table")).to_be_hidden()
        page.get_by_role("tab", name="全部结果").click()
        page.locator("#value-filter").fill("FMzul")
        visible = page.locator("#values-table tbody tr:visible")
        self.assertGreater(visible.count(), 0)
        for text in visible.all_inner_texts():
            self.assertIn("fmzul", text.lower())

    def test_adding_and_removing_layers_updates_section(self) -> None:
        page = self.page
        page.locator("#section-add-layer").click()
        expect(page.locator("#layers .layer")).to_have_count(3)
        expect(self.export).to_be_enabled()
        expect(self.plate_rects(2).first).to_be_attached()
        # A new layer is inserted below the selected one and becomes selected.
        expect(page.locator("#selected-layer")).to_have_text("选中：2. 板 3")
        expect(page.locator("#layers .layer").nth(1)).to_contain_text("板 3")
        expect(self.metric("lK")).to_have_text("60 mm")
        page.locator("#section-remove-layer").click()
        expect(page.locator("#layers .layer")).to_have_count(2)
        expect(self.export).to_be_enabled()
        expect(self.plate_rects(2)).to_have_count(0)
        expect(self.metric("lK")).to_have_text("40 mm")

    def test_too_many_layers_reports_bolt_length_and_marks_section_stale(self) -> None:
        page = self.page
        page.get_by_role("tab", name="板层").click()
        page.locator("#f-plates-0-thickness").fill("50")
        alert = page.get_by_role("alert")
        expect(alert).to_contain_text("螺栓长度")
        expect(page.locator("#section-stale")).to_be_visible()
        expect(page.locator("#section")).to_have_class(re.compile(r"\bstale\b"))
        expect(page.locator("#tab-bolt")).to_have_class(re.compile(r"\bhas-error\b"))
        alert.get_by_role("button").first.click()
        expect(page.locator("#panel-bolt")).to_be_visible()
        expect(page.locator("#f-bolt-length")).to_be_focused()
        page.locator("#f-bolt-length").fill("90")
        expect(self.export).to_be_enabled()
        expect(page.locator("#section-stale")).to_be_hidden()
        expect(alert).to_be_hidden()

    def test_clicking_plate_in_section_selects_layer(self) -> None:
        page = self.page
        self.plate_rects(1).first.click()
        expect(page.get_by_role("tab", name="板层")).to_have_attribute("aria-selected", "true")
        expect(page.locator("#f-plates-1-thickness")).to_be_visible()
        expect(page.locator("#f-plates-0-thickness")).to_have_count(0)
        expect(page.locator("#selected-layer")).to_contain_text("2.")
        expect(self.plate_rects(1).first).to_have_class(re.compile(r"\bselected\b"))

    def test_layer_fields_are_filled_and_editable(self) -> None:
        page = self.page
        page.get_by_role("tab", name="板层").click()
        expect(page.locator("#f-plates-0-thickness")).to_have_value("20")
        expect(page.locator("#f-plates-0-material_id")).not_to_have_value("")
        page.locator("#f-plates-0-thickness").fill("25")
        expect(self.export).to_be_enabled()
        expect(self.metric("lK")).to_have_text("45 mm")
        expect(page.get_by_role("button", name="编辑板层 1")).to_contain_text("h 25")

    def test_catalog_variant_fills_bolt_fields(self) -> None:
        page = self.page
        page.locator("#f-bolt-catalog_variant_id").select_option("ISO4014-M16x2.0")
        expect(page.locator("#f-bolt-d")).to_have_value("16")
        expect(page.locator("#f-bolt-pitch")).to_have_value("2")
        marker = page.locator('.field[data-path="bolt.d"] .src')
        expect(marker).to_have_class(re.compile(r"\bprovisional\b"))
        expect(self.export).to_be_enabled()
        expect(page.locator("#section > text").first).to_be_attached()
        expect(page.locator("#section")).to_contain_text("M16")
        page.locator("#f-bolt-head_height").fill("10.5")
        expect(page.locator('.field[data-path="bolt.head_height"] .src')).not_to_have_class(re.compile("provisional"))
        expect(self.export).to_be_enabled()

    def test_tapped_joint_hides_nut_fields(self) -> None:
        page = self.page
        expect(page.locator("#f-nut-height")).to_be_visible()
        page.locator("#f-joint-type").select_option("ESV")
        expect(page.locator("#f-nut-height")).to_be_hidden()
        expect(page.locator("#f-tapped-youngs_modulus")).to_be_visible()
        expect(self.export).to_be_enabled()
        expect(page.locator("#section")).to_contain_text("ESV")

    def test_export_matches_report_preview(self) -> None:
        page = self.page
        page.locator("#project-title").fill("法兰 A")
        expect(self.export).to_be_disabled()
        expect(self.export).to_be_enabled()
        with page.expect_download() as event:
            self.export.click()
        download = event.value
        self.assertEqual(download.suggested_filename, "VDI2230-法兰_A.txt")
        with TemporaryDirectory() as directory:
            path = Path(directory) / download.suggested_filename
            download.save_as(path)
            text = path.read_text(encoding="utf-8")
        self.assertEqual(text, page.locator("#report-preview").text_content())
        self.assertIn("法兰 A", text)
        self.assertIn("数据待核验", text)

    def test_late_response_does_not_replace_newer_result(self) -> None:
        page = self.page
        page.get_by_role("tab", name="板层").click()
        held = []
        page.route(CALCULATE, lambda route: held.append(route))
        with page.expect_request(CALCULATE):
            page.locator("#f-plates-0-thickness").fill("21")
        with page.expect_request(CALCULATE):
            page.locator("#f-plates-0-thickness").fill("22")
        self.wait_until(lambda: len(held) == 2)
        with page.expect_response(CALCULATE):
            held[1].continue_()
        expect(self.metric("lK")).to_have_text("42 mm")
        with page.expect_response(CALCULATE):
            held[0].continue_()
        page.wait_for_timeout(100)
        expect(self.metric("lK")).to_have_text("42 mm")
        expect(self.export).to_be_enabled()

    def test_server_failure_disables_export(self) -> None:
        page = self.page
        page.route(CALCULATE, lambda route: route.fulfill(status=500, json={"error": "测试失败", "field_errors": []}))
        page.locator("#f-bolt-length").fill("75")
        expect(page.get_by_role("alert")).to_contain_text("测试失败")
        expect(self.export).to_be_disabled()
        expect(page.locator("#verdict")).to_have_text("计算失败")
        page.unroute(CALCULATE)
        page.locator("#f-bolt-length").fill("70")
        expect(self.export).to_be_enabled()
        expect(page.get_by_role("alert")).to_be_hidden()

    def test_narrow_viewport_stacks_without_horizontal_overflow(self) -> None:
        page = self.page
        page.set_viewport_size({"width": 390, "height": 844})
        expect(self.export).to_be_enabled()
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("innerWidth"))
        self.export.scroll_into_view_if_needed()
        expect(self.export).to_be_visible()
        expect(page.locator("#checks-table")).to_be_visible()


if __name__ == "__main__":
    unittest.main()
