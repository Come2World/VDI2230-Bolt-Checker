"""Toolkit-neutral form state for the desktop general calculator.

Mirrors the behaviour of ``web/static/app.js`` (catalog fill, material fill,
layer editing, field visibility) so the Tk window only binds widgets. Nothing
here imports tkinter, which keeps the logic testable without a display.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
from typing import Any

from vdi2230 import data as engineering_data
from vdi2230.calculations.general import GeneralCalculationResult, calculate_general
from vdi2230.domain.general_inputs import (
    InputValidationError,
    WASHER_ESTIMATE_SOURCE,
    WASHER_SECTIONS,
    field_schema_json,
    parse_general_input,
)
from vdi2230.infrastructure.general_report import render_general_report
from vdi2230.infrastructure.general_section import TEXT_FILL, Shape, section_target
from vdi2230.i18n import Language, translate


DEFAULT_TITLE = "通用螺栓连接"
CATALOG_PATHS = ("bolt.catalog_variant_id", "bolt.property_class")
BOLT_MATERIAL = frozenset({
    "bolt.youngs_modulus", "bolt.yield_strength", "bolt.tensile_strength", "bolt.tensile_strength_max",
    "bolt.shear_ratio", "bolt.rolling", "bolt.thread_friction", "bolt.bearing_friction",
})
MATERIAL_FIELDS = {
    "plates": ("youngs_modulus", "limiting_surface_pressure"),
    "tapped": ("youngs_modulus", "tensile_strength", "shear_strength"),
    "head_washer": ("youngs_modulus", "limiting_surface_pressure"),
    "nut_washer": ("youngs_modulus", "limiting_surface_pressure"),
}
INPUT_TABS = (("bolt", "螺栓"), ("plates", "板层"), ("load", "载荷"), ("assembly", "装配"))
KEY_METRICS = (("lK", "lK"), ("Φn", "Φn"), ("FMzul", "FMzul"), ("FSmax", "FS,max"), ("FKRmin", "FKR,min"), ("MA", "MA"))
TEXT_ANCHORS = {"start": "w", "middle": "center", "end": "e"}
_LAYER_PATH = re.compile(r"^plates\[(\d+)]\.(\w+)$")
_PLATE_ROLE = re.compile(r"^plate-(\d+)$")


def fmt(value: Any) -> str:
    """Compact display with four significant digits (same rule as the web UI)."""
    if value is None:
        return "—"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if not math.isfinite(value):
        return "—"
    if value == 0:
        return "0"
    magnitude = abs(value)
    if magnitude < 1e-3 or magnitude >= 1e9:
        return f"{value:.3e}"
    if magnitude >= 1000:
        return str(round(value))
    return f"{float(f'{value:.4g}'):g}"


def entry_text(value: Any) -> str:
    """Lossless text for an entry widget (no rounding of catalog values)."""
    if value is None:
        return ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def coerce(spec: dict[str, Any], raw: Any) -> Any:
    """Convert widget text to the model value; unparsable text is kept so validation can report it."""
    if spec["kind"] == "bool":
        return bool(raw)
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if text == "":
        return None
    if spec["kind"] in ("float", "int"):
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return text
        return number if math.isfinite(number) else text
    return text


def relevant(path: str, values: dict[str, Any]) -> bool:
    if path.startswith(("nut.", "nut_washer.")):
        return values.get("joint.type") == "DSV"
    if path.startswith("tapped."):
        return values.get("joint.type") == "ESV"
    if path == "load_introduction.n":
        return values.get("load_introduction.mode") == "manual"
    if path in ("load_introduction.joint_class", "load_introduction.la_over_h", "load_introduction.ak_over_h"):
        return values.get("load_introduction.mode") == "table"
    if path == "embedding.fz_um":
        return values.get("embedding.mode") == "manual"
    if path == "embedding.interface_count":
        return values.get("embedding.mode") == "table"
    return True


def subsection_of(spec: dict[str, Any]) -> str:
    section = spec["path"].split(".")[0]
    group = spec["group"]
    if group == "bolt":
        if section == "joint":
            return "连接与目录"
        if section == "bolt":
            return "螺栓材料与摩擦" if spec["path"] in BOLT_MATERIAL else "螺栓几何"
        return "螺母（DSV）" if section == "nut" else "内螺纹件（ESV）"
    if group == "plates":
        return {"head_washer": "头侧垫片", "nut_washer": "螺母侧垫片（DSV）"}.get(section, "孔与外径")
    if group == "load":
        return "载荷导入系数 n" if section == "load_introduction" else "外载荷"
    return {"assembly": "拧紧", "embedding": "嵌入", "advanced": "高级选项", "requirements": "安全系数要求"}.get(section, section)


def plate_index(tags: tuple[str, ...] | list[str]) -> int | None:
    for tag in tags:
        match = _PLATE_ROLE.match(tag)
        if match:
            return int(match.group(1))
    return None


def canvas_item(shape: Shape) -> tuple[str, tuple[float, ...], dict[str, Any]]:
    """Map a section ``Shape`` to a Tk canvas ``create_*`` call: (kind, coordinates, options)."""
    tags = (shape.role, "plate") if _PLATE_ROLE.match(shape.role) else ((shape.role,) if shape.role else ())
    if target := section_target(shape.role):
        tags += ("interactive", f"target:{target}")
    fill = "" if shape.fill in ("", "none") else shape.fill
    dash = shape.dash_pattern or ((4, 3) if shape.dash else ())
    if shape.kind == "rect":
        return "rectangle", shape.points, {"fill": fill, "outline": shape.stroke, "dash": dash, "tags": tags, "width": shape.stroke_width}
    if shape.kind == "polygon":
        # Canvas has no alpha compositing: leave translucent overlays unfilled, not opaque pastel.
        return "polygon", shape.points, {
            "fill": fill if shape.opacity >= 1 else "", "outline": shape.stroke, "dash": dash, "tags": tags, "width": shape.stroke_width,
        }
    if shape.kind == "line":
        return "line", shape.points, {"fill": shape.stroke or TEXT_FILL, "dash": dash, "tags": tags, "width": shape.stroke_width}
    if shape.kind == "text":
        return "text", shape.points[:2], {
            "text": shape.text,
            "fill": fill or TEXT_FILL,
            "anchor": TEXT_ANCHORS.get(shape.anchor, "w"),
            "font": ("Helvetica", -max(8, round(shape.size))),
            "angle": -shape.rotate,
            "tags": tags,
        }
    raise ValueError(f"未知图形类型：{shape.kind}")


@dataclass
class Layer:
    values: dict[str, Any]
    prov: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FieldError:
    path: str
    message: str


@dataclass(frozen=True)
class Outcome:
    result: GeneralCalculationResult | None = None
    report: str = ""
    error: str = ""
    field_errors: tuple[FieldError, ...] = ()

    @property
    def ok(self) -> bool:
        return self.result is not None


class GeneralFormModel:
    def __init__(self) -> None:
        schema = field_schema_json()
        self.schema_id: str = schema["schema"]
        self.max_layers: int = schema["max_layers"]
        self.fields: tuple[dict[str, Any], ...] = tuple(schema["fields"])
        self.layer_fields: tuple[dict[str, Any], ...] = tuple(schema["layer_fields"])
        self.specs = {spec["path"]: spec for spec in self.fields}
        self.layer_specs = {spec["path"]: spec for spec in self.layer_fields}
        self.catalog = engineering_data.catalog_summary()
        self.materials = {record["material_id"]: record for record in self.catalog["materials"]}
        self.provisional: set[str] = set()
        self.reset(schema["defaults"])

    # ----- state -----

    def reset(self, defaults: dict[str, Any]) -> None:
        self.title = defaults.get("title") or DEFAULT_TITLE
        self.values: dict[str, Any] = {}
        for spec in self.fields:
            section, name = spec["path"].split(".")
            self.values[spec["path"]] = (defaults.get(section) or {}).get(name)
        self.layers = [Layer(dict(values)) for values in defaults["plates"]]
        self.prov: dict[str, str] = {}
        for path, source in (defaults.get("provenance") or {}).items():
            match = _LAYER_PATH.match(path)
            if match and int(match.group(1)) < len(self.layers):
                self.layers[int(match.group(1))].prov[match.group(2)] = source
            elif not match:
                self.prov[path] = source
        self.selected = 0

    def source_for(self, path: str) -> str | None:
        match = _LAYER_PATH.match(path)
        if match:
            index = int(match.group(1))
            return self.layers[index].prov.get(match.group(2)) if index < len(self.layers) else None
        return self.prov.get(path)

    def label_for(self, path: str) -> str:
        match = _LAYER_PATH.match(path)
        if match:
            spec = self.layer_specs.get(match.group(2))
            return f"板层 {int(match.group(1)) + 1} · {spec['label'] if spec else match.group(2)}"
        spec = self.specs.get(path)
        if spec and path.split(".")[0] in WASHER_SECTIONS:
            return f"{subsection_of(spec)} · {spec['label']}"
        return spec["label"] if spec else (path or "输入")

    def is_relevant(self, path: str) -> bool:
        return relevant(path, self.values)

    # ----- edits -----

    def set_value(self, path: str, value: Any) -> str | None:
        """Store a user edit; returns a message when a catalog lookup fails."""
        if path not in self.specs:
            raise KeyError(path)
        self.values[path] = value
        self.prov.pop(path, None)
        if path in CATALOG_PATHS:
            return self.apply_catalog(force=True)
        if path == "bolt.length" and self.values.get("bolt.catalog_variant_id"):
            return self.apply_catalog(force=False)
        section, name = path.split(".")
        if name == "material_id":
            self._apply_material(value, section)
        if path == "bolt.d":
            self.refresh_washer_estimates()
        return None

    def refresh_washer_estimates(self) -> None:
        diameter = self.values.get("bolt.d")
        if isinstance(diameter, bool) or not isinstance(diameter, (int, float)) or not math.isfinite(diameter) or diameter <= 0:
            return
        for spec in self.fields:
            factor = spec["diameter_factor"]
            if factor is not None and self.prov.get(spec["path"]) == WASHER_ESTIMATE_SOURCE:
                self.values[spec["path"]] = round(diameter * factor, 6)

    def apply_catalog(self, force: bool) -> str | None:
        """Fill bolt/nut geometry from the catalog.

        ``force`` overwrites everything (new variant or class); otherwise only
        values whose provenance is still the catalog source are refreshed, so
        user overrides survive a length change.
        """
        variant = self.values.get("bolt.catalog_variant_id")
        property_class = self.values.get("bolt.property_class")
        length = self.values.get("bolt.length")
        if not variant or not property_class or isinstance(length, bool) or not isinstance(length, (int, float)):
            return None
        if not math.isfinite(length) or length <= 0:
            return None
        try:
            values = engineering_data.bolt_catalog_values(variant, float(length), property_class)
            sources = engineering_data.catalog_value_sources(variant, property_class)
        except (KeyError, ValueError, StopIteration):
            return f"目录中没有 {variant} / {property_class} 的组合。"
        for path, value in values.items():
            source = sources.get(path)
            if not force and (not source or self.prov.get(path) != source):
                continue
            self.values[path] = value
            if source:
                self.prov[path] = source
        self.refresh_washer_estimates()
        return None

    def _apply_material(self, material_id: Any, kind: str, layer: Layer | None = None) -> None:
        record = self.materials.get(material_id) if isinstance(material_id, str) else None
        if record is None:
            return
        for name in MATERIAL_FIELDS[kind]:
            if layer is None:
                self.values[f"{kind}.{name}"] = record[name]
                self.prov[f"{kind}.{name}"] = f"material:{material_id}"
            else:
                layer.values[name] = record[name]
                layer.prov[name] = f"material:{material_id}"

    def set_layer_value(self, index: int, name: str, value: Any) -> None:
        if name not in self.layer_specs:
            raise KeyError(name)
        layer = self.layers[index]
        layer.values[name] = value
        layer.prov.pop(name, None)
        if name == "material_id":
            self._apply_material(value, "plates", layer)

    def layer_summary(self, index: int) -> str:
        values = self.layers[index].values
        return f"{index + 1}. {values.get('name') or '（未命名）'} · {values.get('material_id') or '自定义'} · h {fmt(values.get('thickness'))}"

    def layer_name(self, index: int) -> str:
        return self.layers[index].values.get("name") or f"板层 {index + 1}"

    def _unique_layer_name(self) -> str:
        names = {layer.values.get("name") for layer in self.layers}
        number = len(self.layers) + 1
        while f"板 {number}" in names:
            number += 1
        return f"板 {number}"

    def add_layer(self) -> bool:
        """Insert a copy of the selected layer below it and select the new layer."""
        if len(self.layers) >= self.max_layers:
            return False
        base = self.layers[self.selected]
        self.layers.insert(self.selected + 1, Layer({**base.values, "name": self._unique_layer_name()}, dict(base.prov)))
        self.selected += 1
        return True

    def remove_layer(self, index: int) -> bool:
        if len(self.layers) <= 1 or not 0 <= index < len(self.layers):
            return False
        del self.layers[index]
        if self.selected > index or self.selected >= len(self.layers):
            self.selected -= 1
        return True

    def move_layer(self, index: int, direction: int) -> bool:
        target = index + direction
        if not (0 <= index < len(self.layers) and 0 <= target < len(self.layers)):
            return False
        self.layers[index], self.layers[target] = self.layers[target], self.layers[index]
        self.selected = target
        return True

    def select_layer(self, index: int) -> None:
        if not 0 <= index < len(self.layers):
            raise IndexError(index)
        self.selected = index

    # ----- calculation -----

    def to_input_json(self) -> dict[str, Any]:
        item: dict[str, Any] = {"schema": self.schema_id, "title": self.title.strip() or DEFAULT_TITLE}
        for spec in self.fields:
            section, name = spec["path"].split(".")
            item.setdefault(section, {})[name] = self.values.get(spec["path"])
        item["plates"] = [dict(layer.values) for layer in self.layers]
        provenance = dict(self.prov)
        for index, layer in enumerate(self.layers):
            for name, source in layer.prov.items():
                provenance[f"plates[{index}].{name}"] = source
        item["provenance"] = provenance
        return item

    def calculate(self, language: Language = "zh") -> Outcome:
        try:
            result = calculate_general(parse_general_input(self.to_input_json()))
        except InputValidationError as exc:
            return Outcome(
                error=translate(f"输入有误（{len(exc.errors)} 项），请修正标红字段。", language),
                field_errors=tuple(FieldError(error.path, translate(error.message, language)) for error in exc.errors),
            )
        except (ValueError, ArithmeticError) as exc:
            return Outcome(error=translate(f"计算无法完成，请检查输入：{exc}", language))
        self.provisional = {entry.split(" ← ")[0] for entry in result.provisional_sources}
        calculated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return Outcome(result=result, report=render_general_report(result, calculated_at=calculated_at, language=language))
