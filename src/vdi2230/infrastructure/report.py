from vdi2230 import __version__
from vdi2230.domain.models import CalculationResult, ProjectSnapshot


DISCLAIMER = (
    "工程辅助计算报告，不替代正式标准、专业工程判断或设计审查。"
)


def render_text_report(
    project: ProjectSnapshot,
    result: CalculationResult,
) -> str:
    if project.case_id != result.case_id:
        raise ValueError("Project and calculation result case IDs do not match")

    lines = [
        "VDI 2230 螺栓连接计算报告",
        f"软件版本：{__version__}",
        f"计算时间（UTC）：{result.calculated_at}",
        f"计算案例：{result.case_id} — {result.model_name}",
        f"项目标题：{project.title}",
        f"计算依据：{result.source_reference}",
        f"整体判定：{result.overall_status.value}",
        f"计算完整性：{'完整' if result.is_fully_calculated else '不完整'}",
        "",
        "一、输入快照",
    ]
    for key, value in project.inputs.items():
        unit = project.input_units.get(key, "")
        source = project.input_sources.get(key, "")
        rendered_unit = f" {unit}" if unit else ""
        rendered_source = f" [{source}]" if source else ""
        lines.append(f"{key} = {value}{rendered_unit}{rendered_source}")
    for key, value in project.metadata.items():
        lines.append(f"{key} = {value}")

    lines.extend(["", "二、假设"])
    lines.extend(f"- {assumption}" for assumption in project.assumptions)
    if not project.assumptions:
        lines.append("- 无")

    lines.extend(["", "三、计算结果"])
    for item in result.values:
        rendered_value = (
            "未提供" if item.value is None else str(item.value)
        )
        unit = f" {item.unit}" if item.unit else ""
        lines.append(
            f"{item.symbol} ({item.label}) = {rendered_value}{unit}"
            f" | 状态：{item.status.value}"
            f" | 依据：{item.formula_reference}"
        )
        if item.reference_value is not None:
            if item.reference_value == 0:
                error = (
                    "未计算"
                    if item.absolute_error is None
                    else f"{item.absolute_error:g}{unit}"
                )
                tolerance = (
                    "未指定"
                    if item.absolute_tolerance is None
                    else f"{item.absolute_tolerance:g}{unit}"
                )
                lines.append(
                    f"  参考值：0{unit}；绝对误差：{error}"
                    f"；绝对容差：{tolerance}"
                )
            else:
                error = (
                    "未计算"
                    if item.relative_error_percent is None
                    else f"{item.relative_error_percent:.3f}%"
                )
                lines.append(
                    f"  参考值：{item.reference_value:g}{unit}"
                    f"；相对误差：{error}"
                )
        if item.note:
            lines.append(f"  说明：{item.note}")

    lines.extend(["", "四、警告"])
    lines.extend(f"- {warning}" for warning in result.warnings)
    if not result.warnings:
        lines.append("- 无")

    lines.extend(["", DISCLAIMER, ""])
    return "\n".join(lines)
