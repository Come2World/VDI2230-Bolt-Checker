from __future__ import annotations

from collections.abc import Callable, Mapping

from vdi2230.calculations import (
    calculate_b1,
    calculate_b2,
    calculate_b3,
    calculate_b4,
    calculate_b5,
)
from vdi2230.domain.models import (
    CalculationResult,
    JsonValue,
    ProjectSnapshot,
)
from vdi2230.domain.section import SectionGeometry
from vdi2230.ui.forms import InputFieldSpec
from vdi2230.ui.main_window import CaseFormDefinition


_CASE_CALCULATORS: tuple[
    tuple[str, str, Callable[[], CalculationResult]], ...
] = (
    ("B1", "B1 — 液压缸螺栓连接", calculate_b1),
    ("B2", "B2 — 多螺栓法兰摩擦传扭", calculate_b2),
    ("B3", "B3 — 空心中心螺栓", calculate_b3),
    ("B4", "B4 — 偏心载荷与缩颈螺栓", calculate_b4),
    ("B5", "B5 — 脉动压力缸盖连接", calculate_b5),
)


def _number(
    inputs: Mapping[str, JsonValue],
    key: str,
    default: float,
) -> float:
    value = inputs.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Reference geometry input {key} must be numeric")
    return float(value)


def _geometry(case_id: str, inputs: Mapping[str, JsonValue]) -> SectionGeometry:
    if case_id == "B1":
        grip = _number(inputs, "lK", 42)
        geometry = SectionGeometry(
            outer_diameter_mm=_number(inputs, "DZ", 80),
            hole_diameter_mm=_number(inputs, "dh", 13.5),
            head_diameter_mm=_number(inputs, "dK", 18),
            head_height_mm=7.5,
            shank_diameter_mm=_number(inputs, "d", 12),
            threaded_diameter_mm=_number(inputs, "d3", 9.85),
            shank_length_mm=max(60, grip),
            clamp_layer_thicknesses_mm=(grip / 2, grip / 2),
            threaded_length_mm=_number(inputs, "lGew", 18),
        )
    elif case_id == "B2":
        grip = _number(inputs, "lk", 60)
        geometry = SectionGeometry(
            outer_diameter_mm=_number(inputs, "Da", 338),
            hole_diameter_mm=_number(inputs, "dh", 17),
            head_diameter_mm=24,
            head_height_mm=10,
            shank_diameter_mm=_number(inputs, "d", 16),
            threaded_diameter_mm=_number(inputs, "d3", 13.546),
            shank_length_mm=_number(inputs, "l", 80),
            clamp_layer_thicknesses_mm=(grip / 2, grip / 2),
            threaded_length_mm=_number(inputs, "lGew", 18),
            nut_height_mm=_number(inputs, "mM", 14.1),
            bolt_count=int(_number(inputs, "boltCount", 12)),
            pitch_circle_diameter_mm=_number(inputs, "Dt", 258),
        )
    elif case_id == "B3":
        thicknesses = tuple(
            _number(inputs, key, fallback)
            for key, fallback in (("l1", 1.5), ("l2", 7), ("l3", 7.5))
        )
        grip = sum(thicknesses)
        geometry = SectionGeometry(
            outer_diameter_mm=_number(inputs, "DA", 72),
            hole_diameter_mm=_number(inputs, "dh", 29),
            head_diameter_mm=_number(inputs, "dWmin", 36),
            head_height_mm=_number(inputs, "k", 10),
            shank_diameter_mm=_number(inputs, "d0", 24),
            threaded_diameter_mm=_number(inputs, "d", 27),
            shank_length_mm=grip + _number(inputs, "l4", 20) + 10,
            clamp_layer_thicknesses_mm=thicknesses,
            threaded_length_mm=_number(inputs, "l4", 20),
            hollow_diameter_mm=_number(inputs, "db", 16),
        )
    elif case_id == "B4":
        geometry = SectionGeometry(
            outer_diameter_mm=25,
            hole_diameter_mm=_number(inputs, "dh", 9),
            head_diameter_mm=_number(inputs, "dW", 12.3),
            head_height_mm=6,
            shank_diameter_mm=_number(inputs, "d", 8),
            threaded_diameter_mm=_number(inputs, "d3", 6.466),
            shank_length_mm=_number(inputs, "lS", 53),
            clamp_layer_thicknesses_mm=(
                _number(inputs, "l1", 22),
                _number(inputs, "l2", 6),
                _number(inputs, "l3", 15) + _number(inputs, "lGew", 2),
            ),
            threaded_length_mm=_number(inputs, "lGew", 2),
            neck_length_mm=_number(inputs, "l1", 22)
            + _number(inputs, "l3", 15),
            neck_diameter_mm=_number(inputs, "dT", 5.8194),
            load_offset_mm=_number(inputs, "e", 5.5),
        )
    elif case_id == "B5":
        geometry = SectionGeometry(
            outer_diameter_mm=_number(inputs, "Da", 210),
            hole_diameter_mm=_number(inputs, "dh", 22),
            head_diameter_mm=_number(inputs, "dK", 30),
            head_height_mm=10,
            shank_diameter_mm=_number(inputs, "d", 20),
            threaded_diameter_mm=_number(inputs, "d3", 16.93),
            shank_length_mm=_number(inputs, "lS", 60),
            clamp_layer_thicknesses_mm=(_number(inputs, "lk", 35),),
            threaded_length_mm=_number(inputs, "lS", 60)
            - _number(inputs, "lk", 35),
            load_offset_mm=_number(inputs, "e", 15.5),
            bolt_count=int(_number(inputs, "i", 15)),
            pitch_circle_diameter_mm=_number(inputs, "Dst", 175),
        )
    else:
        raise ValueError(f"Unsupported reference case: {case_id}")
    geometry.validate()
    return geometry


def build_reference_cases() -> tuple[CaseFormDefinition, ...]:
    cases: list[CaseFormDefinition] = []
    for case_id, title, calculate in _CASE_CALCULATORS:
        reference_result = calculate()
        fields = tuple(
            InputFieldSpec(
                key=value.symbol,
                label=value.label,
                unit=value.unit,
                default_value=value.value,
                source=value.formula_reference,
                read_only=True,
            )
            for value in reference_result.values
            if value.note.startswith(
                "Source-table/chart selection used as a calculation input."
            )
        )
        if not fields:
            raise ValueError(f"Reference case {case_id} has no input values")
        expected = {
            field.key: field.default_value for field in fields
        }

        def calculate_reference(
            project: ProjectSnapshot,
            *,
            _calculate: Callable[[], CalculationResult] = calculate,
            _expected: dict[str, JsonValue] = expected,
            _case_id: str = case_id,
        ) -> CalculationResult:
            if project.case_id != _case_id:
                raise ValueError("Project case does not match reference case")
            if project.inputs != _expected:
                raise ValueError(
                    "This version only recalculates the fixed PDF reference inputs."
                )
            return _calculate()

        cases.append(
            CaseFormDefinition(
                case_id=case_id,
                title=title,
                fields=fields,
                calculate=calculate_reference,
                geometry=lambda inputs, _case_id=case_id: _geometry(
                    _case_id,
                    inputs,
                ),
            )
        )
    return tuple(cases)
