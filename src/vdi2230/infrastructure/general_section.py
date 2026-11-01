"""Toolkit-neutral 2D section drawing of a general single-bolt joint.

Shapes are laid out in pixel coordinates for a given Tk canvas size.
Roles tag shapes for interaction, e.g. ``plate-0`` selects the first
clamped layer. Geometry can be tested without creating a window.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from vdi2230.calculations.general import (
    SectionMetrics,
    deformation_breakpoints,
    deformation_diameter,
)
from vdi2230.domain.general_inputs import GeneralInput
from functools import partial
from vdi2230.i18n import Language, translate


MIN_VIEW = 200
MAX_VIEW = 2400
LINE_HEIGHT = 13.0
DRAWING_BACKGROUND = "#04101f"
GRID_STROKE = "#0b253b"
PLATE_FILLS = ("#0a2940", "#10243d")
PLATE_STROKE = "#61cfff"
BOLT_FILL = "#07334c"
THREAD_FILL = BOLT_FILL
BOLT_STROKE = "#66e3ff"
TAPPED_FILL = "#172749"
CONE_FILL = "#be85ff"
INTERFACE_STROKE = "#dc8aff"
DIMENSION_STROKE = "#83def5"
BEARING_STROKE = "#ffd166"
TEXT_FILL = "#d6efff"
MUTED_TEXT = "#89abc5"


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
    stroke_width: float = 1.0
    dash_pattern: tuple[float, ...] = ()


def section_target(role: str) -> str:
    plate = re.fullmatch(r"plate-(\d+)", role)
    if plate:
        return f"plates[{plate.group(1)}].thickness"
    if role.startswith("bolt-") or role == "label-head":
        return "bolt.head_height" if role in {"bolt-head", "label-head"} else "bolt.length"
    return {
        "nut": "nut.height", "label-nut": "nut.height", "tapped": "tapped.material_id",
        "bearing-head": "bolt.head_bearing_diameter", "dim-dW": "bolt.head_bearing_diameter",
        "bearing-nut": "nut.bearing_diameter",
        "washer-head": "head_washer.thickness", "washer-nut": "nut_washer.thickness",
    }.get(role, "")


def _hatched_rect(x0: float, top: float, x1: float, bottom: float, fill: str, role: str, reverse: bool = False) -> list[Shape]:
    shapes = [Shape("rect", (x0, top, x1, bottom), fill=fill, stroke=PLATE_STROKE, role=role, stroke_width=1.4)]
    width, height = x1 - x0, bottom - top
    offset = 8.0
    while offset < width + height:
        start_x, start_y = max(0.0, offset - height), min(height, offset)
        end_x, end_y = min(width, offset), max(0.0, offset - width)
        if reverse:
            start_y, end_y = height - start_y, height - end_y
        shapes.append(Shape("line", (x0 + start_x, top + start_y, x0 + end_x, top + end_y),
                            stroke="#298fb5", role=role, stroke_width=0.7))
        offset += 8.0
    return shapes


def _hex_profile(cx: float, top: float, bottom: float, width: float, role: str, flipped: bool = False) -> list[Shape]:
    """Chamfered hex outline and the three curved face projections of a conventional elevation."""
    left, right = cx - width / 2, cx + width / 2
    bevel = min(width * 0.09, (bottom - top) * 0.23)

    def point(x: float, depth: float) -> tuple[float, float]:
        return x, bottom - depth if flipped else top + depth

    height = bottom - top
    outline = (*point(left, height), *point(left, bevel), *point(left + bevel, 0),
               *point(right - bevel, 0), *point(right, bevel), *point(right, height))
    shapes = [Shape("polygon", outline, fill=BOLT_FILL, stroke=BOLT_STROKE, role=role, stroke_width=1.6)]
    divisions = (left, cx - width / 4, cx + width / 4, right)
    for start, end in zip(divisions, divisions[1:]):
        points = []
        for index in range(17):
            t = index / 16
            points.extend(point(start + (end - start) * t, bevel * (2 * t - 1) ** 2))
        shapes.append(Shape("line", tuple(points), stroke=BOLT_STROKE, role=role, stroke_width=1.1))
    for x in divisions[1:-1]:
        shapes.append(Shape("line", (*point(x, bevel), *point(x, height)), stroke=BOLT_STROKE, role=role))
    return shapes


def _socket_head(cx: float, top: float, bottom: float, collar: float, dk: float, dw: float,
                 socket: float, depth: float, role: str) -> list[Shape]:
    """Cylindrical socket head: top edge chamfer, underside run-out to dW and a hexagon socket with drill point."""
    chamfer = min(0.06 * dk, 0.2 * (bottom - top))
    outline = (cx - dw / 2, bottom, cx - dk / 2, bottom - collar, cx - dk / 2, top + chamfer, cx - dk / 2 + chamfer, top,
               cx + dk / 2 - chamfer, top, cx + dk / 2, top + chamfer, cx + dk / 2, bottom - collar, cx + dw / 2, bottom)
    shapes = [Shape("polygon", outline, fill=BOLT_FILL, stroke=BOLT_STROKE, role=role, stroke_width=1.6)]
    depth = min(depth, 0.8 * (bottom - top))
    point = min(0.3 * socket, 0.9 * (bottom - top) - depth)
    recess = (cx - socket / 2, top, cx - socket / 2, top + depth, cx, top + depth + max(point, 0.0),
              cx + socket / 2, top + depth, cx + socket / 2, top)
    shapes.append(Shape("polygon", recess, fill=DRAWING_BACKGROUND, stroke=BOLT_STROKE, role=role, stroke_width=1.2))
    for x in (cx - socket / 4, cx + socket / 4):
        shapes.append(Shape("line", (x, top, x, top + depth), stroke=BOLT_STROKE, role=role, stroke_width=0.7))
    return shapes


def _bearing_ring(cx: float, level: float, inner: float, outer: float, role: str) -> list[Shape]:
    """Highlight the effective bearing annulus (dha … dW) on both sides of the axis."""
    return [
        Shape("line", (cx + sign * inner / 2, level, cx + sign * outer / 2, level),
              stroke=BEARING_STROKE, role=role, stroke_width=2.6)
        for sign in (-1, 1)
    ]


def head_drawing_sizes(bolt) -> dict[str, float]:
    """Head outline sizes in mm; catalog values when present, otherwise proportional estimates from dW."""
    dw = bolt.head_bearing_diameter
    # Stale values (e.g. after a manual dW change) must never draw a head smaller than its bearing face.
    if bolt.head_type == "hex":
        flats = bolt.head_width_across_flats
        flats = flats if flats and flats >= dw else dw / 0.92
        return {"width": flats * 2 / 3 ** 0.5, "flats": flats}
    dk = bolt.head_diameter
    dk = dk if dk and dk >= dw else dw * 1.05
    socket = bolt.socket_size
    depth = bolt.socket_depth
    return {
        "width": dk,
        "dk": dk,
        "socket": socket if socket and socket < 0.8 * dk else 0.42 * dk,
        "depth": depth if depth and depth < bolt.head_height else 0.5 * bolt.head_height,
    }


def _fmt(value: float) -> str:
    return f"{value:.4g}"


def general_section_shapes(
    item: GeneralInput,
    metrics: SectionMetrics,
    width: float,
    height: float,
    *,
    language: Language = "zh",
) -> tuple[Shape, ...]:
    t = partial(translate, language=language)
    if not (MIN_VIEW <= width <= MAX_VIEW and MIN_VIEW <= height <= MAX_VIEW):
        raise ValueError(f"绘图区域须在 {MIN_VIEW}–{MAX_VIEW} px 之间")
    bolt, joint, nut = item.bolt, item.joint, item.nut
    dsv = item.is_through_bolt
    clamp = metrics.clamp_length
    head_sizes = head_drawing_sizes(bolt)
    head_width = head_sizes["width"]
    # Front elevation of a hexagon shows the width across corners e = 2s/√3.
    nut_width = max(nut.width_across_flats, nut.bearing_diameter) * 2 / 3 ** 0.5
    shank_total = 0.0 if bolt.thread_length is None else bolt.length - bolt.thread_length
    if dsv:
        below = max(bolt.length, clamp + nut.height)
    else:
        below = max(bolt.length + 0.4 * bolt.d, clamp + metrics.engagement_length + 0.5 * bolt.d)
    total_mm = bolt.head_height + below
    across_mm = max(joint.outer_diameter, head_width, nut_width if dsv else 0.0,
                    *(washer.outer_diameter for side in ("head", "nut") if (washer := item.washer_at(side))))

    pad = 12.0
    left_band = min(64.0, width * 0.15)
    label_band = min(max(width * 0.32, 95.0), 230.0)
    top_band, bottom_band = 64.0, 40.0
    gx0, gx1 = pad + left_band, width - pad - label_band
    gy0, gy1 = pad + top_band, height - pad - bottom_band
    scale = min((gx1 - gx0) / across_mm, (gy1 - gy0) / total_mm)
    cx = (gx0 + gx1) / 2
    y_top = gy0

    def y(depth: float) -> float:
        return y_top + (bolt.head_height + depth) * scale

    def half(diameter: float) -> float:
        return diameter * scale / 2

    shapes: list[Shape] = [Shape("rect", (0.0, 0.0, width, height), fill=DRAWING_BACKGROUND, role="background")]
    for x in range(24, int(width), 24):
        shapes.append(Shape("line", (x, 0.0, x, height), stroke=GRID_STROKE, role="grid", stroke_width=0.5))
    for level in range(24, int(height), 24):
        shapes.append(Shape("line", (0.0, level, width, level), stroke=GRID_STROKE, role="grid", stroke_width=0.5))
    hatching: list[Shape] = []
    y_end = y(below)

    if not dsv:
        shapes.append(Shape(
            "rect", (cx - half(joint.outer_diameter), y(clamp), cx + half(joint.outer_diameter), y_end),
            fill=TAPPED_FILL, stroke=PLATE_STROKE, role="tapped",
        ))

    boundaries = [item.head_washer_thickness]
    for layer in item.plates:
        boundaries.append(boundaries[-1] + layer.thickness)
    for index, layer in enumerate(item.plates):
        top, bottom = y(boundaries[index]), y(boundaries[index + 1])
        fill = PLATE_FILLS[index % 2]
        for x0, x1 in (
            (cx - half(joint.outer_diameter), cx - half(joint.hole_diameter)),
            (cx + half(joint.hole_diameter), cx + half(joint.outer_diameter)),
        ):
            rectangle, *lines = _hatched_rect(x0, top, x1, bottom, fill, f"plate-{index}", reverse=bool(index % 2))
            shapes.append(rectangle)
            hatching.extend(lines)

    for side in ("head", "nut"):
        washer = item.washer_at(side)
        if washer:
            top = 0.0 if side == "head" else clamp - washer.thickness
            for sign in (-1, 1):
                x0, x1 = sorted((cx + sign * half(washer.inner_diameter), cx + sign * half(washer.outer_diameter)))
                shapes.extend(_hatched_rect(x0, y(top), x1, y(top + washer.thickness), "#173c55", f"washer-{side}"))

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
        item.plate_length, joint.outer_diameter, metrics.w, metrics.tan_phi,
        metrics.cone_start_head, metrics.cone_start_nut,
    )
    for side in (-1, 1):
        outline = []
        for depth in depths:
            diameter = deformation_diameter(
                depth, item.plate_length, joint.outer_diameter, metrics.w, metrics.tan_phi,
                metrics.cone_start_head, metrics.cone_start_nut,
            )
            outline.extend((cx + side * half(diameter), y(depth + item.head_washer_thickness)))
        polygon = (cx + side * half(joint.hole_diameter), y(boundaries[0]), *outline,
                   cx + side * half(joint.hole_diameter), y(boundaries[-1]))
        shapes.append(Shape("polygon", polygon, fill=CONE_FILL, stroke=CONE_FILL, dash=True, role="cone", opacity=0.06))
    shapes.extend(hatching)

    # Bearing face (washer face / underside run-out) of diameter dW; drawn thickness is visual only.
    collar = min(max(0.08 * bolt.head_height * scale, 2.0), 0.3 * bolt.head_height * scale)
    if bolt.head_type == "hex":
        shapes.extend(_hex_profile(cx, y_top, y(0.0) - collar, head_width * scale, "bolt-head"))
        shapes.append(Shape(
            "rect", (cx - half(bolt.head_bearing_diameter), y(0.0) - collar, cx + half(bolt.head_bearing_diameter), y(0.0)),
            fill=BOLT_FILL, stroke=BOLT_STROKE, role="bolt-head", stroke_width=1.4,
        ))
    else:
        shapes.extend(_socket_head(
            cx, y_top, y(0.0), collar, head_sizes["dk"] * scale, bolt.head_bearing_diameter * scale,
            head_sizes["socket"] * scale, head_sizes["depth"] * scale, "bolt-head",
        ))
    shapes.extend(_bearing_ring(cx, y(0.0), item.bearing_inner("head") * scale, item.bearing_outer("head") * scale, "bearing-head"))

    shank_end = min(max(shank_total, 0.0), bolt.length)
    shank_diameter = bolt.shank_diameter or bolt.d
    if shank_end > 0:
        shapes.append(Shape(
            "rect", (cx - half(shank_diameter), y(0.0), cx + half(shank_diameter), y(shank_end)),
            fill=BOLT_FILL, stroke=BOLT_STROKE, role="bolt-shank",
        ))
    if shank_end < bolt.length:
        tip = min(bolt.pitch * 0.6, (bolt.length - shank_end) / 3)
        shapes.append(Shape(
            "polygon", (cx - half(bolt.d), y(shank_end), cx + half(bolt.d), y(shank_end),
                        cx + half(bolt.d), y(bolt.length - tip), cx + half(bolt.d - 2 * tip), y(bolt.length),
                        cx - half(bolt.d - 2 * tip), y(bolt.length), cx - half(bolt.d), y(bolt.length - tip)),
            fill=THREAD_FILL, stroke=BOLT_STROKE, role="bolt-thread", stroke_width=1.6,
        ))
        for side in (-1, 1):
            shapes.append(Shape(
                "line", (cx + side * half(bolt.d3), y(shank_end), cx + side * half(bolt.d3), y(bolt.length)),
                stroke=BOLT_STROKE, role="bolt-thread", stroke_width=0.65,
            ))
        shapes.append(Shape("line", (cx - half(bolt.d), y(bolt.length - tip),
                                    cx + half(bolt.d), y(bolt.length - tip)), stroke=BOLT_STROKE, role="bolt-thread", stroke_width=0.7))
    if bolt.bore_diameter > 0:
        shapes.append(Shape(
            "rect", (cx - half(bolt.bore_diameter), y_top, cx + half(bolt.bore_diameter), y(bolt.length)),
            fill=DRAWING_BACKGROUND, stroke=BOLT_STROKE, role="bolt-bore",
        ))

    if dsv:
        nut_collar = min(max(0.08 * nut.height * scale, 2.0), 0.3 * nut.height * scale)
        shapes.extend(_hex_profile(cx, y(clamp) + nut_collar, y(clamp + nut.height), nut_width * scale, "nut", flipped=True))
        shapes.append(Shape(
            "rect", (cx - half(nut.bearing_diameter), y(clamp), cx + half(nut.bearing_diameter), y(clamp) + nut_collar),
            fill=BOLT_FILL, stroke=BOLT_STROKE, role="nut", stroke_width=1.4,
        ))
        shapes.extend(_bearing_ring(cx, y(clamp), item.bearing_inner("nut") * scale, item.bearing_outer("nut") * scale, "bearing-nut"))

    shapes.append(Shape("line", (cx, y_top - 6, cx, y_end + 6), stroke=MUTED_TEXT,
                        role="axis", dash_pattern=(12, 4, 2, 4), stroke_width=0.8))

    shapes.extend(_dimensions(item, metrics, cx, y, half, gx0, gy1))
    shapes.extend(_labels(item, metrics, cx, y, half, head_width, nut_width, gx1 + 10, gy0, gy1, y_top, language))
    class_text = f" · {bolt.property_class}" if bolt.property_class else ""
    bore_text = f" · {t('空心')} db {_fmt(bolt.bore_diameter)}" if bolt.bore_diameter else ""
    shank_text = f" · {t('细腰')} dT {_fmt(bolt.shank_diameter)}" if bolt.shank_diameter and bolt.shank_diameter < bolt.d else ""
    shapes.append(Shape(
        "text", (pad, pad + 6),
        fill=TEXT_FILL, size=12,
        text=f"{t('DSV 螺栓 + 螺母' if dsv else 'ESV 螺纹孔')} · M{_fmt(bolt.d)}×{_fmt(bolt.pitch)}{class_text} · l {_fmt(bolt.length)}{bore_text}{shank_text}",
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
        shapes.append(Shape("text", ((x0 + x1) / 2, y0 - 9), fill=TEXT_FILL, text=text, anchor="middle", role=role))
    length = abs(y1 - y0) if vertical else abs(x1 - x0)
    arrow = min(5.0, length / 4)
    for x, y, sign in ((x0, y0, 1), (x1, y1, -1)):
        points = (x, y, x - 2, y + sign * arrow, x + 2, y + sign * arrow) if vertical else (
            x, y, x + sign * arrow, y - 2, x + sign * arrow, y + 2)
        shapes.append(Shape("polygon", points, fill=DIMENSION_STROKE, role=role))
    return shapes


def _dimensions(item, metrics, cx, y, half, gx0, gy1) -> list[Shape]:
    clamp = metrics.clamp_length
    step = min(20.0, (gx0 - 14) / 3)
    shapes = _dimension(gx0 - 8 - step, y(0.0), gx0 - 8 - step, y(clamp), f"lK {_fmt(clamp)}", "dim-lK", True)
    shapes += _dimension(gx0 - 8 - 2 * step, y(0.0), gx0 - 8 - 2 * step, y(item.bolt.length), f"l {_fmt(item.bolt.length)}", "dim-l", True)
    depth = item.head_washer_thickness
    for index, layer in enumerate(item.plates):
        if y(depth + layer.thickness) - y(depth) >= 24:
            shapes += _dimension(gx0 - 8, y(depth), gx0 - 8, y(depth + layer.thickness),
                                 f"t{index + 1} {_fmt(layer.thickness)}", f"dim-t{index + 1}", True)
        depth += layer.thickness
    head_top = y(-item.bolt.head_height)
    dw = item.bolt.head_bearing_diameter
    shapes += _dimension(cx - half(dw), head_top - 16, cx + half(dw), head_top - 16, f"dW {_fmt(dw)}", "dim-dW", False)
    for sign in (-1, 1):
        shapes.append(Shape("line", (cx + sign * half(dw), head_top - 20, cx + sign * half(dw), y(0.0)),
                            stroke=DIMENSION_STROKE, role="dim-dW", stroke_width=0.6, dash_pattern=(2, 3)))
    shapes += _dimension(cx - half(item.bolt.d), head_top - 34, cx + half(item.bolt.d), head_top - 34,
                         f"d {_fmt(item.bolt.d)}", "dim-d", False)
    outer = item.joint.outer_diameter
    shapes += _dimension(cx - half(outer), gy1 + 20, cx + half(outer), gy1 + 20, f"DA {_fmt(outer)}", "dim-DA", False)
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


def _labels(item, metrics, cx, y, half, head_width, nut_width, label_x, top_limit, bottom_limit, y_top, language: Language = "zh") -> list[Shape]:
    t = partial(translate, language=language)
    bolt, nut, tapped = item.bolt, item.nut, item.tapped
    dsv = item.is_through_bolt
    layers = item.plates
    head_mu = f"μK {_fmt(bolt.bearing_friction)} · μG {_fmt(bolt.thread_friction)}"
    # (anchor y, anchor x, title, detail, short name, role)
    entries: list[tuple[float, float, str, str, str, str]] = [(
        (y_top + y(0.0)) / 2,
        cx + half(head_width),
        f"{t('螺栓头')} {t('外六角' if bolt.head_type == 'hex' else '内六角')}",
        f"dW {_fmt(bolt.head_bearing_diameter)} · {head_mu}",
        t("头"),
        "label-head",
    )]
    for side, depth in (("head", 0.0), ("nut", metrics.clamp_length - item.nut_washer_thickness)):
        washer = item.washer_at(side)
        if washer:
            entries.append((
                y(depth + washer.thickness / 2), cx + half(washer.outer_diameter),
                f"{t('头侧垫片' if side == 'head' else '螺母侧垫片')} · {washer.material_id or t('自定义')}",
                f"di {_fmt(washer.inner_diameter)} · Do {_fmt(washer.outer_diameter)} · t {_fmt(washer.thickness)}",
                t("垫片"), f"washer-{side}",
            ))
    depth = item.head_washer_thickness
    slip_layers = len(layers) - 1 if dsv else len(layers)
    for index, layer in enumerate(layers):
        middle = depth + layer.thickness / 2
        depth += layer.thickness
        detail = f"h {_fmt(layer.thickness)} · Rz {_fmt(layer.roughness_rz)}"
        if index < slip_layers:
            detail += f" · μT {_fmt(layer.interface_friction)}"
        material = layer.material_id or t("自定义")
        entries.append((
            y(middle), cx + half(item.joint.outer_diameter),
            f"{layer.name} · {material}", detail, layer.name, f"plate-{index}",
        ))
    clamp = metrics.clamp_length
    if dsv:
        entries.append((
            y(clamp + nut.height / 2), cx + half(nut_width),
            f"{t('螺母')} m {_fmt(nut.height)}", f"dW {_fmt(nut.bearing_diameter)} · {head_mu}", t("螺母"), "label-nut",
        ))
    else:
        material = tapped.material_id or t("自定义")
        entries.append((
            y(clamp + metrics.engagement_length / 2), cx + half(item.joint.outer_diameter),
            f"{t('内螺纹件')} · {material}",
            f"{t('旋合')} {_fmt(metrics.engagement_length)} · μG {_fmt(bolt.thread_friction)}",
            t("内螺纹"), "tapped",
        ))

    entries.sort(key=lambda entry: entry[0])
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
            shapes.append(Shape("line", (anchor_x + 2, anchor_y, label_x - 4, centre), stroke=MUTED_TEXT, role=role))
            shapes.append(Shape("text", (label_x, top + LINE_HEIGHT / 2), fill=TEXT_FILL, text=title, role=role))
            shapes.append(Shape("text", (label_x, top + 1.5 * LINE_HEIGHT), fill=MUTED_TEXT, text=detail, role=role, size=10.5))
        else:
            centre = top + step / 2
            shapes.append(Shape("line", (anchor_x + 2, anchor_y, label_x - 4, centre), stroke=MUTED_TEXT, role=role))
            shapes.append(Shape("text", (label_x, centre), fill=TEXT_FILL, text=f"{short} · {detail}", role=role, size=size))
    return shapes
