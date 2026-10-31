from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import re
import unittest

from vdi2230.domain.general_inputs import FIELD_SPECS, LAYER_SPECS, default_input_json
from vdi2230.i18n import MESSAGES, MissingTranslationError, format_text, source_label, translate
from vdi2230.web.general_api import calculate_payload
from test_general_engine import b1_payload, b2_payload, b3_payload


class TranslationTests(unittest.TestCase):
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
                zh_status, zh = calculate_payload({"input": payload})
                en_status, en = calculate_payload({"input": payload, "language": "en"})
                self.assertEqual((zh_status, en_status), (200, 200))
                self.assertEqual(payload, original)
                self.assertEqual(zh["input"], en["input"])
                self.assertEqual(zh["metrics"], en["metrics"])
                self.assertEqual(zh["verdict"], en["verdict"])
                self.assertEqual(zh["provisional_sources"], en["provisional_sources"])
                self.assertIn("计算报告", zh["report"])
                self.assertIn("Calculation Report", en["report"])
                self.assertIn("Warnings and assumptions", en["report"])
                self.assertNotRegex(en["report"], r"[\u4e00-\u9fff]")
                for first, second in zip(zh["values"], en["values"]):
                    self.assertEqual((first["symbol"], first["value"], first["unit"]),
                                     (second["symbol"], second["value"], second["unit"]))
                    for key in ("label", "note", "formula_reference"):
                        self.assertNotRegex(second[key], r"[\u4e00-\u9fff]")
                for first, second in zip(zh["checks"], en["checks"]):
                    for key in ("symbol", "value", "required", "unit", "status"):
                        self.assertEqual(first[key], second[key])
                    self.assertNotRegex(second["label"] + second["status_label"] + second["note"], r"[\u4e00-\u9fff]")
                for first, second in zip(zh["section"]["shapes"], en["section"]["shapes"]):
                    self.assertEqual(first["points"], second["points"])
                    self.assertEqual(first["target"], second["target"])
                    self.assertNotRegex(second["text"], r"[\u4e00-\u9fff]")
                    self.assertEqual(first["text_by_language"]["en"], second["text"])

    def test_free_text_survives_english_report_and_drawing(self):
        payload = default_input_json()
        payload["title"] = "项目标题不翻译 <script>"
        payload["plates"][0]["name"] = "用户板层"
        payload["provenance"]["bolt.d"] = "manual:用户确认"
        status, result = calculate_payload({"input": payload, "language": "en"})
        self.assertEqual(status, 200)
        self.assertIn(payload["title"], result["report"])
        self.assertIn("用户板层", result["report"])
        self.assertIn("manual:用户确认", result["report"])
        self.assertTrue(any("用户板层" in shape["text"] for shape in result["section"]["shapes"]))

    def test_invalid_language_and_translated_field_errors(self):
        for language in ("fr", None, [], 1):
            status, data = calculate_payload({"input": default_input_json(), "language": language})
            self.assertEqual(status, 400)
            self.assertIn("Unsupported language", data["error"])
        for path, value in (("d", -1), ("bearing_friction", "abc"), ("thread_friction", 2)):
            payload = default_input_json()
            payload["bolt"][path] = value
            status, data = calculate_payload({"input": payload, "language": "en"})
            self.assertEqual(status, 400)
            self.assertIn("Invalid input", data["error"])
            self.assertTrue(data["field_errors"])
            for error in data["field_errors"]:
                self.assertNotRegex(error["message"], r"[\u4e00-\u9fff]")

    def test_parallel_clients_do_not_share_language_state(self):
        def calculate(language):
            _, data = calculate_payload({"input": default_input_json(), "language": language})
            return language, bool(re.search(r"计算报告", data["report"]))
        with ThreadPoolExecutor(max_workers=4) as pool:
            for language, chinese in pool.map(calculate, ["zh", "en"] * 4):
                self.assertEqual(chinese, language == "zh")
