"use strict";

const byId = (id) => document.getElementById(id);
const selector = byId("case-select");
const calculateButton = byId("calculate");
const exportButton = byId("export");
const svgNamespace = "http://www.w3.org/2000/svg";
let currentCase = null;
let currentResult = null;
let revision = 0;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function number(value) {
  if (value === null || value === undefined) return "未计算";
  if (typeof value !== "number") return String(value);
  return Number(value.toPrecision(7)).toString();
}

function errorText(value) {
  if (value.reference_value === 0) {
    const absolute = value.absolute_error ?? (typeof value.value === "number" ? Math.abs(value.value) : null);
    return absolute === null ? "未计算" : `绝对 ${number(absolute)}`;
  }
  return value.relative_error_percent === null ? "—" : `${value.relative_error_percent.toFixed(3)}%`;
}

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return response.json();
}

function showError(error) {
  byId("error").textContent = `操作失败：${error.message}`;
  byId("error").hidden = false;
  byId("status").textContent = "操作失败";
  byId("status").dataset.state = "review";
}

function resetResults() {
  currentResult = null;
  byId("result-panel").setAttribute("aria-busy", "false");
  exportButton.disabled = true;
  byId("error").hidden = true;
  byId("status").dataset.state = "";
  byId("result-summary").textContent = "尚未计算；点击“计算”重新验证当前实例。";
  byId("safety-table").tBodies[0].replaceChildren();
  byId("results-table").tBodies[0].replaceChildren();
  byId("warnings").replaceChildren();
  byId("result-details").replaceChildren();
  byId("result-details").hidden = true;
  byId("report-preview").textContent = "";
}

function drawSection(data) {
  const svg = byId("section");
  svg.replaceChildren();
  for (const primitive of data.section) {
    const [x1, y1, x2, y2] = primitive.coordinates;
    const tag = { rectangle: "rect", line: "line", text: "text" }[primitive.kind];
    if (!tag) throw new Error(`未知剖面图元：${primitive.kind}`);
    const element = document.createElementNS(svgNamespace, tag);
    const attributes = tag === "rect"
      ? { x: x1, y: y1, width: x2 - x1, height: y2 - y1 }
      : tag === "line" ? { x1, y1, x2, y2 } : { x: x1, y: y1 };
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    element.setAttribute("fill", primitive.fill || (tag === "text" ? "#34495e" : "none"));
    if (primitive.outline) element.setAttribute("stroke", primitive.outline);
    if (tag === "text") {
      element.textContent = primitive.text;
      element.setAttribute("dominant-baseline", "middle");
    }
    svg.append(element);
  }
  const geometry = data.geometry;
  const metrics = [
    ["螺杆直径 / 长度", `${number(geometry.shank_diameter_mm)} / ${number(geometry.shank_length_mm)} mm`],
    ["板层厚度", `${geometry.clamp_layer_thicknesses_mm.map(number).join(" + ")} mm`],
    ["螺栓数量", String(geometry.bolt_count)],
    ["载荷偏心距", `${number(geometry.load_offset_mm)} mm`],
  ];
  if (geometry.hollow_diameter_mm) metrics.push(["空心内径", `${number(geometry.hollow_diameter_mm)} mm`]);
  if (geometry.neck_diameter_mm) metrics.push(["缩颈直径", `${number(geometry.neck_diameter_mm)} mm`]);
  byId("geometry").replaceChildren(...metrics.map(([label, value]) => {
    const item = node("div");
    item.append(node("dt", label), node("dd", value));
    return item;
  }));
}

function showDetails(value) {
  const detail = byId("result-details");
  detail.replaceChildren(
    node("h3", `${value.symbol} · ${value.label}`),
    node("p", `计算值：${number(value.value)} ${value.unit}；PDF：${number(value.reference_value)}；误差：${errorText(value)}`),
    node("p", `状态：${value.status}`),
    node("p", `依据：${value.formula_reference}`),
  );
  if (value.note) detail.append(node("p", `说明：${value.note}`));
  detail.hidden = false;
}

function resultRow(value, safety) {
  const row = node("tr");
  row.dataset.symbol = value.symbol;
  const first = node("td");
  const button = node("button", value.symbol, "symbol-button");
  button.type = "button";
  button.setAttribute("aria-label", `查看 ${value.symbol} 计算依据`);
  button.addEventListener("click", () => showDetails(value));
  first.append(button, node("span", safety ? value.label : value.unit, "factor-label"));
  row.append(first);
  const cells = safety
    ? [number(value.reference_value), number(value.value), errorText(value)]
    : [number(value.value), number(value.reference_value), errorText(value), value.status];
  for (const text of cells) row.append(node("td", text));
  if (safety && value.relative_error_percent !== null && value.relative_error_percent <= 3) {
    row.lastElementChild.className = "within-tolerance";
  }
  return row;
}

async function loadCase() {
  const token = ++revision;
  currentCase = null;
  resetResults();
  calculateButton.disabled = true;
  byId("status").textContent = "正在加载…";
  byId("inputs").replaceChildren();
  byId("section").replaceChildren();
  byId("geometry").replaceChildren();
  byId("case-title").textContent = "";
  try {
    const data = await request(`/api/cases/${encodeURIComponent(selector.value)}`);
    if (token !== revision) return;
    for (const field of data.fields) {
      const wrapper = node("div", undefined, "input-field");
      const label = node("label", field.key);
      const id = `input-${field.key}`;
      label.htmlFor = id;
      label.append(node("span", field.unit));
      const input = node("input");
      input.id = id;
      input.value = field.default_value;
      input.readOnly = true;
      const source = node("details");
      source.append(node("summary", field.label), node("p", field.source, "muted"));
      wrapper.append(label, input, source);
      byId("inputs").append(wrapper);
    }
    drawSection(data);
    byId("case-title").textContent = data.title;
    currentCase = data;
    byId("status").textContent = "尚未计算";
    calculateButton.disabled = false;
  } catch (error) {
    if (token === revision) showError(error);
  }
}

async function calculate() {
  if (!currentCase) return;
  const token = ++revision;
  const caseData = currentCase;
  resetResults();
  calculateButton.disabled = true;
  byId("status").textContent = "正在计算…";
  byId("result-panel").setAttribute("aria-busy", "true");
  try {
    const result = await request(`/api/cases/${caseData.case_id}/calculate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputs: caseData.inputs }),
    });
    if (token !== revision) return;
    currentResult = result;
    byId("status").textContent = `计算状态：${result.overall_status}`;
    byId("status").dataset.state = result.overall_status === "通过" ? "pass" : "review";
    byId("result-summary").textContent = `${result.case_id} · ${result.values.length} 个记录项 · 计算${result.is_fully_calculated ? "完整" : "不完整，存在需确认项"}。以下分别列出安全系数误差。`;
    byId("safety-table").tBodies[0].replaceChildren(...result.safety_factors.map((value) => resultRow(value, true)));
    byId("results-table").tBodies[0].replaceChildren(...result.values.map((value) => resultRow(value, false)));
    byId("warnings").replaceChildren(...result.warnings.map((warning) => node("p", warning)));
    byId("report-preview").textContent = result.report;
    exportButton.disabled = false;
  } catch (error) {
    if (token === revision) showError(error);
  } finally {
    if (token === revision) {
      calculateButton.disabled = false;
      byId("result-panel").setAttribute("aria-busy", "false");
    }
  }
}

selector.addEventListener("change", loadCase);
calculateButton.addEventListener("click", calculate);
exportButton.addEventListener("click", () => {
  if (!currentResult) return;
  const url = URL.createObjectURL(new Blob([currentResult.report], { type: "text/plain;charset=utf-8" }));
  const link = node("a");
  link.href = url;
  link.download = `VDI2230-${currentResult.case_id}.txt`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function initialize() {
  try {
    const cases = await request("/api/cases");
    if (!cases.length) throw new Error("没有可用参考算例。");
    selector.replaceChildren(...cases.map((item) => {
      const option = node("option", item.title);
      option.value = item.case_id;
      return option;
    }));
    selector.disabled = false;
    await loadCase();
  } catch (error) {
    showError(error);
  }
}

initialize();
