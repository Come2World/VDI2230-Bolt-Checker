# 外六角螺栓目录

## 目录范围

`catalog.json` 是可版本化的螺栓参数目录，当前目录版本为 `0.4.0`，覆盖：

- ISO 4014 部分螺纹外六角螺栓和 ISO 4017 全螺纹外六角螺栓。
- M6–M30 公制粗牙，12 个公称直径。
- 强度等级 8.8、10.9、12.9、A2-70、A2-80 和 A2-90（厂商参考）。
- 标准长度建议值及用户自定义长度路径。
- `joint_dimension_records`：ISO 4014 支承直径 `dw,min`、ISO 273 通孔（精/中/粗）以及 ISO 4032 螺母高度与支承直径。

目录随 Python 包分发（`src/vdi2230/data/bolt_catalog/`），程序通过 `vdi2230.data` 加载；同级目录还有 `plate_materials.json`（VDI 2230 表 A9 板材材料）与 `vdi_tables.json`（表 2、5、7、A5、A8）。

数据采用标准/尺寸/参数分离的稳定结构：`thread_sizes` 保存螺纹规格和派生截面值；`bolt_geometries` 保存标准相关的头部及螺纹形式；`property_class_records` 保存按直径范围适用的材料强度，区间端点由 `diameter_min_inclusive`/`diameter_max_inclusive` 显式声明；`length_catalog` 保存长度候选；`joint_dimension_records` 按螺纹规格保存连接尺寸。项目中选中的型号、用户覆盖值和计算快照应另行保存，不要直接修改此目录文件。

## 输入选择与覆盖顺序

1. 用户先选标准、螺纹规格、螺栓长度和强度等级。
2. 目录字段优先自动填入，字段标识为“目录值”，并保留目录版本与来源。
3. 目录缺项时才允许手动输入；用户覆盖目录值时保留原始值、新值、覆盖人/时间及来源。
4. 随附螺栓、材料和表格记录按项目约定为 `accepted_baseline`，不再仅因使用数据库数据而强制“待核验”。原始来源和差异记录保留；特定产品参考值的**适用性**、经验尺寸和模型限制仍单独提示。
5. 碳钢螺栓 `ES` 默认 205000 MPa；A2 默认从板材库 `X5CrNi18-10` 取代表性值 200000 MPa，并标记该材料来源。两者均可覆盖，不保证特定产品模量；螺母模量独立设置。

### A2 数据及适用性

| 等级 | 最低抗拉强度 Rm | 0.2% 规定非比例延伸应力 Rp0.2 | 剪切强度比 τB/Rm |
|---|---:|---:|---:|
| A2-70 | 700 MPa | 450 MPa | 0.72，VDI 表 7 |
| A2-80 | 800 MPa | 600 MPa | 0.68，VDI 表 7 |
| A2-90 | 900 MPa | 700 MPa | 无表值，必须按实际产品输入 |

A2-70/80 强度取 [Andrews Fasteners 的 ISO 3506-1:2020 二级资料](https://andrewsfasteners.uk/standards/mechanical-properties-for-austenitic-stainless-steel/)。
A2-90 采用用户选定的[富田螺子 SUS304CUN 特定产品资料](https://tomitarashi.com/a2-90_a2-100_bolt.html)，不是通用 ISO 等级或其他厂商的保证。
该厂商页面列出 M6、M8、M10、M12、M16、M20，几何按 JIS B1180；
软件为了可编辑性在 M6–M30 目录规格上提供参考强度，但不表示其他尺寸由该厂商供应或符合其保证，也不表示 ISO 4014/4017 绘图尺寸与该厂商产品一致。
采用该目录强度时，适用性单独标记“需确认”；手动值应按实际规格和证书核对。
`proof_stress_mpa` 没有由 Rp0.2 推断，保持空值。

切换至 A2-90 时清空旧剪切比及表格来源，未输入时禁止计算；再次选择有表值的等级时恢复对应值。
切换螺栓规格/等级或手动更改公称直径时，清空产品专用疲劳强度幅；涉及 A2 时同时清空 Rm,max。
仅改长度时保留这些手动值，仍须由用户确认其适用于实际工况。
当等级或保留的来源标识 A2 时，交变轴向载荷下须手动输入适用于实际产品与寿命的疲劳强度幅，否则 SD 为“需确认”；
完全手动且无材料标识时，程序无法识别是否为 A2，用户必须输入适用的实际疲劳数据，不能依赖钢螺栓默认值。
ESV/非标准螺母 R11 还需实际 Rm,max，非标准螺母需其自身抗拉强度和剪切比。
标准匹配螺母免算依据的是界面设置，不是程序选定或认证了实际螺母。

## 数据字段

| 字段 | 含义 | 单位/规则 |
|---|---|---|
| `nominal_diameter_mm` | 螺纹公称直径 `d` | mm |
| `pitch_mm` | 粗牙螺距 `P` | mm |
| `pitch_diameter_d2_mm` | 外螺纹中径 | mm；采信的派生值 |
| `external_thread_minor_diameter_d3_mm` | 外螺纹小径 | mm；采信的派生值 |
| `tensile_stress_area_as_mm2` | 螺纹应力截面积 | mm²；采信的公式派生值 |
| `area_a0_mm2` | VDI 2230 定义下的 `A0` | 当前为空；先确认符号定义及适用截面 |
| `head_height_k_mm` | 六角头高度 | mm |
| `width_across_flats_s_mm` | 对边宽度 | mm |
| `head_corner_diameter_e_mm` | 对角尺寸 | mm；发现来源冲突时记录在 `field_conflicts` |
| `thread_length_b1/b2/b3_mm` | ISO 4014 依长度段适用的螺纹长度 | mm；长度边界需按标准版本复核 |
| `unthreaded_shank_length_h_mm` | ISO 4017 页面列出的无螺纹杆段参数 | mm |
| `property_class_records` | 强度等级、软件目录直径区间、最低强度/可选证明应力 | MPa；采信记录不代表所有实际产品均适用，A2-90 另有适用性提示 |
| `head_bearing_diameter_dw_min_mm` | 螺栓头支承面外径 `dw,min` | mm；保留二级来源记录，项目采信 |
| `clearance_hole_fine/medium/coarse_mm` | ISO 273 通孔直径 | mm；默认取中等系列 |
| `nut_iso4032_height_m_max_mm` / `nut_iso4032_bearing_diameter_dw_min_mm` | ISO 4032 螺母高度与支承直径 | mm；保留二级来源记录，项目采信 |
| `candidate_nominal_lengths_mm` | 上游项目的通用候选长度 | mm；未按直径/标准验证，不作为权威标准长度表 |

`A0` 不与 `As` 混用。数据库暂不为 `A0` 填值，以免在未确认 VDI 符号定义、危险截面和公式用途前误用。

## 来源、许可与复核

来源 ID、固定版本、字段映射和核验状态都保存在 `catalog.json` 的 `sources` 中。BOLTS 条目标为 LGPL-2.1-or-later；螺距、ISO 4017 交叉核对及候选长度分别来自 MIT 许可的 GitHub 项目，许可证副本保存在 `licenses/`。外部数值的许可和归属须随目录分发。

本目录页面之间已发现少数 `e` 值不一致，差异继续记录在 `field_conflicts`；当前选定数值不变。上游数据页面未声明标准版次，此信息仍保留。`accepted_baseline` 表示项目默认采信，不宣称已经独立认证所有来源；来源审计备注、许可证及原始差异不被删除。通用长度列表仍只是建议，不保证每个直径/标准组合均可采购。

## 数据结构验证

在仓库根目录运行：

```sh
python3 -m unittest tests.test_bolt_catalog
```

该测试只检查 JSON 结构、唯一性、引用完整性和保守状态标记，不证明任何工程数值符合标准。
