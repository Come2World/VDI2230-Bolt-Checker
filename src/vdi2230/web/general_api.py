"""JSON handlers for the general (parameterised) VDI 2230 calculator.

Handlers are plain functions returning ``(status, payload)`` so they can be
tested without HTTP; ``server.py`` only does transport and security checks.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import logging
import math
from typing import Any
from urllib.parse import parse_qs

from vdi2230 import data as engineering_data
from vdi2230.calculations.general import GeneralCalculationResult, calculate_general
from vdi2230.domain.general_inputs import (
    InputValidationError,
    field_schema_json,
    parse_general_input,
)
from vdi2230.infrastructure.general_report import render_general_report
from vdi2230.infrastructure.general_section import MAX_VIEW, MIN_VIEW, general_section_shapes, section_target


LOGGER = logging.getLogger(__name__)
DEFAULT_VIEW = (640.0, 520.0)
Response = tuple[int, dict[str, Any]]


def _json_safe(value: Any) -> Any:
    """Replace non-finite floats (e.g. a safety factor of inf at zero load) with None for strict JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def schema_payload() -> Response:
    return 200, field_schema_json()


def catalog_payload() -> Response:
    return 200, {**engineering_data.catalog_summary(), "friction_classes": list(engineering_data.friction_classes())}


def catalog_values_payload(query: str) -> Response:
    params = parse_qs(query, keep_blank_values=True)
    if set(params) != {"variant", "length", "class"} or any(len(v) != 1 for v in params.values()):
        return 400, {"error": "需要且仅需要 variant、length、class 三个参数。"}
    variant, length_text, property_class = (params[key][0] for key in ("variant", "length", "class"))
    try:
        length = float(length_text)
        if not math.isfinite(length) or length <= 0:
            raise ValueError
    except ValueError:
        return 400, {"error": "螺栓长度必须是正数。"}
    try:
        values = engineering_data.bolt_catalog_values(variant, length, property_class)
        sources = engineering_data.catalog_value_sources(variant, property_class)
    except (KeyError, ValueError, StopIteration):
        return 400, {"error": f"目录中没有 {variant} / {property_class} 的组合。"}
    return 200, {
        "values": values,
        "sources": sources,
        "provisional": sorted(path for path, source in sources.items() if engineering_data.source_is_provisional(source)),
    }


def _view(raw: Any) -> tuple[float, float]:
    if raw is None:
        return DEFAULT_VIEW
    if not isinstance(raw, dict) or set(raw) - {"width", "height"}:
        raise ValueError("view 必须是 {width, height} 对象。")
    size = []
    for key, default in zip(("width", "height"), DEFAULT_VIEW):
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"view.{key} 必须是有限数值。")
        size.append(min(max(float(value), MIN_VIEW), MAX_VIEW))
    return size[0], size[1]


def result_json(result: GeneralCalculationResult, width: float, height: float, calculated_at: str) -> dict[str, Any]:
    shapes = general_section_shapes(result.input, result.metrics, width, height)
    return _json_safe({
        "input": result.input.to_json(),
        "verdict": result.verdict.value,
        "verdict_label": result.verdict_label,
        "checks": [
            {**asdict(check), "status": check.status.value}
            for check in result.checks
        ],
        "values": [asdict(value) for value in result.result.values],
        "warnings": list(result.warnings),
        "provisional_sources": list(result.provisional_sources),
        "metrics": asdict(result.metrics),
        "section": {"width": width, "height": height, "shapes": [
            {**asdict(shape), "target": section_target(shape.role)} for shape in shapes
        ]},
        "calculated_at": calculated_at,
        "report": render_general_report(result, calculated_at=calculated_at),
    })


def calculate_payload(body: Any) -> Response:
    if not isinstance(body, dict) or "input" not in body or set(body) - {"input", "view"}:
        return 400, {"error": "请求必须包含 input 对象，可选 view。", "field_errors": []}
    try:
        width, height = _view(body.get("view"))
    except ValueError as exc:
        return 400, {"error": str(exc), "field_errors": []}
    try:
        item = parse_general_input(body["input"])
        result = calculate_general(item)
    except InputValidationError as exc:
        return 400, {
            "error": f"输入有误（{len(exc.errors)} 项），请修正标红字段。",
            "field_errors": [{"path": error.path, "message": error.message} for error in exc.errors],
        }
    except (ValueError, ArithmeticError) as exc:
        LOGGER.warning("General calculation rejected: %s", exc)
        return 400, {"error": f"计算无法完成，请检查输入：{exc}", "field_errors": []}
    calculated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return 200, result_json(result, width, height, calculated_at)
