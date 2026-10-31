"""Plain-text report for the general VDI 2230 calculation."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import partial

from vdi2230 import __version__
from vdi2230.calculations.general import GeneralCalculationResult
from vdi2230.domain.general_inputs import FIELD_SPECS, LAYER_SPECS, FieldSpec, GeneralInput
from vdi2230.domain.models import ResultStatus
from vdi2230.infrastructure.report import DISCLAIMER
from vdi2230.i18n import Language, format_text, language_code, source_label, translate


GROUP_TITLES = (
    ("bolt", "连接、螺栓与螺母/内螺纹件"),
    ("plates", "被夹件几何"),
    ("load", "载荷"),
    ("assembly", "装配与校核要求"),
)
RULE = "=" * 72
THIN_RULE = "-" * 72


def _number(value: float | None) -> str:
    if value is None:
        return "—"
    if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e7):
        return f"{value:.4e}"
    return f"{value:.6g}"


def _field_value(spec: FieldSpec, value: object, language: Language = "zh") -> str:
    t = partial(translate, language=language)
    if value is None:
        return f"({t(spec.help)})" if language == "en" and spec.help else (f"（空：{spec.help}）" if spec.help else t("（空）"))
    if spec.kind == "choice":
        return t(dict(spec.choices).get(value, str(value)))
    if spec.kind == "bool":
        return t("是" if value else "否")
    if isinstance(value, float):
        return _number(value)
    return str(value)


def _relevant(item: GeneralInput, path: str) -> bool:
    if path.startswith(("head_washer.", "nut_washer.")):
        section, name = path.split(".")
        if section == "nut_washer" and not item.is_through_bolt:
            return False
        return name == "enabled" or getattr(item, section).enabled
    if path.startswith("nut."):
        return item.is_through_bolt
    if path.startswith("tapped."):
        return not item.is_through_bolt
    if path == "load_introduction.n":
        return item.load_introduction.mode == "manual"
    if path in {"load_introduction.joint_class", "load_introduction.la_over_h", "load_introduction.ak_over_h"}:
        return item.load_introduction.mode == "table"
    if path == "embedding.fz_um":
        return item.embedding.mode == "manual"
    if path == "embedding.interface_count":
        return item.embedding.mode == "table"
    return True


def _input_value(item: GeneralInput, path: str) -> object:
    section, name = path.split(".", 1)
    return getattr(getattr(item, section), name)


def _source(item: GeneralInput, path: str, language: Language = "zh") -> str:
    source = item.provenance.get(path)
    return f"  [{source_label(source, language)}]" if source else ""


def render_general_report(
    result: GeneralCalculationResult,
    *,
    calculated_at: str | None = None,
    language: Language = "zh",
) -> str:
    language_code(language)
    t = partial(translate, language=language)
    colon = "：" if language == "zh" else ": "
    item = result.input
    timestamp = calculated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        t("VDI 2230 螺栓连接计算报告（通用同心单螺栓）"),
        RULE,
        f"{t('项目标题')}{colon}{item.title}",
        f"{t('软件版本')}{colon}{__version__}",
        f"{t('计算时间（UTC）')}{colon}{timestamp}",
        f"{t('计算模型')}{colon}{t(result.result.model_name)}",
        f"{t('计算依据')}{colon}{t(result.result.source_reference)}",
        f"{t('连接类型')}{colon}{t('通孔螺栓 + 螺母 (DSV)' if item.is_through_bolt else '螺纹孔连接 (ESV)')}",
        f"{t('总体判定')}{colon}{t(result.verdict_label)}",
    ]
    if result.provisional_sources:
        lines.append(t("注意：数据待核验——使用了未经核验的数据或模型假设，结果不得作为最终结论。"))

    lines += ["", t("一、安全系数与校核"), THIN_RULE]
    label_width = max([22, *(len(t(check.label)) + 2 for check in result.checks)])
    lines.append(f"{t('符号'):<8}{t('校核项'):<{label_width}}{t('计算值'):>14}{t('要求值'):>12}  {t('状态')}")
    for check in result.checks:
        unit = f" {check.unit}" if check.unit else ""
        value = _number(check.value) + unit if check.value is not None else "—"
        required = _number(check.required) + unit if check.required is not None else "—"
        left, right = ("（", "）") if language == "zh" else ("(", ")")
        note = f"  {left}{t(check.note)}{right}" if check.note and check.status == ResultStatus.NOT_APPLICABLE else ""
        lines.append(f"{check.symbol:<8}{t(check.label):<{label_width}}{value:>14}{required:>12}  {t(check.status.value)} · {t(check.reference)}{note}")

    lines += ["", t("二、输入参数"), THIN_RULE]
    for group, title in GROUP_TITLES:
        lines.append(f"[{t(title)}]")
        for spec in FIELD_SPECS:
            if spec.group != group or not _relevant(item, spec.path):
                continue
            value = _input_value(item, spec.path)
            unit = f" {spec.unit}" if spec.unit and value is not None else ""
            prefix = {"head_washer": t("头侧垫片") + " · ", "nut_washer": t("螺母侧垫片") + " · "}.get(spec.path.split(".")[0], "")
            lines.append(f"  {prefix}{t(spec.label)} = {_field_value(spec, value, language)}{unit}{_source(item, spec.path, language)}")
        if group == "plates":
            lines.append("  " + format_text("板层（自螺栓头侧起，共 {count} 层，Σh = {length} mm；含垫片 lK = {grip} mm）：", language,
                                          count=len(item.plates), length=_number(item.plate_length), grip=_number(item.clamp_length)))
            for index, layer in enumerate(item.plates):
                parts = []
                for spec in LAYER_SPECS:
                    if spec.name == "name":
                        continue
                    value = getattr(layer, spec.name)
                    rendered = _field_value(spec, value, language) if value is not None else t("自定义")
                    unit = f" {spec.unit}" if spec.unit and value is not None else ""
                    parts.append(f"{t(spec.label)} {rendered}{unit}")
                lines.append(f"    {index + 1}. {layer.name}{colon}" + ("；" if language == "zh" else "; ").join(parts))
                for spec in LAYER_SPECS:
                    path = f"plates[{index}].{spec.name}"
                    if path in item.provenance:
                        lines.append(f"       {t(spec.label)} {t('来源')}{_source(item, path, language)}")

    lines += ["", t("三、计算过程与全部结果"), THIN_RULE]
    for value in result.result.values:
        unit = f" {value.unit}" if value.unit else ""
        number = value.value if isinstance(value.value, (int, float)) else None
        lines.append(f"{value.symbol} ({t(value.label)}) = {_number(number)}{unit} | {t('依据')}{colon}{t(value.formula_reference)}")
        if value.note:
            lines.append(f"  {t('说明')}{colon}{t(value.note)}")

    lines += ["", t("四、待核验数据来源"), THIN_RULE]
    lines.extend(f"- {source_label(source, language)}" for source in result.provisional_sources)
    if not result.provisional_sources:
        lines.append("- " + t("无（使用用户输入或项目采信数据）"))

    lines += ["", t("五、警告与假设"), THIN_RULE]
    lines.extend(f"- {t(warning)}" for warning in result.warnings)
    lines += [t(line) for line in [
        "- 适用范围：同心单螺栓，轴向载荷 + 横向载荷/扭矩；不含偏心、弯曲、温度影响和螺栓组分配。",
        "- R10 工作面压取 FVmax = FMzul − FZ；DSV 采用 w = 1，两侧锥体起始直径分别取螺栓头与螺母 dW。",
        "- R11 公差按 ISO 965-1 6g/6H 公式近似；断裂力取 Rm,max·A0（A0 = min(AS, AT)）。",
        "- μK 与 μG 在螺栓页分别独立输入；垫片不随拧紧件转动，力矩使用紧固件/垫片接触环面，不使用垫片外径代替 dW。",
        "- 平垫片初始尺寸：di = 1.1d、Do = 2d、t = 0.16d；仅为经验估计，不代表 ISO 标准尺寸。",
        "- 垫片有效环面：Deff = min(dW, Do, DA)，di,eff = max(di, dh, dha)；δW = t/(EW·Aeff)。不计载荷扩散；邻接板层按较大的 di/dh 孔径保守积分，锥长度不含垫片。",
        "- Sp,K / Sp,M 取对应板层与垫片校核的最小值；垫片分别检查两接触面。嵌入界面数覆盖包含垫片/板层界面；手动 fZ 必须自行包含垫片影响。",
    ]]
    lines += ["", t(DISCLAIMER), ""]
    return "\n".join(lines)
