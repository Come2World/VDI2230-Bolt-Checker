from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Mapping

from vdi2230.domain.models import (
    CalculationValue,
    CalculationResult,
    JsonValue,
    ProjectSnapshot,
)
from vdi2230.infrastructure.project_file import load_project, save_project
from vdi2230.infrastructure.report import render_text_report
from vdi2230.ui.forms import CaseFormDefinition, InputFieldSpec, parse_form_values
from vdi2230.ui.section_view import SectionView


def format_result_value(result: CalculationValue) -> str:
    shown = "未计算" if result.value is None else str(result.value)
    if result.reference_value is None:
        return shown
    if result.reference_value == 0:
        error = (
            "未计算"
            if result.absolute_error is None
            else f"{result.absolute_error:g}"
        )
        tolerance = (
            "未指定"
            if result.absolute_tolerance is None
            else f"{result.absolute_tolerance:g}"
        )
        return f"{shown} (PDF=0; 绝对误差={error}; 容差={tolerance})"
    error = (
        "未计算"
        if result.relative_error_percent is None
        else f"{result.relative_error_percent:.2f}%"
    )
    return f"{shown} (PDF={result.reference_value:g}; 误差={error})"


def format_result_details(result: CalculationValue) -> str:
    unit = f" {result.unit}" if result.unit else ""
    lines = [
        f"{result.symbol}（{result.label}） = "
        f"{format_result_value(result)}{unit}",
        f"状态：{result.status.value}",
        f"依据：{result.formula_reference}",
    ]
    if result.note:
        lines.append(f"说明：{result.note}")
    return "\n".join(lines)


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        cases: tuple[CaseFormDefinition, ...],
    ) -> None:
        if not cases:
            raise ValueError("At least one calculation case is required")
        if len({case.case_id for case in cases}) != len(cases):
            raise ValueError("Calculation case IDs must be unique")

        self.root = root
        self.cases = {case.case_id: case for case in cases}
        self.case_var = tk.StringVar(value=cases[0].case_id)
        self.title_var = tk.StringVar(value=cases[0].title)
        self.state_var = tk.StringVar(value="尚未计算")
        self._entry_vars: dict[str, tk.StringVar] = {}
        self._source_vars: dict[str, tk.StringVar] = {}
        self._result_values_by_item: dict[str, CalculationValue] = {}
        self._project: ProjectSnapshot | None = None
        self._result: CalculationResult | None = None
        self._stale = True

        self.root.title("VDI 2230 螺栓连接计算")
        self.root.minsize(1000, 620)
        self._build_layout()
        self.title_var.trace_add("write", self._mark_stale)
        self._load_case_form(cases[0].case_id)

    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="打开项目", command=self._open_project).pack(
            side=tk.LEFT,
        )
        ttk.Button(toolbar, text="保存项目", command=self._save_project).pack(
            side=tk.LEFT,
            padx=(6, 0),
        )
        ttk.Button(toolbar, text="计算", command=self._calculate).pack(
            side=tk.LEFT,
            padx=(14, 0),
        )
        self._export_button = ttk.Button(
            toolbar,
            text="导出 TXT",
            command=self._export_report,
            state=tk.DISABLED,
        )
        self._export_button.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(toolbar, textvariable=self.state_var).pack(
            side=tk.RIGHT,
            padx=(8, 0),
        )
        ttk.Entry(toolbar, textvariable=self.title_var, width=28).pack(
            side=tk.RIGHT,
        )

        panes = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        input_panel = ttk.Frame(panes, padding=4)
        drawing_panel = ttk.Frame(panes, padding=4)
        result_panel = ttk.Frame(panes, padding=4)
        panes.add(input_panel, weight=2)
        panes.add(drawing_panel, weight=3)
        panes.add(result_panel, weight=2)

        self._build_input_panel(input_panel)
        self.section_view = SectionView(drawing_panel)
        self.section_view.pack(fill=tk.BOTH, expand=True)
        self._build_result_panel(result_panel)

    def _build_input_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="计算模型").pack(anchor=tk.W)
        case_selector = ttk.Combobox(
            parent,
            textvariable=self.case_var,
            values=tuple(self.cases),
            state="readonly",
        )
        case_selector.pack(fill=tk.X, pady=(2, 8))
        case_selector.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._load_case_form(self.case_var.get()),
        )
        ttk.Label(
            parent,
            text="参考算例验证模式：输入为原文示例值，只读；修改参数驱动计算尚未支持。",
            wraplength=320,
            foreground="#8a4b08",
        ).pack(anchor=tk.W, pady=(0, 6))

        scroll_frame = ttk.Frame(parent)
        scroll_frame.pack(fill=tk.BOTH, expand=True)
        self._input_canvas = tk.Canvas(
            scroll_frame,
            highlightthickness=0,
            width=320,
        )
        scrollbar = ttk.Scrollbar(
            scroll_frame,
            orient=tk.VERTICAL,
            command=self._input_canvas.yview,
        )
        self._input_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._input_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._input_fields_frame = ttk.Frame(self._input_canvas)
        self._input_window = self._input_canvas.create_window(
            (0, 0),
            window=self._input_fields_frame,
            anchor=tk.NW,
        )
        self._input_fields_frame.bind(
            "<Configure>",
            lambda _event: self._input_canvas.configure(
                scrollregion=self._input_canvas.bbox("all")
            ),
        )
        self._input_canvas.bind(
            "<Configure>",
            lambda event: self._input_canvas.itemconfigure(
                self._input_window,
                width=event.width,
            ),
        )

    def _build_result_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="结构化计算结果").pack(anchor=tk.W)
        columns = ("symbol", "value", "unit", "status", "reference")
        self._results = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=16,
        )
        headings = {
            "symbol": "符号",
            "value": "结果",
            "unit": "单位",
            "status": "状态",
            "reference": "公式/对照",
        }
        widths = {
            "symbol": 64,
            "value": 96,
            "unit": 52,
            "status": 74,
            "reference": 120,
        }
        for column in columns:
            self._results.heading(column, text=headings[column])
            self._results.column(column, width=widths[column], stretch=True)
        self._results.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        self._results.bind("<<TreeviewSelect>>", self._show_selected_result)

        self._result_details = tk.Text(
            parent,
            height=5,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self._result_details.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(parent, text="提示与警告").pack(anchor=tk.W)
        self._warnings = tk.Text(parent, height=7, wrap=tk.WORD, state=tk.DISABLED)
        self._warnings.pack(fill=tk.X, pady=(4, 0))

    def _load_case_form(self, case_id: str) -> None:
        case = self.cases[case_id]
        read_only_case = all(field.read_only for field in case.fields)
        self._entry_vars.clear()
        self._source_vars.clear()
        for child in self._input_fields_frame.winfo_children():
            child.destroy()

        headings = (
            ("参考输入", "数值", "")
            if read_only_case
            else ("参数", "输入值", "数据来源")
        )
        for column, heading in enumerate(headings):
            if not heading:
                continue
            ttk.Label(
                self._input_fields_frame,
                text=heading,
                font=("TkDefaultFont", 9, "bold"),
            ).grid(row=0, column=column, sticky=tk.W, padx=4, pady=(2, 6))

        for row, field in enumerate(case.fields):
            label = f"{field.label} ({field.unit})" if field.unit else field.label
            ttk.Label(
                self._input_fields_frame,
                text=label,
                wraplength=145,
            ).grid(row=row + 1, column=0, sticky=tk.W, padx=(4, 8), pady=3)
            default_value = (
                "" if field.default_value is None else str(field.default_value)
            )
            variable = tk.StringVar(value=default_value)
            self._entry_vars[field.key] = variable
            if field.kind == "choice":
                widget = ttk.Combobox(
                    self._input_fields_frame,
                    textvariable=variable,
                    values=field.choices,
                    state="readonly",
                    width=18,
                )
            else:
                widget = ttk.Entry(
                    self._input_fields_frame,
                    textvariable=variable,
                    width=20,
                    state="readonly" if field.read_only else "normal",
                )
            widget.grid(
                row=row + 1,
                column=1,
                sticky=tk.EW,
                padx=(0, 4),
                pady=3,
            )
            variable.trace_add("write", self._on_input_changed)
            source_var = tk.StringVar(value=field.source)
            self._source_vars[field.key] = source_var
            if not field.read_only:
                ttk.Entry(
                    self._input_fields_frame,
                    textvariable=source_var,
                    width=20,
                ).grid(
                    row=row + 1,
                    column=2,
                    sticky=tk.EW,
                    padx=(0, 4),
                    pady=3,
                )
                source_var.trace_add("write", self._mark_stale)

        self._input_fields_frame.columnconfigure(0, weight=1)
        self._input_fields_frame.columnconfigure(1, weight=1)
        if not read_only_case:
            self._input_fields_frame.columnconfigure(2, weight=1)
        self.title_var.set(case.title)
        self._mark_stale()
        self._update_geometry(case)

    def _on_input_changed(self, *_args: object) -> None:
        self._mark_stale()
        case = self.cases[self.case_var.get()]
        try:
            inputs = parse_form_values(
                case.fields,
                {
                    key: variable.get()
                    for key, variable in self._entry_vars.items()
                },
            )
        except ValueError:
            self.section_view.delete("all")
            self.section_view.create_text(
                16,
                16,
                anchor=tk.NW,
                text="输入几何参数后显示剖面图",
            )
            return
        self._update_geometry(case, inputs)

    def _mark_stale(self, *_args: object) -> None:
        self._stale = True
        self.state_var.set("输入已修改；请重新计算")
        self._export_button.configure(state=tk.DISABLED)

    def _parse_inputs(self, case: CaseFormDefinition) -> dict[str, JsonValue]:
        raw = {
            key: variable.get()
            for key, variable in self._entry_vars.items()
        }
        inputs = parse_form_values(case.fields, raw)
        self._update_geometry(case, inputs)
        return inputs

    def _read_sources(self, case: CaseFormDefinition) -> dict[str, str]:
        sources = {
            field.key: self._source_vars[field.key].get().strip()
            for field in case.fields
        }
        missing = [
            field.label
            for field in case.fields
            if not sources[field.key]
        ]
        if missing:
            raise ValueError(
                "请填写以下输入项的数据来源：" + "、".join(missing)
            )
        return sources

    def _update_geometry(
        self,
        case: CaseFormDefinition,
        inputs: Mapping[str, JsonValue] | None = None,
    ) -> None:
        if inputs is None:
            inputs = {
                field.key: field.default_value
                for field in case.fields
            }
        try:
            geometry = case.geometry(inputs)
        except ValueError as exc:
            self.section_view.delete("all")
            self.section_view.create_text(
                16,
                16,
                anchor=tk.NW,
                text=f"剖面图不可用：{exc}",
                fill="#9b2c2c",
            )
            return
        if geometry is None:
            self.section_view.delete("all")
            self.section_view.create_text(
                16,
                16,
                anchor=tk.NW,
                text="当前模型尚无可绘制的几何输入",
            )
            return
        self.section_view.set_geometry(geometry)

    def _calculate(self) -> None:
        case = self.cases[self.case_var.get()]
        try:
            inputs = self._parse_inputs(case)
            units = {field.key: field.unit for field in case.fields}
            sources = self._read_sources(case)
            project = ProjectSnapshot(
                case_id=case.case_id,
                title=self.title_var.get(),
                inputs=inputs,
                input_units=units,
                input_sources=sources,
            )
            result = case.calculate(project)
            if result.case_id != case.case_id:
                raise ValueError("Calculator returned a result for another case")
        except ValueError as exc:
            self._project = None
            self._result = None
            self._stale = True
            self.state_var.set("输入或计算错误")
            messagebox.showerror("无法计算", str(exc), parent=self.root)
            return

        self._project = project
        self._result = result
        self._stale = False
        self.state_var.set(f"计算状态：{result.overall_status.value}")
        self._show_result(result)
        self._export_button.configure(state=tk.NORMAL)

    def _show_result(self, result: CalculationResult) -> None:
        children = self._results.get_children()
        if children:
            self._results.delete(*children)
        self._result_values_by_item.clear()
        for value in result.values:
            shown_value = format_result_value(value)
            item_id = self._results.insert(
                "",
                tk.END,
                values=(
                    value.symbol,
                    shown_value,
                    value.unit,
                    value.status.value,
                    value.formula_reference,
                ),
            )
            self._result_values_by_item[item_id] = value

        warning_text = "\n".join(f"• {item}" for item in result.warnings)
        self._warnings.configure(state=tk.NORMAL)
        self._warnings.delete("1.0", tk.END)
        self._warnings.insert("1.0", warning_text or "无")
        self._warnings.configure(state=tk.DISABLED)
        if result.values:
            first_item = self._results.get_children()[0]
            self._results.selection_set(first_item)
            self._results.focus(first_item)
            self._show_selected_result()

    def _show_selected_result(self, _event: tk.Event | None = None) -> None:
        selection = self._results.selection()
        item = self._result_values_by_item.get(selection[0]) if selection else None
        self._result_details.configure(state=tk.NORMAL)
        self._result_details.delete("1.0", tk.END)
        if item is not None:
            self._result_details.insert("1.0", format_result_details(item))
        self._result_details.configure(state=tk.DISABLED)

    def _save_project(self) -> None:
        case = self.cases[self.case_var.get()]
        try:
            inputs = self._parse_inputs(case)
            sources = self._read_sources(case)
        except ValueError as exc:
            messagebox.showerror("无法保存", str(exc), parent=self.root)
            return
        path_text = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".json",
            filetypes=(("VDI 2230 项目", "*.json"), ("所有文件", "*")),
        )
        if not path_text:
            return
        project = ProjectSnapshot(
            case_id=case.case_id,
            title=self.title_var.get(),
            inputs=inputs,
            input_units={field.key: field.unit for field in case.fields},
            input_sources=sources,
        )
        try:
            save_project(Path(path_text), project)
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.root)
            return
        self._project = project
        messagebox.showinfo("项目已保存", path_text, parent=self.root)

    def _open_project(self) -> None:
        path_text = filedialog.askopenfilename(
            parent=self.root,
            filetypes=(("VDI 2230 项目", "*.json"), ("所有文件", "*")),
        )
        if not path_text:
            return
        try:
            project = load_project(Path(path_text))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("打开失败", str(exc), parent=self.root)
            return
        case = self.cases.get(project.case_id)
        if case is None:
            messagebox.showerror(
                "打开失败",
                f"不支持项目中的计算模型：{project.case_id}",
                parent=self.root,
            )
            return
        allowed_keys = {field.key for field in case.fields}
        if set(project.inputs) - allowed_keys:
            messagebox.showerror(
                "打开失败",
                "项目包含当前计算模型不识别的输入字段。",
                parent=self.root,
            )
            return
        expected_inputs = {
            field.key: field.default_value for field in case.fields
        }
        if project.inputs != expected_inputs:
            messagebox.showerror(
                "打开失败",
                "项目输入与固定参考算例不一致，当前版本不能使用修改过的算例数据。",
                parent=self.root,
            )
            return

        self.case_var.set(project.case_id)
        self._load_case_form(project.case_id)
        self.title_var.set(project.title)
        for key, value in project.inputs.items():
            self._entry_vars[key].set("" if value is None else str(value))
        for key, source in project.input_sources.items():
            if key in self._source_vars:
                self._source_vars[key].set(source)
        self._project = project
        self._result = None
        self._stale = True
        self.state_var.set("项目已载入；请重新计算")
        self._export_button.configure(state=tk.DISABLED)

    def _export_report(self) -> None:
        if self._stale or self._project is None or self._result is None:
            messagebox.showwarning(
                "结果已过期",
                "请先对当前输入重新计算，再导出报告。",
                parent=self.root,
            )
            return
        path_text = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".txt",
            filetypes=(("纯文本报告", "*.txt"), ("所有文件", "*")),
        )
        if not path_text:
            return
        try:
            Path(path_text).write_text(
                render_text_report(self._project, self._result),
                encoding="utf-8",
            )
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.root)
            return
        messagebox.showinfo("报告已导出", path_text, parent=self.root)
