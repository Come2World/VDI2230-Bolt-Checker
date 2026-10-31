import argparse
import tkinter as tk


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vdi2230", description="VDI 2230 螺栓连接计算（桌面版）")
    parser.add_argument("--reference", action="store_true", help="打开 B1–B5 固定参考算例验证窗口")
    args = parser.parse_args(argv)
    root = tk.Tk()
    if args.reference:
        from vdi2230.ui.main_window import MainWindow
        from vdi2230.ui.reference_cases import build_reference_cases

        MainWindow(root, build_reference_cases())
    else:
        from vdi2230.ui.general_window import GeneralWindow

        GeneralWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
