from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import re
from string import Formatter
import unittest

from vdi2230.domain.general_inputs import FIELD_SPECS, LAYER_SPECS, default_input_json
from vdi2230.i18n import MESSAGES, TEMPLATES, MissingTranslationError, format_text, language_code, source_label, translate
from vdi2230.infrastructure.general_section import general_section_shapes, section_target
from vdi2230.ui.general_model import GeneralFormModel
from test_general_engine import b1_payload, b2_payload, b3_payload


class TranslationTests(unittest.TestCase):
    def calculate_form(self, payload, language="zh"):
        model = GeneralFormModel()
        model.reset(payload)
        return model.calculate(language)

    def test_specific_validation_template_precedes_its_shorter_prefix(self):
        message = "须大于夹紧长度 lK = 92.88，留出旋合长度"
        self.assertEqual(translate(message, "en"), "Must exceed grip length lK = 92.88 to allow thread engagement")

    def test_every_formatted_template_matches_its_own_translation(self):
        for source in TEMPLATES:
            values = {name: "1" for _, name, _, _ in Formatter().parse(source) if name}
            with self.subTest(source=source):
                self.assertEqual(translate(source.format(**values), "en"), format_text(source, "en", **values))

    def test_catalog_and_all_input_metadata_have_english_translations(self):
        for source, english in MESSAGES.items():
            with self.subTest(source=source):
                self.assertEqual(translate(source, "en"), english)
                self.assertEqual(translate(source), source)
                self.assertNotRegex(english, r"[\u4e00-\u9fff]")
        for spec in (*FIELD_SPECS, *LAYER_SPECS):
            for text in (spec.label, spec.help, *(label for _, label in spec.choices)):
                self.assertNotRegex(translate(text, "en"), r"[\u4e00-\u9fff]")

    def test_formatting_preserves_user_text_and_unknown_messages_are_explicit(self):
        self.assertEqual(format_text("已导出 {name}", "en", name="项目报告.txt"), "Exported 项目报告.txt")
        self.assertEqual(source_label("bolt.d ← manual:用户确认", "en"), "bolt.d ← manual:用户确认")
        with self.assertRaisesRegex(MissingTranslationError, "Missing English translation"):
            translate("没有译文的应用文案", "en")
        with self.assertRaisesRegex(MissingTranslationError, "Missing English translation"):
            format_text("没有译文的应用文案", "en")

    def test_both_report_languages_preserve_calculations_and_cover_general_modes(self):
        washer = default_input_json()
        washer["head_washer"]["enabled"] = washer["nut_washer"]["enabled"] = True
        for payload in (default_input_json(), washer, b1_payload(), b2_payload(), b3_payload()):
            payload["title"] = "Design"
            for index, plate in enumerate(payload["plates"]):
                plate["name"] = f"Part {index + 1}"
            original = deepcopy(payload)
            with self.subTest(type=payload["joint"]["type"], diameter=payload["bolt"]["d"]):
                zh = self.calculate_form(payload)
                en = self.calculate_form(payload, "en")
                self.assertTrue(zh.ok, zh.error)
                self.assertTrue(en.ok, en.error)
                assert zh.result is not None and en.result is not None
                self.assertEqual(payload, original)
                self.assertEqual(zh.result.input, en.result.input)
                self.assertEqual(zh.result.metrics, en.result.metrics)
                self.assertEqual(zh.result.verdict, en.result.verdict)
                self.assertEqual(zh.result.provisional_sources, en.result.provisional_sources)
                self.assertIn("计算报告", zh.report)
                self.assertIn("Calculation Report", en.report)
                self.assertIn("Warnings and assumptions", en.report)
                self.assertNotRegex(en.report, r"[\u4e00-\u9fff]")
                self.assertEqual(zh.result.result.values, en.result.result.values)
                self.assertEqual(zh.result.checks, en.result.checks)
                for value in en.result.result.values:
                    for text in (value.label, value.note, value.formula_reference):
                        self.assertNotRegex(translate(text, "en"), r"[\u4e00-\u9fff]")
                for check in en.result.checks:
                    for text in (check.label, check.status.value, check.note, check.reference):
                        self.assertNotRegex(translate(text, "en"), r"[\u4e00-\u9fff]")
                zh_shapes = general_section_shapes(zh.result.input, zh.result.metrics, 640, 560)
                en_shapes = general_section_shapes(en.result.input, en.result.metrics, 640, 560, language="en")
                self.assertEqual(len(zh_shapes), len(en_shapes))
                for first, second in zip(zh_shapes, en_shapes):
                    self.assertEqual(first.points, second.points)
                    self.assertEqual(section_target(first.role), section_target(second.role))
                    self.assertNotRegex(second.text, r"[\u4e00-\u9fff]")

    def test_free_text_survives_english_report_and_drawing(self):
        payload = default_input_json()
        payload["title"] = "项目标题不翻译 <script>"
        payload["plates"][0]["name"] = "用户板层"
        payload["provenance"]["bolt.d"] = "manual:用户确认"
        outcome = self.calculate_form(payload, "en")
        self.assertTrue(outcome.ok, outcome.error)
        assert outcome.result is not None
        self.assertIn("项目标题不翻译 &lt;script&gt;", outcome.report)
        self.assertNotIn("<script>", outcome.report)
        self.assertIn("用户板层", outcome.report)
        self.assertIn("manual:用户确认", outcome.report)
        shapes = general_section_shapes(outcome.result.input, outcome.result.metrics, 640, 560, language="en")
        self.assertTrue(any("用户板层" in shape.text for shape in shapes))

    def test_invalid_language_and_translated_field_errors(self):
        for language in ("fr", None, [], 1):
            with self.assertRaisesRegex(ValueError, "Unsupported language"):
                language_code(language)
        for path, value in (("d", -1), ("bearing_friction", "abc"), ("thread_friction", 2)):
            payload = default_input_json()
            payload["bolt"][path] = value
            outcome = self.calculate_form(payload, "en")
            self.assertFalse(outcome.ok)
            self.assertIn("Invalid input", outcome.error)
            self.assertTrue(outcome.field_errors)
            for error in outcome.field_errors:
                self.assertNotRegex(error.message, r"[\u4e00-\u9fff]")

    def test_independent_form_models_do_not_share_language_state(self):
        def calculate(language):
            outcome = self.calculate_form(default_input_json(), language)
            self.assertTrue(outcome.ok, outcome.error)
            return language, bool(re.search(r"计算报告", outcome.report))
        with ThreadPoolExecutor(max_workers=4) as pool:
            for language, chinese in pool.map(calculate, ["zh", "en"] * 4):
                self.assertEqual(chinese, language == "zh")
