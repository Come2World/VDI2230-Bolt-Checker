from dataclasses import dataclass
from typing import Callable, Literal, Mapping

from vdi2230.domain.models import (
    CalculationResult,
    JsonScalar,
    JsonValue,
    ProjectSnapshot,
)
from vdi2230.domain.section import SectionGeometry
from vdi2230.domain.validation import require_finite


@dataclass(frozen=True)
class InputFieldSpec:
    key: str
    label: str
    unit: str = ""
    kind: Literal["number", "integer", "text", "choice"] = "number"
    required: bool = True
    default_value: JsonScalar = ""
    choices: tuple[str, ...] = ()
    source: str = ""
    read_only: bool = False

    def __post_init__(self) -> None:
        if not self.key or not self.label:
            raise ValueError("Input field key and label must not be empty")
        if self.kind == "choice":
            if not self.choices:
                raise ValueError(
                    f"Choice field {self.key} must define choices"
                )
            if (
                self.default_value
                and self.default_value not in self.choices
            ):
                raise ValueError(
                    f"Choice field {self.key} has an invalid default"
                )
        elif self.choices:
            raise ValueError(
                f"Non-choice field {self.key} cannot define choices"
            )


CalculationFunction = Callable[[ProjectSnapshot], CalculationResult]
GeometryFunction = Callable[[Mapping[str, JsonValue]], SectionGeometry | None]


@dataclass(frozen=True)
class CaseFormDefinition:
    case_id: str
    title: str
    fields: tuple[InputFieldSpec, ...]
    calculate: CalculationFunction
    geometry: GeometryFunction

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("Calculation case ID must not be empty")
        field_keys = [field.key for field in self.fields]
        if len(set(field_keys)) != len(field_keys):
            raise ValueError(f"Duplicate input field in {self.case_id}")


def parse_form_values(
    fields: tuple[InputFieldSpec, ...],
    raw_values: Mapping[str, str],
) -> dict[str, JsonValue]:
    parsed: dict[str, JsonValue] = {}
    for field in fields:
        raw_value = raw_values.get(field.key, "").strip()
        if not raw_value:
            if field.required:
                raise ValueError(f"{field.label}不能为空")
            parsed[field.key] = None
            continue

        if field.kind == "number":
            try:
                parsed[field.key] = require_finite(
                    field.label,
                    float(raw_value),
                )
            except ValueError as exc:
                raise ValueError(f"{field.label}必须是有限数值") from exc
        elif field.kind == "integer":
            try:
                numeric_value = require_finite(
                    field.label,
                    float(raw_value),
                )
            except ValueError as exc:
                raise ValueError(f"{field.label}必须是整数") from exc
            if not numeric_value.is_integer():
                raise ValueError(f"{field.label}必须是整数")
            parsed[field.key] = int(numeric_value)
        elif field.kind == "choice":
            if raw_value not in field.choices:
                raise ValueError(
                    f"{field.label}必须从有效选项中选择"
                )
            parsed[field.key] = raw_value
        elif field.kind == "text":
            parsed[field.key] = raw_value
        else:
            raise ValueError(f"Unsupported input field kind: {field.kind}")
    return parsed
