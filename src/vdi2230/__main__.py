import tkinter as tk

from vdi2230.ui.main_window import MainWindow
from vdi2230.ui.reference_cases import build_reference_cases


def main() -> None:
    root = tk.Tk()
    MainWindow(root, build_reference_cases())
    root.mainloop()


if __name__ == "__main__":
    main()
