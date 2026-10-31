"""General VDI 2230 Part 1:2015 calculation for a concentric single-bolt joint.

Scope: through-bolt (DSV) or tapped-thread (ESV) joints, multi-layer clamped
parts, solid/hollow and reduced-shank bolts, concentric axial load, transverse
load and torque. Eccentric loading, bending and thermal preload changes are
outside this model.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from vdi2230 import data as engineering_data
from vdi2230.domain.general_inputs import (
    FieldError,
    GeneralInput,
    InputValidationError,
    PlateLayer,
    WasherInput,
    WASHER_SECTIONS,
)
from vdi2230.domain.models import (
    CalculationResult,
    CalculationValue,
    ResultStatus,
)


ND_CYCLES = 2e6
TAN30 = math.tan(math.pi / 6)
ISO_DIAMETER_STEPS = (0.99, 1.4, 2.8, 5.6, 11.2, 22.4, 45.0, 90.0, 180.0, 355.0, 600.0)
STANDARD = "VDI 2230 Blatt 1:2015"
MODEL_NAME = "VDI 2230-1:2015 通用同心单螺栓计算"
REVIEW_LABEL = "需确认 · 数据待核验"


@dataclass(frozen=True)
class SafetyCheck:
    symbol: str
    label: str
    value: float | None
    required: float | None
    unit: str
    status: ResultStatus
    reference: str
    note: str = ""


@dataclass(frozen=True)
class SectionMetrics:
    """Derived geometry needed by section drawings."""
    clamp_length: float
    shank_length_in_grip: float
    thread_length_in_grip: float
    engagement_length: float
    tan_phi: float
    limiting_diameter: float
    w: int
    critical_diameter: float
    cone_start_head: float
    cone_start_nut: float
    cone_kind: str


@dataclass(frozen=True)
class GeneralCalculationResult:
    input: GeneralInput
    result: CalculationResult
    checks: tuple[SafetyCheck, ...]
    verdict: ResultStatus
    verdict_label: str
    provisional_sources: tuple[str, ...]
    metrics: SectionMetrics

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.result.warnings

    def value(self, symbol: str) -> float:
        for item in self.result.values:
            if item.symbol == symbol:
                if not isinstance(item.value, (int, float)):
                    raise KeyError(symbol)
                return float(item.value)
        raise KeyError(symbol)

    def check(self, symbol: str) -> SafetyCheck:
        for item in self.checks:
            if item.symbol == symbol:
                return item
        raise KeyError(symbol)


class _Values:
    def __init__(self) -> None:
        self.values: list[CalculationValue] = []

    def add(
        self,
        symbol: str,
        label: str,
        value: float,
        unit: str,
        formula: str,
        note: str = "",
    ) -> float:
        if not math.isfinite(value):
            raise ValueError(f"{symbol} 计算结果非有限值")
        self.values.append(CalculationValue(
            symbol=symbol,
            label=label,
            value=float(value),
            unit=unit,
            formula_reference=f"{STANDARD}, {formula}",
            note=note,
        ))
        return value


def area_circle(diameter: float) -> float:
    return math.pi / 4 * diameter**2


def iso965_tolerances(d: float, pitch: float, d2: float) -> dict[str, float]:
    """6g/6H limits from the ISO 965-1 tolerance formulas (unrounded)."""
    geometric_mean = None
    for low, high in zip(ISO_DIAMETER_STEPS, ISO_DIAMETER_STEPS[1:]):
        if low < d <= high:
            geometric_mean = math.sqrt(low * high)
            break
    if geometric_mean is None:
        raise ValueError("d 超出 ISO 965-1 直径范围")
    es = -(15 + 11 * pitch) / 1000
    td = (180 * pitch ** (2 / 3) - 3.15 / math.sqrt(pitch)) / 1000
    td2 = 90 * pitch**0.4 * geometric_mean**0.1 / 1000
    tD2 = 1.32 * td2
    tD1 = (230 * pitch**0.7 if pitch >= 1 else 433 * pitch - 190 * pitch**1.22) / 1000
    d1 = d - 1.0825318 * pitch
    return {
        "D1": d1,
        "d_min": d + es - td,
        "d2_min": d2 + es - td2,
        "D2_max": d2 + tD2,
        "D1_max": d1 + tD1,
    }


def _cone_tangent(kind: str, beta: float, y: float) -> float:
    if kind == "TBJ":
        return 0.362 + 0.032 * math.log(beta / 2) + 0.153 * math.log(y)
    return 0.348 + 0.013 * math.log(beta) + 0.193 * math.log(y)


def deformation_diameter(
    position: float,
    clamp: float,
    outer: float,
    w: int,
    tan_phi: float,
    start_head: float,
    start_nut: float,
) -> float:
    """Outer diameter of the deformation body at depth ``position`` below the head."""
    raw = start_head + 2 * position * tan_phi
    if w == 1:
        raw = min(raw, start_nut + 2 * (clamp - position) * tan_phi)
    return min(raw, outer)


def deformation_breakpoints(
    clamp: float,
    outer: float,
    w: int,
    tan_phi: float,
    start_head: float,
    start_nut: float,
) -> tuple[float, ...]:
    """Depths where the deformation-body outline changes slope (cone apex, cone/sleeve)."""
    points = {0.0, clamp}
    if w == 1:
        points.add(clamp / 2 + (start_nut - start_head) / (4 * tan_phi))
    if outer > start_head:
        points.add((outer - start_head) / (2 * tan_phi))
    if w == 1 and outer > start_nut:
        points.add(clamp - (outer - start_nut) / (2 * tan_phi))
    return tuple(sorted(point for point in points if 0 <= point <= clamp))


def _plate_compliance(
    item: GeneralInput,
    w: int,
    tan_phi: float,
    start_head: float,
    start_nut: float,
) -> float:
    """Integrate the cone/sleeve deformation body layer by layer (eq. 40/41 generalised)."""
    clamp = item.plate_length
    outer = item.joint.outer_diameter

    def diameter(position: float) -> float:
        return deformation_diameter(position, clamp, outer, w, tan_phi, start_head, start_nut)

    boundaries = [0.0]
    for layer in item.plates:
        boundaries.append(boundaries[-1] + layer.thickness)
    points = set(deformation_breakpoints(clamp, outer, w, tan_phi, start_head, start_nut))
    points.update(boundaries)
    ordered = sorted(point for point in points if 0 <= point <= clamp)

    compliance = 0.0
    for start, end in zip(ordered, ordered[1:]):
        if end - start <= 1e-12:
            continue
        middle = (start + end) / 2
        index = next(
            (i for i, boundary in enumerate(boundaries[1:]) if middle <= boundary),
            len(item.plates) - 1,
        )
        modulus = item.plates[index].youngs_modulus
        hole = item.joint.hole_diameter
        hole_path = "joint.hole_diameter"
        for side, edge in (("head", 0), ("nut", len(item.plates) - 1)):
            washer = item.washer_at(side)
            if index == edge and washer and washer.inner_diameter > hole:
                hole, hole_path = washer.inner_diameter, f"{side}_washer.inner_diameter"
        if min(diameter(start), diameter(end)) <= hole:
            raise InputValidationError([
                FieldError(hole_path, "孔径须小于相邻板层全厚度内的有效变形体直径；请检查垫片及支承尺寸"),
            ])
        if diameter(middle) >= outer - 1e-12:
            compliance += 4 * (end - start) / (modulus * math.pi * (outer**2 - hole**2))
        else:
            low, high = sorted((diameter(start), diameter(end)))
            compliance += math.log(
                ((low + hole) * (high - hole)) / ((low - hole) * (high + hole))
            ) / (modulus * math.pi * hole * tan_phi)
    return compliance


def _status(value: float, required: float) -> ResultStatus:
    return ResultStatus.PASS if value >= required else ResultStatus.FAIL


def _bearing_check(item: GeneralInput, side: str, force: float, v: _Values) -> float:
    suffix = "K" if side == "head" else "M"
    label = "螺栓头侧" if side == "head" else "螺母侧"
    layer = item.plates[0 if side == "head" else -1]
    washer = item.washer_at(side)
    outer, inner = item.bearing_outer(side), item.bearing_inner(side)
    area = v.add(f"Ap,{suffix}", f"{label}板层支承面积", area_circle(outer) - area_circle(inner), "mm²",
                 "R10: π/4·(Deff²−di,eff²)" if washer else "R10: π/4·(dW²−dha²)")
    pressure = v.add(f"pmax,{suffix}", f"{label}板层最大面压", force / area, "MPa", "R10/1, R10/2")
    safety = layer.limiting_surface_pressure / pressure
    if washer:
        v.add(f"Sp,P,{suffix}", f"{label}板层面压安全系数", safety, "", "R10/4")
        bearing = item.bolt.head_bearing_diameter if side == "head" else item.nut.bearing_diameter
        washer_area = v.add(f"Ap,W,{suffix}", f"{label}垫片与紧固件接触面积",
                            area_circle(min(bearing, washer.outer_diameter)) - area_circle(washer.inner_diameter),
                            "mm²", "π/4·(min(dW,Do)²−di²)，不计垫片扩散")
        washer_pressure = v.add(f"pmax,W,{suffix}", f"{label}垫片最大面压",
                                max(force / washer_area, pressure), "MPa", "垫片两接触面面压的最大值")
        washer_safety = v.add(f"Sp,W,{suffix}", f"{label}垫片面压安全系数",
                             washer.limiting_surface_pressure / washer_pressure, "", "R10/4")
        safety = min(safety, washer_safety)
    return v.add(f"Sp,{suffix}", f"{label}面压安全系数", safety, "", "R10/4",
                 "取板层与垫片面压安全系数中的较小值" if washer else "")


def calculate_general(item: GeneralInput) -> GeneralCalculationResult:
    v = _Values()
    warnings: list[str] = []
    provisional: dict[str, str] = {}
    for path, source in sorted(item.provenance.items()):
        section = path.split(".")[0]
        if section in WASHER_SECTIONS and not item.washer_at(section.split("_")[0]):
            continue
        if engineering_data.source_is_provisional(source):
            provisional[path] = source

    bolt, joint, nut, tapped = item.bolt, item.joint, item.nut, item.tapped
    load, assembly = item.load, item.assembly
    layers = item.plates
    dsv = item.is_through_bolt
    d, pitch, d2, d3 = bolt.d, bolt.pitch, bolt.d2, bolt.d3
    es = bolt.youngs_modulus
    em = nut.youngs_modulus if dsv else tapped.youngs_modulus
    bore = bolt.bore_diameter
    bore_area = area_circle(bore)
    shank_d = bolt.shank_diameter or d
    hole = joint.hole_diameter
    chamfer = joint.chamfer_diameter or hole

    # R0 geometry
    clamp = v.add("lK", "夹紧长度", item.clamp_length, "mm", "lK = Σh + tW,K + tW,M")
    plate_length = v.add("lP", "板层总厚度", item.plate_length, "mm", "lP = Σh（不含垫片）")
    shank_total = 0.0 if bolt.thread_length is None else bolt.length - bolt.thread_length
    l1 = v.add("l1", "夹紧区内光杆长度", min(max(shank_total, 0.0), clamp), "mm", "l1 = min(l − b, lK)")
    l_gew = v.add("lGew", "夹紧区内自由螺纹长度", clamp - l1, "mm", "lGew = lK − l1")
    if dsv:
        protrusion = bolt.length - clamp
        engagement = min(nut.height, protrusion)
    else:
        threaded_start = max(clamp, shank_total)
        engagement = bolt.length - threaded_start
        if tapped.engagement_length is not None:
            engagement = min(engagement, tapped.engagement_length)
    v.add("mvorh", "现有旋合长度", max(engagement, 0.0), "mm", "DSV: min(m, l − lK); ESV: l − max(lK, l − b)")

    # R3 compliances
    area_nominal = area_circle(d)
    area_head = area_nominal - bore_area
    area_shank = area_circle(shank_d) - bore_area
    area_d3 = area_circle(d3) - bore_area
    area_stress = bolt.stress_area - bore_area
    head_factor = 0.5 if bolt.head_type == "hex" else 0.4
    nut_factor = 0.4 if dsv else 0.33
    delta_sk = v.add("δSK", "螺栓头柔度", head_factor * d / (es * area_head), "mm/N", "式 (19), lSK = %.1fd" % head_factor)
    delta_1 = v.add("δ1", "光杆柔度", l1 / (es * area_shank), "mm/N", "式 (19), δi = li/(ES·Ai)")
    delta_gew = v.add("δGew", "自由螺纹柔度", l_gew / (es * area_d3), "mm/N", "式 (19), Ad3")
    delta_g = v.add("δG", "旋合螺纹柔度", 0.5 * d / (es * area_d3), "mm/N", "式 (20), lG = 0.5d")
    delta_m = v.add("δM", "螺母/内螺纹柔度", nut_factor * d / (em * area_nominal), "mm/N", "式 (20), lM = %.2fd" % nut_factor)
    delta_s = v.add("δS", "螺栓总柔度", delta_sk + delta_1 + delta_gew + delta_g + delta_m, "mm/N", "式 (19)")

    w = (1 if dsv else 2) if item.advanced.w == "auto" else int(item.advanced.w)
    cone_kind = ("TBJ" if dsv else "TTJ") if item.advanced.cone == "auto" else item.advanced.cone
    start_head = item.advanced.cone_start_diameter or item.bearing_outer("head")
    start_nut = item.advanced.cone_start_diameter or (item.bearing_outer("nut") if dsv else start_head)
    reference_diameter = (start_head + start_nut) / 2 if w == 1 else start_head
    substitute = joint.substitute_diameter or joint.outer_diameter
    beta = v.add("βL", "板层长度比", plate_length / reference_diameter, "", "βL = lP/dW（垫片另计柔度）")
    y_ratio = v.add("y", "外径比", substitute / reference_diameter, "", "y = DA′/dW")
    tan_phi = _cone_tangent(cone_kind, beta, y_ratio)
    if tan_phi <= 0.05:
        raise InputValidationError([FieldError("joint.substitute_diameter", "βL/y 超出锥角公式适用范围")])
    v.add("tanφ", "替代锥角正切", tan_phi, "", "式 (43) DSV" if cone_kind == "TBJ" else "式 (42) ESV")
    limiting_value = reference_diameter + w * plate_length * tan_phi
    limiting = v.add(
        "DA,Gr",
        "极限直径",
        limiting_value,
        "mm",
        "DA,Gr = dW + w·lP·tanφ",
        "DA ≥ DA,Gr：变形体为纯锥体" if joint.outer_diameter >= limiting_value else "DA < DA,Gr：锥体 + 套筒",
    )
    plate_compliance = v.add("δP,plates", "板层柔度", _plate_compliance(item, w, tan_phi, start_head, start_nut),
                            "mm/N", "式 (40)/(41)，仅对板层逐层积分")
    washer_compliance = 0.0
    for side, suffix in (("head", "K"), ("nut", "M")):
        washer = item.washer_at(side)
        if washer:
            area = area_circle(item.bearing_outer(side)) - area_circle(item.bearing_inner(side))
            washer_compliance += v.add(f"δW,{suffix}", f"{'头' if side == 'head' else '螺母'}侧垫片柔度",
                                      washer.thickness / (washer.youngs_modulus * area), "mm/N",
                                      "t/(EW·Aeff)，共同承压环面，不计载荷扩散")
            provisional[f"{side}_washer.model"] = "default:保守平垫片模型（弯曲与载荷扩散未验证）"
    if washer_compliance:
        warnings.append("垫片采用保守平垫片模型：不按整个外径扩散载荷；计入厚度、环形压缩柔度、嵌入与两接触面面压。垫片弯曲、局部屈服及实际载荷分布仍须另行验证。")
    delta_p = v.add("δP", "被夹件总柔度", plate_compliance + washer_compliance, "mm/N", "δP = δP,plates + ΣδW")
    delta_pzu = v.add("δPzu", "附加柔度", (w - 1) * delta_m, "mm/N", "δPzu = (w−1)·δM")
    v.add("w", "连接系数", float(w), "", "DSV w=1, ESV w=2")

    li = item.load_introduction
    if li.mode == "table":
        n = engineering_data.load_introduction_factor(li.joint_class, li.la_over_h, li.ak_over_h)
        if engineering_data.source_is_provisional("table:load_introduction_factor_n") and load.axial_max > 0:
            provisional["load_introduction.n"] = "table:load_introduction_factor_n"
        if li.la_over_h > 0.3 or li.ak_over_h > 0.5:
            warnings.append("lA/h 或 ak/h 超出表 2 范围，n 取边界值。")
    else:
        n = li.n
    v.add("n", "载荷导入系数", n, "", "表 2" if li.mode == "table" else "手动输入")
    phi_k = v.add("ΦK", "载荷系数 (n=1)", (delta_p + delta_pzu) / (delta_s + delta_p), "", "ΦK = (δP+δPzu)/(δS+δP)")
    phi = v.add("Φn", "载荷系数", n * phi_k, "", "Φn = n·ΦK")

    # R4 embedding
    shear_load = load.transverse > 0 or load.torque > 0
    if item.embedding.mode == "table":
        fz_um = _table_embedding(item, shear_load)
        if engineering_data.source_is_provisional("table:embedding_um"):
            provisional["embedding.fz_um"] = "table:embedding_um"
    else:
        fz_um = item.embedding.fz_um
    fz_mm = v.add("fZ", "嵌入量", fz_um / 1000, "mm", "表 5" if item.embedding.mode == "table" else "手动输入")
    fz_force = v.add("FZ", "嵌入预紧力损失", fz_mm / (delta_s + delta_p), "N", "R4: FZ = fZ/(δS+δP)")

    # R2 required clamp load
    interfaces = layers[:-1] if dsv else layers
    if not interfaces:
        interfaces = layers
        if shear_load:
            warnings.append("单层 DSV 无内部分界面，μT 取第 1 层数值。")
    mu_t = v.add("μT,min", "最小界面摩擦系数", min(layer.interface_friction for layer in interfaces), "", "板层数据")
    torque_nmm = load.torque * 1000
    fkq = load.transverse / (load.slip_interfaces * mu_t)
    if load.torque > 0:
        fkq += torque_nmm / (load.torque_interfaces * (load.friction_radius or 1.0) * mu_t)
    fkq = v.add("FKQerf", "传递横向载荷所需夹紧力", fkq, "N", "R2/1: FQ/(qF·μT) + MY/(qM·ra·μT)")
    fkp = v.add("FKP", "密封所需夹紧力", load.sealing_area * load.sealing_pressure, "N", "R2/2: AD·pi,max")
    fk_axial = max(fkp, load.residual_clamp)
    v.add("FK,ax", "轴向/密封最小残余夹紧力", fk_axial, "N", "max(FKP, FK,erf 输入)")
    fkerf = v.add("FKerf", "所需最小夹紧力", max(fkq, fk_axial), "N", "R2/3: max(FKQerf, FKP + FKA)")

    # R5/R6 preload
    fmmin = v.add("FMmin", "最小装配预紧力", fkerf + (1 - phi) * load.axial_max + fz_force, "N", "R5: FKerf + (1−Φn)FAmax + FZ")
    fmmax = v.add("FMmax", "最大装配预紧力", assembly.tightening_factor * fmmin, "N", "R6: αA·FMmin")

    # R7 assembly stress
    thread_diameter = (d2 + d3) / 2
    use_shank = l1 > 0 and area_shank < area_stress
    d0 = shank_d if use_shank else thread_diameter
    a0 = v.add("A0", "最小截面积", area_shank if use_shank else area_stress, "mm²", "A0 = min(AS, AT) − Abore")
    v.add("d0", "危险截面直径", d0, "mm", "d0 = dT 或 dS = (d2+d3)/2")
    wppl = v.add("WPpl", "塑性极惯性矩", math.pi / 12 * (d0**3 - bore**3), "mm³", "WPpl = π/12·(d0³−db³)")
    torsion = d2 / 2 * (pitch / (math.pi * d2) + 1.155 * bolt.thread_friction)
    k_factor = torsion * a0 / wppl
    fmzul_calc = v.add(
        "FMzul,R7",
        "许用装配预紧力 (R7)",
        a0 * assembly.utilization * bolt.yield_strength / math.sqrt(1 + 3 * k_factor**2),
        "N",
        "R7/1, 式 (140)",
    )
    if item.advanced.preload_override is not None:
        fmzul = v.add("FMzul", "许用装配预紧力", item.advanced.preload_override, "N", "用户覆盖 (例如表 A1)")
        warnings.append("FMzul 使用覆盖值；R7 计算值仅供对照。")
    else:
        fmzul = v.add("FMzul", "许用装配预紧力", fmzul_calc, "N", "R7/1")

    # R8 working stress
    fsa_max = v.add("FSAmax", "螺栓附加载荷", phi * load.axial_max, "N", "FSA = Φn·FAmax")
    fs_max = v.add("FSmax", "最大螺栓力", fmzul + fsa_max, "N", "R8/1: FMzul + Φn·FAmax")
    sigma_z = v.add("σz,max", "最大拉应力", fs_max / a0, "MPa", "R8/2")
    mg = v.add("MG", "螺纹力矩", fmzul * torsion, "N·mm", "R8/3")
    wp = math.pi / 16 * (d0**4 - bore**4) / d0
    v.add("WP", "极截面模量", wp, "mm³", "WP = π/16·(d0⁴−db⁴)/d0")
    tau = v.add("τmax", "最大扭转应力", mg / wp, "MPa", "R8/3")
    sigma_red = v.add("σred,B", "工作等效应力", math.sqrt(sigma_z**2 + 3 * (0.5 * tau) ** 2), "MPa", "R8/4, kτ = 0.5")
    sf = v.add("SF", "抗屈服安全系数", bolt.yield_strength / sigma_red, "", "R8/5")

    # R9 fatigue
    sigma_a = v.add("σa", "交变应力幅", phi * (load.axial_max - load.axial_min) / (2 * area_stress), "MPa", "R9/1")
    sigma_asv = 0.85 * (150 / d + 45)
    v.add("σASV", "疲劳极限 (SV)", sigma_asv, "MPa", "R9/5-1")
    sigma_as = sigma_asv
    if bolt.rolling == "SG":
        f02 = area_stress * bolt.yield_strength
        fsm = phi * (load.axial_max + load.axial_min) / 2 + fmzul
        sigma_as = v.add("σASG", "疲劳极限 (SG)", max(2 - fsm / f02, 0.0) * sigma_asv, "MPa", "R9/5-2")
    if load.cycles is not None and load.cycles < ND_CYCLES:
        factor_sv = (ND_CYCLES / load.cycles) ** (1 / 3)
        finite_sv = sigma_asv * factor_sv
        if bolt.rolling == "SG":
            finite = max(sigma_as * (ND_CYCLES / load.cycles) ** (1 / 6), finite_sv)
        else:
            finite = finite_sv
        sigma_as = v.add("σAZS", "有限寿命疲劳强度", finite, "MPa", "R9/6")
    if d > 40:
        warnings.append("d > 40 mm：R9/5 疲劳极限参考值需另行确认。")

    # R10 surface pressure
    fv_max = fmzul - fz_force
    bearing_force = max(fmzul, fv_max + fsa_max)
    sp_head = _bearing_check(item, "head", bearing_force, v)
    sp_nut = _bearing_check(item, "nut", bearing_force, v) if dsv else None

    # R11 engagement
    engagement_check = _engagement_check(item, v, engagement, a0, provisional, warnings)

    # R12 residual clamp, slip and shear
    fkr = v.add("FKRmin", "最小残余夹紧力", fmzul / assembly.tightening_factor - (1 - phi) * load.axial_max - fz_force, "N", "R12/1")
    sg = v.add("SG", "抗滑移安全系数", fkr / fkq, "", "R12/4") if fkq > 0 else None
    sa = None
    if load.transverse > 0:
        interface_positions = []
        position = item.head_washer_thickness
        for layer in interfaces if (dsv and len(layers) > 1) or not dsv else []:
            position += layer.thickness
            interface_positions.append(position)
        if not interface_positions:
            interface_positions = [item.head_washer_thickness]
        shear_area = min(area_shank if pos <= l1 + 1e-9 else area_d3 for pos in interface_positions)
        v.add("Aτ", "剪切面截面积", shear_area, "mm²", "R12/5")
        tau_b = v.add("τB", "螺栓抗剪强度", bolt.shear_ratio * bolt.tensile_strength, "MPa", "表 7: (τB/Rm)·Rm")
        v.add("τQmax", "滑移时剪应力", load.transverse / shear_area, "MPa", "R12/5")
        sa = v.add("SA", "抗剪安全系数", tau_b * shear_area / load.transverse, "", "R12/7")

    # R13 tightening torque
    side = assembly.tighten_side
    bearing_d = nut.bearing_diameter if side == "nut" else bolt.head_bearing_diameter
    washer = item.washer_at(side)
    contact_inner = washer.inner_diameter if washer else chamfer
    contact_outer = min(bearing_d, washer.outer_diameter) if washer else bearing_d
    dkm = v.add("DKm", "支承摩擦平均直径", (contact_outer + contact_inner) / 2, "mm", "R13: 拧紧件接触环面内外径的平均值（垫片不随拧紧件转动）")
    mu_k = v.add("μK", "支承面摩擦系数", bolt.bearing_friction, "", "螺栓输入；假设 μK = μG")
    v.add("MA", "拧紧力矩", fmzul * (0.16 * pitch + 0.58 * d2 * bolt.thread_friction + dkm / 2 * mu_k) / 1000, "N·m", "R13/1")

    req = item.requirements
    checks = [
        SafetyCheck("FMzul", "预紧力 FMzul ≥ FMmax", fmzul, fmmax, "N", _status(fmzul, fmmax), "R7"),
        SafetyCheck("SF", "抗屈服安全系数", sf, req.SF, "", _status(sf, req.SF), "R8"),
    ]
    if sigma_a > 0:
        sd = v.add("SD", "疲劳安全系数", sigma_as / sigma_a, "", "R9/4")
        checks.append(SafetyCheck("SD", "疲劳安全系数", sd, req.SD, "", _status(sd, req.SD), "R9"))
    else:
        checks.append(SafetyCheck("SD", "疲劳安全系数", None, req.SD, "", ResultStatus.NOT_APPLICABLE, "R9", "无交变轴向载荷"))
    checks.append(SafetyCheck("Sp,K", "螺栓头面压安全系数", sp_head, req.Sp, "", _status(sp_head, req.Sp), "R10"))
    if sp_nut is not None:
        checks.append(SafetyCheck("Sp,M", "螺母侧面压安全系数", sp_nut, req.Sp, "", _status(sp_nut, req.Sp), "R10"))
    checks.append(engagement_check)
    checks.append(SafetyCheck(
        "FKR", "残余夹紧力 FKRmin ≥ FK,ax", fkr, fk_axial, "N", _status(fkr, fk_axial), "R12",
        "FK,ax = 0 时表示连接不张开",
    ))
    if sg is not None:
        checks.append(SafetyCheck("SG", "抗滑移安全系数", sg, req.SG, "", _status(sg, req.SG), "R12"))
    else:
        checks.append(SafetyCheck("SG", "抗滑移安全系数", None, req.SG, "", ResultStatus.NOT_APPLICABLE, "R12", "无横向载荷或扭矩"))
    if sa is not None:
        checks.append(SafetyCheck("SA", "抗剪安全系数", sa, req.SA, "", _status(sa, req.SA), "R12"))
    else:
        checks.append(SafetyCheck("SA", "抗剪安全系数", None, req.SA, "", ResultStatus.NOT_APPLICABLE, "R12", "无横向载荷"))

    statuses = {check.status for check in checks}
    provisional_sources = tuple(f"{path} ← {source}" for path, source in sorted(provisional.items()))
    if ResultStatus.FAIL in statuses:
        verdict, verdict_label = ResultStatus.FAIL, ResultStatus.FAIL.value
    elif ResultStatus.NEEDS_REVIEW in statuses or provisional_sources:
        verdict, verdict_label = ResultStatus.NEEDS_REVIEW, REVIEW_LABEL
    else:
        verdict, verdict_label = ResultStatus.PASS, ResultStatus.PASS.value
    if provisional_sources:
        warnings.insert(0, "使用了未经核验的数据或模型假设，结果须核验后方可作为最终结论。")

    result = CalculationResult(
        case_id="GENERAL",
        model_name=MODEL_NAME,
        source_reference=f"{STANDARD}, 第 5 章 / R0–R13",
        values=tuple(v.values),
        warnings=tuple(warnings),
    )
    metrics = SectionMetrics(
        clamp_length=clamp,
        shank_length_in_grip=l1,
        thread_length_in_grip=l_gew,
        engagement_length=max(engagement, 0.0),
        tan_phi=tan_phi,
        limiting_diameter=limiting,
        w=w,
        critical_diameter=d0,
        cone_start_head=start_head,
        cone_start_nut=start_nut,
        cone_kind=cone_kind,
    )
    return GeneralCalculationResult(
        input=item,
        result=result,
        checks=tuple(checks),
        verdict=verdict,
        verdict_label=verdict_label,
        provisional_sources=provisional_sources,
        metrics=metrics,
    )


def _table_embedding(item: GeneralInput, shear: bool) -> float:
    contacts: list[tuple[str, PlateLayer | WasherInput]] = [
        (f"plates[{index}]", layer) for index, layer in enumerate(item.plates)
    ]
    if item.washer_at("head"):
        contacts.insert(0, ("head_washer", item.head_washer))
    if item.washer_at("nut"):
        contacts.append(("nut_washer", item.nut_washer))

    def values(index: int) -> tuple[float, float, float]:
        path, part = contacts[index]
        try:
            return engineering_data.embedding_values(part.roughness_rz, shear)
        except ValueError as error:
            raise InputValidationError([
                FieldError(f"{path}.roughness_rz", f"{error}；请改用手动 fZ"),
            ]) from error

    thread, head_bearing, _ = values(0)
    total = thread + head_bearing
    if item.is_through_bolt:
        total += values(len(contacts) - 1)[1]
    override = item.embedding.interface_count
    if override is not None:
        roughest = max(range(len(contacts)), key=lambda i: contacts[i][1].roughness_rz)
        total += override * values(roughest)[2]
        return total
    for index in range(len(contacts) - 1):
        roughest = index if contacts[index][1].roughness_rz >= contacts[index + 1][1].roughness_rz else index + 1
        total += values(roughest)[2]
    if not item.is_through_bolt:
        total += values(len(contacts) - 1)[2]
    return total


def _engagement_check(
    item: GeneralInput,
    v: _Values,
    engagement: float,
    breaking_area: float,
    provisional: dict[str, str],
    warnings: list[str],
) -> SafetyCheck:
    bolt, nut, tapped = item.bolt, item.nut, item.tapped
    if item.is_through_bolt and nut.standard_adequate:
        if engagement < nut.height - 1e-9:
            return SafetyCheck(
                "mges", "螺纹旋合长度", engagement, nut.height, "mm", ResultStatus.FAIL, "R11",
                "螺栓伸出长度不足以旋满螺母",
            )
        return SafetyCheck(
            "mges", "螺纹旋合长度", engagement, nut.height, "mm", ResultStatus.NOT_APPLICABLE, "R11",
            "标准螺母且等级匹配，按 VDI 免算脱扣",
        )
    d, pitch, d2 = bolt.d, bolt.pitch, bolt.d2
    if item.is_through_bolt:
        rm_internal = nut.tensile_strength or bolt.tensile_strength
        tau_internal = (nut.shear_ratio or bolt.shear_ratio) * rm_internal
        surround = nut.width_across_flats
    else:
        rm_internal = tapped.tensile_strength
        tau_internal = tapped.shear_strength
        surround = tapped.outer_diameter
    tolerances = iso965_tolerances(d, pitch, d2)
    provisional["R11.tolerances"] = "default:ISO 965-1 6g/6H 公差公式近似"
    d1 = tolerances["D1"]
    rs = v.add(
        "RS",
        "螺纹强度比",
        d * (pitch / 2 + (d - d2) * TAN30) / (d1 * (pitch / 2 + (d2 - d1) * TAN30)) * rm_internal / bolt.tensile_strength,
        "",
        "式 (199)",
    )
    if surround is None or surround / d > 1.9:
        c1 = 1.0
    else:
        ratio = surround / d
        if ratio < 1.4:
            warnings.append("s/d < 1.4：式 (201) 超出适用范围。")
        c1 = 3.8 * ratio - ratio**2 - 2.61
    v.add("C1", "螺母扩张修正系数", c1, "", "式 (201)")
    rm_max = bolt.tensile_strength_max or 1.2 * bolt.tensile_strength
    # The bolt breaks at its smallest section (AS or a reduced/hollow shank), eq. (206).
    breaking = rm_max * breaking_area * pitch
    d_min = tolerances["d_min"]
    if rs < 1:
        rs_eff = max(rs, 0.4)
        c3 = v.add("C3", "内螺纹修正系数", 0.728 + 1.769 * rs_eff - 2.896 * rs_eff**2 + 1.296 * rs_eff**3, "", "式 (202)")
        flank = pitch / 2 + (d_min - tolerances["D2_max"]) * TAN30
        required = breaking / (c1 * c3 * tau_internal * flank * math.pi * d_min) + 2 * pitch
        formula = "式 (210)，内螺纹临界，Rm,max·A0"
    else:
        c2 = 1.187 if rs >= 2.2 else 5.594 - 13.682 * rs + 14.107 * rs**2 - 6.057 * rs**3 + 0.9353 * rs**4
        v.add("C2", "外螺纹修正系数", c2, "", "式 (211)/(212)")
        tau_bolt = bolt.shear_ratio * bolt.tensile_strength
        flank = pitch / 2 + (tolerances["d2_min"] - tolerances["D1_max"]) * TAN30
        required = breaking / (c1 * c2 * tau_bolt * flank * math.pi * d_min) + 2 * pitch
        formula = "式 (213)，螺栓螺纹临界，Rm,max·A0"
    required = v.add("mges,min", "最小旋合长度", required, "mm", formula)
    return SafetyCheck(
        "mges", "螺纹旋合长度", engagement, required, "mm", _status(engagement, required), "R11",
        "公差按 ISO 965-1 6g/6H 公式近似",
    )
