from copy import deepcopy
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
        self.page.goto(self.base_url + "/?lang=zh")
        self.export = self.page.get_by_role("button", name="导出 TXT")
        expect(self.export).to_be_enabled()

    def tearDown(self) -> None:
        self.assertEqual(self.page_errors, [])

    def metric(self, term: str):
        return self.page.locator(f"xpath=//dl[@id='key-metrics']//dt[normalize-space()='{term}']/following-sibling::dd[1]")

    def test_browser_template_matching_prefers_specific_messages(self):
        failures = self.page.evaluate("""() => Object.entries(i18n.templates).flatMap(([source, target]) => {
            const message=source.replace(/\\{\\w+\\}/g, '1');
            const expected=target.replace(/\\{\\w+\\}/g, '1');
            try {
                const actual=translateText(message, 'en');
                return actual===expected ? [] : [{source, actual, expected}];
            } catch(error) { return [{source, error:error.message}]; }
        })""")
        self.assertEqual(failures, [])

    def test_geometry_and_load_edits_update_drawing_and_results(self):
        page = self.page
        page.locator("#language").select_option("en")
        expect(page.locator("#report-preview")).to_contain_text("Calculation Report")
        for tab, path, value, role, text in (
            ("plates", "plates-0-thickness", "25", "dim-t1", "t1 25"),
            ("plates", "joint-outer_diameter", "70", "dim-DA", "DA 70"),
            ("bolt", "bolt-length", "65", "dim-l", "l 65"),
            ("bolt", "bolt-bearing_friction", "0.10", "label-head", "μK 0.1"),
            ("plates", "head_washer-enabled", True, "washer-head", "Head washer"),
            ("plates", "head_washer-thickness", "3.2", "washer-head", "t 3.2"),
        ):
            with self.subTest(path=path):
                page.locator(f"#tab-{tab}").click()
                if path == "head_washer-enabled":
                    page.locator("summary").get_by_text("Head washer", exact=True).click()
                with page.expect_response(CALCULATE) as response:
                    control = page.locator(f"#f-{path}")
                    if value is True:
                        control.check()
                    else:
                        control.fill(value)
                self.assertEqual(response.value.status, 200)
                expect(page.locator("#export")).to_be_enabled()
                expect(page.locator("#section-stale")).to_be_hidden()
                expect(page.locator(f"#section text[data-role='{role}']").filter(has_text=text)).to_have_count(1)
        force = page.evaluate("state.result.values.find(value=>value.symbol==='FSmax').value")
        page.locator("#tab-load").click()
        with page.expect_response(CALCULATE) as response:
            page.locator("#f-load-axial_max").fill("20000")
        self.assertEqual(response.value.status, 200)
        expect(page.locator("#export")).to_be_enabled()
        self.assertNotEqual(page.evaluate("state.result.values.find(value=>value.symbol==='FSmax').value"), force)
        self.assertEqual(page.evaluate("state.result.input.load.axial_max"), 20000)

    def test_esv_thickness_error_keeps_stale_section_and_recovers_after_length_edit(self):
        page = self.page
        page.locator("#language").select_option("en")
        page.locator("#f-joint-type").select_option("ESV")
        page.locator("#f-bolt-catalog_variant_id").select_option("ISO4014-M18x2.5")
        expect(page.locator("#f-bolt-d")).to_have_value("18")
        page.locator("#f-bolt-length").fill("90")
        page.locator("#tab-plates").click()
        page.locator("summary").get_by_text("Head washer", exact=True).click()
        page.locator("#f-head_washer-enabled").check()
        for _ in range(3):
            page.locator("#add-layer").click()
        for index, thickness in enumerate((20, 5, 5, 5, 40)):
            page.locator(".layer-select").nth(index).click()
            page.locator(f"#f-plates-{index}-thickness").fill(str(thickness))
        expect(self.metric("lK")).to_have_text("77.88 mm")
        page.locator(".layer-select").nth(1).click()
        with page.expect_response(CALCULATE) as response:
            page.locator("#f-plates-1-thickness").fill("20")
        self.assertEqual(response.value.status, 400)
        expect(page.locator("#error")).to_contain_text("to allow thread engagement")
        expect(page.locator("#section-stale")).to_be_visible()
        expect(page.locator("#export")).to_be_disabled()
        expect(page.locator("#report-preview")).to_be_empty()
        expect(page.locator("#section text[data-role='plate-1']").filter(has_text="h 5")).to_have_count(1)
        for index in (2, 3):
            page.locator(".layer-select").nth(index).click()
            page.locator(f"#f-plates-{index}-thickness").fill("20")
        page.locator("#tab-bolt").click()
        page.locator("#f-bolt-length").fill("160")
        expect(self.metric("lK")).to_have_text("122.9 mm")
        expect(page.locator("#section-stale")).to_be_hidden()
        expect(page.locator("#export")).to_be_enabled()
        self.assertEqual(page.evaluate("state.result.input.plates.map(plate=>plate.thickness)"), [20, 20, 20, 20, 40])
        expect(page.locator("#section text[data-role='plate-1']").filter(has_text="h 20")).to_have_count(1)

    def test_other_invalid_edits_keep_previous_section_and_recover(self):
        page = self.page
        page.locator("#language").select_option("en")
        expect(page.locator("#report-preview")).to_contain_text("Calculation Report")
        for tab, path, invalid in (
            ("plates", "plates-0-thickness", "0"), ("bolt", "bolt-length", "10"),
            ("plates", "joint-hole_diameter", "5"), ("bolt", "bolt-bearing_friction", "-1"),
            ("load", "load-axial_min", "100000"),
        ):
            with self.subTest(path=path):
                page.locator(f"#tab-{tab}").click()
                control = page.locator(f"#f-{path}")
                original = control.input_value()
                previous_section = page.evaluate("JSON.stringify(state.section)")
                with page.expect_response(CALCULATE) as response:
                    control.fill(invalid)
                self.assertEqual(response.value.status, 400)
                expect(page.locator("#section-stale")).to_be_visible()
                expect(page.locator("#export")).to_be_disabled()
                expect(page.locator("#report-preview")).to_be_empty()
                self.assertEqual(page.evaluate("JSON.stringify(state.section)"), previous_section)
                self.assertNotRegex(page.locator("#error").text_content(), r"[\u4e00-\u9fff]")
                with page.expect_response(CALCULATE) as response:
                    control.fill(original)
                self.assertEqual(response.value.status, 200)
                expect(page.locator("#section-stale")).to_be_hidden()
                expect(page.locator("#export")).to_be_enabled()

    def test_edit_invalidates_inflight_result_before_debounce_fires(self):
        page = self.page
        held = []
        page.route(CALCULATE, lambda route: held.append((route, route.fetch())))
        page.clock.install(time=1800000000000)
        page.clock.pause_at(1800000000000)
        page.locator("#tab-plates").click()
        page.locator("#f-plates-0-thickness").fill("25")
        page.clock.run_for(300)
        self.wait_until(lambda: len(held) == 1)
        page.locator("#f-plates-0-thickness").fill("30")
        with page.expect_response(CALCULATE):
            route, response = held[0]
            route.fulfill(response=response)
        page.wait_for_timeout(50)
        expect(page.locator("#export")).to_be_disabled()
        self.assertNotEqual(page.evaluate("state.result.input.plates[0].thickness"), 25)
        page.clock.run_for(300)
        self.wait_until(lambda: len(held) == 2)
        with page.expect_response(CALCULATE):
            route, response = held[1]
            route.fulfill(response=response)
        expect(page.locator("#export")).to_be_enabled()
        self.assertEqual(page.evaluate("state.result.input.plates[0].thickness"), 30)
        expect(self.metric("lK")).to_have_text("50 mm")

    def test_default_startup_uses_english_names_and_report(self):
        page = self.page
        page.goto(self.base_url)
        expect(page.locator("#language")).to_have_value("en")
        expect(page.locator("#project-title")).to_have_value("General bolt joint")
        page.locator("#tab-plates").click()
        expect(page.locator("#f-plates-0-name")).to_have_value("clamped plate 1")
        expect(page.locator("#layers")).to_contain_text("clamped plate 2")
        expect(page.locator("#export")).to_be_enabled()
        self.assertNotRegex(page.locator("#report-preview").text_content(), r"[\u4e00-\u9fff]")
        self.assertNotRegex(page.locator("#section").text_content(), r"[\u4e00-\u9fff]")
        page.locator("#add-layer").click()
        expect(page.locator("#f-plates-1-name")).to_have_value("clamped plate 3")
        page.get_by_role("button", name="Move plate 2 down", exact=True).click()
        page.locator("#language").select_option("zh")
        expect(page.locator("#project-title")).to_have_value("通用螺栓连接")
        expect(page.locator("#f-plates-2-name")).to_have_value("板 3")
        page.locator("#language").select_option("en")
        expect(page.locator("#f-plates-2-name")).to_have_value("clamped plate 3")
        expect(page.locator("#report-preview")).to_contain_text("clamped plate 3")

    def test_explicit_default_text_is_preserved_and_blank_title_uses_localized_fallback(self):
        page = self.page
        page.locator("#project-title").fill("通用螺栓连接")
        page.locator("#tab-plates").click()
        page.locator("#f-plates-0-name").fill("板 3")
        page.locator("#language").select_option("en")
        expect(page.locator("#project-title")).to_have_value("通用螺栓连接")
        expect(page.locator("#f-plates-0-name")).to_have_value("板 3")
        page.locator("#add-layer").click()
        expect(page.locator("#f-plates-1-name")).to_have_value("clamped plate 4")
        expect(page.locator("#report-preview")).to_contain_text("clamped plate 4")
        with page.expect_response(CALCULATE) as response:
            page.locator("#project-title").fill("")
        self.assertEqual(response.value.json()["input"]["title"], "General bolt joint")
        expect(page.locator("#export")).to_be_enabled()
        with page.expect_download() as download:
            page.locator("#export").click()
        self.assertEqual(download.value.suggested_filename, "VDI2230-General_bolt_joint.txt")
        self.assertIn("板 3", Path(download.value.path()).read_text(encoding="utf-8"))

    def test_language_switch_preserves_inputs_results_and_localizes_download(self):
        page = self.page
        page.set_viewport_size({"width": 1280, "height": 720})
        page.locator("#project-title").fill("用户标题 <script>")
        page.locator("#f-bolt-bearing_friction").fill("0.10")
        self.enable_washers()
        page.locator("#f-plates-0-name").fill("用户板层")
        with page.expect_response(CALCULATE) as response:
            page.locator("#language").select_option("en")
        english = response.value.json()
        expect(page.locator("#export")).to_be_enabled()
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator("#tab-plates")).to_have_text("Plates")
        expect(page.locator("#tab-plates")).to_have_attribute("aria-selected", "true")
        expect(page.locator("#project-title")).to_have_value("用户标题 <script>")
        expect(page.locator("#f-bolt-bearing_friction")).to_have_value("0.10")
        expect(page.locator("#f-head_washer-enabled")).to_be_checked()
        expect(page.locator("#f-plates-0-name")).to_have_value("用户板层")
        expect(page.locator("#report-preview")).to_contain_text("Warnings and assumptions")
        expect(page.locator("#report-preview")).to_contain_text("用户标题 <script>")
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), True)
        self.assertEqual(page.evaluate("document.documentElement.scrollHeight <= innerHeight"), True)
        with page.expect_download() as download:
            page.locator("#export").click()
        text = Path(download.value.path()).read_text(encoding="utf-8")
        self.assertEqual(text, page.locator("#report-preview").text_content())
        with page.expect_response(CALCULATE) as response:
            page.locator("#language").select_option("zh")
        chinese = response.value.json()
        expected_chinese = deepcopy(english["input"])
        self.assertEqual(expected_chinese["plates"][1]["name"], "clamped plate 2")
        expected_chinese["plates"][1]["name"] = "板 2"
        self.assertEqual(chinese["input"], expected_chinese)
        self.assertEqual([(v["symbol"], v["value"]) for v in chinese["values"]],
                         [(v["symbol"], v["value"]) for v in english["values"]])
        expect(page.locator("#report-preview")).to_contain_text("计算报告")

    def test_english_startup_and_invalid_input_keep_export_disabled(self):
        page = self.page
        page.goto(self.base_url + "/?lang=en")
        expect(page.get_by_role("button", name="Export TXT")).to_be_enabled()
        expect(page.locator("label[for='f-bolt-thread_friction']")).to_have_text("Thread friction μG")
        page.locator("#language").select_option("zh")
        expect(page.locator("#report-preview")).to_contain_text("计算报告")
        page.locator("#f-bolt-d").fill("abc")
        expect(page.locator("#export")).to_be_disabled()
        page.locator("#language").select_option("en")
        expect(page.locator("#error")).to_contain_text("Must be numeric")
        expect(page.locator("#f-bolt-d")).to_have_value("abc")
        expect(page.locator("#export")).to_be_disabled()
        expect(page.locator("#section-stale")).to_be_visible()
        expect(page.locator("#section [data-role='label-head']").filter(has_text="Bolt head")).to_have_count(1)
        expect(page.locator("#section text[data-role='plate-0']").filter(has_text="clamped plate 1")).to_have_count(1)
        expect(page.locator("#project-title")).to_have_value("General bolt joint")
        page.locator("#tab-plates").click()
        expect(page.locator("#f-plates-0-name")).to_have_value("clamped plate 1")
        page.reload()
        expect(page.get_by_role("button", name="Export TXT")).to_be_enabled()
        expect(page.locator("html")).to_have_attribute("lang", "en")

    def test_late_response_cannot_restore_previous_report_language(self):
        page = self.page
        held = []

        def delay_english(route):
            if route.request.post_data_json.get("language") == "en":
                held.append((route, route.fetch()))
            else:
                route.continue_()

        page.route(CALCULATE, delay_english)
        page.locator("#language").select_option("en")
        self.wait_until(lambda: bool(held))
        expect(page.locator("#export")).to_be_disabled()
        page.locator("#language").select_option("zh")
        expect(page.locator("#export")).to_be_enabled()
        expect(page.locator("#report-preview")).to_contain_text("计算报告")
        with page.expect_response(lambda response: response.request.post_data_json.get("language") == "en"):
            for route, response in held:
                route.fulfill(response=response)
        page.wait_for_timeout(100)
        self.assertEqual(page.evaluate("state.result.language"), "zh")
        expect(page.locator("#report-preview")).to_contain_text("计算报告")

    def wait_until(self, predicate, timeout_ms: int = 5000) -> None:
        for _ in range(timeout_ms // 20):
            if predicate():
                return
            self.page.wait_for_timeout(20)
        self.fail("condition not reached in time")

    def plate_rects(self, index: int):
        return self.page.locator(f'#section rect[data-role="plate-{index}"]')

    def enable_washers(self):
        self.page.get_by_role("tab", name="板层").click()
        for side, title in (("head", "头侧垫片"), ("nut", "螺母侧垫片（DSV）")):
            self.page.locator("summary").get_by_text(title, exact=True).click()
            self.page.locator(f"#f-{side}_washer-enabled").check()
        expect(self.metric("lK")).to_have_text("43.84 mm")

    def test_washers_autofill_allow_override_and_update_clamp(self):
        page = self.page
        self.enable_washers()
        expect(page.locator("#f-head_washer-inner_diameter")).to_have_value("13.2")
        expect(page.locator("#f-head_washer-outer_diameter")).to_have_value("24")
        expect(page.locator("#f-head_washer-thickness")).to_have_value("1.92")
        page.locator("#f-head_washer-thickness").fill("3")
        page.locator("#f-head_washer-outer_diameter").fill("30")
        expect(self.metric("lK")).to_have_text("44.92 mm")
        page.get_by_role("tab", name="螺栓", exact=True).click()
        page.locator("#f-bolt-catalog_variant_id").select_option("ISO4014-M16x2.0")
        expect(page.locator("#f-head_washer-inner_diameter")).to_have_value("17.6")
        expect(page.locator("#f-nut_washer-thickness")).to_have_value("2.56")
        expect(page.locator("#f-head_washer-thickness")).to_have_value("3")
        expect(page.locator("#f-head_washer-outer_diameter")).to_have_value("30")
        expect(self.metric("lK")).to_have_text("45.56 mm")
        page.get_by_role("tab", name="报告", exact=True).click()
        expect(page.locator("#report-preview")).to_contain_text("头侧垫片")
        expect(page.locator("#report-preview")).to_contain_text("不计载荷扩散")

    def test_clicking_each_part_activates_tab_expands_section_and_focuses_field(self):
        page = self.page
        self.enable_washers()
        for selector, field, tab in (
            ("polygon[data-role='bolt-head']", "bolt-head_height", "bolt"),
            ("rect[data-role='bolt-shank']", "bolt-length", "bolt"),
            ("polygon[data-role='bolt-thread']", "bolt-length", "bolt"),
            ("polygon[data-role='nut']", "nut-height", "bolt"),
            ("rect[data-role='washer-head']", "head_washer-thickness", "plates"),
            ("rect[data-role='washer-nut']", "nut_washer-thickness", "plates"),
        ):
            with self.subTest(part=selector):
                page.get_by_role("tab", name="载荷").click()
                page.locator(f"#section {selector}").first.click()
                expect(page.locator(f"#tab-{tab}")).to_have_attribute("aria-selected", "true")
                expect(page.locator(f"#f-{field}")).to_be_focused()
                expect(page.locator(f"#f-{field}")).to_be_in_viewport()
        self.assertLessEqual(page.evaluate("document.documentElement.scrollHeight"), page.evaluate("innerHeight"))
        page.locator("#section polygon[data-role='bolt-head']").focus()
        page.keyboard.press("Enter")
        expect(page.locator("#f-bolt-head_height")).to_be_focused()

    def test_washer_validation_and_material_selection(self):
        page = self.page
        self.enable_washers()
        page.locator("#f-head_washer-material_id").select_option("42CrMo4")
        expect(page.locator(".field[data-path='head_washer.youngs_modulus'] .src")).to_have_attribute("title", re.compile("42CrMo4"))
        page.locator("#f-head_washer-inner_diameter").fill("20")
        expect(page.get_by_role("alert")).to_contain_text("有效承压环面")
        expect(self.export).to_be_disabled()
        page.get_by_role("tab", name="载荷").click()
        page.get_by_role("alert").get_by_role("button").click()
        expect(page.locator("#f-head_washer-inner_diameter")).to_be_focused()
        page.locator("#f-head_washer-inner_diameter").fill("13.2")
        expect(self.export).to_be_enabled()

    def test_esv_ignores_nut_washer_and_removes_its_drawing(self):
        page = self.page
        self.enable_washers()
        page.get_by_role("tab", name="螺栓", exact=True).click()
        page.locator("#f-joint-type").select_option("ESV")
        expect(self.metric("lK")).to_have_text("41.92 mm")
        expect(page.locator("#section [data-role='washer-nut']")).to_have_count(0)
        expect(page.locator("#section [data-role='washer-head']").first).to_be_attached()
        page.get_by_role("tab", name="板层").click()
        expect(page.locator("#f-nut_washer-enabled")).to_be_hidden()
        page.get_by_role("tab", name="螺栓", exact=True).click()
        page.locator("#f-joint-type").select_option("DSV")
        expect(self.metric("lK")).to_have_text("43.84 mm")

    def test_bolt_friction_inputs_are_independent(self):
        page = self.page
        with page.expect_response(CALCULATE):
            page.locator("#f-bolt-bearing_friction").fill("0.10")
        with page.expect_response(CALCULATE) as response:
            page.locator("#f-bolt-thread_friction").fill("0.18")
        result = response.value.json()
        self.assertAlmostEqual(next(value["value"] for value in result["values"] if value["symbol"] == "μK"), 0.10)
        self.assertEqual(result["input"]["bolt"]["thread_friction"], 0.18)
        self.assertFalse(any("bearing_friction" in layer for layer in result["input"]["plates"]))
        expect(page.locator("#f-bolt-bearing_friction")).to_have_value("0.10")
        expect(page.locator("label[for='f-bolt-thread_friction']")).to_contain_text("螺纹摩擦 μG")
        expect(page.locator(".field[data-path='bolt.bearing_friction']")).to_be_visible()
        expect(page.locator(".field[data-path^='plates'][data-path$='.bearing_friction']")).to_have_count(0)

    def test_cyberpunk_theme_contrast_and_translucent_section(self):
        page = self.page
        palette = page.evaluate("""() => {
          const css = getComputedStyle(document.documentElement);
          return Object.fromEntries(['pane','input','text','muted','accent','purple','pass','pass-bg','fail','fail-bg','review','review-bg']
            .map(key => [key, css.getPropertyValue('--' + key).trim()]));
        }""")
        self.assertEqual(palette["accent"], "#00d9ff")
        self.assertEqual(palette["purple"], "#bd83ff")

        def luminance(color):
            channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
            return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

        for foreground, background in (("text", "pane"), ("muted", "input"), ("pass", "pass-bg"),
                                       ("fail", "fail-bg"), ("review", "review-bg")):
            values = sorted((luminance(palette[foreground]), luminance(palette[background])))
            self.assertGreaterEqual((values[1] + 0.05) / (values[0] + 0.05), 4.5)
        expect(page.locator("#section [data-role='background']")).to_have_attribute("fill", "#04101f")
        self.assertGreater(page.locator("#section [data-role='grid']").count(), 0)
        cones = page.locator("#section [data-role='cone']")
        expect(cones).to_have_count(2)
        for cone in cones.all():
            self.assertLessEqual(float(cone.get_attribute("fill-opacity")), 0.06)
        expect(page.locator("#f-bolt-d")).to_have_css("background-color", "rgb(6, 16, 31)")
        expect(page.locator("#f-bolt-d")).to_have_css("color", "rgb(214, 239, 255)")

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
        expect(page.locator("#verdict")).to_have_text("通过")
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
        expect(page.locator("#report-preview")).to_contain_text("总体判定：通过")
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
        expect(marker).to_have_class(re.compile(r"\bcatalog\b"))
        expect(self.export).to_be_enabled()
        expect(page.locator("#section > text").first).to_be_attached()
        expect(page.locator("#section")).to_contain_text("M16")
        page.locator("#f-bolt-head_height").fill("10.5")
        expect(page.locator('.field[data-path="bolt.head_height"] .src')).to_have_class("src")
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
        self.assertIn("总体判定：通过", text)

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
