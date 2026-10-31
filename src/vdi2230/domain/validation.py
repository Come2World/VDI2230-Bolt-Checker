import math


def require_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def relative_error_percent(actual: float, reference: float) -> float:
    reference_value = require_finite("reference", reference)
    actual_value = require_finite("actual", actual)
    if reference_value == 0:
        raise ValueError("relative error is undefined for a zero reference")
    return abs(actual_value - reference_value) / abs(reference_value) * 100


def within_relative_tolerance(
    actual: float,
    reference: float,
    tolerance_percent: float = 3.0,
) -> bool:
    tolerance = require_finite("tolerance_percent", tolerance_percent)
    if tolerance < 0:
        raise ValueError("tolerance_percent must not be negative")
    return relative_error_percent(actual, reference) <= tolerance


def matches_reference(
    actual: float,
    reference: float,
    tolerance_percent: float = 3.0,
    absolute_tolerance: float | None = None,
) -> bool:
    reference_value = require_finite("reference", reference)
    actual_value = require_finite("actual", actual)
    if reference_value != 0:
        return within_relative_tolerance(
            actual_value,
            reference_value,
            tolerance_percent,
        )
    if absolute_tolerance is None:
        raise ValueError(
            "absolute_tolerance is required when the reference is zero"
        )
    tolerance = require_finite("absolute_tolerance", absolute_tolerance)
    if tolerance < 0:
        raise ValueError("absolute_tolerance must not be negative")
    return abs(actual_value) <= tolerance
