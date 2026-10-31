"""Toolkit-neutral 2D section drawing of a general single-bolt joint.

Shapes are laid out in pixel coordinates for a given view size so the web
(SVG) and desktop (Tk canvas) front ends render identical drawings. Roles tag
shapes for interaction, e.g. ``plate-0`` selects the first clamped layer.
"""
from __future__ import annotations

from dataclasses import dataclass

from vdi2230.calculations.general import (
    SectionMetrics,
    deformation_breakpoints,
    deformation_diameter,
)
from vdi2230.domain.general_inputs import GeneralInput


MIN_VIEW = 200
MAX_VIEW = 2400
LINE_HEIGHT = 13.0
PLATE_FILLS = ("#d7e3ef", "#c4d5e6")
PLATE_STROKE = "#5b7083"
BOLT_FILL = "#9aa7b4"
THREAD_FILL = "#7f8e9c"
BOLT_STROKE = "#2f3e4c"
TAPPED_FILL = "#e6dfd1"
CONE_FILL = "#f2a541"
INTERFACE_STROKE = "#c0392b"
DIMENSION_STROKE = "#455a64"
TEXT_FILL = "#263238"
MUTED_TEXT = "#607d8b"


@dataclass(frozen=True)
class Shape:
    kind: str
    points: tuple[float, ...]
    fill: str = "none"
    stroke: str = ""
    text: str = ""
    dash: bool = False
    role: str = ""
    anchor: str = "start"
    size: float = 11.0
    rotate: float = 0.0
    opacity: float = 1.0


def _fmt(value: float) -> str:
    return f"{value:.4g}"


def general_section_shapes(
    item: GeneralInput,
    metrics: SectionMetrics,
    width: float,
    height: float,
) -> tuple[Shape, ...]:
    if not (MIN_VIEW <= width <= MAX_VIEW and MIN_VIEW <= height <= MAX_VIEW):
        raise ValueError(f"绘图区域须在 {MIN_VIEW}–{MAX_VIEW} px 之间")
    bolt, joint, nut = item.bolt, item.joint, item.nut
    dsv = item.is_through_bolt
    clamp = metrics.clamp_length
    head_width = bolt.head_bearing_diameter * (1.1 if bolt.head_type == "hex" else 1.05)
    nut_width = max(nut.width_across_flats, nut.bearing_diameter * 1.05)
    shank_total = 0.0 if bolt.thread_length is None else bolt.length - bolt.thread_length
    if dsv:
        below = max(bolt.length, clamp + nut.height)
    else:
        below = max(bolt.length + 0.4 * bolt.d, clamp + metrics.engagement_length + 0.5 * bolt.d)
    total_mm = bolt.head_height + below
    across_mm = max(joint.outer_diameter, head_width, nut_width if dsv else 0.0)

    pad = 12.0
    left_band = 44.0
    label_band = min(max(width * 0.32, 140.0), 230.0)
    top_band, bottom_band = 22.0, 30.0
    gx0, gx1 = pad + left_band, width - pad - label_band
    gy0, gy1 = pad + top_band, height - pad - bottom_band
    scale = min((gx1 - gx0) / across_mm, (gy1 - gy0) / total_mm)
    cx = (gx0 + gx1) / 2
    y_top = gy0

    def y(depth: float) -> float:
        return y_top + (bolt.head_height + depth) * scale

    def half(diameter: float) -> float:
        return diameter * scale / 2

    shapes: list[Shape] = []
    y_end = y(below)
    shapes.append(Shape("line", (cx, y_top - 6, cx, y_end + 6), stroke=MUTED_TEXT, dash=True, role="axis"))

    if not dsv:
        shapes.append(Shape(
            "rect", (cx - half(joint.outer_diameter), y(clamp), cx + half(joint.outer_diameter), y_end),
            fill=TAPPED_FILL, stroke=PLATE_STROKE, role="tapped",
        ))

    boundaries = [0.0]
    for layer in item.plates:
        boundaries.append(boundaries[-1] + layer.thickness)
    for index, layer in enumerate(item.plates):
        top, bottom = y(boundaries[index]), y(boundaries[index + 1])
        fill = PLATE_FILLS[index % 2]
        for x0, x1 in (
            (cx - half(joint.outer_diameter), cx - half(joint.hole_diameter)),
            (cx + half(joint.hole_diameter), cx + half(joint.outer_diameter)),
        ):
            shapes.append(Shape("rect", (x0, top, x1, bottom), fill=fill, stroke=PLATE_STROKE, role=f"plate-{index}"))

    slip_interfaces = range(1, len(item.plates)) if dsv else range(1, len(item.plates) + 1)
    for boundary_index in slip_interfaces:
        level = y(boundaries[boundary_index])
        for x0, x1 in (
            (cx - half(joint.outer_diameter), cx - half(joint.hole_diameter)),
            (cx + half(joint.hole_diameter), cx + half(joint.outer_diameter)),
        ):
            shapes.append(Shape(
                "line", (x0, level, x1, level), stroke=INTERFACE_STROKE, dash=True,
                role=f"interface-{boundary_index - 1}",
            ))

    depths = deformation_breakpoints(
        clamp, joint.outer_diameter, metrics.w, metrics.tan_phi,
        metrics.cone_start_head, metrics.cone_start_nut,
    )
    for side in (-1, 1):
        outline = []
        for depth in depths:
            diameter = deformation_diameter(
                depth, clamp, joint.outer_diameter, metrics.w, metrics.tan_phi,
                metrics.cone_start_head, metrics.cone_start_nut,
            )
            outline.extend((cx + side * half(diameter), y(depth)))
        polygon = (cx + side * half(joint.hole_diameter), y(0.0), *outline, cx + side * half(joint.hole_diameter), y(clamp))
        shapes.append(Shape("polygon", polygon, fill=CONE_FILL, stroke="#b9770e", dash=True, role="cone", opacity=0.28))

    shapes.append(Shape(
        "rect", (cx - half(head_width), y_top, cx + half(head_width), y(0.0)),
        fill=BOLT_FILL, stroke=BOLT_STROKE, role="bolt-head",
    ))
    if bolt.head_type == "socket":
        shapes.append(Shape(
            "rect", (cx - half(0.8 * bolt.d), y_top, cx + half(0.8 * bolt.d), y_top + 0.5 * bolt.head_height * scale),
            fill="#ffffff", stroke=BOLT_STROKE, role="bolt-head",
        ))

    shank_end = min(max(shank_total, 0.0), bolt.length)
    shank_diameter = bolt.shank_diameter or bolt.d
    if shank_end > 0:
        shapes.append(Shape(
            "rect", (cx - half(shank_diameter), y(0.0), cx + half(shank_diameter), y(shank_end)),
            fill=BOLT_FILL, stroke=BOLT_STROKE, role="bolt-shank",
        ))
    if shank_end < bolt.length:
        shapes.append(Shape(
            "rect", (cx - half(bolt.d), y(shank_end), cx + half(bolt.d), y(bolt.length)),
            fill=THREAD_FILL, stroke=BOLT_STROKE, role="bolt-thread",
        ))
        for side in (-1, 1):
            shapes.append(Shape(
                "line", (cx + side * half(bolt.d3), y(shank_end), cx + side * half(bolt.d3), y(bolt.length)),
                stroke="#dfe6ec", dash=True, role="bolt-thread",
            ))
    if bolt.bore_diameter > 0:
        shapes.append(Shape(
            "rect", (cx - half(bolt.bore_diameter), y_top, cx + half(bolt.bore_diameter), y(bolt.length)),
            fill="#ffffff", stroke=BOLT_STROKE, role="bolt-bore",
        ))

    if dsv:
        shapes.append(Shape(
            "rect", (cx - half(nut_width), y(clamp), cx + half(nut_width), y(clamp + nut.height)),
            fill=BOLT_FILL, stroke=BOLT_STROKE, role="nut",
        ))
        for side in (-1, 1):
            shapes.append(Shape(
                "line", (cx + side * half(bolt.d), y(clamp), cx + side * half(bolt.d), y(clamp + min(nut.height, bolt.length - clamp))),
                stroke=BOLT_STROKE, role="nut",
            ))

    shapes.extend(_dimensions(item, metrics, cx, y, half, gx0, gy1))
    shapes.extend(_labels(item, metrics, cx, y, half, head_width, nut_width, gx1 + 10, gy0, gy1, y_top))
    class_text = f" · {bolt.property_class}" if bolt.property_class else ""
    bore_text = f" · 空心 db {_fmt(bolt.bore_diameter)}" if bolt.bore_diameter else ""
    shank_text = f" · 细腰 dT {_fmt(bolt.shank_diameter)}" if bolt.shank_diameter and bolt.shank_diameter < bolt.d else ""
    shapes.append(Shape(
        "text", (pad, pad + 6),
        fill=TEXT_FILL, size=12,
        text=f"{'DSV 螺栓 + 螺母' if dsv else 'ESV 螺纹孔'} · M{_fmt(bolt.d)}×{_fmt(bolt.pitch)}{class_text} · l {_fmt(bolt.length)}{bore_text}{shank_text}",
        role="title",
    ))
    return tuple(shapes)


def _dimension(x0: float, y0: float, x1: float, y1: float, text: str, role: str, vertical: bool) -> list[Shape]:
    tick = 4.0
    shapes = [Shape("line", (x0, y0, x1, y1), stroke=DIMENSION_STROKE, role=role)]
    if vertical:
        shapes.append(Shape("line", (x0 - tick, y0, x0 + tick, y0), stroke=DIMENSION_STROKE, role=role))
        shapes.append(Shape("line", (x1 - tick, y1, x1 + tick, y1), stroke=DIMENSION_STROKE, role=role))
        shapes.append(Shape(
            "text", (x0 - 6, (y0 + y1) / 2), fill=TEXT_FILL, text=text, anchor="middle", rotate=-90, role=role,
        ))
    else:
        shapes.append(Shape("line", (x0, y0 - tick, x0, y0 + tick), stroke=DIMENSION_STROKE, role=role))
        shapes.append(Shape("line", (x1, y1 - tick, x1, y1 + tick), stroke=DIMENSION_STROKE, role=role))
        shapes.append(Shape("text", ((x0 + x1) / 2, y0 + 11), fill=TEXT_FILL, text=text, anchor="middle", role=role))
    return shapes


def _dimensions(item, metrics, cx, y, half, gx0, gy1) -> list[Shape]:
    clamp = metrics.clamp_length
    shapes = _dimension(gx0 - 8, y(0.0), gx0 - 8, y(clamp), f"lK {_fmt(clamp)}", "dim-lK", True)
    shapes += _dimension(gx0 - 30, y(0.0), gx0 - 30, y(item.bolt.length), f"l {_fmt(item.bolt.length)}", "dim-l", True)
    outer = item.joint.outer_diameter
    shapes += _dimension(cx - half(outer), gy1 + 10, cx + half(outer), gy1 + 10, f"DA {_fmt(outer)}", "dim-DA", False)
    return shapes


def _place_labels(anchors: list[float], step: float, top_limit: float, bottom_limit: float) -> list[float]:
    """Top edge of each label block: as close to its anchor as possible, never overlapping."""
    placed: list[float] = []
    for anchor in anchors:
        top = max(anchor - step / 2, top_limit)
        if placed:
            top = max(top, placed[-1] + step)
        placed.append(top)
    limit = bottom_limit - step
    for index in range(len(placed) - 1, -1, -1):
        placed[index] = min(placed[index], limit)
        limit = placed[index] - step
    return placed


def _labels(item, metrics, cx, y, half, head_width, nut_width, label_x, top_limit, bottom_limit, y_top) -> list[Shape]:
    bolt, nut, tapped = item.bolt, item.nut, item.tapped
    dsv = item.is_through_bolt
    layers = item.plates
    head_mu = f"μK {_fmt(layers[0].bearing_friction)}"
    # (anchor y, anchor x, title, detail, short name, role)
    entries: list[tuple[float, float, str, str, str, str]] = [(
        (y_top + y(0.0)) / 2,
        cx + half(head_width),
        f"螺栓头 {'外六角' if bolt.head_type == 'hex' else '内六角'}",
        f"dW {_fmt(bolt.head_bearing_diameter)} · {head_mu}",
        "头",
        "label-head",
    )]
    depth = 0.0
    slip_layers = len(layers) - 1 if dsv else len(layers)
    for index, layer in enumerate(layers):
        middle = depth + layer.thickness / 2
        depth += layer.thickness
        detail = f"h {_fmt(layer.thickness)} · Rz {_fmt(layer.roughness_rz)}"
        if index < slip_layers:
            detail += f" · μT {_fmt(layer.interface_friction)}"
        material = layer.material_id or "自定义"
        entries.append((
            y(middle), cx + half(item.joint.outer_diameter),
            f"{layer.name} · {material}", detail, layer.name, f"plate-{index}",
        ))
    clamp = metrics.clamp_length
    if dsv:
        side_mu = f" · μK {_fmt(layers[-1].bearing_friction)}" if item.assembly.tighten_side == "nut" else ""
        entries.append((
            y(clamp + nut.height / 2), cx + half(nut_width),
            f"螺母 m {_fmt(nut.height)}", f"μG {_fmt(bolt.thread_friction)}{side_mu}", "螺母", "label-nut",
        ))
    else:
        material = tapped.material_id or "自定义"
        entries.append((
            y(clamp + metrics.engagement_length / 2), cx + half(item.joint.outer_diameter),
            f"内螺纹件 · {material}",
            f"旋合 {_fmt(metrics.engagement_length)} · μG {_fmt(bolt.thread_friction)}",
            "内螺纹", "tapped",
        ))

    available = bottom_limit - top_limit
    two_line = 2 * LINE_HEIGHT + 4
    one_line = LINE_HEIGHT + 2
    if len(entries) * two_line <= available:
        step, size = two_line, 11.0
    else:
        step = min(one_line, available / len(entries))
        size = min(11.0, max(6.0, step - 2))
    placed = _place_labels([entry[0] for entry in entries], step, top_limit, bottom_limit)

    shapes: list[Shape] = []
    for (anchor_y, anchor_x, title, detail, short, role), top in zip(entries, placed):
        if step == two_line:
            centre = top + LINE_HEIGHT
            shapes.append(Shape("line", (anchor_x + 2, anchor_y, label_x - 4, centre), stroke="#90a4ae", role=role))
            shapes.append(Shape("text", (label_x, top + LINE_HEIGHT / 2), fill=TEXT_FILL, text=title, role=role))
            shapes.append(Shape("text", (label_x, top + 1.5 * LINE_HEIGHT), fill=MUTED_TEXT, text=detail, role=role, size=10.5))
        else:
            centre = top + step / 2
            shapes.append(Shape("line", (anchor_x + 2, anchor_y, label_x - 4, centre), stroke="#90a4ae", role=role))
            shapes.append(Shape("text", (label_x, centre), fill=TEXT_FILL, text=f"{short} · {detail}", role=role, size=size))
    return shapes
