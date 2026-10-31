from dataclasses import dataclass
import math


def _is_finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


@dataclass(frozen=True)
class SectionGeometry:
    outer_diameter_mm: float
    hole_diameter_mm: float
    head_diameter_mm: float
    head_height_mm: float
    shank_diameter_mm: float
    threaded_diameter_mm: float
    shank_length_mm: float
    clamp_layer_thicknesses_mm: tuple[float, ...]
    threaded_length_mm: float = 0.0
    neck_length_mm: float = 0.0
    nut_height_mm: float = 0.0
    hollow_diameter_mm: float = 0.0
    neck_diameter_mm: float = 0.0
    load_offset_mm: float = 0.0
    bolt_count: int = 1
    pitch_circle_diameter_mm: float = 0.0

    def validate(self) -> None:
        positive = {
            "outer_diameter_mm": self.outer_diameter_mm,
            "hole_diameter_mm": self.hole_diameter_mm,
            "head_diameter_mm": self.head_diameter_mm,
            "head_height_mm": self.head_height_mm,
            "shank_diameter_mm": self.shank_diameter_mm,
            "threaded_diameter_mm": self.threaded_diameter_mm,
            "shank_length_mm": self.shank_length_mm,
        }
        for name, value in positive.items():
            if not _is_finite_number(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name, value in (
            ("nut_height_mm", self.nut_height_mm),
            ("threaded_length_mm", self.threaded_length_mm),
            ("neck_length_mm", self.neck_length_mm),
            ("hollow_diameter_mm", self.hollow_diameter_mm),
            ("neck_diameter_mm", self.neck_diameter_mm),
            ("pitch_circle_diameter_mm", self.pitch_circle_diameter_mm),
        ):
            if not _is_finite_number(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not _is_finite_number(self.load_offset_mm):
            raise ValueError("load_offset_mm must be finite")
        if self.hole_diameter_mm >= min(
            self.outer_diameter_mm,
            self.head_diameter_mm,
        ):
            raise ValueError("hole diameter must be smaller than outer/head diameter")
        if self.hollow_diameter_mm >= self.shank_diameter_mm:
            raise ValueError("hollow diameter must be smaller than shank diameter")
        if self.neck_diameter_mm and self.neck_diameter_mm > self.shank_diameter_mm:
            raise ValueError("neck diameter must not exceed shank diameter")
        if self.neck_diameter_mm and not self.neck_length_mm:
            raise ValueError("neck length is required for a reduced-shank bolt")
        if (
            self.threaded_length_mm + self.neck_length_mm
            > self.shank_length_mm
        ):
            raise ValueError("thread and neck lengths exceed the shank length")
        if not self.clamp_layer_thicknesses_mm:
            raise ValueError("at least one clamped layer is required")
        if any(
            not _is_finite_number(thickness) or thickness <= 0
            for thickness in self.clamp_layer_thicknesses_mm
        ):
            raise ValueError("clamp layer thicknesses must be finite and positive")
        if (
            isinstance(self.bolt_count, bool)
            or not isinstance(self.bolt_count, int)
            or self.bolt_count < 1
        ):
            raise ValueError("bolt_count must be a positive integer")
        if self.bolt_count > 1 and self.pitch_circle_diameter_mm <= 0:
            raise ValueError(
                "a positive pitch circle diameter is required for bolt groups"
            )


@dataclass(frozen=True)
class DrawingPrimitive:
    kind: str
    coordinates: tuple[float, ...]
    fill: str = ""
    outline: str = ""
    text: str = ""


def section_primitives(
    width: int,
    height: int,
    geometry: SectionGeometry,
) -> tuple[DrawingPrimitive, ...]:
    geometry.validate()
    if width < 100 or height < 100:
        raise ValueError("drawing area must be at least 100 by 100 pixels")

    margin = 36.0
    stack_height = sum(geometry.clamp_layer_thicknesses_mm)
    total_height = (
        geometry.head_height_mm
        + stack_height
        + geometry.shank_length_mm
        + geometry.nut_height_mm
    )
    group_width = (
        geometry.pitch_circle_diameter_mm + geometry.head_diameter_mm
        if geometry.bolt_count > 1
        else 0
    )
    drawing_width = max(
        geometry.outer_diameter_mm,
        geometry.head_diameter_mm,
        group_width,
        2 * abs(geometry.load_offset_mm) + geometry.head_diameter_mm,
    )
    scale = min(
        (width - 2 * margin) / drawing_width,
        (height - 2 * margin) / total_height,
    )
    center_x = width / 2
    top_y = margin
    half_outer = geometry.outer_diameter_mm * scale / 2
    half_hole = geometry.hole_diameter_mm * scale / 2
    clamp_top = top_y + geometry.head_height_mm * scale
    primitives: list[DrawingPrimitive] = []

    primitives.append(
        DrawingPrimitive(
            "line",
            (center_x, top_y - 8, center_x, height - margin),
            outline="#888888",
        )
    )
    layer_y = clamp_top
    for index, thickness in enumerate(geometry.clamp_layer_thicknesses_mm):
        next_y = layer_y + thickness * scale
        primitives.extend(
            (
                DrawingPrimitive(
                    "rectangle",
                    (
                        center_x - half_outer,
                        layer_y,
                        center_x - half_hole,
                        next_y,
                    ),
                    fill="#dce6f1",
                    outline="#586a7a",
                ),
                DrawingPrimitive(
                    "rectangle",
                    (
                        center_x + half_hole,
                        layer_y,
                        center_x + half_outer,
                        next_y,
                    ),
                    fill="#dce6f1",
                    outline="#586a7a",
                ),
                DrawingPrimitive(
                    "text",
                    (center_x - half_outer, (layer_y + next_y) / 2),
                    text=f"Layer {index + 1}: {thickness:g} mm",
                ),
            )
        )
        layer_y = next_y

    head_half = geometry.head_diameter_mm * scale / 2
    head_bottom = clamp_top
    primitives.append(
        DrawingPrimitive(
            "rectangle",
            (
                center_x - head_half,
                top_y,
                center_x + head_half,
                head_bottom,
            ),
            fill="#aeb8c2",
            outline="#34495e",
        )
    )

    bolt_bottom = min(
        height - margin,
        clamp_top + geometry.shank_length_mm * scale,
    )
    shank_half = geometry.shank_diameter_mm * scale / 2
    thread_start = bolt_bottom - geometry.threaded_length_mm * scale
    neck_start = thread_start - geometry.neck_length_mm * scale
    segments = (
        (
            head_bottom,
            neck_start if geometry.neck_length_mm else thread_start,
            geometry.shank_diameter_mm,
        ),
        (
            neck_start,
            thread_start,
            geometry.neck_diameter_mm,
        ),
        (
            thread_start,
            bolt_bottom,
            geometry.threaded_diameter_mm,
        ),
    )
    for segment_start, segment_end, diameter in segments:
        if segment_end <= segment_start or diameter <= 0:
            continue
        half_diameter = diameter * scale / 2
        primitives.append(
            DrawingPrimitive(
                "rectangle",
                (
                    center_x - half_diameter,
                    segment_start,
                    center_x + half_diameter,
                    segment_end,
                ),
                fill="#8796a5",
                outline="#34495e",
            )
        )

    if geometry.hollow_diameter_mm:
        hollow_half = geometry.hollow_diameter_mm * scale / 2
        primitives.append(
            DrawingPrimitive(
                "rectangle",
                (
                    center_x - hollow_half,
                    head_bottom,
                    center_x + hollow_half,
                    bolt_bottom,
                ),
                fill="white",
                outline="#34495e",
            )
        )

    if geometry.load_offset_mm:
        load_x = center_x + geometry.load_offset_mm * scale
        primitives.append(
            DrawingPrimitive(
                "line",
                (load_x, clamp_top + 8, load_x, clamp_top + 44),
                outline="#c0392b",
            )
        )
        primitives.append(
            DrawingPrimitive(
                "text",
                (load_x + 4, clamp_top + 22),
                fill="#c0392b",
                text=f"Load offset {geometry.load_offset_mm:g} mm",
            )
        )

    if geometry.nut_height_mm:
        nut_top = bolt_bottom
        nut_bottom = min(
            height - margin,
            nut_top + geometry.nut_height_mm * scale,
        )
        nut_half = geometry.head_diameter_mm * scale / 2
        primitives.append(
            DrawingPrimitive(
                "rectangle",
                (
                    center_x - nut_half,
                    nut_top,
                    center_x + nut_half,
                    nut_bottom,
                ),
                fill="#aeb8c2",
                outline="#34495e",
            )
        )

    if geometry.bolt_count > 1:
        primitives.append(
            DrawingPrimitive(
                "text",
                (margin, height - 18),
                text=(
                    f"{geometry.bolt_count} bolts on "
                    f"{geometry.pitch_circle_diameter_mm:g} mm pitch circle"
                ),
            )
        )

    return tuple(primitives)
