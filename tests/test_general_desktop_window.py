import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from vdi2230 import __main__ as entry
from vdi2230.ui.general_model import entry_text
from vdi2230.infrastructure.general_section import DRAWING_BACKGROUND, PLATE_FILLS, TEXT_FILL
from vdi2230.ui.general_window import ACCENT, INPUT_BACKGROUND, PANEL, WINDOW_MIN_SIZE, WINDOW_SIZE, GeneralWindow, fit_window


class FitWindowTests(unittest.TestCase):
    def test_large_screen_uses_default_size_centered(self):
        geometry, min_size = fit_window(3840, 2160)
        self.assertEqual(geometry, f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}+1200+433")
        self.assertEqual(min_size, WINDOW_MIN_SIZE)

    def test_laptop_screen_keeps_window_inside(self):
        geometry, _ = fit_window(1512, 982)
        self.assertEqual(geometry, "1440x860+36+40")

    def test_small_screen_shrinks_window_and_min_size(self):
        geometry, min_size = fit_window(1024, 700)
        self.assertEqual(geometry, "984x580+20+40")
        self.assertEqual(min_size, (984, 580))


class WindowPlacementTests(unittest.TestCase):
    def test_window_is_sized_to_the_screen(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk 不可用：{exc}")
        root.withdraw()
        with mock.patch.object(root, "winfo_screenwidth", return_value=1512), \
                mock.patch.object(root, "winfo_screenheight", return_value=982), \
                mock.patch.object(root, "geometry") as geometry:
            window = GeneralWindow(root)
        try:
            geometry.assert_called_once_with("1440x860+36+40")
            self.assertEqual(root.minsize(), WINDOW_MIN_SIZE)
        finally:
            window.close()


class GeneralWindowTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk 不可用：{exc}")
        self.root.withdraw()
        self.window = GeneralWindow(self.root)
        self.window.calculate_now()

    def tearDown(self):
        self.window.close()

    def set_choice(self, path, value):
        label = self.window._choices[path][0][value]
        self.window._vars[path].set(label)

    def tab_text(self, key):
        return self.window.input_tabs.tab(self.window._tab_index[key], "text")

    def test_default_case_renders_checks_section_and_report(self):
        window = self.window
        self.assertEqual(window.verdict_label.cget("text"), "需确认 · 数据待核验")
        self.assertIn("SF", window.check_tree.get_children())
        self.assertEqual(window.check_tree.set("SF", "status"), "通过")
        self.assertTrue(window.canvas.find_withtag("plate-0"))
        self.assertTrue(window.canvas.find_withtag("plate-1"))
        self.assertFalse(window.canvas.find_withtag("stale"))
        self.assertIn("lK 40 mm", window.metrics_var.get())
        self.assertIn("通用螺栓连接", window.report())
        self.assertTrue(window.values_tree.get_children())
        self.assertTrue(window.export_button.instate(["!disabled"]))

    def test_language_switch_preserves_inputs_selection_and_exports_english(self):
        window = self.window
        window.title_var.set("保留项目标题")
        window._vars["bolt.bearing_friction"].set("0.10")
        window.model.set_layer_value(1, "name", "用户板层")
        window.select_layer(1, reveal=True)
        before = window.calculate_now()
        inputs = window.model.to_input_json()
        window.language_var.set("English")
        window.language_selector.event_generate("<<ComboboxSelected>>")
        self.root.update()
        self.assertEqual(window.language, "en")
        self.assertEqual(window._vars["bolt.bearing_friction"].get(), "0.10")
        self.assertEqual(window.model.to_input_json(), inputs)
        self.assertEqual(window.model.selected, 1)
        self.assertEqual(window.input_tabs.index("current"), window._tab_index["plates"])
        self.assertEqual(window.check_tree.set("SF", "status"), "Pass")
        self.assertEqual(window.outcome.result.value("MA"), before.result.value("MA"))
        self.assertIn("保留项目标题", window.report())
        self.assertIn("Bearing friction μK", window.report())
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report-en.txt"
            window.export_report(target)
            self.assertEqual(target.read_text(encoding="utf-8"), window.report())
        window.set_language("zh")
        self.assertEqual(window.model.to_input_json(), inputs)
        self.assertIn("计算报告", window.report())
        self.assertEqual(window.check_tree.set("SF", "status"), "通过")

    def test_language_switch_keeps_invalid_input_and_localizes_stale_section(self):
        window = self.window
        window._vars["bolt.d"].set("abc")
        window.calculate_now()
        window.set_language("en")
        self.assertEqual(window._vars["bolt.d"].get(), "abc")
        self.assertFalse(window.outcome.ok)
        self.assertIn("Invalid input", window.outcome.error)
        self.assertTrue(window.export_button.instate(["disabled"]))
        self.assertTrue(window.canvas.find_withtag("stale"))
        labels = [window.canvas.itemcget(item, "text") for item in window.canvas.find_withtag("label-head")
                  if window.canvas.type(item) == "text"]
        self.assertTrue(any("Bolt head" in label for label in labels))

    def test_values_filter_narrows_the_list(self):
        window = self.window
        total = len(window.values_tree.get_children())
        window.filter_var.set("FMzul")
        filtered = len(window.values_tree.get_children())
        self.assertGreater(filtered, 0)
        self.assertLess(filtered, total)

    def test_adding_a_layer_redraws_the_section(self):
        window = self.window
        window.add_layer()
        self.assertTrue(window.export_button.instate(["disabled"]))
        outcome = window.calculate_now()
        self.assertTrue(outcome.ok, outcome.error)
        self.assertTrue(window.canvas.find_withtag("plate-2"))
        self.assertEqual(window.layer_list.size(), 3)
        self.assertEqual(window.selected_var.get(), "选中：2. 板 3")
        self.assertEqual(window._vars["plates[1].name"].get(), "板 3")
        self.assertIn("lK 60 mm", window.metrics_var.get())

    def test_layer_buttons_follow_selection(self):
        window = self.window
        self.assertTrue(window.layer_buttons["up"].instate(["disabled"]))
        self.assertTrue(window.layer_buttons["down"].instate(["!disabled"]))
        window.move_layer(1)
        self.assertEqual(window.model.selected, 1)
        self.assertTrue(window.layer_buttons["down"].instate(["disabled"]))
        window.remove_layer()
        self.assertEqual(window.layer_list.size(), 1)
        self.assertTrue(window.layer_buttons["remove"].instate(["disabled"]))

    def test_invalid_input_is_flagged_and_can_be_fixed(self):
        window = self.window
        window._vars["plates[0].thickness"].set("abc")
        outcome = window.calculate_now()
        self.assertFalse(outcome.ok)
        self.assertEqual(window.verdict_label.cget("text"), "输入有误")
        self.assertEqual(window.error_list.size(), 1)
        self.assertEqual(window.error_list.winfo_manager(), "pack")
        self.assertIn("板层 1 · 厚度 h", window.error_list.get(0))
        self.assertTrue(window.export_button.instate(["disabled"]))
        self.assertIsNone(window.export_report(Path(tempfile.gettempdir()) / "never.txt"))
        self.assertEqual(self.tab_text("plates"), "板层 ✕")
        self.assertEqual(window._rows["plates[0].thickness"][2].cget("text"), "✕")
        self.assertTrue(window.canvas.find_withtag("plate-0"), "last valid section stays visible")
        self.assertTrue(window.canvas.find_withtag("stale"))
        self.assertEqual(window.report(), "")

        window.input_tabs.select(window._tab_index["load"])
        window.error_list.selection_set(0)
        window._on_error_select()
        self.assertEqual(window.input_tabs.index("current"), window._tab_index["plates"])

        window._vars["plates[0].thickness"].set("20")
        self.assertTrue(window.calculate_now().ok)
        self.assertEqual(self.tab_text("plates"), "板层")
        self.assertEqual(window.error_list.winfo_manager(), "")
        self.assertFalse(window.canvas.find_withtag("stale"))

    def test_catalog_variant_fills_geometry(self):
        window = self.window
        self.set_choice("bolt.catalog_variant_id", "ISO4014-M16x2.0")
        self.assertEqual(window._vars["bolt.d"].get(), "16")
        self.assertEqual(window._vars["bolt.pitch"].get(), "2")
        self.assertEqual(window._rows["bolt.d"][2].cget("text"), "●")
        self.assertTrue(window.calculate_now().ok)
        self.assertIn("M16", window.report())

    def test_user_override_clears_catalog_marker(self):
        window = self.window
        window._vars["bolt.head_bearing_diameter"].set("17")
        self.assertEqual(window.model.values["bolt.head_bearing_diameter"], 17.0)
        self.assertEqual(window._rows["bolt.head_bearing_diameter"][2].cget("text"), "")

    def test_material_choice_fills_layer_fields(self):
        window = self.window
        record = window.model.materials["42CrMo4"]
        self.set_choice("plates[0].material_id", "42CrMo4")
        self.assertEqual(window._vars["plates[0].youngs_modulus"].get(), entry_text(record["youngs_modulus"]))
        self.assertIn("42CrMo4", window.layer_list.get(0))

    def test_esv_switches_visible_fields(self):
        window = self.window
        self.assertTrue(window.is_field_visible("nut.height"))
        self.assertFalse(window.is_field_visible("tapped.youngs_modulus"))
        self.set_choice("joint.type", "ESV")
        self.assertFalse(window.is_field_visible("nut.height"))
        self.assertTrue(window.is_field_visible("tapped.youngs_modulus"))
        headers = {header.cget("text"): header.winfo_manager() for header, _ in window._sections}
        self.assertEqual(headers["螺母（DSV）"], "")
        self.assertEqual(headers["内螺纹件（ESV）"], "grid")
        self.assertTrue(window.calculate_now().ok)

    def test_washers_update_geometry_and_keep_manual_values(self):
        window = self.window
        for side in ("head", "nut"):
            window._vars[f"{side}_washer.enabled"].set(True)
        self.assertTrue(window.calculate_now().ok)
        self.assertIn("lK 43.84 mm", window.metrics_var.get())
        self.assertTrue(window.canvas.find_withtag("washer-head"))
        self.assertTrue(window.canvas.find_withtag("washer-nut"))
        window._vars["head_washer.thickness"].set("3")
        self.set_choice("bolt.catalog_variant_id", "ISO4014-M16x2.0")
        self.assertEqual(window._vars["head_washer.thickness"].get(), "3")
        self.assertEqual(window._vars["head_washer.inner_diameter"].get(), "17.6")
        self.assertTrue(window.calculate_now().ok)
        self.assertIn("lK 45.56 mm", window.metrics_var.get())
        self.set_choice("joint.type", "ESV")
        self.assertFalse(window.is_field_visible("nut_washer.enabled"))
        self.assertTrue(window.calculate_now().ok)
        self.assertFalse(window.canvas.find_withtag("washer-nut"))

    def test_native_part_hit_testing_reveals_corresponding_pages(self):
        window = self.window
        window._vars["head_washer.enabled"].set(True)
        window._vars["nut_washer.enabled"].set(True)
        window.calculate_now()
        for role, group in (("bolt-head", "bolt"), ("bolt-shank", "bolt"), ("nut", "bolt"),
                            ("washer-head", "plates"), ("washer-nut", "plates"), ("plate-1", "plates")):
            with self.subTest(role=role):
                window.input_tabs.select(window._tab_index["load"])
                shape = next(item for item in window.canvas.find_withtag(role)
                             if window.canvas.type(item) in ("rectangle", "polygon"))
                x0, y0, x1, y1 = window.canvas.bbox(shape)
                event = SimpleNamespace(x=(x0 + x1) / 2, y=(y0 + y1) / 2)
                self.assertTrue(window._section_target(event))
                window._on_section_click(event)
                self.assertEqual(window.input_tabs.index("current"), window._tab_index[group])
        self.assertEqual(window.model.selected, 1)

    def test_real_canvas_click_event_reveals_washer_and_bolt_fields(self):
        window = self.window
        self.root.deiconify()
        self.root.geometry("1280x720+40+80")
        window._vars["head_washer.enabled"].set(True)
        self.root.update()
        window.calculate_now()
        self.root.update()
        for role, group, field in (("washer-head", "plates", "head_washer.thickness"),
                                   ("bolt-head", "bolt", "bolt.head_height"),
                                   ("nut", "bolt", "nut.height")):
            window.input_tabs.select(window._tab_index["load"])
            self.root.update()
            shape = window.canvas.find_withtag(role)[0]
            x0, y0, x1, y1 = window.canvas.bbox(shape)
            window.canvas.event_generate("<Button-1>", x=round((x0 + x1) / 2), y=round((y0 + y1) / 2))
            self.root.update()
            self.assertEqual(window.input_tabs.index("current"), window._tab_index[group])
            widget = window._widgets[field]
            scroller = window._scrollers[group]
            top = widget.winfo_rooty() - scroller.canvas.winfo_rooty()
            self.assertGreaterEqual(top, 0)
            self.assertLess(top + widget.winfo_height(), scroller.canvas.winfo_height())

    def test_washer_errors_point_to_plate_page_and_bolt_frictions_are_independent(self):
        window = self.window
        window._vars["head_washer.enabled"].set(True)
        window._vars["head_washer.inner_diameter"].set("20")
        self.assertFalse(window.calculate_now().ok)
        self.assertIn("头侧垫片", window.error_list.get(0))
        window.go_to_field("head_washer.inner_diameter")
        self.assertEqual(window.input_tabs.index("current"), window._tab_index["plates"])
        window._vars["head_washer.inner_diameter"].set("13.2")
        window._vars["bolt.bearing_friction"].set("0.10")
        window._vars["bolt.thread_friction"].set("0.18")
        outcome = window.calculate_now()
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.result.value("μK"), 0.10)
        self.assertEqual(window._vars["bolt.bearing_friction"].get(), "0.10")
        self.assertNotIn("plates[0].bearing_friction", window._vars)

    def test_cyberpunk_theme_covers_native_and_ttk_widgets(self):
        window = self.window
        style = ttk.Style(self.root)
        self.assertEqual(style.theme_use(), "clam")
        self.assertEqual(style.lookup("TEntry", "fieldbackground"), INPUT_BACKGROUND)
        self.assertEqual(style.lookup("TCombobox", "fieldbackground", ("readonly",)), INPUT_BACKGROUND)
        self.assertEqual(style.lookup("TFrame", "background"), PANEL)
        self.assertEqual(window.canvas.cget("background"), DRAWING_BACKGROUND)
        self.assertEqual(window.report_text.cget("background"), INPUT_BACKGROUND)
        self.assertEqual(window.report_text.cget("foreground"), TEXT_FILL)
        self.assertEqual(window.layer_list.cget("background"), INPUT_BACKGROUND)
        self.assertEqual(window._rows["bolt.d"][2].cget("background"), PANEL)

    def test_compression_cone_is_transparent_and_plate_fill_is_preserved(self):
        window = self.window
        cones = window.canvas.find_withtag("cone")
        self.assertEqual(len(cones), 2)
        for cone in cones:
            self.assertEqual(window.canvas.itemcget(cone, "fill"), "")
            self.assertTrue(window.canvas.itemcget(cone, "outline"))
            self.assertTrue(window.canvas.itemcget(cone, "dash"))
        plates = [item for item in window.canvas.find_withtag("plate-0") if window.canvas.type(item) == "rectangle"]
        self.assertEqual(len(plates), 2)
        self.assertTrue(all(window.canvas.itemcget(item, "fill") == PLATE_FILLS[0] for item in plates))
        self.assertTrue(window.canvas.find_withtag("grid"))

    def test_layer_selection_highlights_plate_and_reveals_tab(self):
        window = self.window
        window.select_layer(1, reveal=True)
        self.assertEqual(window.input_tabs.index("current"), window._tab_index["plates"])
        outlines = {
            tag: window.canvas.itemcget(window.canvas.find_withtag(tag)[0], "outline") for tag in ("plate-0", "plate-1")
        }
        self.assertEqual(outlines["plate-1"], ACCENT)
        self.assertNotEqual(outlines["plate-0"], ACCENT)

    def test_title_change_flows_into_report(self):
        window = self.window
        window.title_var.set("法兰连接 A")
        window.calculate_now()
        self.assertIn("法兰连接 A", window.report())

    def test_export_writes_the_report(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "report.txt"
            self.assertEqual(self.window.export_report(target), target)
            self.assertEqual(target.read_text(encoding="utf-8"), self.window.report())
        self.assertEqual(self.window.status_var.get(), "已导出 report.txt")

    def test_reference_window_opens_as_toplevel(self):
        reference = self.window.open_reference()
        self.assertIsInstance(reference, tk.Toplevel)
        self.assertIn("VDI", reference.title())
        reference.destroy()


class EntryPointTests(unittest.TestCase):
    def test_help_exits_cleanly(self):
        with mock.patch("sys.stdout"), self.assertRaises(SystemExit) as context:
            entry.main(["--help"])
        self.assertEqual(context.exception.code, 0)

    def test_default_launches_general_window(self):
        with mock.patch.object(entry.tk, "Tk") as tk_class, \
                mock.patch("vdi2230.ui.general_window.GeneralWindow") as window_class:
            entry.main([])
        window_class.assert_called_once_with(tk_class.return_value)
        tk_class.return_value.mainloop.assert_called_once()

    def test_reference_flag_launches_reference_window(self):
        with mock.patch.object(entry.tk, "Tk") as tk_class, \
                mock.patch("vdi2230.ui.main_window.MainWindow") as window_class, \
                mock.patch("vdi2230.ui.reference_cases.build_reference_cases", return_value=["cases"]):
            entry.main(["--reference"])
        window_class.assert_called_once_with(tk_class.return_value, ["cases"])


if __name__ == "__main__":
    unittest.main()
