import tkinter as tk

from vdi2230.domain.section import SectionGeometry, section_primitives


class SectionView(tk.Canvas):
    def __init__(self, master: tk.Misc, **kwargs: object) -> None:
        super().__init__(master, background="white", highlightthickness=0, **kwargs)
        self._geometry: SectionGeometry | None = None
        self.bind("<Configure>", self._on_resize)

    def set_geometry(self, geometry: SectionGeometry) -> None:
        geometry.validate()
        self._geometry = geometry
        self.redraw()

    def redraw(self) -> None:
        if self._geometry is None:
            return
        if self.winfo_width() < 100 or self.winfo_height() < 100:
            return
        self.delete("all")
        for primitive in section_primitives(
            self.winfo_width(),
            self.winfo_height(),
            self._geometry,
        ):
            if primitive.kind == "line":
                self.create_line(
                    *primitive.coordinates,
                    fill=primitive.outline,
                    dash=(4, 3) if primitive.outline == "#888888" else (),
                    arrow=tk.LAST if primitive.outline == "#c0392b" else tk.NONE,
                )
            elif primitive.kind == "rectangle":
                self.create_rectangle(
                    *primitive.coordinates,
                    fill=primitive.fill,
                    outline=primitive.outline,
                )
            elif primitive.kind == "text":
                self.create_text(
                    *primitive.coordinates,
                    text=primitive.text,
                    fill=primitive.fill or "#263238",
                    anchor=tk.W,
                )

    def _on_resize(self, _event: tk.Event) -> None:
        self.redraw()
