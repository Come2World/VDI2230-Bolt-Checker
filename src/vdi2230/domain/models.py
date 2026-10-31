from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = (
    JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
)


class ResultStatus(str, Enum):
    PASS = "通过"
    FAIL = "不通过"
    NOT_CALCULATED = "未计算"
    NEEDS_REVIEW = "需确认"
    OUT_OF_SCOPE = "超出范围"
    ERROR = "计算错误"


@dataclass(frozen=True)
class ProjectSnapshot:
    case_id: str
    title: str
    inputs: dict[str, JsonValue]
    assumptions: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    input_units: dict[str, str] = field(default_factory=dict)
    input_sources: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CalculationValue:
    symbol: str
    label: str
    value: float | str | None
    unit: str
    formula_reference: str
    status: ResultStatus = ResultStatus.PASS
    reference_value: float | None = None
    relative_error_percent: float | None = None
    absolute_error: float | None = None
    absolute_tolerance: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.symbol or not self.label:
            raise ValueError("Calculation symbol and label must not be empty")
        if isinstance(self.value, bool):
            raise ValueError("Boolean values are not valid calculation results")
        if self.value is not None and not isinstance(
            self.value,
            (int, float, str),
        ):
            raise TypeError("Calculation result must be numeric, text, or None")
        if isinstance(self.value, (int, float)) and not math.isfinite(
            self.value
        ):
            raise ValueError("Calculation result must be finite")
        for name, value in (
            ("reference_value", self.reference_value),
            ("relative_error_percent", self.relative_error_percent),
            ("absolute_error", self.absolute_error),
            ("absolute_tolerance", self.absolute_tolerance),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite when provided")
        if self.relative_error_percent is not None and (
            self.relative_error_percent < 0
        ):
            raise ValueError("relative error must not be negative")
        if self.absolute_error is not None and self.absolute_error < 0:
            raise ValueError("absolute error must not be negative")
        if self.absolute_tolerance is not None and self.absolute_tolerance < 0:
            raise ValueError("absolute tolerance must not be negative")
        if (
            self.reference_value == 0
            and self.relative_error_percent is not None
        ):
            raise ValueError("zero reference values require absolute comparison")


@dataclass(frozen=True)
class CalculationResult:
    case_id: str
    model_name: str
    source_reference: str
    values: tuple[CalculationValue, ...]
    warnings: tuple[str, ...] = ()
    calculated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    )

    @property
    def is_fully_calculated(self) -> bool:
        incomplete = {
            ResultStatus.NOT_CALCULATED,
            ResultStatus.NEEDS_REVIEW,
            ResultStatus.OUT_OF_SCOPE,
            ResultStatus.ERROR,
        }
        return bool(self.values) and all(
            value.status not in incomplete for value in self.values
        )

    @property
    def overall_status(self) -> ResultStatus:
        statuses = {value.status for value in self.values}
        if not statuses:
            return ResultStatus.NOT_CALCULATED
        for status in (
            ResultStatus.ERROR,
            ResultStatus.OUT_OF_SCOPE,
            ResultStatus.FAIL,
            ResultStatus.NEEDS_REVIEW,
            ResultStatus.NOT_CALCULATED,
        ):
            if status in statuses:
                return status
        return ResultStatus.PASS
