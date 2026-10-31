# 外六角螺栓目录

## 目录范围

`catalog.json` 是首版统一、可版本化的螺栓参数目录，覆盖：

- ISO 4014 部分螺纹外六角螺栓和 ISO 4017 全螺纹外六角螺栓。
- M6–M30 公制粗牙，12 个公称直径。
- 强度等级 8.8、10.9、12.9。
- 标准长度建议值及用户自定义长度路径。
- `joint_dimension_records`：ISO 4014 支承直径 `dw,min`、ISO 273 通孔（精/中/粗）以及 ISO 4032 螺母高度与支承直径。

目录随 Python 包分发（`src/vdi2230/data/bolt_catalog/`），程序通过 `vdi2230.data` 加载；同级目录还有 `plate_materials.json`（VDI 2230 表 A9 板材材料）与 `vdi_tables.json`（表 2、5、7、A5、A8）。

数据采用标准/尺寸/参数分离的稳定结构：`thread_sizes` 保存螺纹规格和派生截面值；`bolt_geometries` 保存标准相关的头部及螺纹形式；`property_class_records` 保存按直径范围适用的材料强度，区间端点由 `diameter_min_inclusive`/`diameter_max_inclusive` 显式声明；`length_catalog` 保存长度候选；`joint_dimension_records` 按螺纹规格保存连接尺寸。项目中选中的型号、用户覆盖值和计算快照应另行保存，不要直接修改此目录文件。

## 输入选择与覆盖顺序

1. 用户先选标准、螺纹规格、螺栓长度和强度等级。
2. 目录字段优先自动填入，字段标识为“目录值”，并保留目录版本与来源。
3. 目录缺项时才允许手动输入；用户覆盖目录值时保留原始值、新值、覆盖人/时间及来源。
4. 本目录当前为 `provisional`（`selection_policy.provisional_values_are_calculation_eligible = true`）。未经主标准复核的目录值可以参与计算，但结果必须标记“数据待核验”，整体判定不得为最终“通过”（`provisional_values_force_review_status = true`）。冲突字段需用户核对或输入，不得静默选用某一来源。
5. 螺栓弹性模量 `ES` 默认取钢制螺栓典型值 205000 MPa，同样作为待核验默认值；用户可覆盖并注明来源。

## 数据字段

| 字段 | 含义 | 单位/规则 |
|---|---|---|
| `nominal_diameter_mm` | 螺纹公称直径 `d` | mm |
| `pitch_mm` | 粗牙螺距 `P` | mm |
| `pitch_diameter_d2_mm` | 外螺纹中径候选值 | mm；派生值，待核验 |
| `external_thread_minor_diameter_d3_mm` | 外螺纹小径候选值 | mm；派生值，待核验 |
| `tensile_stress_area_as_mm2` | 螺纹应力截面积候选值 | mm²；公式派生值，待核验 |
| `area_a0_mm2` | VDI 2230 定义下的 `A0` | 当前为空；先确认符号定义及适用截面 |
| `head_height_k_mm` | 六角头高度 | mm |
| `width_across_flats_s_mm` | 对边宽度 | mm |
| `head_corner_diameter_e_mm` | 对角尺寸 | mm；发现来源冲突时记录在 `field_conflicts` |
| `thread_length_b1/b2/b3_mm` | ISO 4014 依长度段适用的螺纹长度 | mm；长度边界需按标准版本复核 |
| `unthreaded_shank_length_h_mm` | ISO 4017 页面列出的无螺纹杆段参数 | mm |
| `property_class_records` | 强度等级、直径区间、最低强度/证明应力 | MPa；二级来源，可参与计算但强制“待核验”（`requires_review_warning`） |
| `head_bearing_diameter_dw_min_mm` | 螺栓头支承面外径 `dw,min` | mm；二级来源，待核验 |
| `clearance_hole_fine/medium/coarse_mm` | ISO 273 通孔直径 | mm；默认取中等系列 |
| `nut_iso4032_height_m_max_mm` / `nut_iso4032_bearing_diameter_dw_min_mm` | ISO 4032 螺母高度与支承直径 | mm；二级来源，待核验 |
| `candidate_nominal_lengths_mm` | 上游项目的通用候选长度 | mm；未按直径/标准验证，不作为权威标准长度表 |

`A0` 不与 `As` 混用。数据库暂不为 `A0` 填值，以免在未确认 VDI 符号定义、危险截面和公式用途前误用。

## 来源、许可与复核

来源 ID、固定版本、字段映射和核验状态都保存在 `catalog.json` 的 `sources` 中。BOLTS 条目标为 LGPL-2.1-or-later；螺距、ISO 4017 交叉核对及候选长度分别来自 MIT 许可的 GitHub 项目，许可证副本保存在 `licenses/`。外部数值的许可和归属须随目录分发。

本目录页面之间已发现少数 `e` 值不一致；因此保留冲突标记，而不是猜测。上游数据页面未声明标准版次。加入正式计算前，应针对用户选定的 ISO 版次和 VDI 2230 附录逐字段核验：尺寸、公差、长度适用区间、螺纹参数、应力面积、`A0` 定义以及 8.8/10.9/12.9 的直径分组强度值。复核通过后更新 `verification_status`、复核记录及目录版本，并为每个字段保留来源。

## 数据结构验证

在仓库根目录运行：

```sh
python3 -m unittest tests.test_bolt_catalog
```

该测试只检查 JSON 结构、唯一性、引用完整性和保守状态标记，不证明任何工程数值符合标准。
