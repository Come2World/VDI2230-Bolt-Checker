import unittest

from test_general_engine import b3_payload
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
        self.assertIn("[material:S355J0]", text)
        self.assertIn("[catalog:ISO4014-M12x1.75]", text)

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
