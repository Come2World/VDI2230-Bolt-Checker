# VDI 2230 螺栓连接计算软件：架构与发布验证

| 项目 | 内容 |
|---|---|
| 文档版本 | 0.11 |
| 日期 | 2026-11-01 |
| 应用版本 | 0.0.1 |
| 发布分支 | `VDI2230_BOLT_CHECKER_RELEASE_0.0.1` |
| 对应需求 | [需求规格说明书](./SOFTWARE_REQUIREMENTS_SPECIFICATION.md) v1.5 |
| 当前交付 | 通用 Tk 桌面计算器；内部保留标准算例回归 |

## 1. 发布范围与裁剪原则

此分支仅提供同心单螺栓 DSV/ESV 的通用 Tk 界面。
删除原有 Web 服务、API、静态页面、浏览器测试和 Playwright 可选依赖，
以及固定参考验证器的窗口、表单、专用绘图和相应界面测试。

`vdi2230` / `python -m vdi2230` 是唯一应用入口。
不再提供 `vdi2230-web`、`python -m vdi2230.web` 或 `--reference`；
通用窗口也不再包含参考算例按钮。
`--version` 输出 0.0.1。重新安装可编辑包以清除旧 console script，
已经运行的旧进程必须关闭或重启，不能认为切换分支会热更新它。

按用户确认，**保留 B1–B5 的内部数值回归及必要计算数据**。
这些固定输入计算器不是产品模式，不能用其偏心或多螺栓测试覆盖扩大通用模型范围。
通用计算公式、输入格式、数据库工程值及既有 Tk 交互不因界面裁剪而改变。

## 2. 技术栈及实际模块

| 层次 | 实现 | 职责 |
|---|---|---|
| 入口 | `__main__.py` | 参数解析、版本、创建 Tk 根窗口 |
| 窗口 | `ui/general_window.py` | ttk 表单、Canvas、结果/报告、错误与定时任务 |
| 表单状态 | `ui/general_model.py` | 目录/材料填充、覆盖、板层、来源、输入快照、Outcome |
| 输入 | `domain/general_inputs.py` | 字段 schema、不可变输入对象、默认值及校验 |
| 计算 | `calculations/general.py` | 通用计算编排、指标、逐项校核及总体判定 |
| 数据 | `data/` | 版本化螺栓、材料、表格数据与许可证 |
| 图元 | `infrastructure/general_section.py` | 与窗口无关的 Shape 几何和部件角色 |
| 报告 | `infrastructure/general_report.py` | 来自同一次计算的 UTF-8 TXT |
| 翻译 | `i18n.py` | 离线消息、完整模板和来源标签 |
| 内部回归 | `calculations/b1.py` … `b5.py` | 固定标准输入下的独立重新计算 |
| 共享基础 | `domain/models.py`、`validation.py` | 结果、状态、来源和误差判据 |

`infrastructure/report.py`、`project_file.py` 及 `ProjectSnapshot` 保留为内部
结果审计/序列化测试的基础工具，不代表通用 Tk 已具备项目保存或载入功能。
旧固定剖面模块 `domain/section.py` 和旧 UI 适配层已删除，当前绘图只走通用 Shape。

依赖方向：

```text
__main__ → GeneralWindow → GeneralFormModel
                              ├→ parse_general_input → calculate_general
                              └→ render_general_report
             └→ general_section_shapes → canvas_item → Tk Canvas

tests → 同一通用模型 / 报告 / 图元 / Tk 控件
tests/test_reference_cases.py → 内部固定标准算例计算器
```

计算层不能依赖 Tk、文件对话框或界面事件。图形消费输入和计算指标，
不能反向影响工程结果。运行时与测试使用标准库；构建由 pyproject 声明的 setuptools 执行。

## 3. 状态、计算和来源

### 3.1 单一输入路径

`GeneralFormModel.to_input_json()` 生成 `vdi2230.general/3` 输入和 provenance，
经 `parse_general_input()` 校验后交给 `calculate_general()`。
结果封装为 `GeneralCalculationResult`，包含输入、metrics、checks、
原始计算结果、警告及来源。`Outcome` 只表示有效结果或明确错误，不返回伪成功。

几何字段与材料分别归属于螺栓、板层、垫片或内螺纹件。
μG/μK 均归螺栓且独立；板层使用 μT。程序计算值不因显示舍入而改变。
应用版本 0.0.1、工程输入 schema 3 和各数据库版本独立管理。

### 3.2 自动计算与过期状态

1. 输入更新模型，立即禁用报告导出，取消并重设约 300 ms 的计算定时器。
2. 有效输入生成结果/报告；窗口据同一次结果更新剖面、数值和判定。
3. `InputValidationError` 转为本地化字段错误；明确的数值/定义域拒绝转为错误 Outcome。
4. 失败清空结果/报告、禁用导出，缓存的最后有效几何显示过期标记。
5. 参数修正后恢复计算；不自动修改螺栓长度或绕过旋合校验。
6. 关闭窗口取消剩余计算/绘图任务并销毁窗口。

英文动态模板按固定文本长度降序匹配，避免短模板吞入更具体提示的后缀。
未登记的应用文案仍显式报错，不用宽泛异常捕获隐藏缺失译文。

### 3.3 数据与总体判定

随附 JSON 记录状态为 `accepted_baseline`，派生规格传递此状态。
保持来源、版本、原始差异及许可证，不改变工程值或宣称独立认证。
字段来源使用目录、强度等级、材料、表格或用户标识；手动修改清除原自动来源。
长度变化只更新仍属于目录的值，用户覆盖不被重置。

总体优先级：适用校核失败 → 不通过；否则有待确认项/来源 → 需确认；
其余满足当前判据时 → 通过。不适用项目单独显示。
经验垫片尺寸、未知目录记录和模型假设不因随附数据采信而免于提示。
内部 `provisional_sources` 等名称继续用于这些未采信来源，不等同于数据库记录仍为 provisional。

## 4. 垫片、图元与双语

### 4.1 普通平垫片

`head_washer` / `nut_washer` 独立于板层，默认关闭，ESV 保留但不用螺母侧设置。
经验系数为 1.1 / 2 / 0.16；仅自动估计字段随公称直径更新。

厚度计入 lK、螺栓柔度、旋合与剪切面；板层变形锥使用板层总厚。
环形柔度按 `Deff = min(dW, Do, DA)`、`di,eff = max(di, dh, dha)` 计算，
与板层柔度串联，不假设全外径载荷扩散。分别校核垫片两面和邻接板，
Sp,K / Sp,M 使用最小值。嵌入界面和手动覆盖按既有规则处理。
拧紧扭矩假设垫片静止；弯曲和真实载荷分布仍为待确认模型限制。

### 4.2 Canvas 绘图与选择

Shape 保存坐标、线型、填色、文字及 role，`section_target(role)` 产生目标字段，
`canvas_item()` 转成 Canvas 图元及 `target:<path>` 标签。
部件命中不应被轴线或压缩锥遮挡；点击定位输入标签页、字段及选中板。

倒角、面弧线、螺纹线和尺寸箭头用基础图元表达，不增加绘图依赖。
透明度小于 1 的多边形在 Tk 中映射为空填充/虚线，压缩锥不遮住板层。
主题为标准库 clam 的深蓝、青色、紫色组合；颜色和窗口尺寸不参与计算。

### 4.3 双语状态

新窗口默认英文，报告跟随窗口语言。翻译只影响展示，
数值、坐标、状态、来源和输入 schema 不变。
生成名称标记存于 UI 状态而非工程输入：用户编辑/载入的名称不自动翻译。
板名标记随板移动；新增板使用当前语言并避开中英文默认编号冲突。

切换保留原始文本、覆盖值、选中板、标签页及筛选。
失败时可用缓存的有效结果和名称信息重新绘制另一语言的旧图，
但仍保留过期标识、空报告及禁用导出。
不使用网络翻译或对整份报告作字符串替换。

## 5. 测试保留及迁移

所有测试统一使用：

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

安装后可省略 `PYTHONPATH`。VS Code 任务为 **VDI 2230: Tk UI**
和 **VDI 2230: All tests**。

| 测试组 | 验证内容 |
|---|---|
| `test_bolt_catalog`、`test_engineering_data` | 随附值、来源、采信及未知来源 |
| `test_general_inputs`、`test_general_engine` | 输入边界、公式、状态和通用模型标准参数回归 |
| `test_general_washers` | 几何、串联柔度、面压、力矩、ESV 及 Canvas 点击目标 |
| `test_general_section`、`test_general_report` | 图元、尺寸、范围、来源、报告及判定 |
| `test_i18n` | 双语全部数值/校核/坐标一致、完整模板、自由文本、独立模型语言隔离 |
| `test_general_desktop_model` | 目录填充/覆盖、增删移、输入快照、双语 DSV/ESV 错误矩阵 |
| `test_general_desktop_window` | 真实 Tk 控件、定时回调、重绘、部件点击、导出、主题、唯一入口 |
| `test_release_structure` | 包含的 UI 模块、版本/入口、无旧界面、模型不依赖 Tk/HTTP |
| `test_reference_cases`、`test_domain_foundation` | 内部标准算例、误差/来源/状态、序列化和审计报告 |

删除的是 HTTP 传输、DOM、浏览器时序及已删除参考 UI 的专属测试。
原 API 测试中的垫片错误、双语计算/报告/图元及输入错误矩阵已转为直接验证
`GeneralFormModel` / 通用图元，不能仅因移除 Web 就丢失工程行为覆盖。
Tk 修改厚度导致短螺栓、非法参数恢复和英文模板回调回归仍保留。

### 5.1 内部 B1–B5 回归门槛

固定算例计算器保留原始输入与公式来源。所有有明确参考值的数值仍按既有
3% 相对误差门槛验证；零参考值使用显式绝对比较。
12 项安全系数必须分别断言，不能仅检查总最大误差：

| 算例 | 逐项安全系数 |
|---|---|
| B1 | SF、Sp |
| B2 | SG |
| B3 | Sp、SG |
| B4 | SD、SpK、SpMu、SG |
| B5 | SF、SD、Sp |

同时保留 B1 未解决附加柔度矛盾及“需确认/不完整”状态，禁止为达标反向拟合。
通用模型保留 B1–B3 同口径输入回归；B3 μG = 0.12、μK = 0.10，
MA = 521.135 N·m。内部回归通过不等同于数据库认证或通用模型支持偏心/螺栓组。

### 5.2 显示环境

无显示或 Tk 不可用时，实际窗口测试明确跳过。发布验收必须在有显示的机器运行，
记录跳过项；不能将“仅核心测试通过”称作桌面 UI 验证完成。
macOS 的结果不替代 Windows 上的窗口、文件对话框和字体布局验证。

## 6. 构建、安装与发布检查

```sh
python -m pip wheel --no-deps --wheel-dir dist .
python -m pip install -e .
vdi2230 --version
python -m unittest discover -s tests -v
```

pip 的隔离构建安装 pyproject 声明的构建依赖；运行时仍无第三方依赖。
若使用 `--no-build-isolation`，调用者必须先准备 setuptools 构建环境。
包发现关闭 namespace 扫描，避免把无包定义的残留目录作为发布模块。

发布时核对：

1. 包元数据、`__version__`、CLI 和报告版本一致。
2. console script 仅 `vdi2230`；没有 Web/固定参考 UI 模块或静态页面。
3. 三份工程 JSON、来源说明、许可证及内部回归计算器完整保留。
4. 从 wheel 独立加载/计算/生成报告，避免可编辑源码掩盖缺失资源。
5. 所有适用测试通过，逐项安全系数不超过误差门槛；明确披露平台/显示限制。
6. 核对 diff、清理临时构建物并创建可回滚提交，不修改主分支的既有版本。

wheel 是 Python 包，不是独立 macOS/Windows 应用。原生安装包、签名/公证和
Windows 实机验收属于后续分发工作；不得将一次 wheel 构建等同于这些项目已完成。
