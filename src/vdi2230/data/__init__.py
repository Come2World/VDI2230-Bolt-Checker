"""Bundled, versioned engineering data (bolt catalog, Table A9 materials, VDI tables).

Bundled records are accepted as the project's calculation baseline. Source
and audit notes remain available; model assumptions still require review.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json
import math
from typing import Any


PROVISIONAL_STATUSES = frozenset({
    "provisional",
    "provisional_conflict",
    "secondary_reference_only",
})
STEEL_YOUNGS_MODULUS_MPA = 205_000.0
A2_MODULUS_MATERIAL_ID = "X5CrNi18-10"
FULL_THREAD_STANDARDS = frozenset({"ISO 4017"})


def _read_json(*parts: str) -> dict[str, Any]:
    text = files(__name__).joinpath(*parts).read_text(encoding="utf-8")
    return json.loads(text)


@lru_cache(maxsize=1)
def _bolt_catalog() -> dict[str, Any]:
    return _read_json("bolt_catalog", "catalog.json")


@lru_cache(maxsize=1)
def _materials() -> dict[str, Any]:
    return _read_json("plate_materials.json")


@lru_cache(maxsize=1)
def _tables() -> dict[str, Any]:
    return _read_json("vdi_tables.json")


def bolt_catalog_document() -> dict[str, Any]:
    """Return a fresh copy of the raw bolt catalog document."""
    return json.loads(json.dumps(_bolt_catalog()))


@dataclass(frozen=True)
class BoltVariant:
    variant_id: str
    standard: str
    size_id: str
    nominal_diameter: float
    pitch: float
    pitch_diameter: float
    minor_diameter: float
    stress_area: float
    head_height: float
    width_across_flats: float | None
    threading: str
    thread_lengths: tuple[float | None, float | None, float | None]
    head_bearing_diameter: float
    clearance_holes: tuple[float, float, float]
    nut_height: float
    nut_bearing_diameter: float
    verification_status: str
    head_type: str = "hex"
    head_diameter: float | None = None
    socket_size: float | None = None
    socket_depth: float | None = None
    full_thread_max_length: float | None = None
    nut_width_across_flats: float | None = None

    @property
    def label(self) -> str:
        return f"{self.standard} M{self.nominal_diameter:g}×{self.pitch:g}"

    def thread_length_for(self, length: float) -> float | None:
        """Reference thread length b by nominal length; None = full thread.

        ISO 4014 selects b1/b2/b3 by length; ISO 4762 is fully threaded up to
        its tabulated limit and uses the single reference b above it.
        """
        if self.threading == "full":
            return None
        if self.full_thread_max_length is not None:
            return None if length <= self.full_thread_max_length else self.thread_lengths[0]
        b1, b2, b3 = self.thread_lengths
        value = b1 if length <= 125 else b2 if length <= 200 else b3
        if value is None:
            raise ValueError(f"{self.variant_id} has no thread length for l={length:g} mm")
        return value


@dataclass(frozen=True)
class PropertyClassRecord:
    property_class: str
    diameter_min: float
    diameter_min_inclusive: bool
    diameter_max: float
    diameter_max_inclusive: bool
    tensile_strength: float
    yield_strength: float
    verification_status: str
    source_ids: tuple[str, ...]
    applicability_note: str | None

    def applies_to(self, diameter: float) -> bool:
        above = (
            diameter > self.diameter_min
            or (self.diameter_min_inclusive and diameter == self.diameter_min)
        )
        below = (
            diameter < self.diameter_max
            or (self.diameter_max_inclusive and diameter == self.diameter_max)
        )
        return above and below


@dataclass(frozen=True)
class MaterialRecord:
    material_id: str
    name: str
    group: str
    group_label: str
    youngs_modulus: float
    tensile_strength: float
    yield_strength: float
    shear_strength: float
    limiting_surface_pressure: float
    thermal_expansion: float | None
    verification_status: str


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


@lru_cache(maxsize=1)
def bolt_variants() -> tuple[BoltVariant, ...]:
    catalog = _bolt_catalog()
    sizes = {row["size_id"]: row for row in catalog["thread_sizes"]}
    joints = {row["thread_size_id"]: row for row in catalog["joint_dimension_records"]}
    variants = []
    for row in catalog["bolt_geometries"]:
        size = sizes[row["thread_size_id"]]
        joint = joints[row["thread_size_id"]]
        statuses = {row["verification_status"], size["verification_status"], joint["verification_status"]}
        variants.append(BoltVariant(
            variant_id=row["variant_id"],
            standard=row["standard"],
            size_id=row["thread_size_id"],
            nominal_diameter=float(size["nominal_diameter_mm"]),
            pitch=float(size["pitch_mm"]),
            pitch_diameter=float(size["pitch_diameter_d2_mm"]),
            minor_diameter=float(size["external_thread_minor_diameter_d3_mm"]),
            stress_area=float(size["tensile_stress_area_as_mm2"]),
            head_height=float(row["head_height_k_mm"]),
            width_across_flats=_optional_float(row.get("width_across_flats_s_mm")),
            threading=row["threading"],
            thread_lengths=(
                (row["thread_length_b_mm"], None, None) if "thread_length_b_mm" in row else (
                    row["thread_length_b1_mm"],
                    row["thread_length_b2_mm"],
                    row["thread_length_b3_mm"],
                )
            ),
            # Socket screws carry their own dw; hex bolts share the ISO 4014 joint record.
            head_bearing_diameter=float(row.get("head_bearing_diameter_dw_mm", joint["head_bearing_diameter_dw_min_mm"])),
            clearance_holes=(
                float(joint["clearance_hole_fine_mm"]),
                float(joint["clearance_hole_medium_mm"]),
                float(joint["clearance_hole_coarse_mm"]),
            ),
            nut_height=float(joint["nut_iso4032_height_m_max_mm"]),
            nut_bearing_diameter=float(joint["nut_iso4032_bearing_diameter_dw_min_mm"]),
            nut_width_across_flats=float(joint["nut_iso4032_width_across_flats_s_mm"]),
            head_type=row.get("head_type", "hex"),
            head_diameter=_optional_float(row.get("head_diameter_dk_mm")),
            socket_size=_optional_float(row.get("socket_size_s_mm")),
            socket_depth=_optional_float(row.get("socket_depth_t_mm")),
            full_thread_max_length=_optional_float(row.get("full_thread_max_length_mm")),
            verification_status=(
                "accepted_baseline" if statuses == {"accepted_baseline"}
                else "provisional_conflict" if "provisional_conflict" in statuses else "provisional"
            ),
        ))
    return tuple(variants)


def bolt_variant(variant_id: str) -> BoltVariant:
    for variant in bolt_variants():
        if variant.variant_id == variant_id:
            return variant
    raise KeyError(variant_id)


@lru_cache(maxsize=1)
def property_classes() -> tuple[PropertyClassRecord, ...]:
    return tuple(
        PropertyClassRecord(
            property_class=row["property_class"],
            diameter_min=float(row["diameter_min_mm"]),
            diameter_min_inclusive=row["diameter_min_inclusive"],
            diameter_max=float(row["diameter_max_mm"]),
            diameter_max_inclusive=row["diameter_max_inclusive"],
            tensile_strength=float(row["tensile_strength_min_mpa"]),
            yield_strength=float(row["yield_strength_min_mpa"]),
            verification_status=row["verification_status"],
            source_ids=tuple(row["source_ids"]),
            applicability_note=row.get("applicability_note"),
        )
        for row in _bolt_catalog()["property_class_records"]
    )


def property_class_record(property_class: str, diameter: float) -> PropertyClassRecord:
    matches = [
        row for row in property_classes()
        if row.property_class == property_class and row.applies_to(diameter)
    ]
    if len(matches) != 1:
        raise KeyError(f"{property_class} @ d={diameter:g}")
    return matches[0]


def candidate_lengths() -> tuple[float, ...]:
    return tuple(float(value) for value in _bolt_catalog()["length_catalog"]["candidate_nominal_lengths_mm"])


@lru_cache(maxsize=1)
def materials() -> tuple[MaterialRecord, ...]:
    return tuple(
        MaterialRecord(
            material_id=row["material_id"],
            name=row["name"],
            group=row["group"],
            group_label=row["group_label_zh"],
            youngs_modulus=float(row["youngs_modulus_mpa"]),
            tensile_strength=float(row["tensile_strength_rm_min_mpa"]),
            yield_strength=float(row["yield_strength_rp02_min_mpa"]),
            shear_strength=float(row["shear_strength_tau_b_min_mpa"]),
            limiting_surface_pressure=float(row["limiting_surface_pressure_pg_mpa"]),
            thermal_expansion=row["thermal_expansion_1e6_per_k"],
            verification_status=row["verification_status"],
        )
        for row in _materials()["materials"]
    )


def material(material_id: str) -> MaterialRecord:
    for record in materials():
        if record.material_id == material_id:
            return record
    raise KeyError(material_id)


def shear_strength_ratio(property_class: str) -> float | None:
    value = _tables()["shear_strength_ratio"]["values"].get(property_class)
    return None if value is None else float(value)


def load_introduction_types() -> tuple[str, ...]:
    return tuple(_tables()["load_introduction_factor_n"]["values"])


def _interpolate(axis: list[float], value: float) -> tuple[int, int, float]:
    if value <= axis[0]:
        return 0, 0, 0.0
    if value >= axis[-1]:
        last = len(axis) - 1
        return last, last, 0.0
    for index in range(len(axis) - 1):
        low, high = axis[index], axis[index + 1]
        if low <= value <= high:
            return index, index + 1, (value - low) / (high - low)
    raise AssertionError("unreachable")


def load_introduction_factor(joint_class: str, la_over_h: float, ak_over_h: float) -> float:
    """VDI 2230 Table 2: bilinear interpolation, clamped to the table limits."""
    table = _tables()["load_introduction_factor_n"]
    if joint_class not in table["values"]:
        raise KeyError(joint_class)
    for name, value in (("lA/h", la_over_h), ("ak/h", ak_over_h)):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")
    grid = table["values"][joint_class]
    i0, i1, ti = _interpolate(table["la_over_h"], la_over_h)
    j0, j1, tj = _interpolate(table["ak_over_h"], ak_over_h)
    low = grid[i0][j0] + (grid[i0][j1] - grid[i0][j0]) * tj
    high = grid[i1][j0] + (grid[i1][j1] - grid[i1][j0]) * tj
    return low + (high - low) * ti


def embedding_values(roughness_um: float, shear: bool) -> tuple[float, float, float]:
    """VDI 2230 Table 5 guide values (thread, bearing, interface) in μm."""
    if not math.isfinite(roughness_um) or roughness_um < 0:
        raise ValueError("Rz must be finite and non-negative")
    load = "shear" if shear else "axial"
    for row in _tables()["embedding_um"]["rows"]:
        if row["load"] == load and row["rz_min_um"] <= roughness_um < row["rz_max_um"]:
            return float(row["thread"]), float(row["bearing"]), float(row["interface"])
    raise ValueError("Rz ≥ 160 μm is outside VDI 2230 Table 5; enter fZ manually")


def tightening_factor_presets() -> tuple[dict[str, Any], ...]:
    return tuple(dict(row) for row in _tables()["tightening_factor_alpha_a"]["rows"])


def table_status(table_key: str) -> str:
    return _tables()[table_key]["verification_status"]


def source_is_provisional(source: str) -> bool:
    """Whether a provenance tag refers to a record that still needs verification.

    Tags: ``catalog:<variant_id>``, ``class:<property_class>``,
    ``material:<material_id>``, ``table:<vdi table key>`` and
    ``default:<note>`` refer to bundled data; ``user`` / ``user:<note>`` are
    values the engineer entered and is responsible for.
    """
    kind, _, key = source.partition(":")
    try:
        if kind == "catalog":
            status = bolt_variant(key).verification_status
        elif kind == "class":
            status = next(row for row in property_classes() if row.property_class == key).verification_status
        elif kind == "material":
            status = material(key).verification_status
        elif kind == "table":
            status = table_status(key)
        elif kind == "default":
            return True
        else:
            return False
    except (KeyError, StopIteration):
        return True
    return status in PROVISIONAL_STATUSES


def friction_classes() -> tuple[dict[str, Any], ...]:
    return tuple(dict(row) for row in _tables()["friction_classes"]["rows"])


def is_a2_bolt_class(property_class: object) -> bool:
    return isinstance(property_class, str) and property_class.strip().upper().startswith("A2-")


def bolt_catalog_values(
    variant_id: str,
    length: float,
    property_class: str,
) -> dict[str, float | str | None]:
    """Catalog-first values for the general input, keyed by input path."""
    variant = bolt_variant(variant_id)
    strength = property_class_record(property_class, variant.nominal_diameter)
    ratio = shear_strength_ratio(property_class)
    return {
        "bolt.head_type": variant.head_type,
        "bolt.d": variant.nominal_diameter,
        "bolt.pitch": variant.pitch,
        "bolt.d2": variant.pitch_diameter,
        "bolt.d3": variant.minor_diameter,
        "bolt.stress_area": round(variant.stress_area, 3),
        "bolt.head_bearing_diameter": variant.head_bearing_diameter,
        "bolt.head_height": variant.head_height,
        "bolt.head_width_across_flats": variant.width_across_flats,
        "bolt.head_diameter": variant.head_diameter,
        "bolt.socket_size": variant.socket_size,
        "bolt.socket_depth": variant.socket_depth,
        "bolt.thread_length": variant.thread_length_for(length),
        "bolt.shank_diameter": variant.nominal_diameter,
        "bolt.youngs_modulus": (
            material(A2_MODULUS_MATERIAL_ID).youngs_modulus
            if is_a2_bolt_class(property_class) else STEEL_YOUNGS_MODULUS_MPA
        ),
        "bolt.yield_strength": strength.yield_strength,
        "bolt.tensile_strength": strength.tensile_strength,
        "bolt.shear_ratio": ratio,
        "joint.hole_diameter": variant.clearance_holes[1],
        "nut.height": variant.nut_height,
        "nut.bearing_diameter": variant.nut_bearing_diameter,
        "nut.width_across_flats": variant.nut_width_across_flats,
    }


STRENGTH_PATHS = frozenset({"bolt.yield_strength", "bolt.tensile_strength"})
SHEAR_RATIO_PATH = "bolt.shear_ratio"
CATALOG_GEOMETRY_PATHS = (
    "bolt.head_type",
    "bolt.d",
    "bolt.pitch",
    "bolt.d2",
    "bolt.d3",
    "bolt.stress_area",
    "bolt.head_bearing_diameter",
    "bolt.head_height",
    "bolt.head_width_across_flats",
    "bolt.head_diameter",
    "bolt.socket_size",
    "bolt.socket_depth",
    "bolt.thread_length",
    "bolt.shank_diameter",
    "bolt.youngs_modulus",
    "joint.hole_diameter",
    "nut.height",
    "nut.bearing_diameter",
    "nut.width_across_flats",
)
MATERIAL_FIELDS_BY_TARGET = {
    "plates": ("youngs_modulus", "limiting_surface_pressure"),
    "tapped": ("youngs_modulus", "tensile_strength", "shear_strength"),
}


def uses_a2_bolt(property_class: object, provenance: Mapping[str, str]) -> bool:
    if is_a2_bolt_class(property_class):
        return True
    sources = (provenance.get(path, "") for path in STRENGTH_PATHS)
    return any(
        source.startswith("class:") and is_a2_bolt_class(source.removeprefix("class:"))
        for source in sources
    ) or provenance.get("bolt.youngs_modulus") == f"material:{A2_MODULUS_MATERIAL_ID}"


def catalog_value_sources(variant_id: str, property_class: str) -> dict[str, str]:
    """Provenance tags for the values ``bolt_catalog_values`` fills in."""
    sources = {path: f"catalog:{variant_id}" for path in CATALOG_GEOMETRY_PATHS}
    sources.update({path: f"class:{property_class}" for path in STRENGTH_PATHS})
    if is_a2_bolt_class(property_class):
        sources["bolt.youngs_modulus"] = f"material:{A2_MODULUS_MATERIAL_ID}"
    if shear_strength_ratio(property_class) is not None:
        sources[SHEAR_RATIO_PATH] = "table:shear_strength_ratio"
    return sources


def material_value_sources(material_id: str, prefix: str) -> dict[str, str]:
    """Provenance tags for material values copied into ``prefix`` (``tapped`` or ``plates[i]``)."""
    target = "plates" if prefix.startswith("plates[") else prefix
    return {f"{prefix}.{name}": f"material:{material_id}" for name in MATERIAL_FIELDS_BY_TARGET[target]}


def material_values(material_id: str) -> dict[str, float]:
    record = material(material_id)
    return {
        "youngs_modulus": record.youngs_modulus,
        "limiting_surface_pressure": record.limiting_surface_pressure,
        "tensile_strength": record.tensile_strength,
        "shear_strength": record.shear_strength,
    }


def catalog_summary() -> dict[str, Any]:
    """JSON-serializable lookup data for user interfaces."""
    def class_sort_key(value: str) -> tuple[int, float, str]:
        try:
            return (0, float(value), "")
        except ValueError:
            return (1, 0.0, value)

    return {
        "catalog_version": _bolt_catalog()["catalog_version"],
        "status": _bolt_catalog()["catalog_status"],
        "bolts": [
            {
                "variant_id": variant.variant_id,
                "standard": variant.standard,
                "size_id": variant.size_id,
                "label": variant.label,
                "nominal_diameter": variant.nominal_diameter,
                "threading": variant.threading,
                "head_type": variant.head_type,
            }
            for variant in bolt_variants()
        ],
        "property_classes": sorted({row.property_class for row in property_classes()}, key=class_sort_key),
        "lengths": list(candidate_lengths()),
        "materials": [
            {
                "material_id": record.material_id,
                "name": record.name,
                "group": record.group_label,
                **material_values(record.material_id),
            }
            for record in materials()
        ],
        "load_introduction_types": list(load_introduction_types()),
        "tightening_presets": list(tightening_factor_presets()),
    }
