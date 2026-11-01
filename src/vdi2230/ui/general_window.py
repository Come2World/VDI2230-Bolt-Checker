"""Tk desktop front end for the general calculator.

Three-pane layout: tabbed inputs, an interactive 2D
section (click a plate to edit it), JSON project files and Markdown reports.
All state lives in :class:`GeneralFormModel`; this module only binds widgets.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from typing import Any, Callable
from vdi2230.i18n import Language, format_text, language_code, translate

from vdi2230.domain.models import ResultStatus
from vdi2230.domain.general_inputs import InputValidationError
from vdi2230.infrastructure.project_file import load_general_project, save_general_project, write_text_atomic
from vdi2230.infrastructure.general_section import (
    DRAWING_BACKGROUND, MAX_VIEW, MIN_VIEW, MUTED_TEXT, PLATE_STROKE, TEXT_FILL, general_section_shapes,
)
from vdi2230.ui.general_model import (
    CATALOG_PATHS,
    INPUT_TABS,
    KEY_METRICS,
    GeneralFormModel,
    Outcome,
    canvas_item,
    coerce,
    entry_text,
    fmt,
    plate_index,
    subsection_of,
)


ACCENT = "#00d9ff"
PURPLE = "#bd83ff"
PANEL = "#071525"
INPUT_BACKGROUND = "#06101f"
BORDER = "#205572"
SELECT_BACKGROUND = "#123d56"
STATUS_COLORS = {"通过": ("#28e6b3", "#073529"), "不通过": ("#ff718c", "#391528"), "需确认": ("#ffd078", "#302616")}
NEUTRAL_COLORS = (MUTED_TEXT, "#102437")
MARKERS = {"catalog": ("●", ACCENT), "provisional": ("●", STATUS_COLORS["需确认"][0]), "error": ("✕", STATUS_COLORS["不通过"][0])}
CALC_DELAY_MS = 300
PANE_SPLIT = (0.30, 0.68)
WINDOW_SIZE = (1440, 860)
WINDOW_MIN_SIZE = (1100, 640)
# Horizontal / vertical room left for screen edges, menu bar and Dock.
SCREEN_MARGIN = (40, 120)
_LAYER_PATH = re.compile(r"^plates\[(\d+)]\.(\w+)$")
_FILENAME_UNSAFE = re.compile(r'[\\/:*?"<>|\s]+')


def fit_window(screen_width: int, screen_height: int) -> tuple[str, tuple[int, int]]:
    """Return a ``WxH+X+Y`` geometry and a min size that both fit on the screen.

    Without an explicit geometry Tk sizes the window to its requested content
    width, which can exceed laptop screens.
    """
    width = max(1, min(WINDOW_SIZE[0], screen_width - SCREEN_MARGIN[0]))
    height = max(1, min(WINDOW_SIZE[1], screen_height - SCREEN_MARGIN[1]))
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 3)
    min_size = (min(WINDOW_MIN_SIZE[0], width), min(WINDOW_MIN_SIZE[1], height))
    return f"{width}x{height}+{x}+{y}", min_size


def _field_columns(frame: tk.Misc) -> None:
    frame.columnconfigure(0, weight=5, uniform="field")
    frame.columnconfigure(1, weight=3, uniform="field")


class ScrollFrame(ttk.Frame):
    """Vertically scrollable container; place children in ``body``."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, background=PANEL, highlightthickness=0, borderwidth=0)
        bar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, padding=(4, 2))
        window = self.canvas.create_window(0, 0, window=self.body, anchor=tk.NW)
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))

    def scroll(self, units: int) -> None:
        self.canvas.yview_scroll(units, "units")


class GeneralWindow:
    def __init__(self, root: tk.Tk | tk.Toplevel, model: GeneralFormModel | None = None, *, language: Language = "en") -> None:
        self.root = root
        self.language = language_code(language)
        self.model = model or GeneralFormModel()
        self.model.set_language(self.language)
        self.outcome: Outcome | None = None
        self._last_good = None
        self._last_good_names: tuple[str | None, ...] = ()
        self._syncing = False
        self._calc_job: str | None = None
        self._draw_job: str | None = None
        self._vars: dict[str, tk.Variable] = {}
        self._rows: dict[str, tuple[tk.Widget, ...]] = {}
        self._widgets: dict[str, tk.Widget] = {}
        self._choices: dict[str, tuple[dict[Any, str], dict[str, Any]]] = {}
        self._sections: list[tuple[ttk.Label, list[str]]] = []
        self._error_paths: list[str] = []
        self._edit_notice: str | None = None
        self.project_path: Path | None = None
        self._saved_inputs = self.model.to_input_json()

        root.title(self.t("VDI 2230 螺栓连接计算 · 通用"))
        geometry, min_size = fit_window(root.winfo_screenwidth(), root.winfo_screenheight())
        root.minsize(*min_size)
        root.geometry(geometry)
        self._configure_style()
        self._build()
        self.apply_visibility()
        self.render_layers()
        root.bind_all("<MouseWheel>", self._on_wheel, add="+")
        root.bind_all("<Button-4>", self._on_wheel, add="+")
        root.bind_all("<Button-5>", self._on_wheel, add="+")
        self.calculate_now()
        root.protocol("WM_DELETE_WINDOW", self.request_close)

    def t(self, text: str) -> str:
        return translate(text, self.language)

    def _translate_static(self, widget: tk.Misc) -> None:
        if isinstance(widget, tk.Widget) and "text" in widget.keys() and not widget.cget("textvariable"):
            widget.configure(text=self.t(str(widget.cget("text"))))
        if isinstance(widget, ttk.Notebook):
            for tab in widget.tabs():
                widget.tab(tab, text=self.t(widget.tab(tab, "text")))
        if isinstance(widget, ttk.Treeview):
            for column in ("#0", *widget.cget("columns")):
                widget.heading(column, text=self.t(widget.heading(column, "text")))
        for child in widget.winfo_children():
            self._translate_static(child)

    def set_language(self, language: Language) -> None:
        language = language_code(language)
        if language == self.language:
            return
        selected = self.input_tabs.index("current")
        result_tab = self.result_tabs.index("current")
        query = self.filter_var.get()
        scroll = {key: scroller.canvas.yview()[0] for key, scroller in self._scrollers.items()}
        entered = {path: var.get() for path, var in self._vars.items()
                   if path not in self._choices and isinstance(var, tk.StringVar)}
        for job in (self._calc_job, self._draw_job):
            if job is not None:
                self.root.after_cancel(job)
        self._calc_job = self._draw_job = None
        changed = self.model.set_language(language)
        self.language = language
        self.root.title(self.t("VDI 2230 螺栓连接计算 · 通用"))
        self._rebuild()
        self.input_tabs.select(selected)
        self.result_tabs.select(result_tab)
        self.filter_var.set(query)
        self.apply_visibility()
        self.render_layers()
        self._syncing = True
        try:
            for path, value in entered.items():
                if path in self._vars and path not in changed:
                    self._vars[path].set(value)
        finally:
            self._syncing = False
        self.calculate_now()
        self.root.update_idletasks()
        for key, position in scroll.items():
            self._scrollers[key].canvas.yview_moveto(position)

    def _layer_summary(self, index: int) -> str:
        values = self.model.layers[index].values
        return f"{index + 1}. {values.get('name') or self.t('（未命名）')} · {values.get('material_id') or self.t('自定义')} · h {fmt(values.get('thickness'))}"

    def _selection_text(self, index: int) -> str:
        name = self.model.layers[index].values.get("name") or self.t(f"板层 {index + 1}")
        return format_text("选中：{name}", self.language, name=f"{index + 1}. {name}")

    # ----- layout -----

    def _rebuild(self) -> None:
        self.topbar.destroy()
        self.panes.destroy()
        self._vars.clear()
        self._rows.clear()
        self._widgets.clear()
        self._choices.clear()
        self._sections.clear()
        self._build()

    def _configure_style(self) -> None:
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont"):
            tkfont.nametofont(name, root=self.root).configure(size=12)
        base = tkfont.nametofont("TkDefaultFont", root=self.root)
        self._fonts = {
            "head": tkfont.Font(root=self.root, family=base.actual("family"), size=12, weight="bold"),
            "section": tkfont.Font(root=self.root, family=base.actual("family"), size=11, weight="bold"),
        }
        style = ttk.Style(self.root)
        style.theme_use("clam")
        self.root.configure(background="#030a17")
        style.configure(".", background=PANEL, foreground=TEXT_FILL, bordercolor=BORDER,
                        darkcolor=PANEL, lightcolor=BORDER, troughcolor=INPUT_BACKGROUND)
        style.configure("Cyber.TFrame", borderwidth=1, relief="solid")
        style.configure("TEntry", fieldbackground=INPUT_BACKGROUND, foreground=TEXT_FILL,
                        insertcolor=ACCENT, padding=(4, 2))
        style.map("TEntry", bordercolor=[("focus", ACCENT)])
        style.configure("TCombobox", fieldbackground=INPUT_BACKGROUND, background=INPUT_BACKGROUND,
                        foreground=TEXT_FILL, arrowcolor=ACCENT, padding=(4, 2))
        style.map("TCombobox", fieldbackground=[("readonly", INPUT_BACKGROUND)],
                  foreground=[("readonly", TEXT_FILL)], bordercolor=[("focus", ACCENT)],
                  selectbackground=[("readonly", SELECT_BACKGROUND)], selectforeground=[("readonly", TEXT_FILL)])
        self.root.option_add("*TCombobox*Listbox.background", INPUT_BACKGROUND)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT_FILL)
        self.root.option_add("*TCombobox*Listbox.selectBackground", SELECT_BACKGROUND)
        self.root.option_add("*TCombobox*Listbox.selectForeground", TEXT_FILL)
        style.configure("TButton", background="#102c43", padding=(6, 3))
        style.map("TButton", background=[("active", SELECT_BACKGROUND)], foreground=[("disabled", MUTED_TEXT), ("active", ACCENT)])
        style.configure("Primary.TButton", background="#0b7490", foreground=TEXT_FILL, bordercolor=ACCENT)
        style.map("Primary.TButton", background=[("active", "#09607b")], foreground=[("disabled", MUTED_TEXT), ("active", TEXT_FILL)])
        style.configure("TCheckbutton", indicatorbackground=INPUT_BACKGROUND, indicatorforeground=ACCENT)
        style.map("TCheckbutton", background=[("active", PANEL)], indicatorbackground=[("selected", SELECT_BACKGROUND)])
        style.configure("TNotebook", borderwidth=1, tabmargins=(2, 2, 2, 0))
        style.configure("TNotebook.Tab", padding=(8, 3), background=INPUT_BACKGROUND, foreground=MUTED_TEXT)
        style.map("TNotebook.Tab", background=[("selected", "#0c263a")], foreground=[("selected", ACCENT)])
        style.map("Results.TNotebook.Tab", foreground=[("selected", PURPLE)])
        style.configure("Treeview", rowheight=22, background=INPUT_BACKGROUND, fieldbackground=INPUT_BACKGROUND,
                        foreground=TEXT_FILL, bordercolor=BORDER)
        style.map("Treeview", background=[("selected", SELECT_BACKGROUND)], foreground=[("selected", TEXT_FILL)])
        style.configure("Treeview.Heading", background="#10223b", foreground=PURPLE, relief="flat")
        style.map("Treeview.Heading", background=[("active", SELECT_BACKGROUND)])
        style.configure("TScrollbar", background="#154460", arrowcolor=ACCENT, borderwidth=0)
        style.configure("Head.TLabel", foreground=ACCENT, font=self._fonts["head"])
        style.configure("ResultHead.TLabel", foreground=PURPLE, font=self._fonts["head"])
        style.configure("Section.TLabel", foreground=ACCENT, font=self._fonts["section"])
        style.configure("Muted.TLabel", foreground=MUTED_TEXT)
        style.configure("Unit.TLabel", foreground=MUTED_TEXT)

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=(8, 6, 8, 2))
        self.topbar = top
        top.pack(fill=tk.X)
        ttk.Label(top, text="VDI 2230 通用计算", style="Head.TLabel").pack(side=tk.LEFT)
        self.title_var = tk.StringVar(value=self.model.title)
        ttk.Entry(top, textvariable=self.title_var, width=28).pack(side=tk.LEFT, padx=(10, 0))
        self.title_var.trace_add("write", self._on_title)
        self.save_button = ttk.Button(top, text="保存项目", command=self.save_project)
        self.save_button.pack(side=tk.LEFT, padx=(8, 2))
        self.load_button = ttk.Button(top, text="加载项目", command=self.load_project)
        self.load_button.pack(side=tk.LEFT, padx=2)
        self.language_var = tk.StringVar(value="中文" if self.language == "zh" else "English")
        self.language_selector = ttk.Combobox(top, textvariable=self.language_var, values=("中文", "English"), width=7, state="readonly")
        self.language_selector.pack(side=tk.RIGHT, padx=4)
        self.language_selector.bind("<<ComboboxSelected>>", lambda _event: self.set_language("en" if self.language_var.get() == "English" else "zh"))
        self.verdict_label = tk.Label(top, text="—", padx=8, pady=1, background=PANEL, foreground=TEXT_FILL)
        self.verdict_label.pack(side=tk.RIGHT, padx=(0, 10))
        self.status_var = tk.StringVar(value="正在计算…")
        ttk.Label(top, textvariable=self.status_var, style="Muted.TLabel").pack(side=tk.RIGHT, padx=(0, 10))

        panes = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))
        left, center, right = (ttk.Frame(panes, padding=5, style="Cyber.TFrame") for _ in range(3))
        panes.add(left, weight=3)
        panes.add(center, weight=4)
        panes.add(right, weight=3)
        self.panes = panes
        panes.bind("<Configure>", self._initial_sashes)
        self._build_inputs(left)
        self._build_section(center)
        self._build_results(right)
        self._translate_static(top)
        self._translate_static(panes)

    def _initial_sashes(self, event: tk.Event) -> None:
        if event.width < 600:
            return
        self.panes.unbind("<Configure>")
        self.panes.sashpos(0, int(event.width * PANE_SPLIT[0]))
        self.panes.sashpos(1, int(event.width * PANE_SPLIT[1]))

    def _build_inputs(self, parent: ttk.Frame) -> None:
        self.input_tabs = ttk.Notebook(parent)
        self.input_tabs.pack(fill=tk.BOTH, expand=True)
        self._tab_index = {key: index for index, (key, _) in enumerate(INPUT_TABS)}
        bodies: dict[str, ttk.Frame] = {}
        self._scrollers: dict[str, ScrollFrame] = {}
        for key, label in INPUT_TABS:
            scroller = ScrollFrame(self.input_tabs)
            self._scrollers[key] = scroller
            self.input_tabs.add(scroller, text=label)
            bodies[key] = scroller.body
            _field_columns(scroller.body)
        # One grid per tab keeps label and entry columns aligned across subsections.
        sections: dict[str, tuple[ttk.Label, list[str]]] = {}
        for spec in self.model.fields:
            if spec["path"] in CATALOG_PATHS:
                continue
            body = bodies[spec["group"]]
            title = subsection_of(spec)
            key = f"{spec['group']}|{title}"
            if key not in sections:
                header = ttk.Label(body, text=title, style="Section.TLabel")
                header.grid(row=body.grid_size()[1], column=0, columnspan=3, sticky="w", pady=(6, 1))
                sections[key] = (header, [])
                self._sections.append(sections[key])
            paths = sections[key][1]
            extra = CATALOG_PATHS if spec["path"] == "joint.type" else ()
            for path in (spec["path"], *extra):
                self._field_row(body, self.model.specs[path], path, self.model.values.get(path), self._on_field)
                paths.append(path)
        self._build_layer_editor(bodies["plates"])

    def _choice_options(self, spec: dict[str, Any], path: str) -> list[tuple[Any, str]]:
        if path == "bolt.catalog_variant_id":
            options: list[tuple[Any, str]] = [(None, "自定义（手动输入）")]
            labels = [bolt["label"] for bolt in self.model.catalog["bolts"]]
            for bolt in self.model.catalog["bolts"]:
                label = bolt["label"] if labels.count(bolt["label"]) == 1 else f"{bolt['label']} ({bolt['variant_id']})"
                options.append((bolt["variant_id"], label))
            return options
        if path == "bolt.property_class":
            return [(None, "—"), *((value, value) for value in self.model.catalog["property_classes"])]
        if path.endswith("material_id"):
            return [(None, "自定义"), *((m["material_id"], f"{m['material_id']} · {m['name']}") for m in self.model.catalog["materials"])]
        return [(value, label) for value, label in spec["choices"]]

    def _field_row(
        self, frame: ttk.Frame, spec: dict[str, Any], path: str, value: Any, on_change: Callable[[str], None],
    ) -> None:
        row = frame.grid_size()[1]
        label = ttk.Label(frame, text=self.t(spec["label"]) + (f" {spec['unit']}" if spec["unit"] else ""))
        label.grid(row=row, column=0, sticky="w", padx=(0, 6))
        if self.language == "en":
            label.bind("<Configure>", lambda _event: label.configure(wraplength=max(60, frame.winfo_width() * 5 // 8 - 30)))
        if spec["kind"] == "choice" or path in CATALOG_PATHS or path.endswith("material_id"):
            options = [(key, self.t(text)) for key, text in self._choice_options(spec, path)]
            to_label = {key: text for key, text in options}
            self._choices[path] = (to_label, {text: key for key, text in options})
            var: tk.Variable = tk.StringVar(value=to_label.get(value, to_label.get(None, "")))
            widget: tk.Widget = ttk.Combobox(frame, textvariable=var, values=[text for _, text in options], state="readonly", width=8)
        elif spec["kind"] == "bool":
            var = tk.BooleanVar(value=bool(value))
            widget = ttk.Checkbutton(frame, variable=var)
        else:
            var = tk.StringVar(value=entry_text(value))
            widget = ttk.Entry(frame, textvariable=var, width=8)
        widget.grid(row=row, column=1, sticky="ew", pady=1)
        marker = tk.Label(frame, text="", width=2, background=PANEL)
        marker.grid(row=row, column=2, sticky="w")
        self._vars[path] = var
        self._rows[path] = (label, widget, marker)
        self._widgets[path] = widget
        var.trace_add("write", lambda *_args, p=path: on_change(p))
        self._update_marker(path)

    def _build_layer_editor(self, body: ttk.Frame) -> None:
        box = ttk.Frame(body)
        box.grid(row=body.grid_size()[1], column=0, columnspan=3, sticky="ew", pady=(6, 0))
        box.columnconfigure(0, weight=1)
        head = ttk.Frame(box)
        head.grid(row=0, column=0, sticky="ew")
        ttk.Label(head, text="板层", style="Section.TLabel").pack(side=tk.LEFT)
        self.layer_count_var = tk.StringVar()
        ttk.Label(head, textvariable=self.layer_count_var, style="Muted.TLabel").pack(side=tk.LEFT, padx=4)
        hint = ttk.Label(
            box, style="Muted.TLabel", justify=tk.LEFT,
            text="自螺栓头侧起排列。μT 指板层传力界面；μK 与 μG 在螺栓页独立设置。垫片经验尺寸可改，手动值不会随公称直径覆盖。",
        )
        hint.grid(row=1, column=0, sticky="ew", pady=(2, 2))
        hint.bind("<Configure>", lambda e: hint.configure(wraplength=max(e.width - 4, 100)))
        self.layer_list = tk.Listbox(box, height=4, exportselection=False, activestyle="none",
                                    background=INPUT_BACKGROUND, foreground=TEXT_FILL, selectbackground=SELECT_BACKGROUND,
                                    selectforeground=TEXT_FILL, highlightbackground=BORDER, highlightcolor=ACCENT)
        self.layer_list.grid(row=2, column=0, sticky="ew")
        self.layer_list.bind("<<ListboxSelect>>", self._on_layer_list)
        bar = ttk.Frame(box)
        bar.grid(row=3, column=0, sticky="ew", pady=(2, 0))
        self.layer_buttons = {
            "add": ttk.Button(bar, text="+", command=self.add_layer),
            "remove": ttk.Button(bar, text="−", command=self.remove_layer),
            "up": ttk.Button(bar, text="↑", command=lambda: self.move_layer(-1)),
            "down": ttk.Button(bar, text="↓", command=lambda: self.move_layer(1)),
        }
        for column, button in enumerate(self.layer_buttons.values()):
            bar.columnconfigure(column, weight=1, uniform="layer-buttons")
            button.grid(row=0, column=column, sticky="ew")
        self.layer_fields = ttk.Frame(box)
        self.layer_fields.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        _field_columns(self.layer_fields)

    def _build_section(self, parent: ttk.Frame) -> None:
        head = ttk.Frame(parent)
        head.pack(fill=tk.X)
        ttk.Label(head, text="二维剖面", style="Head.TLabel").pack(side=tk.LEFT)
        ttk.Button(head, text="− 删除选中层", command=self.remove_layer).pack(side=tk.RIGHT)
        self.section_add = ttk.Button(head, text="+ 板层", command=self.add_layer)
        self.section_add.pack(side=tk.RIGHT, padx=(0, 4))
        self.selected_var = tk.StringVar()
        ttk.Label(head, textvariable=self.selected_var, style="Muted.TLabel").pack(side=tk.RIGHT, padx=8)
        self.canvas = tk.Canvas(parent, background=DRAWING_BACKGROUND, highlightthickness=1,
                                highlightbackground=ACCENT, highlightcolor=ACCENT)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.canvas.bind("<Configure>", lambda _e: self._schedule_draw())
        self.canvas.bind("<Button-1>", self._on_section_click)
        self.canvas.bind("<Motion>", lambda e: self.canvas.configure(cursor="hand2" if self._section_target(e) else ""))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.configure(cursor=""))
        self.metrics_var = tk.StringVar()
        metrics = ttk.Label(parent, textvariable=self.metrics_var, style="Muted.TLabel", justify=tk.LEFT)
        metrics.pack(fill=tk.X, pady=(3, 0))
        metrics.bind("<Configure>", lambda e: metrics.configure(wraplength=max(e.width - 4, 100)))

    def _build_results(self, parent: ttk.Frame) -> None:
        head = ttk.Frame(parent)
        head.pack(fill=tk.X)
        ttk.Label(head, text="计算结果", style="ResultHead.TLabel").pack(side=tk.LEFT)
        self.export_button = ttk.Button(head, text="导出 Markdown", command=self.export_report, state=tk.DISABLED, style="Primary.TButton")
        self.export_button.pack(side=tk.RIGHT)
        self.banner = tk.Label(parent, anchor="w", justify=tk.LEFT, padx=6, pady=4, wraplength=360,
                               background=PANEL, foreground=TEXT_FILL)
        self.banner.pack(fill=tk.X, pady=(4, 2))
        self.error_list = tk.Listbox(parent, height=0, foreground=STATUS_COLORS["不通过"][0], background=STATUS_COLORS["不通过"][1],
                                    selectbackground=SELECT_BACKGROUND, selectforeground=TEXT_FILL,
                                    highlightbackground=BORDER, activestyle="none", exportselection=False)
        self.error_list.bind("<<ListboxSelect>>", self._on_error_select)
        self.notes_var = tk.StringVar()
        self.notes = ttk.Label(parent, textvariable=self.notes_var, foreground=STATUS_COLORS["需确认"][0], wraplength=360, justify=tk.LEFT)
        self.notes.pack(fill=tk.X)
        self.result_tabs = ttk.Notebook(parent, style="Results.TNotebook")
        self.result_tabs.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        checks = ttk.Frame(self.result_tabs)
        self.result_tabs.add(checks, text="安全系数")
        self.check_tree = ttk.Treeview(checks, columns=("value", "required", "status"), show="tree headings", selectmode="browse")
        for column, text, width, anchor in (
            ("#0", "校核项", 170, "w"), ("value", "计算值", 84, "e"), ("required", "要求", 96, "e"), ("status", "状态", 52, "center"),
        ):
            self.check_tree.heading(column, text=text)
            self.check_tree.column(column, width=width, anchor=anchor, stretch=column == "#0")
        for status, (foreground, _background) in STATUS_COLORS.items():
            self.check_tree.tag_configure(status, foreground=foreground)
        self.check_tree.tag_configure("muted", foreground=NEUTRAL_COLORS[0])
        self.check_tree.pack(fill=tk.BOTH, expand=True)

        values = ttk.Frame(self.result_tabs)
        self.result_tabs.add(values, text="全部结果")
        self.filter_var = tk.StringVar()
        ttk.Entry(values, textvariable=self.filter_var).pack(fill=tk.X, pady=(2, 2))
        self.filter_var.trace_add("write", lambda *_: self._fill_values())
        self.values_tree = ttk.Treeview(values, columns=("label", "value", "unit"), show="headings")
        for column, text, width, anchor in (("label", "名称", 200, "w"), ("value", "数值", 90, "e"), ("unit", "单位", 60, "w")):
            self.values_tree.heading(column, text=text)
            self.values_tree.column(column, width=width, anchor=anchor, stretch=column == "label")
        self.values_tree.pack(fill=tk.BOTH, expand=True)

        report = ttk.Frame(self.result_tabs)
        self.result_tabs.add(report, text="报告")
        self.report_text = tk.Text(report, wrap=tk.NONE, font="TkFixedFont", state=tk.DISABLED, borderwidth=0,
                                  background=INPUT_BACKGROUND, foreground=TEXT_FILL, insertbackground=ACCENT,
                                  selectbackground=SELECT_BACKGROUND, selectforeground=TEXT_FILL)
        yscroll = ttk.Scrollbar(report, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.report_text.pack(fill=tk.BOTH, expand=True)

    # ----- value plumbing -----

    def _read(self, path: str, spec: dict[str, Any]) -> Any:
        raw = self._vars[path].get()
        if path in self._choices:
            return self._choices[path][1].get(raw)
        return coerce(spec, raw)

    def _write(self, path: str, value: Any) -> None:
        var = self._vars.get(path)
        if var is None:
            return
        if path in self._choices:
            to_label = self._choices[path][0]
            var.set(to_label.get(value, to_label.get(None, "")))
        elif isinstance(var, tk.BooleanVar):
            var.set(bool(value))
        else:
            var.set(entry_text(value))

    def _sync(self, skip: str = "") -> None:
        """Push model values into widgets without re-triggering change handlers."""
        self._syncing = True
        try:
            for path in self._vars:
                if path == skip:
                    continue
                match = _LAYER_PATH.match(path)
                if match:
                    self._write(path, self.model.layers[int(match.group(1))].values.get(match.group(2)))
                else:
                    self._write(path, self.model.values.get(path))
                self._update_marker(path)
        finally:
            self._syncing = False

    def _update_marker(self, path: str) -> None:
        row = self._rows.get(path)
        if row is None:
            return
        marker = row[2]
        if path in self._error_paths:
            kind = "error"
        else:
            source = self.model.source_for(path)
            kind = "" if not source or source == "user" else (
                "provisional" if path in self.model.provisional or source.startswith("default:") else "catalog"
            )
        text, color = MARKERS.get(kind, ("", TEXT_FILL))
        marker.configure(text=text, foreground=color)

    def _on_title(self, *_args: object) -> None:
        self.model.set_title(self.title_var.get())
        self.schedule_calculation(500)

    def _on_field(self, path: str) -> None:
        if self._syncing:
            return
        message = self.model.set_value(path, self._read(path, self.model.specs[path]))
        if message:
            self._edit_notice = message
        elif path in (*CATALOG_PATHS, "bolt.head_type", "bolt.fatigue_strength_amplitude", "bolt.tensile_strength_max"):
            self._edit_notice = None
        if path in CATALOG_PATHS or path in ("bolt.length", "bolt.d", "bolt.head_type") or path.endswith(".material_id"):
            self._sync(skip=path)
        self._update_marker(path)
        if path in ("joint.type", "bolt.head_type", "tapped.hole_type", *CATALOG_PATHS) or path.endswith(".mode"):
            self.apply_visibility()
        if message:
            self.status_var.set(self.t(message))
        self.schedule_calculation()

    def _on_layer_field(self, path: str) -> None:
        if self._syncing:
            return
        match = _LAYER_PATH.match(path)
        index, name = int(match.group(1)), match.group(2)
        self.model.set_layer_value(index, name, self._read(path, self.model.layer_specs[name]))
        if name == "material_id":
            self._sync(skip=path)
        self._update_marker(path)
        self.layer_list.delete(index)
        self.layer_list.insert(index, self._layer_summary(index))
        self.layer_list.selection_set(index)
        self.selected_var.set(self._selection_text(index))
        self.schedule_calculation()

    def apply_visibility(self) -> None:
        for path, (label, widget, marker) in self._rows.items():
            if _LAYER_PATH.match(path):
                continue
            for item in (label, widget, marker):
                if self.model.is_relevant(path):
                    item.grid()
                else:
                    item.grid_remove()
        for header, paths in self._sections:
            if any(self.model.is_relevant(path) for path in paths):
                header.grid()
            else:
                header.grid_remove()

    def is_field_visible(self, path: str) -> bool:
        return bool(self._widgets[path].winfo_manager())

    # ----- layers -----

    def render_layers(self) -> None:
        model = self.model
        self.layer_list.delete(0, tk.END)
        for index in range(len(model.layers)):
            self.layer_list.insert(tk.END, self._layer_summary(index))
        self.layer_list.configure(height=min(max(len(model.layers), 2), 6))
        self.layer_list.selection_clear(0, tk.END)
        self.layer_list.selection_set(model.selected)
        self.layer_list.see(model.selected)
        self.layer_count_var.set(f"{len(model.layers)} / {model.max_layers}")
        full = len(model.layers) >= model.max_layers
        for button, enabled in (
            (self.layer_buttons["add"], not full), (self.section_add, not full),
            (self.layer_buttons["remove"], len(model.layers) > 1),
            (self.layer_buttons["up"], model.selected > 0),
            (self.layer_buttons["down"], model.selected < len(model.layers) - 1),
        ):
            button.state(["!disabled"] if enabled else ["disabled"])
        self.selected_var.set(self._selection_text(model.selected))

        for path in [path for path in self._vars if _LAYER_PATH.match(path)]:
            del self._vars[path], self._rows[path], self._widgets[path]
            self._choices.pop(path, None)
        for child in self.layer_fields.winfo_children():
            child.destroy()
        index = model.selected
        layer = model.layers[index]
        ttk.Label(self.layer_fields, text=self.t(f"板层 {index + 1}"), style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        for spec in model.layer_fields:
            self._field_row(self.layer_fields, spec, f"plates[{index}].{spec['path']}", layer.values.get(spec["path"]), self._on_layer_field)
        self._highlight_plate()

    def _on_layer_list(self, _event: object = None) -> None:
        selection = self.layer_list.curselection()
        if selection and selection[0] != self.model.selected:
            self.select_layer(selection[0])

    def select_layer(self, index: int, reveal: bool = False) -> None:
        self.model.select_layer(index)
        self.render_layers()
        if reveal:
            self.input_tabs.select(self._tab_index["plates"])

    def add_layer(self) -> None:
        if self.model.add_layer():
            self.render_layers()
            self.schedule_calculation(0)

    def remove_layer(self) -> None:
        if self.model.remove_layer(self.model.selected):
            self.render_layers()
            self.schedule_calculation(0)

    def move_layer(self, direction: int) -> None:
        if self.model.move_layer(self.model.selected, direction):
            self.render_layers()
            self.schedule_calculation(0)

    # ----- calculation and results -----

    def schedule_calculation(self, delay: int = CALC_DELAY_MS) -> None:
        self.export_button.state(["disabled"])
        if self._calc_job is not None:
            self.root.after_cancel(self._calc_job)
        self._calc_job = self.root.after(delay, self.calculate_now)

    def calculate_now(self) -> Outcome:
        if self._calc_job is not None:
            self.root.after_cancel(self._calc_job)
            self._calc_job = None
        outcome = self.model.calculate(self.language)
        self.outcome = outcome
        if outcome.ok:
            self._last_good = outcome.result
            self._last_good_names = tuple(layer.default_name for layer in self.model.layers)
            self._render_success(outcome)
        else:
            self._render_failure(outcome)
        return outcome

    def _set_verdict(self, text: str, status: str) -> None:
        foreground, background = STATUS_COLORS.get(status, NEUTRAL_COLORS)
        self.verdict_label.configure(text=self.t(text), foreground=foreground, background=background)
        self.banner.configure(foreground=foreground, background=background)

    def _set_tab_errors(self) -> None:
        flagged = set()
        for path in self._error_paths:
            if _LAYER_PATH.match(path):
                flagged.add("plates")
            elif path in self.model.specs:
                flagged.add(self.model.specs[path]["group"])
        for key, label in INPUT_TABS:
            self.input_tabs.tab(self._tab_index[key], text=f"{self.t(label)} ✕" if key in flagged else self.t(label))

    def _clear_results(self) -> None:
        self.check_tree.delete(*self.check_tree.get_children())
        self.values_tree.delete(*self.values_tree.get_children())
        self._set_report("")
        self.metrics_var.set("")
        self.notes_var.set("")

    def _set_report(self, text: str) -> None:
        self.report_text.configure(state=tk.NORMAL)
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", text)
        self.report_text.configure(state=tk.DISABLED)

    def report(self) -> str:
        return self.report_text.get("1.0", "end-1c")

    def _render_success(self, outcome: Outcome) -> None:
        result = outcome.result
        assert result is not None
        self._error_paths = []
        self.error_list.pack_forget()
        self._set_tab_errors()
        self._set_verdict(result.verdict_label, result.verdict.value)
        failing = [check.symbol for check in result.checks if check.status.value == "不通过"]
        detail = (
            f"不通过：{'、'.join(failing)}" if failing
            else "部分校核、数据或模型假设待核验，结果不得作为最终结论。" if result.verdict is ResultStatus.NEEDS_REVIEW
            else "全部校核满足要求。"
        )
        self.banner.configure(text=f"{self.t('总体判定')}: {self.t(result.verdict_label)}\n{self.t(detail)}")

        self.check_tree.delete(*self.check_tree.get_children())
        for check in result.checks:
            unit = f" {check.unit}" if check.unit else ""
            status = check.status.value
            self.check_tree.insert(
                "", tk.END, iid=check.symbol, text=f"{check.symbol}  {self.t(check.label)}",
                values=(
                    "—" if check.value is None else f"{fmt(check.value)}{unit}",
                    "—" if check.required is None else f"≥ {fmt(check.required)}{unit}",
                    self.t(status),
                ),
                tags=(status if status in STATUS_COLORS else "muted",),
            )
        self._fill_values()
        by_symbol = {value.symbol: value for value in result.result.values}
        self.metrics_var.set("    ".join(
            f"{label} {fmt(by_symbol[symbol].value)}{' ' + by_symbol[symbol].unit if by_symbol[symbol].unit else ''}"
            for symbol, label in KEY_METRICS if symbol in by_symbol
        ))
        notes = list(result.warnings)
        if self._edit_notice:
            notes.insert(0, self._edit_notice)
        if result.provisional_sources:
            notes.insert(0, f"待核验数据来源 {len(result.provisional_sources)} 项，详见报告。")
        self.notes_var.set("\n".join(f"• {self.t(note)}" for note in notes))
        self._set_report(outcome.report)
        for path in self._rows:
            self._update_marker(path)
        self.export_button.state(["!disabled"])
        self.status_var.set(self.t(f"已计算 · {datetime.now():%H:%M:%S}"))
        self._draw()

    def _render_failure(self, outcome: Outcome) -> None:
        self._clear_results()
        self._error_paths = [error.path for error in outcome.field_errors]
        self._set_verdict("输入有误" if outcome.field_errors else "计算失败", "不通过")
        self.banner.configure(text=outcome.error)
        self.error_list.delete(0, tk.END)
        for error in outcome.field_errors:
            self.error_list.insert(tk.END, f"{self.t(self.model.label_for(error.path))}: {error.message}")
        if outcome.field_errors:
            self.error_list.configure(height=min(len(outcome.field_errors), 4))
            self.error_list.pack(fill=tk.X, after=self.banner)
        else:
            self.error_list.pack_forget()
        self._set_tab_errors()
        for path in self._rows:
            self._update_marker(path)
        self.export_button.state(["disabled"])
        self.status_var.set(self.t(self._edit_notice or "结果未更新"))
        self._draw()

    def _fill_values(self) -> None:
        self.values_tree.delete(*self.values_tree.get_children())
        if not self.outcome or not self.outcome.ok:
            return
        query = self.filter_var.get().strip().lower()
        for index, value in enumerate(self.outcome.result.result.values):
            text = f"{value.symbol} {self.t(value.label)} {value.unit}".lower()
            if query and query not in text:
                continue
            self.values_tree.insert("", tk.END, iid=f"v{index}", values=(f"{value.symbol}  {self.t(value.label)}", fmt(value.value), value.unit))

    def _on_error_select(self, _event: object = None) -> None:
        selection = self.error_list.curselection()
        if selection:
            self.go_to_field(self._error_paths[selection[0]])

    def go_to_field(self, path: str) -> None:
        match = _LAYER_PATH.match(path)
        if match:
            self.select_layer(int(match.group(1)), reveal=True)
        elif path in self.model.specs:
            self.input_tabs.select(self._tab_index[self.model.specs[path]["group"]])
        widget = self._widgets.get(path)
        if widget is not None:
            group = "plates" if match else self.model.specs[path]["group"]
            self.root.update_idletasks()
            scroller = self._scrollers[group]
            top = widget.winfo_rooty() - scroller.body.winfo_rooty()
            scroller.canvas.yview_moveto(max(0, top - 32) / max(1, scroller.body.winfo_height()))
            widget.focus_set()

    # ----- section drawing -----

    def _view_size(self) -> tuple[int, int]:
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width <= 1 or height <= 1:
            width, height = 640, 520
        return min(max(width, MIN_VIEW), MAX_VIEW), min(max(height, MIN_VIEW), MAX_VIEW)

    def _schedule_draw(self) -> None:
        if self._draw_job is not None:
            self.root.after_cancel(self._draw_job)
        self._draw_job = self.root.after(60, self._draw)

    def _draw(self) -> None:
        self._draw_job = None
        self.canvas.delete("all")
        if self._last_good is None:
            return
        width, height = self._view_size()
        item = self._last_good.input
        item = replace(item, plates=tuple(
            replace(plate, name=self.t(source)) if source else plate
            for plate, source in zip(item.plates, self._last_good_names, strict=True)
        ))
        for shape in general_section_shapes(item, self._last_good.metrics, width, height, language=self.language):
            kind, coordinates, options = canvas_item(shape)
            getattr(self.canvas, f"create_{kind}")(*coordinates, **options)
        self._highlight_plate()
        if self.outcome is not None and not self.outcome.ok:
            fail_color, fail_background = STATUS_COLORS["不通过"]
            note = self.canvas.create_text(width / 2, 14, text=self.t("剖面未更新：请先修正标红输入"), fill=fail_color, tags=("stale",))
            x0, y0, x1, y1 = self.canvas.bbox(note)
            self.canvas.tag_lower(
                self.canvas.create_rectangle(x0 - 8, y0 - 3, x1 + 8, y1 + 3, fill=fail_background, outline=fail_color, tags=("stale",)),
                note,
            )

    def _highlight_plate(self) -> None:
        for item in self.canvas.find_withtag("plate"):
            index = plate_index(self.canvas.gettags(item))
            if self.canvas.type(item) == "rectangle":
                selected = index == self.model.selected
                self.canvas.itemconfigure(item, outline=ACCENT if selected else PLATE_STROKE, width=2 if selected else 1.4)

    def _on_plate_click(self, _event: object = None) -> None:
        index = plate_index(self.canvas.gettags("current"))
        if index is not None and index < len(self.model.layers):
            self.select_layer(index, reveal=True)

    def _section_target(self, event: tk.Event) -> str:
        for item in reversed(self.canvas.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)):
            for tag in self.canvas.gettags(item):
                if tag.startswith("target:"):
                    return tag.removeprefix("target:")
        return ""

    def _on_section_click(self, event: tk.Event) -> None:
        target = self._section_target(event)
        match = _LAYER_PATH.match(target)
        if match and int(match.group(1)) >= len(self.model.layers):
            return
        if target:
            self.go_to_field(target)

    def _on_wheel(self, event: tk.Event) -> None:
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        while widget is not None and not isinstance(widget, ScrollFrame):
            widget = widget.master
        if widget is None:
            return
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            widget.scroll(-1)
        else:
            widget.scroll(1)

    # ----- actions -----

    def save_project(self, path: str | Path | None = None) -> Path | None:
        outcome = self.calculate_now()
        if not outcome.ok:
            messagebox.showerror(self.t("保存失败"), self._outcome_error(outcome), parent=self.root)
            return None
        assert outcome.result is not None
        if path is None:
            title = _FILENAME_UNSAFE.sub("_", outcome.result.input.title)[:60]
            chosen = filedialog.asksaveasfilename(
                parent=self.root, title=self.t("保存项目"), defaultextension=".json",
                initialfile=self.project_path.name if self.project_path else f"VDI2230-{title}.json",
                initialdir=str(self.project_path.parent) if self.project_path else None,
                filetypes=[(self.t("项目文件"), "*.json")],
            )
            if not chosen:
                return None
            path = chosen
        target = Path(path)
        try:
            save_general_project(target, outcome.result.input)
        except OSError as exc:
            messagebox.showerror(self.t("保存失败"), str(exc), parent=self.root)
            return None
        self.project_path = target
        self._saved_inputs = self.model.to_input_json()
        self.status_var.set(format_text("已保存 {name}", self.language, name=target.name))
        return target

    def _outcome_error(self, outcome: Outcome) -> str:
        details = "\n".join(f"{self.t(self.model.label_for(error.path))}: {error.message}" for error in outcome.field_errors)
        return outcome.error + ("\n" + details if details else "")

    def _confirm_replace(self) -> bool:
        if self.model.to_input_json() == self._saved_inputs:
            return True
        answer = messagebox.askyesnocancel(self.t("未保存的修改"), self.t("当前项目有未保存的修改。是否先保存？"),
                                          parent=self.root)
        if answer is None:
            return False
        return not answer or self.save_project() is not None

    def load_project(self, path: str | Path | None = None) -> Path | None:
        if path is None:
            chosen = filedialog.askopenfilename(
                parent=self.root, title=self.t("加载项目"), filetypes=[(self.t("项目文件"), "*.json")],
            )
            if not chosen:
                return None
            path = chosen
        target = Path(path)
        candidate = self._load_candidate(target)
        if candidate is None:
            return None
        saved_inputs = self._saved_inputs
        if not self._confirm_replace():
            return None
        # Saving in the confirmation dialog may overwrite the file selected for loading.
        if self._saved_inputs is not saved_inputs:
            candidate = self._load_candidate(target)
            if candidate is None:
                return None
        for job in (self._calc_job, self._draw_job):
            if job is not None:
                self.root.after_cancel(job)
        self._calc_job = self._draw_job = None
        self.model = candidate
        self._last_good = None
        self._last_good_names = ()
        self._edit_notice = None
        self._error_paths = []
        self.project_path = target
        self._saved_inputs = self.model.to_input_json()
        self._rebuild()
        self.apply_visibility()
        self.render_layers()
        self.calculate_now()
        self.status_var.set(format_text("已加载 {name}", self.language, name=target.name))
        return target

    def _load_candidate(self, target: Path) -> GeneralFormModel | None:
        try:
            item = load_general_project(target)
        except InputValidationError as exc:
            details = "\n".join(f"{self.t(self.model.label_for(error.path))}: {self.t(error.message)}" for error in exc.errors)
            messagebox.showerror(self.t("加载失败"), details, parent=self.root)
            return None
        except (OSError, ValueError) as exc:
            messagebox.showerror(self.t("加载失败"), str(exc), parent=self.root)
            return None
        candidate = GeneralFormModel()
        candidate.reset(item.to_json())
        candidate.set_language(self.language)
        outcome = candidate.calculate(self.language)
        if not outcome.ok:
            messagebox.showerror(self.t("加载失败"), self._outcome_error(outcome), parent=self.root)
            return None
        return candidate

    def request_close(self) -> None:
        if self._confirm_replace():
            self.close()

    def export_report(self, path: str | Path | None = None) -> Path | None:
        if self._calc_job is not None:
            self.calculate_now()
        if self.outcome is None or not self.outcome.ok:
            return None
        if path is None:
            title = _FILENAME_UNSAFE.sub("_", self.model.title.strip() or self.t("通用螺栓连接"))[:60]
            chosen = filedialog.asksaveasfilename(
                parent=self.root, title=self.t("导出计算报告"), defaultextension=".md",
                initialfile=f"VDI2230-{title}.md", filetypes=[(self.t("Markdown 文件"), "*.md")],
            )
            if not chosen:
                return None
            path = chosen
        target = Path(path)
        try:
            write_text_atomic(target, self.outcome.report)
        except OSError as exc:
            messagebox.showerror(self.t("导出失败"), str(exc), parent=self.root)
            return None
        self.status_var.set(format_text("已导出 {name}", self.language, name=target.name))
        return target

    def close(self) -> None:
        for job in (self._calc_job, self._draw_job):
            if job is not None:
                self.root.after_cancel(job)
        self._calc_job = self._draw_job = None
        self.root.destroy()
