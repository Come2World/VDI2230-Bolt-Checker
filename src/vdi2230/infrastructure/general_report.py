"""Plain-text report for the general VDI 2230 calculation."""
from __future__ import annotations

from datetime import datetime, timezone

from vdi2230 import __version__
from vdi2230.calculations.general import GeneralCalculationResult
from vdi2230.domain.general_inputs import FIELD_SPECS, LAYER_SPECS, FieldSpec, GeneralInput
from vdi2230.domain.models import ResultStatus
from vdi2230.infrastructure.report import DISCLAIMER


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


def _field_value(spec: FieldSpec, value: object) -> str:
    if value is None:
        return f"（空：{spec.help}）" if spec.help else "（空）"
    if spec.kind == "choice":
        return dict(spec.choices).get(value, str(value))
    if spec.kind == "bool":
        return "是" if value else "否"
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


def _source(item: GeneralInput, path: str) -> str:
    source = item.provenance.get(path)
    return f"  [{source}]" if source else ""


def render_general_report(
    result: GeneralCalculationResult,
    *,
    calculated_at: str | None = None,
) -> str:
    item = result.input
    timestamp = calculated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "VDI 2230 螺栓连接计算报告（通用同心单螺栓）",
        RULE,
        f"项目标题：{item.title}",
        f"软件版本：{__version__}",
        f"计算时间（UTC）：{timestamp}",
        f"计算模型：{result.result.model_name}",
        f"计算依据：{result.result.source_reference}",
        f"连接类型：{'通孔螺栓 + 螺母 (DSV)' if item.is_through_bolt else '螺纹孔连接 (ESV)'}",
        f"总体判定：{result.verdict_label}",
    ]
    if result.provisional_sources:
        lines.append("注意：数据待核验——使用了未经核验的数据或模型假设，结果不得作为最终结论。")

    lines += ["", "一、安全系数与校核", THIN_RULE]
    lines.append(f"{'符号':<8}{'校核项':<22}{'计算值':>14}{'要求值':>12}  状态")
    for check in result.checks:
        unit = f" {check.unit}" if check.unit else ""
        value = _number(check.value) + unit if check.value is not None else "—"
        required = _number(check.required) + unit if check.required is not None else "—"
        note = f"  （{check.note}）" if check.note and check.status == ResultStatus.NOT_APPLICABLE else ""
        lines.append(f"{check.symbol:<8}{check.label:<22}{value:>14}{required:>12}  {check.status.value} · {check.reference}{note}")

    lines += ["", "二、输入参数", THIN_RULE]
    for group, title in GROUP_TITLES:
        lines.append(f"[{title}]")
        for spec in FIELD_SPECS:
            if spec.group != group or not _relevant(item, spec.path):
                continue
            value = _input_value(item, spec.path)
            unit = f" {spec.unit}" if spec.unit and value is not None else ""
            prefix = {"head_washer": "头侧垫片 · ", "nut_washer": "螺母侧垫片 · "}.get(spec.path.split(".")[0], "")
            lines.append(f"  {prefix}{spec.label} = {_field_value(spec, value)}{unit}{_source(item, spec.path)}")
        if group == "plates":
            lines.append(f"  板层（自螺栓头侧起，共 {len(item.plates)} 层，Σh = {_number(item.plate_length)} mm；含垫片 lK = {_number(item.clamp_length)} mm）：")
            for index, layer in enumerate(item.plates):
                parts = []
                for spec in LAYER_SPECS:
                    if spec.name == "name":
                        continue
                    value = getattr(layer, spec.name)
                    rendered = _field_value(spec, value) if value is not None else "自定义"
                    unit = f" {spec.unit}" if spec.unit and value is not None else ""
                    parts.append(f"{spec.label} {rendered}{unit}")
                lines.append(f"    {index + 1}. {layer.name}：" + "；".join(parts))
                for spec in LAYER_SPECS:
                    path = f"plates[{index}].{spec.name}"
                    if path in item.provenance:
                        lines.append(f"       {spec.label} 来源 [{item.provenance[path]}]")

    lines += ["", "三、计算过程与全部结果", THIN_RULE]
    for value in result.result.values:
        unit = f" {value.unit}" if value.unit else ""
        number = value.value if isinstance(value.value, (int, float)) else None
        lines.append(f"{value.symbol} ({value.label}) = {_number(number)}{unit} | 依据：{value.formula_reference}")
        if value.note:
            lines.append(f"  说明：{value.note}")

    lines += ["", "四、待核验数据来源", THIN_RULE]
    lines.extend(f"- {source}" for source in result.provisional_sources)
    if not result.provisional_sources:
        lines.append("- 无（全部为用户输入或已核验数据）")

    lines += ["", "五、警告与假设", THIN_RULE]
    lines.extend(f"- {warning}" for warning in result.warnings)
    lines += [
        "- 适用范围：同心单螺栓，轴向载荷 + 横向载荷/扭矩；不含偏心、弯曲、温度影响和螺栓组分配。",
        "- R10 工作面压取 FVmax = FMzul − FZ；DSV 采用 w = 1，两侧锥体起始直径分别取螺栓头与螺母 dW。",
        "- R11 公差按 ISO 965-1 6g/6H 公式近似；断裂力取 Rm,max·A0（A0 = min(AS, AT)）。",
        "- μK 与 μG 在螺栓页分别独立输入；垫片不随拧紧件转动，力矩使用紧固件/垫片接触环面，不使用垫片外径代替 dW。",
        "- 平垫片初始尺寸：di = 1.1d、Do = 2d、t = 0.16d；仅为经验估计，不代表 ISO 标准尺寸。",
        "- 垫片有效环面：Deff = min(dW, Do, DA)，di,eff = max(di, dh, dha)；δW = t/(EW·Aeff)。不计载荷扩散；邻接板层按较大的 di/dh 孔径保守积分，锥长度不含垫片。",
        "- Sp,K / Sp,M 取对应板层与垫片校核的最小值；垫片分别检查两接触面。嵌入界面数覆盖包含垫片/板层界面；手动 fZ 必须自行包含垫片影响。",
    ]
    lines += ["", DISCLAIMER, ""]
    return "\n".join(lines)
