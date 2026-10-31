from __future__ import annotations

from math import isfinite

from vdi2230.domain.models import (
    CalculationResult,
    CalculationValue,
    ResultStatus,
)
from vdi2230.domain.validation import relative_error_percent


class ResultBuilder:
    def __init__(self, case_id: str, pages: str) -> None:
        self.case_id = case_id
        self.pages = pages
        self.values: list[CalculationValue] = []
        self.warnings: list[str] = []

    def add(
        self,
        symbol: str,
        label: str,
        value: float,
        unit: str,
        formula: str,
        *,
        reference: float | None = None,
        status: ResultStatus = ResultStatus.PASS,
        note: str = "",
    ) -> float:
        if not isfinite(value):
            raise ValueError(f"{symbol} is not finite")
        error = (
            relative_error_percent(value, reference)
            if reference is not None and reference != 0
            else None
        )
        if error is not None and error > 3.0 and status == ResultStatus.PASS:
            status = ResultStatus.NEEDS_REVIEW
            discrepancy = (
                f"Formula result differs from the printed reference by "
                f"{error:.2f}%; not adjusted to match."
            )
            note = f"{note} {discrepancy}".strip()
        self.values.append(
            CalculationValue(
                symbol=symbol,
                label=label,
                value=value,
                unit=unit,
                formula_reference=(
                    f"VDI 2230 Blatt 1:2015, Appendix B, {formula}; "
                    f"PDF p. {self.pages}"
                ),
                status=status,
                reference_value=reference,
                relative_error_percent=error,
                note=note,
            )
        )
        return value

    def source_input(
        self,
        symbol: str,
        label: str,
        value: float,
        unit: str,
        source: str,
        *,
        note: str = "Source-table/chart selection used as a calculation input.",
    ) -> float:
        return self.add(
            symbol,
            label,
            value,
            unit,
            source,
            reference=value,
            note=note,
        )

    def unresolved(
        self,
        symbol: str,
        label: str,
        unit: str,
        formula: str,
        blocker: str,
    ) -> None:
        self.values.append(
            CalculationValue(
                symbol=symbol,
                label=label,
                value=None,
                unit=unit,
                formula_reference=(
                    f"VDI 2230 Blatt 1:2015, Appendix B, {formula}; "
                    f"PDF p. {self.pages}"
                ),
                status=ResultStatus.NEEDS_REVIEW,
                note=blocker,
            )
        )
        self.warnings.append(f"{symbol}: {blocker}")

    def result(self) -> CalculationResult:
        return CalculationResult(
            case_id=self.case_id,
            model_name="VDI 2230:2015 Appendix B reference calculation",
            source_reference=(
                "VDI 2230 Blatt 1 / Part 1:2015, Appendix B; "
                f"reference case {self.case_id}, PDF p. {self.pages}"
            ),
            values=tuple(self.values),
            warnings=tuple(self.warnings),
        )


def area_circle(diameter: float) -> float:
    from math import pi

    return pi * diameter**2 / 4


def bolt_torsion_moment(
    preload: float, pitch_diameter: float, pitch: float, friction: float
) -> float:
    from math import pi

    return preload * pitch_diameter / 2 * (
        pitch / (pi * pitch_diameter) + 1.155 * friction
    )


def equivalent_stress(tensile: float, shear: float, k_tau: float = 0.5) -> float:
    from math import sqrt

    return sqrt(tensile**2 + 3 * (k_tau * shear) ** 2)


def bearing_area(outer: float, hole: float) -> float:
    from math import pi

    return pi / 4 * (outer**2 - hole**2)


def thread_strength_ratio(
    nominal: float,
    pitch_diameter: float,
    internal_minor_diameter: float,
    pitch: float,
    external_strength: float,
    internal_strength: float,
) -> float:
    from math import tan, pi

    tangent = tan(pi / 6)
    external_term = pitch / 2 + (nominal - pitch_diameter) * tangent
    internal_term = pitch / 2 + (
        pitch_diameter - internal_minor_diameter
    ) * tangent
    return (
        nominal
        * external_term
        / (internal_minor_diameter * internal_term)
        * external_strength
        / internal_strength
    )
