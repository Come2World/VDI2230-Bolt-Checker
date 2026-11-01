"""Input model for the general concentric single-bolt calculation.

One field schema drives validation, JSON round-tripping and the Tkinter
form model, so labels, units and limits stay consistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
import math
from typing import Any

from vdi2230 import data as engineering_data


SCHEMA_ID = "vdi2230.general/4"
LEGACY_SCHEMA_ID = "vdi2230.general/3"
MAX_LAYERS = 10
WASHER_SECTIONS = ("head_washer", "nut_washer")
WASHER_ESTIMATE_SOURCE = "default:平垫片经验尺寸"


@dataclass(frozen=True)
class FieldSpec:
    path: str
    label: str
    unit: str = ""
    kind: str = "float"  # float | int | choice | text | bool
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: bool = False
    optional: bool = False
    choices: tuple[tuple[str, str], ...] = ()
    group: str = ""
    help: str = ""
    diameter_factor: float | None = None

    @property
    def name(self) -> str:
        return self.path.rsplit(".", 1)[-1]

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "label": self.label,
            "unit": self.unit,
            "kind": self.kind,
            "default": self.default,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "exclusive_minimum": self.exclusive_minimum,
            "optional": self.optional,
            "choices": [list(choice) for choice in self.choices],
            "group": self.group,
            "help": self.help,
            "diameter_factor": self.diameter_factor,
        }


def _f(path: str, label: str, unit: str, default: Any, group: str, **options: Any) -> FieldSpec:
    return FieldSpec(path=path, label=label, unit=unit, default=default, group=group, **options)


POSITIVE = {"minimum": 0.0, "exclusive_minimum": True}
NON_NEGATIVE = {"minimum": 0.0}
FRICTION = {"minimum": 0.01, "maximum": 1.0}

JOINT_TYPES = (("DSV", "通孔螺栓 + 螺母 (DSV)"), ("ESV", "螺纹孔连接 (ESV)"))
HEAD_TYPES = (("hex", "外六角头"), ("socket", "内六角圆柱头"))
ROLLING = (("SV", "热处理前滚丝 SV"), ("SG", "热处理后滚丝 SG"))
TABLE_MODES = (("table", "查表"), ("manual", "手动"))
CONE_MODES = (("auto", "自动"), ("TBJ", "DSV 锥公式 (43)"), ("TTJ", "ESV 锥公式 (42)"))
W_MODES = (("auto", "自动"), ("1", "w = 1"), ("2", "w = 2"))
SIDES = (("head", "螺栓头"), ("nut", "螺母"))
DRAWING_ONLY_HELP = "仅用于剖面图；留空或与 dW 不协调时按 dW 估算"
HEAD_DRAWING_PATHS = frozenset({
    "bolt.head_width_across_flats", "bolt.head_diameter", "bolt.socket_size", "bolt.socket_depth",
})
FATIGUE_HELP = "留空 = 8.8/10.9/12.9 按 VDI R9 计算 σASV/σASG（见报告 R9）；A2 有交变载荷时须输入产品值"
SV_CLASSES = tuple((f"SV{i}", f"SV{i}") for i in range(1, 7))


def _washer_specs(section: str, label: str) -> tuple[FieldSpec, ...]:
    return (
        _f(f"{section}.enabled", f"启用{label}", "", False, "plates", kind="bool"),
        _f(f"{section}.inner_diameter", "垫片内径 di", "mm", 13.2, "plates", diameter_factor=1.1, help="经验值 1.1d，可修改", **POSITIVE),
        _f(f"{section}.outer_diameter", "垫片外径 Do", "mm", 24.0, "plates", diameter_factor=2.0, help="经验值 2d，可修改", **POSITIVE),
        _f(f"{section}.thickness", "垫片厚度 t", "mm", 1.92, "plates", diameter_factor=0.16, help="经验值 0.16d，可修改", **POSITIVE),
        _f(f"{section}.material_id", "垫片材料", "", "S355J0", "plates", kind="text", optional=True),
        _f(f"{section}.youngs_modulus", "弹性模量 EW", "MPa", 205_000.0, "plates", **POSITIVE),
        _f(f"{section}.limiting_surface_pressure", "极限面压 pG", "MPa", 760.0, "plates", **POSITIVE),
        _f(f"{section}.roughness_rz", "粗糙度 Rz", "μm", 16.0, "plates", **NON_NEGATIVE),
    )


FIELD_SPECS: tuple[FieldSpec, ...] = (
    _f("joint.type", "连接类型", "", "DSV", "bolt", kind="choice", choices=JOINT_TYPES),
    _f("bolt.catalog_variant_id", "目录型号", "", "ISO4014-M12x1.75", "bolt", kind="text", optional=True),
    _f("bolt.property_class", "强度等级", "", "8.8", "bolt", kind="text", optional=True),
    _f("bolt.head_type", "头部形式", "", "hex", "bolt", kind="choice", choices=HEAD_TYPES),
    _f("bolt.d", "公称直径 d", "mm", 12.0, "bolt", **POSITIVE),
    _f("bolt.pitch", "螺距 P", "mm", 1.75, "bolt", **POSITIVE),
    _f("bolt.d2", "中径 d2", "mm", 10.863342, "bolt", **POSITIVE),
    _f("bolt.d3", "小径 d3", "mm", 9.852979, "bolt", **POSITIVE),
    _f("bolt.stress_area", "应力截面 AS", "mm²", 84.266, "bolt", **POSITIVE),
    _f("bolt.head_bearing_diameter", "头部支承直径 dW", "mm", 16.63, "bolt", **POSITIVE),
    _f("bolt.head_height", "头高 k", "mm", 7.5, "bolt", **POSITIVE),
    _f("bolt.head_width_across_flats", "头部对边 s", "mm", 18.0, "bolt", optional=True, help=DRAWING_ONLY_HELP, **POSITIVE),
    _f("bolt.head_diameter", "头部直径 dk", "mm", None, "bolt", optional=True, help=DRAWING_ONLY_HELP, **POSITIVE),
    _f("bolt.socket_size", "内六角对边 s", "mm", None, "bolt", optional=True, help=DRAWING_ONLY_HELP, **POSITIVE),
    _f("bolt.socket_depth", "内六角深度 t", "mm", None, "bolt", optional=True, help=DRAWING_ONLY_HELP, **POSITIVE),
    _f("bolt.length", "螺栓长度 l", "mm", 70.0, "bolt", **POSITIVE),
    _f("bolt.thread_length", "螺纹长度 b", "mm", 30.0, "bolt", optional=True, help="留空 = 全螺纹", **POSITIVE),
    _f("bolt.shank_diameter", "杆径 dT", "mm", None, "bolt", optional=True, help="留空 = d；小于 d 为细腰杆", **POSITIVE),
    _f("bolt.bore_diameter", "中心孔 db", "mm", 0.0, "bolt", **NON_NEGATIVE),
    _f("bolt.youngs_modulus", "弹性模量 ES", "MPa", 205_000.0, "bolt", **POSITIVE),
    _f("bolt.yield_strength", "屈服强度 Rp0.2", "MPa", 640.0, "bolt", **POSITIVE),
    _f("bolt.tensile_strength", "抗拉强度 Rm", "MPa", 800.0, "bolt", **POSITIVE),
    _f("bolt.tensile_strength_max", "最大抗拉强度 Rm,max", "MPa", None, "bolt", optional=True,
       help="非 A2 留空 = 1.2·Rm；A2 螺纹脱扣校核须输入实际值", **POSITIVE),
    _f("bolt.shear_ratio", "剪切强度比 τB/Rm", "", 0.65, "bolt", minimum=0.3, maximum=1.2),
    _f("bolt.fatigue_strength_amplitude", "产品疲劳强度幅 σA", "MPa", None, "bolt", optional=True,
       help=FATIGUE_HELP, **POSITIVE),
    _f("bolt.rolling", "螺纹滚压", "", "SV", "bolt", kind="choice", choices=ROLLING),
    _f("bolt.thread_friction", "螺纹摩擦 μG", "", 0.12, "bolt", **FRICTION),
    _f("bolt.bearing_friction", "支承摩擦 μK", "", 0.12, "bolt", help="独立输入；拧紧侧螺栓头/螺母与垫片或板面的摩擦", **FRICTION),
    _f("nut.height", "螺母高度 m", "mm", 10.8, "bolt", **POSITIVE),
    _f("nut.bearing_diameter", "螺母支承直径 dW", "mm", 16.6, "bolt", **POSITIVE),
    _f("nut.width_across_flats", "螺母对边 s", "mm", 18.0, "bolt", **POSITIVE),
    _f("nut.youngs_modulus", "螺母弹性模量 EM", "MPa", 205_000.0, "bolt", **POSITIVE),
    _f("nut.standard_adequate", "标准螺母且等级匹配", "", True, "bolt", kind="bool", help="ISO 4032 且螺母等级 ≥ 螺栓等级时免 R11"),
    _f("nut.tensile_strength", "螺母 Rm", "MPa", None, "bolt", optional=True,
       help="非 A2 留空 = 螺栓 Rm；A2 非标准螺母须输入实际值", **POSITIVE),
    _f("nut.shear_ratio", "螺母 τB/Rm", "", None, "bolt", optional=True, minimum=0.3, maximum=1.2),
    _f("tapped.material_id", "内螺纹件材料", "", "Cq45", "bolt", kind="text", optional=True),
    _f("tapped.youngs_modulus", "内螺纹件 EM", "MPa", 205_000.0, "bolt", **POSITIVE),
    _f("tapped.tensile_strength", "内螺纹件 Rm", "MPa", 700.0, "bolt", **POSITIVE),
    _f("tapped.shear_strength", "内螺纹件 τB", "MPa", 460.0, "bolt", **POSITIVE),
    _f("tapped.engagement_length", "旋合长度 mges", "mm", None, "bolt", optional=True, help="留空 = l − lK", **POSITIVE),
    _f("tapped.outer_diameter", "内螺纹外围直径 s", "mm", None, "bolt", optional=True, help="留空 = C1 取 1", **POSITIVE),
    _f("joint.hole_diameter", "通孔直径 dh", "mm", 13.5, "plates", **POSITIVE),
    _f("joint.chamfer_diameter", "倒角直径 dha", "mm", None, "plates", optional=True, help="留空 = dh", **POSITIVE),
    _f("joint.outer_diameter", "外径 DA", "mm", 40.0, "plates", **POSITIVE),
    _f("joint.substitute_diameter", "替代外径 DA′", "mm", None, "plates", optional=True, help="留空 = DA；用于 y = DA′/dW", **POSITIVE),
    *_washer_specs("head_washer", "头侧垫片"),
    *_washer_specs("nut_washer", "螺母侧垫片"),
    _f("load.axial_max", "轴向载荷 FA,max", "N", 10_000.0, "load", **NON_NEGATIVE),
    _f("load.axial_min", "轴向载荷 FA,min", "N", 0.0, "load", **NON_NEGATIVE),
    _f("load.transverse", "横向载荷 FQ,max", "N", 0.0, "load", **NON_NEGATIVE),
    _f("load.torque", "扭矩 MY,max", "N·m", 0.0, "load", **NON_NEGATIVE),
    _f("load.friction_radius", "摩擦半径 ra", "mm", None, "load", optional=True, help="有扭矩时必填", **POSITIVE),
    _f("load.slip_interfaces", "传力界面数 qF", "", 1, "load", kind="int", minimum=1, maximum=20),
    _f("load.torque_interfaces", "传扭界面数 qM", "", 1, "load", kind="int", minimum=1, maximum=20),
    _f("load.residual_clamp", "最小残余夹紧力 FK,erf", "N", 0.0, "load", help="密封或功能要求", **NON_NEGATIVE),
    _f("load.sealing_pressure", "密封压力 pi,max", "MPa", 0.0, "load", **NON_NEGATIVE),
    _f("load.sealing_area", "密封面积 AD", "mm²", 0.0, "load", **NON_NEGATIVE),
    _f("load.cycles", "循环次数 NZ", "", None, "load", optional=True, help="留空 = 无限寿命 (≥2·10⁶)", minimum=1e4, maximum=2e6),
    _f("load_introduction.mode", "载荷导入系数 n", "", "table", "load", kind="choice", choices=TABLE_MODES),
    _f("load_introduction.joint_class", "连接类型 (表 2)", "", "SV1", "load", kind="choice", choices=SV_CLASSES),
    _f("load_introduction.la_over_h", "lA/h", "", 0.0, "load", minimum=0.0, maximum=1.0),
    _f("load_introduction.ak_over_h", "ak/h", "", 0.1, "load", minimum=0.0, maximum=1.0),
    _f("load_introduction.n", "n (手动)", "", 0.5, "load", minimum=0.0, maximum=1.0),
    _f("assembly.tightening_factor", "拧紧系数 αA", "", 1.6, "assembly", minimum=1.0, maximum=5.0),
    _f("assembly.utilization", "利用系数 ν", "", 0.9, "assembly", minimum=0.1, maximum=1.0),
    _f("assembly.tighten_side", "拧紧侧", "", "head", "assembly", kind="choice", choices=SIDES),
    _f("embedding.mode", "嵌入量 fZ", "", "table", "assembly", kind="choice", choices=TABLE_MODES),
    _f("embedding.fz_um", "fZ (手动)", "μm", 11.0, "assembly", **NON_NEGATIVE),
    _f("embedding.interface_count", "界面数覆盖", "", None, "assembly", kind="int", optional=True, minimum=0, maximum=20),
    _f("advanced.w", "连接系数 w", "", "auto", "assembly", kind="choice", choices=W_MODES),
    _f("advanced.cone", "锥角公式", "", "auto", "assembly", kind="choice", choices=CONE_MODES),
    _f("advanced.cone_start_diameter", "锥起始直径", "mm", None, "assembly", optional=True, help="留空 = dW", **POSITIVE),
    _f("advanced.preload_override", "FMzul 覆盖", "N", None, "assembly", optional=True, help="留空 = 按 R7 计算", **POSITIVE),
    _f("requirements.SF", "SF 要求", "", 1.0, "assembly", **POSITIVE),
    _f("requirements.SD", "SD 要求", "", 1.2, "assembly", **POSITIVE),
    _f("requirements.SG", "SG 要求", "", 1.2, "assembly", help="交变横向载荷取 1.8", **POSITIVE),
    _f("requirements.Sp", "Sp 要求", "", 1.0, "assembly", **POSITIVE),
    _f("requirements.SA", "SA 要求", "", 1.1, "assembly", **POSITIVE),
)

LAYER_SPECS: tuple[FieldSpec, ...] = (
    _f("name", "名称", "", "板 1", "plates", kind="text"),
    _f("material_id", "材料", "", "S355J0", "plates", kind="text", optional=True),
    _f("thickness", "厚度 h", "mm", 20.0, "plates", **POSITIVE),
    _f("youngs_modulus", "弹性模量 EP", "MPa", 205_000.0, "plates", **POSITIVE),
    _f("limiting_surface_pressure", "极限面压 pG", "MPa", 760.0, "plates", **POSITIVE),
    _f("roughness_rz", "粗糙度 Rz", "μm", 16.0, "plates", **NON_NEGATIVE),
    _f("interface_friction", "界面摩擦 μT", "", 0.15, "plates", **FRICTION),
)

SPEC_BY_PATH = {spec.path: spec for spec in FIELD_SPECS}


@dataclass(frozen=True)
class FieldError:
    path: str
    message: str


class InputValidationError(ValueError):
    def __init__(self, errors: list[FieldError]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(f"{error.path}: {error.message}" for error in errors))


@dataclass(frozen=True)
class BoltInput:
    catalog_variant_id: str | None
    property_class: str | None
    head_type: str
    d: float
    pitch: float
    d2: float
    d3: float
    stress_area: float
    head_bearing_diameter: float
    head_height: float
    head_width_across_flats: float | None
    head_diameter: float | None
    socket_size: float | None
    socket_depth: float | None
    length: float
    thread_length: float | None
    shank_diameter: float | None
    bore_diameter: float
    youngs_modulus: float
    yield_strength: float
    tensile_strength: float
    tensile_strength_max: float | None
    shear_ratio: float
    fatigue_strength_amplitude: float | None
    rolling: str
    thread_friction: float
    bearing_friction: float


@dataclass(frozen=True)
class NutInput:
    height: float
    bearing_diameter: float
    width_across_flats: float
    youngs_modulus: float
    standard_adequate: bool
    tensile_strength: float | None
    shear_ratio: float | None


@dataclass(frozen=True)
class TappedInput:
    material_id: str | None
    youngs_modulus: float
    tensile_strength: float
    shear_strength: float
    engagement_length: float | None
    outer_diameter: float | None


@dataclass(frozen=True)
class PlateLayer:
    name: str
    material_id: str | None
    thickness: float
    youngs_modulus: float
    limiting_surface_pressure: float
    roughness_rz: float
    interface_friction: float


@dataclass(frozen=True)
class WasherInput:
    enabled: bool
    inner_diameter: float
    outer_diameter: float
    thickness: float
    material_id: str | None
    youngs_modulus: float
    limiting_surface_pressure: float
    roughness_rz: float


@dataclass(frozen=True)
class JointInput:
    type: str
    hole_diameter: float
    chamfer_diameter: float | None
    outer_diameter: float
    substitute_diameter: float | None


@dataclass(frozen=True)
class LoadInput:
    axial_max: float
    axial_min: float
    transverse: float
    torque: float
    friction_radius: float | None
    slip_interfaces: int
    torque_interfaces: int
    residual_clamp: float
    sealing_pressure: float
    sealing_area: float
    cycles: float | None


@dataclass(frozen=True)
class LoadIntroductionInput:
    mode: str
    joint_class: str
    la_over_h: float
    ak_over_h: float
    n: float


@dataclass(frozen=True)
class AssemblyInput:
    tightening_factor: float
    utilization: float
    tighten_side: str


@dataclass(frozen=True)
class EmbeddingInput:
    mode: str
    fz_um: float
    interface_count: int | None


@dataclass(frozen=True)
class AdvancedInput:
    w: str
    cone: str
    cone_start_diameter: float | None
    preload_override: float | None


@dataclass(frozen=True)
class Requirements:
    SF: float
    SD: float
    SG: float
    Sp: float
    SA: float


SECTION_TYPES: dict[str, type] = {
    "joint": JointInput,
    "bolt": BoltInput,
    "nut": NutInput,
    "tapped": TappedInput,
    "head_washer": WasherInput,
    "nut_washer": WasherInput,
    "load": LoadInput,
    "load_introduction": LoadIntroductionInput,
    "assembly": AssemblyInput,
    "embedding": EmbeddingInput,
    "advanced": AdvancedInput,
    "requirements": Requirements,
}


@dataclass(frozen=True)
class GeneralInput:
    title: str
    joint: JointInput
    bolt: BoltInput
    nut: NutInput
    tapped: TappedInput
    head_washer: WasherInput
    nut_washer: WasherInput
    plates: tuple[PlateLayer, ...]
    load: LoadInput
    load_introduction: LoadIntroductionInput
    assembly: AssemblyInput
    embedding: EmbeddingInput
    advanced: AdvancedInput
    requirements: Requirements
    provenance: dict[str, str] = field(default_factory=dict)

    @property
    def is_through_bolt(self) -> bool:
        return self.joint.type == "DSV"

    @property
    def clamp_length(self) -> float:
        return self.plate_length + self.head_washer_thickness + self.nut_washer_thickness

    @property
    def plate_length(self) -> float:
        return sum(layer.thickness for layer in self.plates)

    @property
    def head_washer_thickness(self) -> float:
        return self.head_washer.thickness if self.head_washer.enabled else 0.0

    @property
    def nut_washer_thickness(self) -> float:
        return self.nut_washer.thickness if self.is_through_bolt and self.nut_washer.enabled else 0.0

    def washer_at(self, side: str) -> WasherInput | None:
        washer = self.head_washer if side == "head" else self.nut_washer
        return washer if washer.enabled and (side == "head" or self.is_through_bolt) else None

    def bearing_outer(self, side: str) -> float:
        diameter = self.bolt.head_bearing_diameter if side == "head" else self.nut.bearing_diameter
        washer = self.washer_at(side)
        return min(diameter, washer.outer_diameter, self.joint.outer_diameter) if washer else diameter

    def bearing_inner(self, side: str) -> float:
        chamfer = self.joint.chamfer_diameter or self.joint.hole_diameter
        washer = self.washer_at(side)
        return max(chamfer, self.joint.hole_diameter, washer.inner_diameter) if washer else chamfer

    def to_json(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if is_dataclass(value):
                return {item.name: convert(getattr(value, item.name)) for item in fields(value)}
            if isinstance(value, tuple):
                return [convert(item) for item in value]
            if isinstance(value, dict):
                return dict(value)
            return value

        payload = convert(self)
        return {"schema": SCHEMA_ID, **payload}

    @classmethod
    def from_json(cls, data: Any) -> "GeneralInput":
        return parse_general_input(data)


def default_layer(index: int = 0) -> dict[str, Any]:
    layer = {spec.name: spec.default for spec in LAYER_SPECS}
    layer["name"] = f"板 {index + 1}"
    return layer


def default_input_json() -> dict[str, Any]:
    payload: dict[str, Any] = {"schema": SCHEMA_ID, "title": "通用螺栓连接"}
    for spec in FIELD_SPECS:
        section, name = spec.path.split(".", 1)
        payload.setdefault(section, {})[name] = spec.default
    payload["plates"] = [default_layer(0), default_layer(1)]
    provenance = engineering_data.catalog_value_sources(
        payload["bolt"]["catalog_variant_id"],
        payload["bolt"]["property_class"],
    )
    provenance.update(engineering_data.material_value_sources(payload["tapped"]["material_id"], "tapped"))
    for index, layer in enumerate(payload["plates"]):
        provenance.update(engineering_data.material_value_sources(layer["material_id"], f"plates[{index}]"))
    for section in WASHER_SECTIONS:
        for name in ("youngs_modulus", "limiting_surface_pressure"):
            provenance[f"{section}.{name}"] = f"material:{payload[section]['material_id']}"
    for spec in FIELD_SPECS:
        if spec.diameter_factor is not None:
            provenance[spec.path] = WASHER_ESTIMATE_SOURCE
    payload["provenance"] = provenance
    return payload


def _parse_value(spec: FieldSpec, raw: Any, path: str, errors: list[FieldError]) -> Any:
    if raw is None or (isinstance(raw, str) and raw.strip() == "" and spec.kind != "text"):
        if spec.optional:
            return None
        errors.append(FieldError(path, "必填"))
        return spec.default
    if spec.kind == "text":
        if not isinstance(raw, str):
            errors.append(FieldError(path, "应为文本"))
            return spec.default
        text = raw.strip()
        if len(text) > 120:
            errors.append(FieldError(path, "文本过长"))
        if not text and spec.optional:
            return None
        return text
    if spec.kind == "bool":
        if not isinstance(raw, bool):
            errors.append(FieldError(path, "应为是/否"))
            return spec.default
        return raw
    if spec.kind == "choice":
        allowed = [value for value, _ in spec.choices]
        if raw not in allowed:
            errors.append(FieldError(path, f"可选值: {', '.join(allowed)}"))
            return spec.default
        return raw
    if isinstance(raw, bool):
        errors.append(FieldError(path, "应为数值"))
        return spec.default
    if isinstance(raw, str):
        try:
            raw = float(raw.strip().replace(",", "."))
        except ValueError:
            errors.append(FieldError(path, "应为数值"))
            return spec.default
    if not isinstance(raw, (int, float)) or not math.isfinite(raw):
        errors.append(FieldError(path, "应为有限数值"))
        return spec.default
    value: float | int = float(raw)
    if spec.kind == "int":
        if value != int(value):
            errors.append(FieldError(path, "应为整数"))
            return spec.default
        value = int(value)
    if spec.minimum is not None:
        if spec.exclusive_minimum and value <= spec.minimum:
            errors.append(FieldError(path, f"必须 > {spec.minimum:g}"))
        elif not spec.exclusive_minimum and value < spec.minimum:
            errors.append(FieldError(path, f"必须 ≥ {spec.minimum:g}"))
    if spec.maximum is not None and value > spec.maximum:
        errors.append(FieldError(path, f"必须 ≤ {spec.maximum:g}"))
    return value


def _section_payload(data: dict[str, Any], name: str, errors: list[FieldError]) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        errors.append(FieldError(name, "应为对象"))
        return {}
    return value


def parse_general_input(data: Any) -> GeneralInput:
    """Validate a JSON-like payload; raise InputValidationError with field paths."""
    errors: list[FieldError] = []
    if not isinstance(data, dict):
        raise InputValidationError([FieldError("", "输入应为 JSON 对象")])
    schema = data.get("schema", SCHEMA_ID)
    if schema not in (SCHEMA_ID, LEGACY_SCHEMA_ID):
        errors.append(FieldError("schema", f"仅支持 {SCHEMA_ID} 或 {LEGACY_SCHEMA_ID}；请分别确认螺栓的 thread_friction (μG) 和 bearing_friction (μK)"))
    if (schema == LEGACY_SCHEMA_ID and isinstance(data.get("bolt"), dict)
            and "fatigue_strength_amplitude" in data["bolt"]):
        errors.append(FieldError("bolt.fatigue_strength_amplitude", "产品疲劳强度幅需要输入格式 vdi2230.general/4。"))

    values: dict[str, dict[str, Any]] = {name: {} for name in SECTION_TYPES}
    for spec in FIELD_SPECS:
        section, name = spec.path.split(".", 1)
        payload = _section_payload(data, section, errors)
        raw = payload.get(name, spec.default)
        property_class = values["bolt"].get("property_class")
        is_a2_90 = isinstance(property_class, str) and property_class.upper() == "A2-90"
        if spec.path == "bolt.shear_ratio" and engineering_data.is_a2_bolt_class(property_class) and name not in payload:
            raw = None
        # Drawing-only head sizes absent from older files fall back to dW-based estimates.
        if spec.path in HEAD_DRAWING_PATHS and name not in payload:
            raw = None
        if spec.diameter_factor is not None and name not in payload:
            diameter = values["bolt"].get("d")
            if isinstance(diameter, (int, float)) and diameter > 0:
                raw = round(diameter * spec.diameter_factor, 6)
        values[section][name] = _parse_value(spec, raw, spec.path, errors)
        if (spec.path == "bolt.shear_ratio" and is_a2_90
                and errors and errors[-1].path == spec.path and errors[-1].message == "必填"):
            errors[-1] = FieldError(spec.path, "A2-90 无默认剪切强度比，请按实际产品资料输入。")

    layers_raw = data.get("plates")
    layers: list[PlateLayer] = []
    if not isinstance(layers_raw, list) or not layers_raw:
        errors.append(FieldError("plates", "至少需要一层夹紧板"))
        layers_raw = []
    elif len(layers_raw) > MAX_LAYERS:
        errors.append(FieldError("plates", f"最多 {MAX_LAYERS} 层"))
        layers_raw = layers_raw[:MAX_LAYERS]
    for index, raw_layer in enumerate(layers_raw):
        prefix = f"plates[{index}]"
        if not isinstance(raw_layer, dict):
            errors.append(FieldError(prefix, "应为对象"))
            continue
        if "bearing_friction" in raw_layer:
            errors.append(FieldError(f"{prefix}.bearing_friction", "板层 μK 已移除，请改为螺栓的 bearing_friction"))
        layer_values = {
            spec.name: _parse_value(spec, raw_layer.get(spec.name, spec.default), f"{prefix}.{spec.name}", errors)
            for spec in LAYER_SPECS
        }
        layers.append(PlateLayer(**layer_values))

    title = data.get("title", "通用螺栓连接")
    if not isinstance(title, str) or len(title) > 120:
        errors.append(FieldError("title", "标题应为不超过 120 字的文本"))
        title = "通用螺栓连接"

    provenance_raw = data.get("provenance", {})
    provenance: dict[str, str] = {}
    if not isinstance(provenance_raw, dict):
        errors.append(FieldError("provenance", "应为对象"))
    else:
        for key, value in provenance_raw.items():
            if not isinstance(key, str) or not isinstance(value, str) or len(value) > 160:
                errors.append(FieldError("provenance", "来源记录应为文本"))
                break
            provenance[key] = value

    property_class = values["bolt"].get("property_class")
    if engineering_data.is_a2_bolt_class(property_class):
        for path in sorted(engineering_data.STRENGTH_PATHS):
            source = provenance.get(path, "")
            if source.startswith("class:") and source != f"class:{property_class}":
                errors.append(FieldError(path, "所选 A2 等级与强度来源不一致，请重新选择目录或手动填写。"))
        ratio_path = engineering_data.SHEAR_RATIO_PATH
        if provenance.get(ratio_path) == "table:shear_strength_ratio" and not any(error.path == ratio_path for error in errors):
            ratio = engineering_data.shear_strength_ratio(property_class)
            if ratio is None or values["bolt"]["shear_ratio"] != ratio:
                errors.append(FieldError(ratio_path, "所选 A2 等级的剪切强度比与表 7 不符，请重新选择目录或手动填写。"))

    if errors:
        raise InputValidationError(errors)

    sections = {name: kind(**values[name]) for name, kind in SECTION_TYPES.items()}
    general = GeneralInput(
        title=title.strip() or "通用螺栓连接",
        plates=tuple(layers),
        provenance=provenance,
        **sections,
    )
    _validate_relations(general)
    return general


def _validate_relations(item: GeneralInput) -> None:
    errors: list[FieldError] = []
    bolt, joint, load = item.bolt, item.joint, item.load

    def require(condition: bool, path: str, message: str) -> None:
        if not condition:
            errors.append(FieldError(path, message))

    if engineering_data.uses_a2_bolt(bolt.property_class, item.provenance) and bolt.catalog_variant_id:
        try:
            engineering_data.bolt_variant(bolt.catalog_variant_id)
        except KeyError:
            valid_catalog = False
        else:
            valid_catalog = all(
                not source.startswith("catalog:") or source == f"catalog:{bolt.catalog_variant_id}"
                for path in engineering_data.CATALOG_GEOMETRY_PATHS
                if (source := item.provenance.get(path, ""))
            )
        require(valid_catalog, "bolt.catalog_variant_id", "目录规格不存在或与保留的目录来源不一致，请重新选择或改为自定义。")

    require(bolt.d3 < bolt.d2 < bolt.d, "bolt.d2", "须满足 d3 < d2 < d")
    require(bolt.pitch < 0.25 * bolt.d, "bolt.pitch", "螺距相对直径过大")
    nominal_stress_area = math.pi / 4 * ((bolt.d2 + bolt.d3) / 2) ** 2
    require(
        abs(bolt.stress_area - nominal_stress_area) <= 0.15 * nominal_stress_area,
        "bolt.stress_area",
        f"与 π/4·((d2+d3)/2)² = {nominal_stress_area:.1f} 偏差超过 15%",
    )
    require(bolt.yield_strength < bolt.tensile_strength, "bolt.yield_strength", "须小于 Rm")
    if bolt.tensile_strength_max is not None:
        require(bolt.tensile_strength_max >= bolt.tensile_strength, "bolt.tensile_strength_max", "须 ≥ Rm")
    sourced_classes = {
        source.removeprefix("class:")
        for path in engineering_data.STRENGTH_PATHS
        if (source := item.provenance.get(path, "")).startswith("class:")
        and engineering_data.is_a2_bolt_class(source.removeprefix("class:"))
    }
    for property_class in sorted(sourced_classes):
        try:
            engineering_data.property_class_record(property_class, bolt.d)
        except KeyError:
            errors.append(FieldError("bolt.d", "目录 A2 强度不适用于该公称直径，请使用适用范围或手动输入强度。"))
    if bolt.shank_diameter is not None:
        require(bolt.shank_diameter <= bolt.d, "bolt.shank_diameter", "须 ≤ d")
        require(bolt.shank_diameter > bolt.bore_diameter, "bolt.shank_diameter", "须大于中心孔 db")
    require(bolt.bore_diameter < 0.8 * bolt.d3, "bolt.bore_diameter", "须 < 0.8·d3")
    if bolt.thread_length is not None:
        require(bolt.thread_length <= bolt.length, "bolt.thread_length", "须 ≤ 螺栓长度 l")
    require(joint.hole_diameter > bolt.d, "joint.hole_diameter", "须大于 d")
    chamfer = joint.chamfer_diameter or joint.hole_diameter
    require(chamfer > bolt.d, "joint.chamfer_diameter", "须大于 d")
    require(
        bolt.head_bearing_diameter > max(chamfer, joint.hole_diameter),
        "bolt.head_bearing_diameter",
        "须大于 dh 和 dha",
    )
    cone_start = item.advanced.cone_start_diameter
    if cone_start is not None:
        require(cone_start > joint.hole_diameter, "advanced.cone_start_diameter", "须大于 dh")
    require(joint.outer_diameter > joint.hole_diameter, "joint.outer_diameter", "须大于 dh")
    if joint.substitute_diameter is not None:
        require(joint.substitute_diameter > joint.hole_diameter, "joint.substitute_diameter", "须大于 dh")
    for side in ("head", "nut"):
        washer = item.washer_at(side)
        if washer is None:
            continue
        prefix = f"{side}_washer"
        require(washer.inner_diameter > bolt.d, f"{prefix}.inner_diameter", "须大于螺栓公称直径 d")
        require(washer.outer_diameter > washer.inner_diameter, f"{prefix}.outer_diameter", "须大于垫片内径 di")
        require(
            item.bearing_outer(side) > item.bearing_inner(side),
            f"{prefix}.inner_diameter",
            "垫片、支承面和板层须有共同的有效承压环面（外径须大于内径、dh 和 dha）",
        )
        if cone_start is not None:
            require(cone_start <= item.bearing_outer(side), "advanced.cone_start_diameter", "使用垫片时，锥起始直径不得超过保守有效承压外径")
            require(cone_start > washer.inner_diameter, "advanced.cone_start_diameter", "使用垫片时，锥起始直径须大于垫片内径")
    require(load.axial_min <= load.axial_max, "load.axial_min", "须 ≤ FA,max")
    if load.torque > 0:
        require(load.friction_radius is not None, "load.friction_radius", "有扭矩时必填")
    if load.sealing_pressure > 0:
        require(load.sealing_area > 0, "load.sealing_area", "有密封压力时必填")

    clamp = item.clamp_length
    if item.is_through_bolt:
        require(
            item.nut.bearing_diameter > max(chamfer, joint.hole_diameter),
            "nut.bearing_diameter",
            "须大于 dh 和 dha",
        )
        require(bolt.length > clamp, "bolt.length", f"须大于夹紧长度 lK = {clamp:g}")
        if bolt.thread_length is not None:
            require(
                bolt.length - bolt.thread_length <= clamp + 1e-9,
                "bolt.thread_length",
                "螺纹起点须位于夹紧长度内，否则螺母无法压紧",
            )
        require(item.assembly.tighten_side in {"head", "nut"}, "assembly.tighten_side", "无效")
    else:
        require(bolt.length > clamp, "bolt.length", f"须大于夹紧长度 lK = {clamp:g}，留出旋合长度")
        require(item.assembly.tighten_side == "head", "assembly.tighten_side", "ESV 只能在螺栓头侧拧紧")
        engagement = item.tapped.engagement_length
        if engagement is not None:
            require(engagement <= bolt.length - clamp + 1e-9, "tapped.engagement_length", "不能超过 l − lK")
    if errors:
        raise InputValidationError(errors)


def field_schema_json() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "max_layers": MAX_LAYERS,
        "washer_estimate_source": WASHER_ESTIMATE_SOURCE,
        "fields": [spec.to_json() for spec in FIELD_SPECS],
        "layer_fields": [spec.to_json() for spec in LAYER_SPECS],
        "defaults": default_input_json(),
    }
