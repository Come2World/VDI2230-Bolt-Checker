import unittest
from collections import Counter
from dataclasses import replace
import re

from test_general_engine import b1_payload, b3_payload
from vdi2230.calculations.general import calculate_general
from vdi2230.domain.general_inputs import default_input_json, parse_general_input
from vdi2230.infrastructure.general_report import render_general_report
from vdi2230.infrastructure.report import DISCLAIMER
from vdi2230.ui.general_model import GeneralFormModel


def report_for(payload) -> tuple[object, str]:
    result = calculate_general(parse_general_input(payload))
    return result, render_general_report(result, calculated_at="2025-01-01T00:00:00+00:00")


class GeneralReportTests(unittest.TestCase):
    def test_report_contains_verdict_checks_and_sections(self) -> None:
        result, text = report_for(default_input_json())
        self.assertIn("计算时间（UTC）：2025-01-01T00:00:00+00:00", text)
        self.assertIn("总体判定：通过", text)
        for heading in ("一、安全系数与校核", "二、输入参数", "三、计算过程与全部结果", "四、待核验数据来源", "五、警告与假设"):
            self.assertIn(heading, text)
        for check in result.checks:
            self.assertIn(check.label, text)
        self.assertTrue(text.rstrip().endswith(DISCLAIMER))
        self.assertTrue(text.startswith("# VDI"))
        self.assertIn("## 一、安全系数与校核", text)
        self.assertIn("| --- | --- |", text)
        self.assertNotIn("=" * 72, text)

    def test_model_assumptions_are_still_flagged(self) -> None:
        result, text = report_for(b3_payload())
        self.assertTrue(result.provisional_sources)
        self.assertIn("数据待核验", text)
        for source in result.provisional_sources:
            self.assertIn(source, text)

    def test_user_only_input_has_no_provisional_section_entries(self) -> None:
        payload = default_input_json()
        payload["provenance"] = {}
        payload["load"]["axial_max"] = 0.0
        payload["embedding"]["mode"] = "manual"
        result, text = report_for(payload)
        self.assertEqual(result.provisional_sources, ())
        self.assertIn("无（使用用户输入或项目采信数据）", text)
        self.assertNotIn("注意：数据待核验", text)

    def test_layers_and_sources_are_listed(self) -> None:
        _, text = report_for(default_input_json())
        self.assertIn("共 2 层", text)
        self.assertIn("1. 板 1", text)
        self.assertIn("2. 板 2", text)
        self.assertIn(r"\[material:S355J0\]", text)
        self.assertIn(r"\[catalog:ISO4014-M12x1.75\]", text)

    def test_r1_to_r13_order_and_every_result_appears_once_in_its_step(self):
        payloads = [default_input_json(), b1_payload(), b3_payload()]
        payload = default_input_json()
        payload["bolt"]["rolling"] = "SG"
        payload["load"].update(transverse=1000, cycles=100000)
        payload["head_washer"]["enabled"] = True
        payloads.append(payload)
        for payload in payloads:
            for language in ("zh", "en"):
                with self.subTest(joint=payload["joint"]["type"], language=language):
                    result = calculate_general(parse_general_input(payload))
                    text = render_general_report(result, language=language)
                    blocks = re.split(r"^### R(\d+) — .+$", text, flags=re.MULTILINE)
                    self.assertEqual([int(blocks[i]) for i in range(1, len(blocks), 2)], list(range(1, 14)))
                    steps = {int(blocks[i]): blocks[i + 1].split("\n## ", 1)[0] for i in range(1, len(blocks), 2)}
                    occurrences = Counter()
                    for step, body in steps.items():
                        for symbol in re.findall(r"^\| ([^|]+?) \|", body, re.MULTILINE):
                            occurrences[symbol] += 1
                    for value in result.result.values:
                        self.assertEqual(occurrences[value.symbol], 1, value.symbol)
                        self.assertIn(f"| {value.symbol} |", steps[value.calculation_step])
                    for symbol, step in (("FKerf", 2), ("δS", 3), ("fZ", 4), ("FMmin", 5), ("FMmax", 6),
                                         ("FMzul", 7), ("SF", 8), ("σa", 9), ("mvorh", 11), ("FKRmin", 12), ("MA", 13)):
                        self.assertIn(f"| {symbol} |", steps[step])
                    self.assertIn(f"αA = {result.input.assembly.tightening_factor:g}", steps[1])
                    if any(value.symbol == "SD" for value in result.result.values):
                        self.assertIn("| SD |", steps[9])
                        self.assertIn("\n\n- SD:", steps[9])
                    self.assertEqual(result.check("mges").reference, "R11")

    def test_missing_step_is_explicit_instead_of_dropping_a_result(self):
        result = calculate_general(parse_general_input(default_input_json()))
        value = replace(result.result.values[0], calculation_step=None)
        result = replace(result, result=replace(result.result, values=(value,)))
        with self.assertRaisesRegex(ValueError, "Missing VDI calculation step"):
            render_general_report(result)

    def test_markdown_escapes_user_text_without_injecting_rows_or_headings(self):
        payload = default_input_json()
        payload["title"] = "Design | A\n## Fake <script>*bold*</script>"
        payload["plates"][0]["name"] = "plate | [link](x)"
        payload["provenance"]["bolt.d"] = "manual:a|b"
        _, text = report_for(payload)
        self.assertIn(r"Design \| A<br>\#\# Fake &lt;script&gt;\*bold\*&lt;/script&gt;", text)
        self.assertIn(r"plate \| \[link\](x)", text)
        self.assertNotIn("\n## Fake", text)
        self.assertNotIn("<script>", text)

    def test_non_applicable_checks_are_explained_in_their_steps(self):
        payload = default_input_json()
        payload["load"]["axial_max"] = payload["load"]["axial_min"] = 0
        result, text = report_for(payload)
        r9 = text.split("### R9 —", 1)[1].split("### R10", 1)[0]
        r11 = text.split("### R11 —", 1)[1].split("### R12", 1)[0]
        r12 = text.split("### R12 —", 1)[1].split("### R13", 1)[0]
        self.assertIn("无交变轴向载荷", r9)
        self.assertIn("mges: 不适用", r11)
        self.assertIn("SG: 不适用", r12)
        self.assertIn("SA: 不适用", r12)

    def test_irrelevant_fields_are_omitted(self) -> None:
        _, dsv = report_for(default_input_json())
        _, esv = report_for(b3_payload())
        self.assertIn("螺母高度 m", dsv)
        self.assertNotIn("内螺纹件 EM", dsv)
        self.assertIn("内螺纹件 EM", esv)
        self.assertNotIn("螺母高度 m", esv)
        self.assertNotIn("n (手动)", dsv)
        self.assertNotIn("内六角深度 t =", dsv)

    def test_socket_report_contains_filled_dimensions_in_both_languages(self) -> None:
        model = GeneralFormModel()
        model.set_value("bolt.head_type", "socket")
        zh = model.calculate("zh")
        self.assertTrue(zh.ok, zh.error)
        for text in ("头部直径 dk = 18", "内六角对边 s = 10", "内六角深度 t = 6"):
            self.assertIn(text, zh.report)
        self.assertNotIn("头部对边 s =", zh.report)
        model.set_language("en")
        en = model.calculate("en")
        self.assertTrue(en.ok, en.error)
        for text in ("Head diameter dk = 18", "Socket size s = 10", "Socket depth t = 6"):
            self.assertIn(text, en.report)
        self.assertNotIn("Head width across flats s =", en.report)

    def test_not_applicable_checks_explain_reason(self) -> None:
        _, text = report_for(b3_payload())
        self.assertIn("不适用", text)
        self.assertIn("无交变轴向载荷", text)

    def test_a2_review_reasons_and_supplier_reference_are_bilingual(self) -> None:
        model = GeneralFormModel()
        model.set_value("bolt.property_class", "A2-90")
        model.set_value("bolt.shear_ratio", 0.7)
        model.set_value("load.transverse", 500)
        zh = model.calculate("zh")
        self.assertTrue(zh.ok, zh.error)
        self.assertIn("厂商", zh.report)
        self.assertIn("疲劳", zh.report)
        self.assertIn("需确认", zh.report)
        model.set_language("en")
        en = model.calculate("en")
        self.assertTrue(en.ok, en.error)
        self.assertNotRegex(en.report, r"[\u4e00-\u9fff]")
        self.assertIn("supplier", en.report.lower())
        self.assertIn("fatigue", en.report.lower())
        self.assertIn("Bolt input: (τB/Rm)·Rm", en.report)
        self.assertEqual(zh.result.checks, en.result.checks)


if __name__ == "__main__":
    unittest.main()
