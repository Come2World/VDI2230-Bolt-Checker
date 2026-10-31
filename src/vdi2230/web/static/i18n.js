"use strict";

const i18n = { language: "zh", messages: {}, templates: {}, patterns: [], staticText: [], staticAttributes: [] };
const hasChinese = (text) => /[\u4e00-\u9fff]/.test(text);
const escapePattern = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function t(text) {
  return translateText(text, i18n.language);
}

function translateText(text, language) {
  if (language === "zh" || !text) return text;
  if (Object.hasOwn(i18n.messages, text)) return i18n.messages[text];
  for (const [pattern, target] of i18n.patterns) {
    const match = pattern.exec(text);
    if (match) return target.replace(/\{(\w+)\}/g, (_, key) => translateText(match.groups[key], language));
  }
  for (const separator of [" ← ", " · "]) {
    if (text.includes(separator)) return text.split(separator).map((part) => translateText(part, language)).join(separator);
  }
  for (const prefix of ["VDI 2230 Blatt 1:2015, ", "default:", "- "]) {
    if (text.startsWith(prefix)) return prefix + translateText(text.slice(prefix.length), language);
  }
  if (hasChinese(text)) throw new Error(`Missing English translation: ${text}`);
  return text;
}

function tf(message, values) {
  const template = i18n.language === "en" ? i18n.templates[message] || t(message) : message;
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    if (!Object.hasOwn(values, key)) throw new Error(`Missing message parameter: ${key}`);
    return String(values[key]);
  });
}

function initializeTranslations(data) {
  i18n.messages = data.messages;
  i18n.templates = data.templates;
  i18n.patterns = Object.entries(data.templates).map(([source, target]) => {
    const parts = source.split(/(\{\w+\})/g).map((part) =>
      /^\{\w+\}$/.test(part) ? `(?<${part.slice(1, -1)}>.+?)` : escapePattern(part));
    return [new RegExp(`^${parts.join("")}$`, "s"), target];
  });
  // Capture only the initial HTML, before any user data or dynamic form is rendered.
  const walker = document.createTreeWalker(document, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.parentElement?.closest("[data-no-translate]") && hasChinese(node.data)) {
      i18n.staticText.push([node, node.data, node.data.trim()]);
    }
  }
  for (const node of document.querySelectorAll("[aria-label], [placeholder], [title]")) {
    if (node.closest("[data-no-translate]")) continue;
    for (const key of ["aria-label", "placeholder", "title"]) {
      const value = node.getAttribute(key);
      if (value && hasChinese(value)) i18n.staticAttributes.push([node, key, value]);
    }
  }
  const language = new URL(location.href).searchParams.get("lang") || "en";
  if (!["zh", "en"].includes(language)) throw new Error("Unsupported language; use zh or en.");
  i18n.language = language;
  translateStatic();
}

function translateStatic() {
  document.documentElement.lang = i18n.language === "zh" ? "zh-CN" : "en";
  for (const [node, original, source] of i18n.staticText) node.data = original.replace(source, t(source));
  for (const [node, key, source] of i18n.staticAttributes) node.setAttribute(key, t(source));
  document.getElementById("language").value = i18n.language;
}
