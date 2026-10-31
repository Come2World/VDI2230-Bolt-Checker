"""Bundled, versioned engineering data (bolt catalog, Table A9 materials, VDI tables).

All records are currently provisional transcriptions. Values may be used in
calculations, but every result that relies on them must be flagged for review.
"""
from __future__ import annotations

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
    width_across_flats: float
    threading: str
    thread_lengths: tuple[float | None, float | None, float | None]
    head_bearing_diameter: float
    clearance_holes: tuple[float, float, float]
    nut_height: float
    nut_bearing_diameter: float
    verification_status: str

    @property
    def label(self) -> str:
        return f"{self.standard} M{self.nominal_diameter:g}×{self.pitch:g}"

    def thread_length_for(self, length: float) -> float | None:
        """ISO 4014 reference thread length b by nominal length; None = full thread."""
        if self.threading == "full":
            return None
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
            width_across_flats=float(row["width_across_flats_s_mm"]),
            threading=row["threading"],
            thread_lengths=(
                row["thread_length_b1_mm"],
                row["thread_length_b2_mm"],
                row["thread_length_b3_mm"],
            ),
            head_bearing_diameter=float(joint["head_bearing_diameter_dw_min_mm"]),
            clearance_holes=(
                float(joint["clearance_hole_fine_mm"]),
                float(joint["clearance_hole_medium_mm"]),
                float(joint["clearance_hole_coarse_mm"]),
            ),
            nut_height=float(joint["nut_iso4032_height_m_max_mm"]),
            nut_bearing_diameter=float(joint["nut_iso4032_bearing_diameter_dw_min_mm"]),
            verification_status=(
                "provisional_conflict" if "provisional_conflict" in statuses else "provisional"
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


def friction_classes() -> tuple[dict[str, Any], ...]:
    return tuple(dict(row) for row in _tables()["friction_classes"]["rows"])


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
        "bolt.head_type": "hex",
        "bolt.d": variant.nominal_diameter,
        "bolt.pitch": variant.pitch,
        "bolt.d2": variant.pitch_diameter,
        "bolt.d3": variant.minor_diameter,
        "bolt.stress_area": round(variant.stress_area, 3),
        "bolt.head_bearing_diameter": variant.head_bearing_diameter,
        "bolt.head_height": variant.head_height,
        "bolt.thread_length": variant.thread_length_for(length),
        "bolt.shank_diameter": variant.nominal_diameter,
        "bolt.youngs_modulus": STEEL_YOUNGS_MODULUS_MPA,
        "bolt.yield_strength": strength.yield_strength,
        "bolt.tensile_strength": strength.tensile_strength,
        "bolt.shear_ratio": ratio,
        "joint.hole_diameter": variant.clearance_holes[1],
        "nut.height": variant.nut_height,
        "nut.bearing_diameter": variant.nut_bearing_diameter,
    }


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
    return {
        "catalog_version": _bolt_catalog()["catalog_version"],
        "status": "provisional",
        "bolts": [
            {
                "variant_id": variant.variant_id,
                "standard": variant.standard,
                "size_id": variant.size_id,
                "label": variant.label,
                "nominal_diameter": variant.nominal_diameter,
                "threading": variant.threading,
            }
            for variant in bolt_variants()
        ],
        "property_classes": sorted({row.property_class for row in property_classes()}, key=float),
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
