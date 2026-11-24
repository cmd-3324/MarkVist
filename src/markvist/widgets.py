"""Custom Tk widgets."""

from __future__ import annotations

import tkinter as tk


class ViewSwitch(tk.Canvas):
    """Single control for the three view modes: book | split | code."""

    SEGMENTS = ("read", "split", "edit")

    def __init__(self, parent, palette: dict, ui_scale: float, mono_family: str, on_pick):
        self.s = ui_scale
        self.pad = 2 * ui_scale
        self.w = int(32 * ui_scale * len(self.SEGMENTS) + 12 * ui_scale)
        self.h = int(28 * ui_scale)
        super().__init__(
            parent, width=self.w, height=self.h, bd=0, highlightthickness=0,
            cursor="hand2", takefocus=0,
        )
        self.palette = palette
        self.mono_family = mono_family
        self.on_pick = on_pick
        self.mode = "split"
        self._hover = None
        self.bind("<Button-1>", self._on_click)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _e: self._set_hover(None))
        self._draw()

    # -- public ------------------------------------------------------------ #

    def set_palette(self, palette: dict) -> None:
        self.palette = palette
        self._draw()

    def sync(self, mode: str) -> None:
        if mode != self.mode:
            self.mode = mode
            self._draw()

    # -- drawing ----------------------------------------------------------- #

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]
        return self.create_polygon(pts, smooth=True, **kw)

    def _book_icon(self, cx, cy, color) -> None:
        s = self.s
        wdt, hgt = 6.2 * s, 4.4 * s
        for sign in (-1, 1):
            self.create_polygon(
                cx + sign * wdt, cy - hgt,
                cx + sign * 0.7 * s, cy - hgt * 0.72,
                cx + sign * 0.7 * s, cy + hgt,
                cx + sign * wdt, cy + hgt * 0.76,
                fill=color, outline="",
            )

    def _code_icon(self, cx, cy, color) -> None:
        self.create_text(
            cx, cy, text="</>", fill=color,
            font=(self.mono_family, -max(9, int(11 * self.s)), "bold"),
        )

    def _segment(self, index: int) -> tuple[float, float]:
        inner = self.pad + 2 * self.s
        width = (self.w - 2 * inner) / len(self.SEGMENTS)
        x1 = inner + index * width
        return x1, x1 + width

    def _split_icon(self, cx, cy, color) -> None:
        s = self.s
        line = max(1, int(round(1.1 * s)))
        self.create_rectangle(cx - 6 * s, cy - 4.4 * s, cx - s, cy + 4.4 * s,
                              fill=color, outline=color)
        self.create_rectangle(cx + s, cy - 4.4 * s, cx + 6 * s, cy + 4.4 * s,
                              outline=color, width=line)

    def _icon(self, mode: str, cx: float, cy: float, color) -> None:
        if mode == "read":
            self._book_icon(cx, cy, color)
        elif mode == "split":
            self._split_icon(cx, cy, color)
        else:
            self._code_icon(cx, cy, color)

    def _draw(self) -> None:
        self.delete("all")
        p = self.palette
        s = self.s
        w, h = self.w, self.h
        top = self.pad + 2 * s
        bottom = h - self.pad - 2 * s
        radius = (bottom - top) / 2.0

        self.configure(bg=p["bg_soft"])
        self._round_rect(self.pad, self.pad, w - self.pad, h - self.pad,
                         (h - 2 * self.pad) / 2.0, fill=p["bg_inset"], outline=p["border"])

        for index, mode in enumerate(self.SEGMENTS):
            x1, x2 = self._segment(index)
            if mode == self.mode:
                self._round_rect(x1, top, x2, bottom, radius, fill=p["bg"], outline=p["border"])
            elif self._hover == mode:
                self._round_rect(x1, top, x2, bottom, radius, fill=p["bg_soft"], outline="")
            self._icon(mode, (x1 + x2) / 2.0, h / 2.0,
                       p["accent"] if mode == self.mode else p["muted"])

    # -- interaction ------------------------------------------------------- #

    def _mode_at(self, x: int) -> str:
        x1, _x2 = self._segment(0)
        width = self._segment(1)[0] - x1
        index = int(max(0, min(len(self.SEGMENTS) - 1, (x - x1) // width)))
        return self.SEGMENTS[index]

    def _on_click(self, event) -> None:
        self.on_pick(self._mode_at(event.x))

    def _on_motion(self, event) -> None:
        self._set_hover(self._mode_at(event.x))

    def _set_hover(self, value) -> None:
        if value != self._hover:
            self._hover = value
            self._draw()
