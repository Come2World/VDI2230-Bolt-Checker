"""Shared, offline presentation translations. Engineering values and user text stay untouched."""
from __future__ import annotations

import re
from functools import lru_cache
from string import Formatter
from typing import Literal


Language = Literal["zh", "en"]


class MissingTranslationError(RuntimeError):
    """A bundled application message has no English translation."""


MESSAGES = {
    "螺栓连接计算": "Bolt joint calculator",
    "VDI 2230 · 螺栓连接计算": "VDI 2230 · Bolt joint calculator",
    "VDI 2230 螺栓连接计算 · 通用": "VDI 2230 Bolt joint calculator · General",
    "VDI 2230 通用计算": "VDI 2230 General",
    "项目标题": "Project title",
    "设计输入": "Design inputs",
    "输入分组": "Input groups",
    "结果视图": "Result views",
    "螺栓": "Bolt",
    "板层": "Plates",
    "载荷": "Loads",
    "装配": "Assembly",
    "连接与目录": "Joint and catalog",
    "螺栓几何": "Bolt geometry",
    "螺栓材料与摩擦": "Bolt material and friction",
    "螺母（DSV）": "Nut (DSV)",
    "内螺纹件（ESV）": "Tapped part (ESV)",
    "孔与外径": "Hole and outer diameter",
    "头侧垫片": "Head washer",
    "螺母侧垫片": "Nut washer",
    "螺母侧垫片（DSV）": "Nut washer (DSV)",
    "外载荷": "External loads",
    "拧紧": "Tightening",
    "嵌入": "Embedding",
    "高级选项": "Advanced",
    "安全系数要求": "Required safety factors",
    "二维剖面": "Section",
    "螺栓连接二维剖面": "Bolt joint cross-section",
    "计算结果": "Results",
    "安全系数": "Safety factors",
    "全部结果": "All results",
    "报告": "Report",
    "导出 TXT": "Export TXT",
    "+ 添加板层": "+ Add plate",
    "+ 板层": "+ Plate",
    "− 删除选中层": "− Remove",
    "添加": "Add",
    "删除": "Remove",
    "上移": "Up",
    "下移": "Down",
    "校核项": "Check",
    "计算值": "Value",
    "要求": "Required",
    "要求值": "Required value",
    "状态": "Status",
    "符号": "Symbol",
    "名称": "Name",
    "数值": "Value",
    "单位": "Unit",
    "筛选符号或名称": "Filter symbol or name",
    "筛选结果": "Filter results",
    "待核验数据来源": "Unverified sources",
    "输入": "Input",
    "通过": "Pass",
    "不通过": "Fail",
    "需确认": "Review",
    "不适用": "N/A",
    "未计算": "Not calculated",
    "超出范围": "Out of scope",
    "计算错误": "Calculation error",
    "需确认 · 数据待核验": "Review · unverified data",
    "正在加载…": "Loading…",
    "加载失败": "Loading failed",
    "计算中…": "Calculating…",
    "正在计算…": "Calculating…",
    "输入有误": "Invalid input",
    "计算失败": "Calculation failed",
    "结果未更新": "Results not updated",
    "全部校核满足要求。": "All checks meet the requirements.",
    "计算校核均满足要求，但数据或模型假设待核验，结果不得作为最终结论。":
        "All checks meet the requirements, but data or model assumptions remain unverified. Results are not final.",
    "部分校核、数据或模型假设待核验，结果不得作为最终结论。":
        "Some checks, data, or model assumptions require review. Results are not final.",
    "剖面未更新：请先修正标红输入": "Section not updated: correct the highlighted inputs first",
    "自定义": "Custom",
    "自定义（手动输入）": "Custom (manual)",
    "（未命名）": "(unnamed)",
    "（空）": "(blank)",
    "是": "Yes",
    "否": "No",
    "自动": "Automatic",
    "手动": "Manual",
    "查表": "Table",
    "通用螺栓连接": "General bolt joint",
    "导出计算报告": "Export calculation report",
    "文本文件": "Text files",
    "导出失败": "Export failed",
    "自螺栓头侧起排列。μT 指板层传力界面；μK 与 μG 在螺栓页独立设置。垫片经验尺寸可改，手动值不会随公称直径覆盖。":
        "Order from the bolt head. μT is the plate-interface friction; set μK and μG independently on the Bolt tab. Washer estimates are editable; manual dimensions are retained.",
    "连接类型": "Joint type",
    "目录型号": "Catalog variant",
    "强度等级": "Property class",
    "头部形式": "Head type",
    "公称直径 d": "Nominal diameter d",
    "螺距 P": "Pitch P",
    "中径 d2": "Pitch diameter d2",
    "小径 d3": "Minor diameter d3",
    "应力截面 AS": "Stress area AS",
    "头部支承直径 dW": "Head bearing dW",
    "头高 k": "Head height k",
    "螺栓长度 l": "Bolt length l",
    "螺纹长度 b": "Thread length b",
    "杆径 dT": "Shank diameter dT",
    "中心孔 db": "Axial bore db",
    "弹性模量 ES": "Elastic modulus ES",
    "屈服强度 Rp0.2": "Yield strength Rp0.2",
    "抗拉强度 Rm": "Tensile strength Rm",
    "最大抗拉强度 Rm,max": "Max. strength Rm,max",
    "剪切强度比 τB/Rm": "Shear strength ratio τB/Rm",
    "产品疲劳强度幅 σA": "Product fatigue strength amplitude σA",
    "留空 = 8.8/10.9/12.9 按 VDI R9 计算 σASV/σASG（见报告 R9）；A2 有交变载荷时须输入产品值":
        "Blank = calculated by VDI R9 as σASV/σASG for 8.8/10.9/12.9 (see report R9); A2 with alternating load requires the product value.",
    "头部对边 s": "Head width across flats s",
    "头部直径 dk": "Head diameter dk",
    "内六角对边 s": "Socket size s",
    "内六角深度 t": "Socket depth t",
    "仅用于剖面图；留空或与 dW 不协调时按 dW 估算": "Drawing only; blank or inconsistent with dW = estimated from dW",
    "dW 用于：R10 面压 Ap = π/4·(dW²−dha²)、变形锥起始直径及 βL = lP/dW、y = DA′/dW、R13 支承摩擦直径 DKm = (dW+dha)/2；头部对边 s、dk 和内六角尺寸仅用于剖面图。":
        "dW is used for: R10 bearing area Ap = π/4·(dW²−dha²), the deformation-cone start diameter with βL = lP/dW and y = DA′/dW, and the R13 bearing friction diameter DKm = (dW+dha)/2; head s, dk and socket sizes are for the drawing only.",
    "非 A2 留空 = 1.2·Rm；A2 螺纹脱扣校核须输入实际值":
        "For non-A2 bolts, blank = 1.2·Rm; A2 thread-stripping checks require the actual value.",
    "非 A2 留空 = 螺栓 Rm；A2 非标准螺母须输入实际值":
        "For non-A2 bolts, blank = bolt Rm; A2 nonstandard nuts require the actual value.",
    "螺纹滚压": "Thread rolling",
    "螺纹摩擦 μG": "Thread friction μG",
    "支承摩擦 μK": "Bearing friction μK",
    "独立输入；拧紧侧螺栓头/螺母与垫片或板面的摩擦":
        "Independent input; friction between the rotating head/nut and the washer or plate.",
    "A2-90 无默认剪切强度比，请按实际产品资料输入。":
        "No default shear strength ratio is available for A2-90; enter it from the actual product data.",
    "所选 A2 等级与强度来源不一致，请重新选择目录或手动填写。":
        "The strength source does not match the selected A2 class; reselect the catalog or enter the value manually.",
    "所选 A2 等级的剪切强度比与表 7 不符，请重新选择目录或手动填写。":
        "The shear strength ratio does not match Table 7 for the selected A2 class; reselect the catalog or enter it manually.",
    "目录 A2 强度不适用于该公称直径，请使用适用范围或手动输入强度。":
        "The catalog A2 strengths do not cover this nominal diameter; use an in-range size or enter the strengths manually.",
    "目录规格不存在或与保留的目录来源不一致，请重新选择或改为自定义。":
        "The catalog variant is unknown or does not match the retained catalog sources; reselect it or use custom geometry.",
    "产品疲劳强度幅需要输入格式 vdi2230.general/4。":
        "A product fatigue strength amplitude requires input schema vdi2230.general/4.",
    "规格或等级改变，部分产品专用强度输入已清除，请核对后重新输入。":
        "The size or class changed; some product-specific strength inputs were cleared. Verify and re-enter them.",
    "A2-90 目录强度参考富田螺子厂商 SUS304CUN 产品（M6、M8、M10、M12、M16、M20；JIS B1180）；须核验实际制造商、规格及强度，目录 ISO 几何不代表该产品。":
        "A2-90 catalog strengths reference supplier Tomita Rashi's SUS304CUN products (M6, M8, M10, M12, M16, M20; JIS B1180). Verify the actual manufacturer, size, and strengths; ISO catalog geometry does not represent that product.",
    "A2 螺栓疲劳强度幅需按实际产品及寿命输入；ISO 898-1 钢螺栓疲劳参考公式不适用。":
        "Enter the A2 bolt fatigue strength amplitude for the actual product and life; the ISO 898-1 steel-bolt fatigue reference formula does not apply.",
    "用户输入的疲劳强度幅须适用于实际螺栓、工况和寿命。":
        "The entered fatigue strength amplitude must apply to the actual bolt, conditions, and life.",
    "A2 螺纹脱扣校核需输入实际最大抗拉强度 Rm,max。":
        "The A2 thread-stripping check requires the actual maximum tensile strength Rm,max.",
    "A2 非标准螺母脱扣校核需输入螺母实际抗拉强度和剪切强度比。":
        "The A2 nonstandard-nut stripping check requires the nut's actual tensile strength and shear strength ratio.",
    "当前设置按匹配标准螺母免算 R11；请确认实际螺母材料及等级与 A2 螺栓匹配。":
        "R11 is waived under the matching-standard-nut setting; confirm that the actual nut material and class match the A2 bolt.",
    "输入疲劳强度幅": "Entered fatigue strength amplitude",
    "用户输入（指定工况与寿命）": "User input (specified conditions and life)",
    "螺栓输入: (τB/Rm)·Rm": "Bolt input: (τB/Rm)·Rm",
    "螺母高度 m": "Nut height m",
    "螺母支承直径 dW": "Nut bearing dW",
    "螺母对边 s": "Nut width across flats s",
    "螺母弹性模量 EM": "Nut elastic modulus EM",
    "螺母 Rm": "Nut strength Rm",
    "螺母 τB/Rm": "Nut shear ratio τB/Rm",
    "标准螺母且等级匹配": "Matching standard nut",
    "ISO 4032 且螺母等级 ≥ 螺栓等级时免 R11": "R11 waived for ISO 4032 nuts with a class at least equal to the bolt class",
    "内螺纹件材料": "Tapped part material",
    "内螺纹件 EM": "Tapped part modulus EM",
    "内螺纹件 Rm": "Tapped part strength Rm",
    "内螺纹件 τB": "Tapped part shear strength τB",
    "内螺纹外围直径 s": "Tapped-part outer diameter s",
    "旋合长度 mges": "Engagement length mges",
    "可用旋合长度上限；留空 = 内外螺纹实际重叠长度": "Engagement limit; blank = actual overlap of internal and external threads",
    "攻丝孔类型": "Tapped hole type",
    "盲孔": "Blind hole",
    "通孔": "Through hole",
    "内螺纹件厚度 H": "Tapped part thickness H",
    "钻孔深度 Lh": "Drilled hole depth Lh",
    "完整内螺纹深度 Lt": "Full internal thread depth Lt",
    "留空 = 按螺栓伸入长度和孔深估算；不计入夹紧长度 lK":
        "Blank = estimated from bolt insertion and hole depth; excluded from grip length lK",
    "盲孔自接触面至钻尖；留空 = l − lK + 0.4d；钻尖按 118° 估算":
        "Blind hole: contact face to drill tip; blank = l − lK + 0.4d; drill tip estimated at 118°",
    "自接触面起；留空 = 螺栓伸入与可用孔深的较小值；参与 R11 校核":
        "From the contact face; blank = lesser of bolt insertion and usable hole depth; used in R11",
    "完整内螺纹深度须 ≤ 可用圆柱孔深": "Full internal thread depth must not exceed the usable cylindrical hole depth",
    "内外螺纹须有正的重叠旋合长度": "Internal and external threads must have positive engagement overlap",
    "盲孔钻尖深度须小于内螺纹件厚度 H；通孔请选择通孔类型":
        "Blind drill-tip depth must be less than tapped part thickness H; select through hole for an open hole",
    "螺栓不得顶底：伸入长度须小于盲孔圆柱深度（不含钻尖）":
        "Bolt must not bottom out: insertion must be less than blind cylindrical depth (excluding the drill tip)",
    "没有匹配的头部目录尺寸，已切换为自定义；请输入头部尺寸，留空时绘图使用估算值。":
        "No matching head geometry in the catalog; switched to custom. Enter head dimensions; blank drawing sizes are estimates.",
    "ESV 解析几何（留空尺寸为估算）": "Resolved ESV geometry (blank dimensions are estimates)",
    "盲孔 Lh 含 118° 钻尖；通孔 Lh = H；实际旋合取内外螺纹重叠并受 mges 限制，红色段与 R11 一致。":
        "Blind Lh includes a 118° drill tip; through Lh = H. Actual thread overlap is capped by mges; the red segment matches R11.",
    "DSV: min(m, l − lK); ESV: min(l − lK, Lt) − max(0, l − b − lK)，再受 mges 限制":
        "DSV: min(m, l − lK); ESV: min(l − lK, Lt) − max(0, l − b − lK), capped by mges",
    "通孔直径 dh": "Hole diameter dh",
    "倒角直径 dha": "Chamfer diameter dha",
    "外径 DA": "Outer diameter DA",
    "替代外径 DA′": "Effective outer diameter DA′",
    "连接系数 w": "Joint coefficient w",
    "锥角公式": "Cone-angle formula",
    "锥起始直径": "Cone starting diameter",
    "垫片内径 di": "Washer bore di",
    "垫片外径 Do": "Washer outer diameter Do",
    "垫片厚度 t": "Washer thickness t",
    "垫片材料": "Washer material",
    "弹性模量 EW": "Elastic modulus EW",
    "极限面压 pG": "Limiting pressure pG",
    "粗糙度 Rz": "Roughness Rz",
    "经验值 1.1d，可修改": "Estimate 1.1d; editable",
    "经验值 2d，可修改": "Estimate 2d; editable",
    "经验值 0.16d，可修改": "Estimate 0.16d; editable",
    "轴向载荷 FA,max": "Axial load FA,max",
    "轴向载荷 FA,min": "Axial load FA,min",
    "横向载荷 FQ,max": "Transverse load FQ,max",
    "扭矩 MY,max": "Torque MY,max",
    "摩擦半径 ra": "Friction radius ra",
    "传力界面数 qF": "Load interfaces qF",
    "传扭界面数 qM": "Torque interfaces qM",
    "密封压力 pi,max": "Sealing pressure pi,max",
    "密封面积 AD": "Sealing area AD",
    "最小残余夹紧力 FK,erf": "Min. clamp force FK,erf",
    "密封或功能要求": "Sealing or functional requirement",
    "循环次数 NZ": "Load cycles NZ",
    "载荷导入系数 n": "Load introduction n",
    "n (手动)": "n (manual)",
    "连接类型 (表 2)": "Joint class (Table 2)",
    "拧紧系数 αA": "Tightening factor αA",
    "利用系数 ν": "Utilization ν",
    "拧紧侧": "Tightening side",
    "嵌入量 fZ": "Embedding fZ",
    "fZ (手动)": "fZ (manual)",
    "界面数覆盖": "Interface count override",
    "FMzul 覆盖": "FMzul override",
    "SF 要求": "Required SF",
    "SD 要求": "Required SD",
    "SG 要求": "Required SG",
    "Sp 要求": "Required Sp",
    "SA 要求": "Required SA",
    "交变横向载荷取 1.8": "Use 1.8 for alternating transverse loads",
    "厚度 h": "Thickness h",
    "材料": "Material",
    "弹性模量 EP": "Elastic modulus EP",
    "界面摩擦 μT": "Interface friction μT",
    "通孔螺栓 + 螺母 (DSV)": "DSV: bolt/nut",
    "螺纹孔连接 (ESV)": "ESV: tapped",
    "外六角头": "Hex head",
    "内六角圆柱头": "Socket head",
    "热处理前滚丝 SV": "Pre-heat SV",
    "热处理后滚丝 SG": "Post-heat SG",
    "DSV 锥公式 (43)": "DSV cone formula (43)",
    "ESV 锥公式 (42)": "ESV cone formula (42)",
    "螺栓头": "Bolt head",
    "螺母": "Nut",
    "留空 = 1.2·Rm": "Blank = 1.2·Rm",
    "留空 = C1 取 1": "Blank = C1 of 1",
    "留空 = DA；用于 y = DA′/dW": "Blank = DA; used for y = DA′/dW",
    "留空 = dW": "Blank = dW",
    "留空 = dh": "Blank = dh",
    "留空 = d；小于 d 为细腰杆": "Blank = d; below d for a reduced shank",
    "留空 = l − lK": "Blank = l − lK",
    "留空 = 全螺纹": "Blank = fully threaded",
    "留空 = 按 R7 计算": "Blank = calculate using R7",
    "留空 = 无限寿命 (≥2·10⁶)": "Blank = infinite life (≥2·10⁶)",
    "留空 = 螺栓 Rm": "Blank = bolt Rm",
    "必填": "Required",
    "应为对象": "Must be an object",
    "应为数值": "Must be numeric",
    "应为整数": "Must be an integer",
    "应为文本": "Must be text",
    "应为是/否": "Must be a boolean",
    "应为有限数值": "Must be finite",
    "文本过长": "Text is too long",
    "无效": "Invalid",
    "来源记录应为文本": "Source records must be text",
    "标题应为不超过 120 字的文本": "Title must be text of at most 120 characters",
    "至少需要一层夹紧板": "At least one clamped plate is required",
    "输入应为 JSON 对象": "Input must be a JSON object",
    "板层 μK 已移除，请改为螺栓的 bearing_friction": "Plate μK was removed; use bolt.bearing_friction",
    "ESV 只能在螺栓头侧拧紧": "ESV joints can only be tightened at the bolt head",
    "螺距相对直径过大": "Pitch is too large relative to the diameter",
    "须满足 d3 < d2 < d": "Must satisfy d3 < d2 < d",
    "须 < 0.8·d3": "Must be < 0.8·d3",
    "须 ≤ FA,max": "Must be ≤ FA,max",
    "须 ≤ d": "Must be ≤ d",
    "须 ≤ 螺栓长度 l": "Must be ≤ bolt length l",
    "须 ≥ Rm": "Must be ≥ Rm",
    "须大于 d": "Must be greater than d",
    "须大于 dh": "Must be greater than dh",
    "须大于 dh 和 dha": "Must exceed dh and dha",
    "须大于中心孔 db": "Must exceed the axial bore db",
    "须大于垫片内径 di": "Must exceed the washer bore di",
    "须大于螺栓公称直径 d": "Must exceed the nominal bolt diameter d",
    "须小于 Rm": "Must be less than Rm",
    "不能超过 l − lK": "Must not exceed l − lK",
    "有密封压力时必填": "Required when sealing pressure is specified",
    "有扭矩时必填": "Required when torque is specified",
    "螺纹起点须位于夹紧长度内，否则螺母无法压紧": "The thread must start within the grip length so the nut can clamp the joint",
    "使用垫片时，锥起始直径不得超过保守有效承压外径": "With a washer, the cone start must not exceed the conservative bearing diameter",
    "使用垫片时，锥起始直径须大于垫片内径": "With a washer, the cone start must exceed the washer bore",
    "垫片、支承面和板层须有共同的有效承压环面（外径须大于内径、dh 和 dha）": "The washer, bearing face and plate need a common contact annulus (outer diameter greater than the bore, dh and dha)",
    "VDI 2230-1:2015 通用同心单螺栓计算": "VDI 2230-1:2015 General concentric single-bolt calculation",
    "夹紧长度": "Grip length",
    "板层总厚度": "Total plate thickness",
    "夹紧区内光杆长度": "Unthreaded length within grip",
    "夹紧区内自由螺纹长度": "Free thread length within grip",
    "危险截面直径": "Critical section diameter",
    "最小截面积": "Minimum cross-sectional area",
    "极截面模量": "Polar section modulus",
    "塑性极惯性矩": "Plastic polar moment of inertia",
    "连接系数": "Joint coefficient",
    "板层长度比": "Plate length ratio",
    "外径比": "Outer diameter ratio",
    "替代锥角正切": "Equivalent cone-angle tangent",
    "极限直径": "Limiting diameter",
    "板层柔度": "Plate compliance",
    "螺栓头柔度": "Bolt head compliance",
    "光杆柔度": "Shank compliance",
    "自由螺纹柔度": "Free thread compliance",
    "旋合螺纹柔度": "Engaged thread compliance",
    "螺母/内螺纹柔度": "Nut/tapped-thread compliance",
    "螺栓总柔度": "Total bolt compliance",
    "被夹件总柔度": "Total clamped-part compliance",
    "附加柔度": "Additional compliance",
    "载荷导入系数": "Load introduction factor",
    "载荷系数": "Load factor",
    "载荷系数 (n=1)": "Load factor (n=1)",
    "最小界面摩擦系数": "Minimum interface friction",
    "传递横向载荷所需夹紧力": "Clamp force for transverse loading",
    "密封所需夹紧力": "Clamp force for sealing",
    "轴向/密封最小残余夹紧力": "Minimum axial/sealing clamp force",
    "所需最小夹紧力": "Required minimum clamp force",
    "嵌入量": "Embedding",
    "嵌入预紧力损失": "Preload loss from embedding",
    "最小装配预紧力": "Minimum assembly preload",
    "最大装配预紧力": "Maximum assembly preload",
    "许用装配预紧力 (R7)": "Allowable assembly preload (R7)",
    "许用装配预紧力": "Allowable assembly preload",
    "螺栓附加载荷": "Additional bolt load",
    "最大螺栓力": "Maximum bolt load",
    "最大拉应力": "Maximum tensile stress",
    "螺纹力矩": "Thread torque",
    "最大扭转应力": "Maximum torsional stress",
    "工作等效应力": "Working equivalent stress",
    "抗屈服安全系数": "Yield safety factor",
    "交变应力幅": "Alternating stress amplitude",
    "疲劳极限 (SV)": "Fatigue limit (SV)",
    "疲劳极限 (SG)": "Fatigue limit (SG)",
    "有限寿命疲劳强度": "Finite-life fatigue strength",
    "疲劳安全系数": "Fatigue safety factor",
    "最小残余夹紧力": "Minimum residual clamp force",
    "抗滑移安全系数": "Slip safety factor",
    "剪切面截面积": "Shear section area",
    "螺栓抗剪强度": "Bolt shear strength",
    "滑移时剪应力": "Shear stress after slip",
    "抗剪安全系数": "Shear safety factor",
    "螺纹强度比": "Thread strength ratio",
    "螺母扩张修正系数": "Nut dilation correction factor",
    "外螺纹修正系数": "External thread correction factor",
    "内螺纹修正系数": "Internal thread correction factor",
    "最小旋合长度": "Minimum engagement length",
    "现有旋合长度": "Available engagement length",
    "支承摩擦平均直径": "Mean bearing friction diameter",
    "支承面摩擦系数": "Bearing friction coefficient",
    "拧紧力矩": "Tightening torque",
    "预紧力 FMzul ≥ FMmax": "Preload FMzul ≥ FMmax",
    "螺栓头面压安全系数": "Head bearing safety factor",
    "螺母侧面压安全系数": "Nut bearing safety factor",
    "螺纹旋合长度": "Thread engagement length",
    "残余夹紧力 FKRmin ≥ FK,ax": "Residual clamp FKRmin ≥ FK,ax",
    "手动输入": "Manual input",
    "板层数据": "Plate data",
    "无交变轴向载荷": "No alternating axial load",
    "无横向载荷": "No transverse load",
    "无横向载荷或扭矩": "No transverse load or torque",
    "FK,ax = 0 时表示连接不张开": "For FK,ax = 0, the joint does not open",
    "标准螺母且等级匹配，按 VDI 免算脱扣": "Matching standard nut; thread stripping check waived under VDI",
    "公差按 ISO 965-1 6g/6H 公式近似": "Tolerances approximated using ISO 965-1 6g/6H formulas",
    "用户覆盖 (例如表 A1)": "User override (e.g. Table A1)",
    "FMzul 使用覆盖值；R7 计算值仅供对照。": "FMzul uses an override; the R7 value is provided for comparison only.",
    "lA/h 或 ak/h 超出表 2 范围，n 取边界值。": "lA/h or ak/h is outside Table 2; n uses the boundary value.",
    "βL/y 超出锥角公式适用范围": "βL/y is outside the cone-angle formula range",
    "d 超出 ISO 965-1 直径范围": "d is outside the ISO 965-1 diameter range",
    "s/d < 1.4：式 (201) 超出适用范围。": "s/d < 1.4: equation (201) is outside its range.",
    "d > 40 mm：R9/5 疲劳极限参考值需另行确认。": "d > 40 mm: the R9/5 fatigue limit needs separate verification.",
    "单层 DSV 无内部分界面，μT 取第 1 层数值。": "A single-plate DSV has no internal interface; μT uses the first plate value.",
    "螺栓伸出长度不足以旋满螺母": "Bolt protrusion is insufficient for full nut engagement",
    "孔径须小于相邻板层全厚度内的有效变形体直径；请检查垫片及支承尺寸": "The bore must be smaller than the effective deformation body throughout the adjacent plate; check washer and bearing dimensions",
    "使用了未经核验的数据或模型假设，结果须核验后方可作为最终结论。": "Unverified data or model assumptions are used. Verify them before treating these results as final.",
    "垫片采用保守平垫片模型：不按整个外径扩散载荷；计入厚度、环形压缩柔度、嵌入与两接触面面压。垫片弯曲、局部屈服及实际载荷分布仍须另行验证。":
        "Conservative plain-washer model: no spreading across the full outer diameter. Thickness, annular compliance, embedding and both contact pressures are included. Washer bending, local yielding and actual load distribution still require verification.",
    "DA < DA,Gr：锥体 + 套筒": "DA < DA,Gr: cone + sleeve",
    "DA ≥ DA,Gr：变形体为纯锥体": "DA ≥ DA,Gr: cone-only deformation body",
    "lP = Σh（不含垫片）": "lP = Σh (excluding washers)",
    "βL = lP/dW（垫片另计柔度）": "βL = lP/dW (washer compliance added separately)",
    "d0 = dT 或 dS = (d2+d3)/2": "d0 = dT or dS = (d2+d3)/2",
    "max(FKP, FK,erf 输入)": "max(FKP, input FK,erf)",
    "t/(EW·Aeff)，共同承压环面，不计载荷扩散": "t/(EW·Aeff), common contact annulus, no load spreading",
    "π/4·(min(dW,Do)²−di²)，不计垫片扩散": "π/4·(min(dW,Do)²−di²), no washer load spreading",
    "取板层与垫片面压安全系数中的较小值": "Minimum of plate and washer bearing safety factors",
    "垫片两接触面面压的最大值": "Maximum pressure at the two washer contacts",
    "螺栓输入；独立于螺纹摩擦 μG": "Bolt input; independent of thread friction μG",
    "R13: 拧紧件接触环面内外径的平均值（垫片不随拧紧件转动）": "R13: mean of the rotating-part contact diameters (stationary washer)",
    "式 (19), δi = li/(ES·Ai)": "Eq. (19), δi = li/(ES·Ai)",
    "式 (19), Ad3": "Eq. (19), Ad3",
    "式 (20), lG = 0.5d": "Eq. (20), lG = 0.5d",
    "式 (40)/(41)，仅对板层逐层积分": "Eq. (40)/(41), integrated over plates only",
    "式 (42) ESV": "Eq. (42) ESV",
    "式 (43) DSV": "Eq. (43) DSV",
    "式 (210)，内螺纹临界，Rm,max·A0": "Eq. (210), internal thread critical, Rm,max·A0",
    "式 (213)，螺栓螺纹临界，Rm,max·A0": "Eq. (213), bolt thread critical, Rm,max·A0",
    "表 7: (τB/Rm)·Rm": "Table 7: (τB/Rm)·Rm",
    "R7/1, 式 (140)": "R7/1, Eq. (140)",
    "平垫片经验尺寸": "Empirical plain-washer dimensions",
    "ISO 965-1 6g/6H 公差公式近似": "ISO 965-1 6g/6H tolerance approximation",
    "保守平垫片模型（弯曲与载荷扩散未验证）": "Conservative washer model (bending and load spreading unverified)",
    "头": "Head",
    "垫片": "Washer",
    "外六角": "Hex",
    "内六角": "Socket",
    "内螺纹": "Thread",
    "内螺纹件": "Tapped part",
    "旋合": "Engagement",
    "空心": "Hollow",
    "细腰": "Reduced shank",
    "DSV 螺栓 + 螺母": "DSV bolt + nut",
    "ESV 螺纹孔": "ESV tapped joint",
    "连接、螺栓与螺母/内螺纹件": "Joint, bolt and nut/tapped part",
    "被夹件几何": "Clamped-part geometry",
    "装配与校核要求": "Assembly and check requirements",
    "VDI 2230 螺栓连接计算报告（通用同心单螺栓）": "VDI 2230 Bolt Joint Calculation Report (General Concentric Single Bolt)",
    "软件版本": "Software version",
    "计算时间（UTC）": "Calculated at (UTC)",
    "计算模型": "Calculation model",
    "计算依据": "Calculation basis",
    "总体判定": "Overall verdict",
    "注意：数据待核验——使用了未经核验的数据或模型假设，结果不得作为最终结论。": "CAUTION: unverified data or model assumptions are used. These results are not final.",
    "一、安全系数与校核": "1. Safety factors and checks",
    "二、输入参数": "2. Input parameters",
    "三、计算过程与全部结果": "3. Calculation steps and all results",
    "四、待核验数据来源": "4. Unverified data sources",
    "五、警告与假设": "5. Warnings and assumptions",
    "依据": "Reference",
    "说明": "Note",
    "来源": "Source",
    "无（使用用户输入或项目采信数据）": "None (user inputs or project-accepted data)",
    "工程辅助计算报告，不替代正式标准、专业工程判断或设计审查。": "Engineering calculation aid only; not a substitute for the official standard, professional engineering judgment or design review.",
    "适用范围：同心单螺栓，轴向载荷 + 横向载荷/扭矩；不含偏心、弯曲、温度影响和螺栓组分配。": "Scope: concentric single bolts under axial and transverse load/torque. Eccentricity, bending, thermal effects and bolt-group load distribution are excluded.",
    "R10 工作面压取 FVmax = FMzul − FZ；DSV 采用 w = 1，两侧锥体起始直径分别取螺栓头与螺母 dW。": "R10 working bearing pressure uses FVmax = FMzul − FZ. DSV uses w = 1 with head/nut dW as the respective cone starting diameters.",
    "R11 公差按 ISO 965-1 6g/6H 公式近似；断裂力取 Rm,max·A0（A0 = min(AS, AT)）。": "R11 tolerances approximate ISO 965-1 6g/6H; rupture load is Rm,max·A0 (A0 = min(AS, AT)).",
    "μK 与 μG 在螺栓页分别独立输入；垫片不随拧紧件转动，力矩使用紧固件/垫片接触环面，不使用垫片外径代替 dW。": "μK and μG are independent bolt inputs. The washer remains stationary; torque uses the fastener/washer contact annulus, not the full washer outer diameter as dW.",
    "平垫片初始尺寸：di = 1.1d、Do = 2d、t = 0.16d；仅为经验估计，不代表 ISO 标准尺寸。": "Initial washer dimensions: di = 1.1d, Do = 2d, t = 0.16d. These are empirical estimates, not ISO standard dimensions.",
    "垫片有效环面：Deff = min(dW, Do, DA)，di,eff = max(di, dh, dha)；δW = t/(EW·Aeff)。不计载荷扩散；邻接板层按较大的 di/dh 孔径保守积分，锥长度不含垫片。": "Effective washer annulus: Deff = min(dW, Do, DA), di,eff = max(di, dh, dha); δW = t/(EW·Aeff). No load spreading. Adjacent plates use the larger di/dh bore; cone length excludes washers.",
    "Sp,K / Sp,M 取对应板层与垫片校核的最小值；垫片分别检查两接触面。嵌入界面数覆盖包含垫片/板层界面；手动 fZ 必须自行包含垫片影响。": "Sp,K / Sp,M take the minimum plate/washer safety factor; both washer contacts are checked. Embedding interface overrides include washer/plate contacts; manual fZ must include washer effects.",
}

# Full-message templates cover legacy computed labels/errors, not arbitrary substring replacement.
TEMPLATES = {
    "目录中没有 {variant} / {property_class} 的组合。": "No catalog combination for {variant} / {property_class}.",
    "启用{label}": "Enable {label}",
    "可选值: {values}": "Allowed values: {values}",
    "须大于夹紧长度 lK = {value}": "Must exceed grip length lK = {value}",
    "式 ({number})": "Eq. ({number})",
    "式 ({first})/({second})": "Eq. ({first})/({second})",
    "式 (19), lSK = {value}d": "Eq. (19), lSK = {value}d",
    "式 (20), lM = {value}d": "Eq. (20), lM = {value}d",
    "表 {number}": "Table {number}",
    "{standard}, 第 5 章 / R0–R13": "{standard}, Chapter 5 / R0–R13",
    "{symbol} 计算结果非有限值": "{symbol} calculation is not finite",
    "必须 > {value}": "Must be > {value}",
    "必须 ≥ {value}": "Must be ≥ {value}",
    "必须 ≤ {value}": "Must be ≤ {value}",
    "最多 {count} 层": "At most {count} plates",
    "输入有误（{count} 项），请修正标红字段。": "Invalid input ({count} errors). Correct the highlighted fields.",
    "计算无法完成，请检查输入：{error}": "Calculation cannot be completed; check the inputs: {error}",
    "{error}；请改用手动 fZ": "{error}; please enter fZ manually",
    "与 π/4·((d2+d3)/2)² = {value} 偏差超过 15%": "Deviation from π/4·((d2+d3)/2)² = {value} exceeds 15%",
    "须大于夹紧长度 lK = {value}，留出旋合长度": "Must exceed grip length lK = {value} to allow thread engagement",
    "仅支持 {schema}；请分别确认螺栓的 thread_friction (μG) 和 bearing_friction (μK)": "Only {schema} is supported; confirm bolt thread_friction (μG) and bearing_friction (μK) independently",
    "仅支持 {schema} 或 {legacy}；请分别确认螺栓的 thread_friction (μG) 和 bearing_friction (μK)":
        "Only {schema} or {legacy} is supported; confirm bolt thread_friction (μG) and bearing_friction (μK) independently",
    "已计算 · {time}": "Calculated · {time}",
    "已导出 {name}": "Exported {name}",
    "板层 {index}": "Plate {index}",
    "板 {index}": "clamped plate {index}",
    "选中：{name}": "Selected: {name}",
    "不通过：{symbols}": "Failed: {symbols}",
    "待核验数据来源 {count} 项，详见报告。": "{count} unverified sources; see the report.",
    "请求失败（{status}）": "Request failed ({status})",
    "计算失败（{status}）": "Calculation failed ({status})",
    "无法加载计算模型：{error}": "Cannot load the calculation model: {error}",
    "编辑板层 {index}": "Edit plate {index}",
    "上移板层 {index}": "Move plate {index} up",
    "下移板层 {index}": "Move plate {index} down",
    "删除板层 {index}": "Remove plate {index}",
    "点击编辑：{label}": "Click to edit: {label}",
    "{source}（数据待核验）": "{source} (unverified data)",
    "板层（自螺栓头侧起，共 {count} 层，Σh = {length} mm；含垫片 lK = {grip} mm）：":
        "Plates (from the head, {count} layers, Σh = {length} mm; grip including washers lK = {grip} mm):",
}

for _side, _english in (("螺栓头侧", "Head-side"), ("螺母侧", "Nut-side")):
    for _suffix, _translated in (
        ("板层支承面积", "plate bearing area"), ("板层最大面压", "maximum plate pressure"),
        ("板层面压安全系数", "plate bearing safety factor"), ("垫片与紧固件接触面积", "washer/fastener contact area"),
        ("垫片最大面压", "maximum washer pressure"), ("垫片面压安全系数", "washer bearing safety factor"),
        ("面压安全系数", "bearing safety factor"),
    ):
        MESSAGES[_side + _suffix] = f"{_english} {_translated}"
MESSAGES.update({"头侧垫片柔度": "Head washer compliance", "螺母侧垫片柔度": "Nut washer compliance"})


def language_code(value: object) -> Language:
    if value == "zh":
        return "zh"
    if value == "en":
        return "en"
    raise ValueError("Unsupported language; use 'zh' or 'en'.")


@lru_cache(maxsize=1)
def _patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    records = []
    # A short template's placeholder must not absorb a more specific message's suffix.
    ordered = sorted(TEMPLATES.items(), key=lambda pair: len(re.sub(r"\{\w+\}", "", pair[0])), reverse=True)
    for source, target in ordered:
        parts = []
        for literal, name, _, _ in Formatter().parse(source):
            parts.append(re.escape(literal))
            if name:
                parts.append(f"(?P<{name}>.+?)")
        records.append((re.compile("".join(parts), re.DOTALL), target))
    return tuple(records)


def translate(text: str, language: Language = "zh") -> str:
    """Translate application-owned text only; never pass user titles or plate names."""
    language_code(language)
    if language == "zh" or not text:
        return text
    if text in MESSAGES:
        return MESSAGES[text]
    for pattern, target in _patterns():
        if match := pattern.fullmatch(text):
            return target.format(**{key: translate(value, language) for key, value in match.groupdict().items()})
    for separator in (" ← ", " · "):
        if separator in text:
            return separator.join(translate(part, language) for part in text.split(separator))
    for prefix in ("VDI 2230 Blatt 1:2015, ", "default:", "- "):
        if text.startswith(prefix):
            return prefix + translate(text[len(prefix):], language)
    if re.search(r"[\u4e00-\u9fff]", text):
        raise MissingTranslationError(f"Missing English translation: {text}")
    return text


def format_text(message: str, language: Language = "zh", **values: object) -> str:
    """Format after translation so free-text arguments are never translated."""
    language_code(language)
    if language == "zh":
        template = message
    elif message in TEMPLATES:
        template = TEMPLATES[message]
    else:
        template = translate(message, language)
    return template.format(**values)


def source_label(source: str, language: Language = "zh") -> str:
    """Localize built-in defaults, leaving user-supplied provenance and identifiers intact."""
    path, separator, value = source.partition(" ← ")
    if not separator:
        return translate(source, language) if source.startswith("default:") else source
    return path + separator + source_label(value, language)
