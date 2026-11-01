import argparse
import tkinter as tk

from vdi2230 import __version__


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vdi2230", description="VDI 2230 螺栓连接计算（桌面版）")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    from vdi2230.ui.general_window import GeneralWindow

    root = tk.Tk()
    GeneralWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
