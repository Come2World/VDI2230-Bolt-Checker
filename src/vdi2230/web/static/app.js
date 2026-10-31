"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const CATALOG_PATHS = new Set(["bolt.catalog_variant_id", "bolt.property_class"]);
const BOLT_MATERIAL = new Set([
  "bolt.youngs_modulus", "bolt.yield_strength", "bolt.tensile_strength", "bolt.tensile_strength_max",
  "bolt.shear_ratio", "bolt.rolling", "bolt.thread_friction", "bolt.bearing_friction",
]);
const MATERIAL_FIELDS = {
  plates: ["youngs_modulus", "limiting_surface_pressure"],
  tapped: ["youngs_modulus", "tensile_strength", "shear_strength"],
  head_washer: ["youngs_modulus", "limiting_surface_pressure"],
  nut_washer: ["youngs_modulus", "limiting_surface_pressure"],
};
const COLLAPSED = new Set(["高级选项", "头侧垫片", "螺母侧垫片（DSV）"]);
const KEY_METRICS = [
  ["lK", "lK"], ["Φn", "Φn"], ["FMzul", "FMzul"], ["FSmax", "FS,max"], ["FKRmin", "FKR,min"], ["MA", "MA"],
];
const GROUP_TABS = { bolt: "bolt", plates: "plates", load: "load", assembly: "assembly" };

const state = {
  schema: null,
  catalog: null,
  specs: new Map(),
  layerSpecs: new Map(),
  values: {},
  prov: {},
  layers: [],
  defaultTitle: false,
  selected: 0,
  result: null,
  section: null,
  fieldErrors: [],
  provisional: new Set(),
  seq: 0,
  catalogSeq: 0,
  timer: null,
  lastView: null,
};

/* ---------- helpers ---------- */

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === false || value === null || value === undefined) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  node.append(...children);
  return node;
}

function svgEl(tag, attrs) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== null && value !== undefined) node.setAttribute(key, String(value));
  }
  return node;
}

function fieldId(path) {
  return `f-${path.replace(/[.[\]]+/g, "-").replace(/-$/, "")}`;
}

function fmt(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value !== "number") return String(value);
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude < 1e-3 || magnitude >= 1e9) return value.toExponential(3);
  if (magnitude >= 1000) return String(Math.round(value));
  return String(Number(value.toPrecision(4)));
}

async function getJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) throw new Error(t(data.error || `请求失败（${response.status}）`));
  return data;
}

function setStatus(text) {
  $("#status").textContent = t(text);
}

/* ---------- form fields ---------- */

function readControl(spec, control) {
  if (control.type === "checkbox") return control.checked;
  const raw = control.value.trim();
  if (control.tagName === "SELECT" || spec.kind === "text") return raw === "" ? null : raw;
  if (raw === "") return null;
  const number = Number(raw.replace(",", "."));
  return Number.isFinite(number) ? number : raw;
}

function writeControl(control, value) {
  if (control.type === "checkbox") control.checked = Boolean(value);
  else control.value = value === null || value === undefined ? "" : String(value);
}

function fieldRow(spec, path, value, onChange, options) {
  const id = fieldId(path);
  const row = el("div", { class: "field", "data-path": path });
  const label = el("label", { for: id, title: [spec.label, spec.help].filter(Boolean).map(t).join(" — ") }, t(spec.label));
  if (spec.unit) label.append(el("span", { class: "unit" }, spec.unit));
  let control;
  if (options || spec.kind === "choice") {
    control = el("select", { id });
    for (const [optionValue, text] of options || spec.choices) control.append(el("option", { value: optionValue }, t(text)));
  } else if (spec.kind === "bool") {
    control = el("input", { id, type: "checkbox" });
  } else {
    control = el("input", { id, type: "text", autocomplete: "off", spellcheck: "false" });
    if (spec.kind !== "text") control.inputMode = "decimal";
    if (spec.optional && spec.help) control.placeholder = t(spec.help).split(/[；;]/)[0];
  }
  writeControl(control, value);
  const event = control.tagName === "SELECT" || control.type === "checkbox" ? "change" : "input";
  control.addEventListener(event, () => onChange(readControl(spec, control)));
  row.append(label, control, el("span", { class: "src" }));
  return row;
}

function sourceFor(path) {
  const layer = /^plates\[(\d+)]\.(\w+)$/.exec(path);
  if (layer) return state.layers[Number(layer[1])]?.prov[layer[2]];
  return state.prov[path];
}

function updateSource(path) {
  const row = $(`.field[data-path="${CSS.escape(path)}"]`);
  if (!row) return;
  const marker = $(".src", row);
  const source = sourceFor(path);
  marker.className = "src";
  marker.removeAttribute("title");
  if (source && source !== "user") {
    const provisional = state.provisional.has(path) || source.startsWith("default:");
    marker.classList.add(provisional ? "provisional" : "catalog");
    const shown = source.startsWith("default:") ? t(source) : source;
    marker.title = provisional ? tf("{source}（数据待核验）", { source: shown }) : shown;
  }
}

function syncControl(path) {
  const control = document.getElementById(fieldId(path));
  if (control) writeControl(control, state.values[path]);
  updateSource(path);
}

function materialOptions() {
  return [["", "自定义"], ...state.catalog.materials.map((m) => [m.material_id, `${m.material_id} · ${m.name}`])];
}

function materialRecord(id) {
  return state.catalog.materials.find((m) => m.material_id === id);
}

function subsectionOf(spec) {
  const section = spec.path.split(".")[0];
  if (spec.group === "bolt") {
    if (section === "joint") return "连接与目录";
    if (section === "bolt") return BOLT_MATERIAL.has(spec.path) ? "螺栓材料与摩擦" : "螺栓几何";
    return section === "nut" ? "螺母（DSV）" : "内螺纹件（ESV）";
  }
  if (spec.group === "plates") return { head_washer: "头侧垫片", nut_washer: "螺母侧垫片（DSV）" }[section] || "孔与外径";
  if (spec.group === "load") return section === "load_introduction" ? "载荷导入系数 n" : "外载荷";
  return { assembly: "拧紧", embedding: "嵌入", advanced: "高级选项", requirements: "安全系数要求" }[section] || section;
}

function renderForm() {
  const containers = {
    bolt: $("#panel-bolt"), plates: $("#plates-fields"), load: $("#panel-load"), assembly: $("#panel-assembly"),
  };
  const sections = new Map();
  for (const spec of state.schema.fields) {
    if (CATALOG_PATHS.has(spec.path)) continue;
    const title = subsectionOf(spec);
    const key = `${spec.group}|${title}`;
    if (!sections.has(key)) {
      const details = el("details", { class: "group", "data-section": key, open: !COLLAPSED.has(title) }, el("summary", {}, t(title)));
      containers[spec.group].append(details);
      sections.set(key, details);
    }
    let row;
    if (spec.path.endsWith(".material_id")) {
      row = fieldRow(spec, spec.path, state.values[spec.path], (value) => onPartMaterial(spec.path.split(".")[0], value), materialOptions());
    } else {
      row = fieldRow(spec, spec.path, state.values[spec.path], (value) => onFieldChange(spec.path, value));
    }
    sections.get(key).append(row);
    if (spec.path === "joint.type") sections.get(key).append(...catalogRows());
  }
  const lengths = el("datalist", { id: "bolt-lengths" });
  for (const length of state.catalog.lengths) lengths.append(el("option", { value: length }));
  document.body.append(lengths);
  document.getElementById(fieldId("bolt.length"))?.setAttribute("list", "bolt-lengths");
  for (const path of Object.keys(state.prov)) updateSource(path);
}

function catalogRows() {
  const variantSpec = state.specs.get("bolt.catalog_variant_id");
  const classSpec = state.specs.get("bolt.property_class");
  const variantRow = fieldRow(variantSpec, variantSpec.path, null, (value) => {
    state.values["bolt.catalog_variant_id"] = value;
    loadCatalog(true);
  }, [["", "自定义（手动输入）"]]);
  const select = $("select", variantRow);
  const groups = new Map();
  for (const bolt of state.catalog.bolts) {
    if (!groups.has(bolt.standard)) {
      groups.set(bolt.standard, el("optgroup", { label: bolt.standard }));
      select.append(groups.get(bolt.standard));
    }
    groups.get(bolt.standard).append(el("option", { value: bolt.variant_id }, bolt.label));
  }
  select.value = state.values["bolt.catalog_variant_id"] ?? "";
  const classRow = fieldRow(classSpec, classSpec.path, state.values["bolt.property_class"] ?? "", (value) => {
    state.values["bolt.property_class"] = value;
    loadCatalog(true);
  }, [["", "—"], ...state.catalog.property_classes.map((value) => [value, value])]);
  return [variantRow, classRow];
}

function relevant(path) {
  const values = state.values;
  if (path.startsWith("nut.") || path.startsWith("nut_washer.")) return values["joint.type"] === "DSV";
  if (path.startsWith("tapped.")) return values["joint.type"] === "ESV";
  if (path === "load_introduction.n") return values["load_introduction.mode"] === "manual";
  if (["load_introduction.joint_class", "load_introduction.la_over_h", "load_introduction.ak_over_h"].includes(path)) {
    return values["load_introduction.mode"] === "table";
  }
  if (path === "embedding.fz_um") return values["embedding.mode"] === "manual";
  if (path === "embedding.interface_count") return values["embedding.mode"] === "table";
  return true;
}

function applyVisibility() {
  for (const row of $$(".tabpanel .field[data-path]")) {
    if (!row.dataset.path.startsWith("plates[")) row.hidden = !relevant(row.dataset.path);
  }
  for (const group of $$("details.group")) {
    group.hidden = $$(".field", group).every((row) => row.hidden);
  }
}

function invalidateResult() {
  ++state.seq;
  $("#export").disabled = true;
}

function scheduleCalculation(delay = 250) {
  invalidateResult();
  clearTimeout(state.timer);
  state.timer = setTimeout(calculate, delay);
}

function onFieldChange(path, value) {
  state.values[path] = value;
  delete state.prov[path];
  updateSource(path);
  if (path === "joint.type" || path.endsWith(".mode")) applyVisibility();
  if (path === "bolt.d") refreshWasherEstimates();
  if (path === "bolt.length" && state.values["bolt.catalog_variant_id"]) {
    loadCatalog(false);
    return;
  }
  scheduleCalculation();
}

function onPartMaterial(section, id) {
  state.values[`${section}.material_id`] = id;
  const record = materialRecord(id);
  if (record) {
    for (const name of MATERIAL_FIELDS[section]) {
      const path = `${section}.${name}`;
      state.values[path] = record[name];
      state.prov[path] = `material:${id}`;
      syncControl(path);
    }
  }
  scheduleCalculation();
}

function refreshWasherEstimates() {
  const diameter = state.values["bolt.d"];
  if (typeof diameter !== "number" || !Number.isFinite(diameter) || diameter <= 0) return;
  for (const spec of state.schema.fields) {
    if (spec.diameter_factor !== null && state.prov[spec.path] === state.schema.washer_estimate_source) {
      state.values[spec.path] = Number((diameter * spec.diameter_factor).toFixed(6));
      syncControl(spec.path);
    }
  }
}

async function loadCatalog(force) {
  const variant = state.values["bolt.catalog_variant_id"];
  const propertyClass = state.values["bolt.property_class"];
  const length = state.values["bolt.length"];
  if (!variant || !propertyClass || typeof length !== "number" || !(length > 0)) {
    scheduleCalculation();
    return;
  }
  const seq = ++state.catalogSeq;
  invalidateResult();
  try {
    const params = new URLSearchParams({ variant, length: String(length), class: propertyClass });
    const data = await getJson(`/api/general/catalog-values?${params}`);
    if (seq !== state.catalogSeq) return;
    for (const [path, value] of Object.entries(data.values)) {
      const source = data.sources[path];
      if (!force && (!source || state.prov[path] !== source)) continue;
      state.values[path] = value;
      if (source) state.prov[path] = source;
      syncControl(path);
    }
    refreshWasherEstimates();
    applyVisibility();
  } catch (error) {
    if (seq !== state.catalogSeq) return;
    showError(error.message, []);
  }
  scheduleCalculation(0);
}

/* ---------- layers ---------- */

function layerName(index) {
  return state.layers[index]?.values.name || t(`板层 ${index + 1}`);
}

function layerSummary(layer, index) {
  const v = layer.values;
  return `${index + 1}. ${v.name || t("（未命名）")} · ${v.material_id || t("自定义")} · h ${fmt(v.thickness)}`;
}

function actionButton(text, label, disabled, handler) {
  const button = el("button", { type: "button", "aria-label": t(label), title: t(label), disabled }, text);
  button.addEventListener("click", handler);
  return button;
}

function renderLayers() {
  const list = $("#layers");
  list.replaceChildren();
  const last = state.layers.length - 1;
  state.layers.forEach((layer, index) => {
    const selected = index === state.selected;
    const item = el("li", { class: `layer${selected ? " selected" : ""}`, "data-index": index });
    const pick = el("button", {
      type: "button", class: "layer-select", "aria-expanded": String(selected), "aria-label": t(`编辑板层 ${index + 1}`),
    }, layerSummary(layer, index));
    pick.addEventListener("click", () => selectLayer(index));
    const actions = el("span", { class: "layer-actions" },
      actionButton("↑", `上移板层 ${index + 1}`, index === 0, () => moveLayer(index, -1)),
      actionButton("↓", `下移板层 ${index + 1}`, index === last, () => moveLayer(index, 1)),
      actionButton("✕", `删除板层 ${index + 1}`, state.layers.length === 1, () => removeLayer(index)),
    );
    item.append(el("div", { class: "layer-summary" }, pick, actions));
    if (selected) item.append(layerFields(layer, index, pick));
    list.append(item);
  });
  const full = state.layers.length >= state.schema.max_layers;
  $("#layer-count").textContent = `${state.layers.length} / ${state.schema.max_layers}`;
  $("#add-layer").disabled = full;
  $("#section-add-layer").disabled = full;
  $("#section-remove-layer").disabled = state.layers.length <= 1;
  $("#selected-layer").textContent = tf("选中：{name}", { name: `${state.selected + 1}. ${layerName(state.selected)}` });
  markErrors();
}

function layerFields(layer, index, pick) {
  const box = el("div", { class: "layer-fields" });
  for (const spec of state.schema.layer_fields) {
    const path = `plates[${index}].${spec.path}`;
    const onChange = (value) => {
      layer.values[spec.path] = value;
      delete layer.prov[spec.path];
      if (spec.path === "name") layer.defaultName = null;
      if (spec.path === "material_id") applyLayerMaterial(layer, index, value);
      updateSource(path);
      pick.textContent = layerSummary(layer, index);
      $("#selected-layer").textContent = tf("选中：{name}", { name: `${index + 1}. ${layerName(index)}` });
      scheduleCalculation();
    };
    const options = spec.path === "material_id" ? materialOptions() : undefined;
    box.append(fieldRow(spec, path, layer.values[spec.path], onChange, options));
  }
  queueMicrotask(() => state.schema.layer_fields.forEach((spec) => updateSource(`plates[${index}].${spec.path}`)));
  return box;
}

function applyLayerMaterial(layer, index, id) {
  const record = materialRecord(id);
  if (!record) return;
  for (const name of MATERIAL_FIELDS.plates) {
    layer.values[name] = record[name];
    layer.prov[name] = `material:${id}`;
    const control = document.getElementById(fieldId(`plates[${index}].${name}`));
    if (control) writeControl(control, record[name]);
    updateSource(`plates[${index}].${name}`);
  }
}

function uniqueLayerName() {
  const names = new Set(state.layers.map((layer) => layer.values.name));
  let number = state.layers.length + 1;
  while (["zh", "en"].some((language) => names.has(translateText(`板 ${number}`, language)))) number += 1;
  return `板 ${number}`;
}

function addLayer() {
  if (state.layers.length >= state.schema.max_layers) return;
  const base = state.layers[state.selected] || state.layers[state.layers.length - 1];
  const defaultName = uniqueLayerName();
  const layer = { values: { ...base.values, name: t(defaultName) }, prov: { ...base.prov }, defaultName };
  state.layers.splice(state.selected + 1, 0, layer);
  state.selected += 1;
  renderLayers();
  highlightSection();
  scheduleCalculation(0);
}

function removeLayer(index) {
  if (state.layers.length <= 1) return;
  state.layers.splice(index, 1);
  if (state.selected > index || state.selected >= state.layers.length) state.selected -= 1;
  renderLayers();
  scheduleCalculation(0);
}

function moveLayer(index, direction) {
  const target = index + direction;
  if (target < 0 || target >= state.layers.length) return;
  [state.layers[index], state.layers[target]] = [state.layers[target], state.layers[index]];
  state.selected = target;
  renderLayers();
  scheduleCalculation(0);
}

function selectLayer(index, reveal = false) {
  state.selected = index;
  renderLayers();
  highlightSection();
  if (reveal) {
    showInputTab("plates");
    $(`#layers .layer[data-index="${index}"]`)?.scrollIntoView({ block: "nearest" });
  }
}

/* ---------- tabs ---------- */

function setupTabs(tablist) {
  const tabs = $$('[role="tab"]', tablist);
  const activate = (tab, focus = false) => {
    for (const item of tabs) {
      const on = item === tab;
      item.setAttribute("aria-selected", String(on));
      item.tabIndex = on ? 0 : -1;
      document.getElementById(item.getAttribute("aria-controls")).hidden = !on;
    }
    if (focus) tab.focus();
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tab));
    tab.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (!step) return;
      event.preventDefault();
      activate(tabs[(index + step + tabs.length) % tabs.length], true);
    });
  });
  return (name) => activate(tabs.find((tab) => tab.dataset.tab === name || tab.dataset.rtab === name));
}

let showInputTab = () => {};

/* ---------- calculation ---------- */

function buildInput() {
  const input = { schema: state.schema.schema, title: $("#project-title").value.trim() || t("通用螺栓连接") };
  for (const spec of state.schema.fields) {
    const [section, name] = spec.path.split(".");
    (input[section] ??= {})[name] = state.values[spec.path] ?? null;
  }
  input.plates = state.layers.map((layer) => ({ ...layer.values }));
  const provenance = { ...state.prov };
  state.layers.forEach((layer, index) => {
    for (const [name, source] of Object.entries(layer.prov)) provenance[`plates[${index}].${name}`] = source;
  });
  input.provenance = provenance;
  return input;
}

function viewSize() {
  const wrap = $("#section-wrap");
  const clamp = (value, fallback) => Math.round(Math.min(Math.max(value || fallback, 200), 2000));
  return { width: clamp(wrap.clientWidth, 640), height: clamp(wrap.clientHeight, 520) };
}

async function calculate() {
  const seq = ++state.seq;
  const view = viewSize();
  state.lastView = view;
  setStatus("计算中…");
  let response;
  let data;
  const input = buildInput();
  const names = state.layers.map((layer) => layer.defaultName);
  try {
    response = await fetch("/api/general/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input, view, language: i18n.language }),
    });
    data = await response.json();
  } catch {
    if (seq === state.seq) fail("无法连接本地计算服务。", []);
    return;
  }
  if (seq !== state.seq) return;
  if (!response.ok) {
    fail(data.error || `计算失败（${response.status}）`, data.field_errors || []);
    return;
  }
  for (const shape of data.section.shapes) {
    const match = /^plate-(\d+)$/.exec(shape.role);
    const source = match && names[Number(match[1])];
    if (shape.kind !== "text" || !source) continue;
    const name = input.plates[Number(match[1])].name;
    for (const [language, text] of Object.entries(shape.text_by_language)) {
      if (text === name || text.startsWith(`${name} · `)) {
        shape.text_by_language[language] = translateText(source, language) + text.slice(name.length);
      }
    }
  }
  render(data);
}

function clearResults() {
  state.result = null;
  $("#export").disabled = true;
  $("#checks-table tbody").replaceChildren();
  $("#values-table tbody").replaceChildren();
  $("#report-preview").textContent = "";
  $("#verdict-banner").hidden = true;
  $("#provisional").hidden = true;
  $("#warnings").replaceChildren();
  $("#key-metrics").replaceChildren();
}

function fail(message, fieldErrors) {
  clearResults();
  state.fieldErrors = fieldErrors;
  const verdict = $("#verdict");
  verdict.textContent = t(fieldErrors.length ? "输入有误" : "计算失败");
  verdict.dataset.status = "不通过";
  $("#section").classList.add("stale");
  $("#section-stale").hidden = false;
  showError(message, fieldErrors);
  markErrors();
  setStatus(fieldErrors.length ? "输入有误" : "计算失败");
}

function labelForPath(path) {
  const layer = /^plates\[(\d+)]\.(\w+)$/.exec(path);
  if (layer) return `${t(`板层 ${Number(layer[1]) + 1}`)} · ${t(state.layerSpecs.get(layer[2])?.label || layer[2])}`;
  const spec = state.specs.get(path);
  const prefix = { head_washer: "头侧垫片 · ", nut_washer: "螺母侧垫片 · " }[path.split(".")[0]] || "";
  return (prefix ? t(prefix.slice(0, -3)) + " · " : "") + t(spec?.label || path || "输入");
}

function showError(message, fieldErrors) {
  const box = $("#error");
  box.replaceChildren(el("div", {}, t(message)));
  if (fieldErrors.length) {
    const list = el("ul");
    for (const error of fieldErrors) {
      const jump = el("button", { type: "button" }, labelForPath(error.path));
      jump.addEventListener("click", () => goToField(error.path));
      list.append(el("li", {}, jump, `：${error.message}`));
    }
    box.append(list);
  }
  box.hidden = false;
}

function goToField(path) {
  const layer = /^plates\[(\d+)]/.exec(path);
  if (layer) {
    selectLayer(Number(layer[1]), true);
  } else if (state.specs.has(path)) {
    showInputTab(GROUP_TABS[state.specs.get(path).group]);
  }
  const control = document.getElementById(fieldId(path));
  const group = control?.closest("details");
  if (group) group.open = true;
  control?.scrollIntoView({ block: "nearest" });
  control?.focus({ preventScroll: true });
}

function markErrors() {
  for (const row of $$(".field.invalid")) row.classList.remove("invalid");
  for (const note of $$(".field-error")) note.remove();
  for (const tab of $$(".input-pane [role='tab']")) tab.classList.remove("has-error");
  for (const layer of $$("#layers .layer.invalid")) layer.classList.remove("invalid");
  for (const error of state.fieldErrors) {
    const layer = /^plates\[(\d+)]/.exec(error.path);
    const tab = layer ? "plates" : GROUP_TABS[state.specs.get(error.path)?.group];
    if (tab) $(`#tab-${tab}`).classList.add("has-error");
    if (layer) $(`#layers .layer[data-index="${layer[1]}"]`)?.classList.add("invalid");
    const row = $(`.field[data-path="${CSS.escape(error.path)}"]`);
    if (row) {
      row.classList.add("invalid");
      row.after(el("div", { class: "field-error" }, error.message));
    }
  }
}

function render(data) {
  state.result = data;
  state.fieldErrors = [];
  $("#error").hidden = true;
  markErrors();
  $("#section").classList.remove("stale");
  $("#section-stale").hidden = true;

  const verdict = $("#verdict");
  verdict.textContent = data.verdict_label;
  verdict.dataset.status = data.verdict;
  const banner = $("#verdict-banner");
  banner.dataset.status = data.verdict;
  const failing = data.checks.filter((check) => check.status === "不通过").map((check) => check.symbol);
  banner.replaceChildren(
    `${t("总体判定")}: ${data.verdict_label}`,
    el("small", {}, failing.length
      ? tf("不通过：{symbols}", { symbols: failing.join(", ") })
      : data.provisional_sources.length
        ? t("计算校核均满足要求，但数据或模型假设待核验，结果不得作为最终结论。")
        : t("全部校核满足要求。")),
  );
  banner.hidden = false;

  const checks = $("#checks-table tbody");
  checks.replaceChildren(...data.checks.map((check) => {
    const unit = check.unit ? ` ${check.unit}` : "";
    const label = el("td", {}, el("span", { class: "sym" }, check.symbol), check.label,
      el("span", { class: "note" }, [check.reference, check.note].filter(Boolean).join(" · ")));
    return el("tr", { "data-symbol": check.symbol },
      label,
      el("td", { class: "num" }, check.value === null ? "—" : `${fmt(check.value)}${unit}`),
      el("td", { class: "num" }, check.required === null ? "—" : `≥ ${fmt(check.required)}${unit}`),
      el("td", {}, el("span", { class: "badge", "data-status": check.status }, check.status_label)));
  }));

  state.provisional = new Set(data.provisional_sources.map((entry) => entry.split(" ← ")[0]));
  const provisional = $("#provisional");
  $("#provisional-count").textContent = `(${data.provisional_sources.length})`;
  $("ul", provisional).replaceChildren(...data.provisional_labels.map((entry) => el("li", {}, entry)));
  provisional.hidden = data.provisional_sources.length === 0;
  for (const row of $$(".field[data-path]")) updateSource(row.dataset.path);

  $("#warnings").replaceChildren(...data.warnings.map((warning) => el("li", {}, warning)));

  $("#values-table tbody").replaceChildren(...data.values.map((value) => el("tr", {
    "data-symbol": value.symbol, title: [value.formula_reference, value.note].filter(Boolean).join("\n"),
  },
  el("td", {}, value.symbol),
  el("td", {}, value.label),
  el("td", { class: "num" }, fmt(value.value)),
  el("td", {}, value.unit))));
  filterValues();

  const bySymbol = new Map(data.values.map((value) => [value.symbol, value]));
  $("#key-metrics").replaceChildren(...KEY_METRICS.filter(([symbol]) => bySymbol.has(symbol)).map(([symbol, label]) => {
    const value = bySymbol.get(symbol);
    return el("div", {}, el("dt", {}, label), el("dd", {}, `${fmt(value.value)}${value.unit ? ` ${value.unit}` : ""}`));
  }));

  $("#report-preview").textContent = data.report;
  drawSection(data.section);
  $("#export").disabled = false;
  setStatus(`已计算 · ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`);
}

function filterValues() {
  const query = $("#value-filter").value.trim().toLowerCase();
  for (const row of $$("#values-table tbody tr")) {
    row.hidden = Boolean(query) && !row.textContent.toLowerCase().includes(query);
  }
}

/* ---------- section ---------- */

function svgShape(shape) {
  const p = shape.points;
  let node;
  if (shape.kind === "rect") {
    node = svgEl("rect", {
      x: Math.min(p[0], p[2]), y: Math.min(p[1], p[3]), width: Math.abs(p[2] - p[0]), height: Math.abs(p[3] - p[1]),
    });
  } else if (shape.kind === "polygon") {
    const pairs = [];
    for (let i = 0; i < p.length; i += 2) pairs.push(`${p[i]},${p[i + 1]}`);
    node = svgEl("polygon", { points: pairs.join(" ") });
  } else if (shape.kind === "line") {
    if (p.length === 4) {
      node = svgEl("line", { x1: p[0], y1: p[1], x2: p[2], y2: p[3] });
    } else {
      const pairs = [];
      for (let i = 0; i < p.length; i += 2) pairs.push(`${p[i]},${p[i + 1]}`);
      node = svgEl("polyline", { points: pairs.join(" ") });
    }
  } else {
    node = svgEl("text", {
      x: p[0], y: p[1], "text-anchor": shape.anchor, "dominant-baseline": "central", "font-size": shape.size,
      transform: shape.rotate ? `rotate(${shape.rotate} ${p[0]} ${p[1]})` : null,
    });
    node.textContent = shape.text_by_language[i18n.language];
  }
  node.setAttribute("fill", shape.kind === "line" ? "none" : shape.fill || "none");
  node.setAttribute("stroke", shape.stroke || "none");
  if (shape.stroke) node.setAttribute("stroke-width", String(shape.stroke_width));
  if (shape.dash_pattern.length) node.setAttribute("stroke-dasharray", shape.dash_pattern.join(" "));
  else if (shape.dash) node.setAttribute("stroke-dasharray", "4 3");
  node.setAttribute("stroke-linejoin", "round");
  if (shape.opacity < 1) node.setAttribute(shape.kind === "polygon" ? "fill-opacity" : "opacity", shape.opacity);
  if (shape.role) node.dataset.role = shape.role;
  if (shape.target) node.dataset.target = shape.target;
  return node;
}

function drawSection(section) {
  state.section = section;
  const svg = $("#section");
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${section.width} ${section.height}`);
  for (const shape of section.shapes) {
    const node = svgShape(shape);
    if (shape.target && ["rect", "polygon"].includes(shape.kind)) {
      const title = svgEl("title", {});
      title.textContent = tf("点击编辑：{label}", { label: labelForPath(shape.target) });
      node.append(title);
      node.setAttribute("tabindex", "0");
      node.setAttribute("aria-label", title.textContent);
    }
    svg.append(node);
  }
  highlightSection();
}

function highlightSection() {
  for (const node of $$("#section [data-role^='plate-']")) {
    node.classList.toggle("selected", node.dataset.role === `plate-${state.selected}`);
  }
}

/* ---------- export ---------- */

function exportReport() {
  if (!state.result) return;
  const title = ($("#project-title").value.trim() || t("通用螺栓连接")).replace(/[\\/:*?"<>|\s]+/g, "_").slice(0, 60);
  const blob = new Blob([state.result.report], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = el("a", { href: url, download: `VDI2230-${title}.txt` });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ---------- start-up ---------- */

function loadDefaults(defaults, generatedNames = false) {
  for (const spec of state.schema.fields) {
    const [section, name] = spec.path.split(".");
    state.values[spec.path] = defaults[section]?.[name] ?? null;
  }
  state.layers = defaults.plates.map((values) => ({
    values: { ...values }, prov: {}, defaultName: generatedNames ? values.name : null,
  }));
  for (const [path, source] of Object.entries(defaults.provenance || {})) {
    const layer = /^plates\[(\d+)]\.(\w+)$/.exec(path);
    if (layer) state.layers[Number(layer[1])].prov[layer[2]] = source;
    else state.prov[path] = source;
  }
  $("#project-title").value = defaults.title || "";
  state.defaultTitle = generatedNames;
  localizeDefaultNames();
}

function localizeDefaultNames() {
  const changed = new Set();
  if (state.defaultTitle) $("#project-title").value = t("通用螺栓连接");
  state.layers.forEach((layer, index) => {
    if (layer.defaultName && layer.values.name !== t(layer.defaultName)) {
      layer.values.name = t(layer.defaultName);
      changed.add(fieldId(`plates[${index}].name`));
    }
  });
  return changed;
}

async function init() {
  try {
    const [schema, catalog, translations] = await Promise.all([
      getJson("/api/general/schema"), getJson("/api/general/catalog"), getJson("/api/general/translations"),
    ]);
    initializeTranslations(translations);
    state.schema = schema;
    state.catalog = catalog;
  } catch (error) {
    setStatus("加载失败");
    showError(`无法加载计算模型：${error.message}`, []);
    return;
  }
  for (const spec of state.schema.fields) state.specs.set(spec.path, spec);
  for (const spec of state.schema.layer_fields) state.layerSpecs.set(spec.path, spec);
  loadDefaults(state.schema.defaults, true);

  showInputTab = setupTabs($(".input-pane [role='tablist']"));
  setupTabs($(".result-pane [role='tablist']"));
  renderForm();
  renderLayers();
  applyVisibility();

  $("#add-layer").addEventListener("click", addLayer);
  $("#section-add-layer").addEventListener("click", addLayer);
  $("#section-remove-layer").addEventListener("click", () => removeLayer(state.selected));
  $("#project-title").addEventListener("input", () => {
    state.defaultTitle = false;
    scheduleCalculation(400);
  });
  $("#value-filter").addEventListener("input", filterValues);
  $("#export").addEventListener("click", exportReport);
  $("#language").addEventListener("change", () => {
    const language = $("#language").value;
    if (!["zh", "en"].includes(language)) throw new Error("Unsupported language");
    ++state.seq;
    clearTimeout(state.timer);
    $("#export").disabled = true;
    i18n.language = language;
    const url = new URL(location.href);
    url.searchParams.set("lang", language);
    history.replaceState(null, "", url);
    translateStatic();
    const opened = new Map($$("details.group").map((node) => [node.dataset.section, node.open]));
    const entered = new Map($$(".field input:not([type='checkbox'])").map((node) => [node.id, node.value]));
    const changed = localizeDefaultNames();
    for (const selector of ["#panel-bolt", "#plates-fields", "#panel-load", "#panel-assembly"]) $(selector).replaceChildren();
    $("#bolt-lengths")?.remove();
    renderForm();
    for (const node of $$("details.group")) node.open = opened.get(node.dataset.section) ?? node.open;
    renderLayers();
    for (const [id, value] of entered) {
      const control = document.getElementById(id);
      if (control && !changed.has(id)) control.value = value;
    }
    applyVisibility();
    if (state.section) drawSection(state.section);
    calculate();
  });
  $("#section").addEventListener("click", (event) => {
    const target = event.target.closest("[data-target]")?.dataset.target;
    if (target) goToField(target);
  });
  $("#section").addEventListener("keydown", (event) => {
    const target = event.target.closest("[data-target]")?.dataset.target;
    if (target && ["Enter", " "].includes(event.key)) {
      event.preventDefault();
      goToField(target);
    }
  });
  new ResizeObserver(() => {
    const view = viewSize();
    if (state.lastView && (Math.abs(view.width - state.lastView.width) > 8 || Math.abs(view.height - state.lastView.height) > 8)) {
      scheduleCalculation(200);
    }
  }).observe($("#section-wrap"));
  calculate();
}

init();
