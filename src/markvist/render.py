"""Rendering parsed Markdown into a Tk text widget with tags.

The look aims at a modern document reader: a clear type scale, tinted code
cards with language captions, banded block quotes with an accent bar, real
table grids, task checkboxes and clickable links.

Everything is drawn with Tk text tags (plus small embedded widgets for tables
and horizontal rules), so no third-party packages are needed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from .bidi import visual_runs
from .theme import SIZE_FACTOR

HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


class PreviewRenderer:
    def __init__(
        self,
        widget: tk.Text,
        palette: dict,
        zoom: float,
        ui_scale: float,
        fonts: dict,
        doc_family: str,
        mono_family: str,
        links: dict,
        rtl: bool = False,
        visual_rtl: bool = False,
    ):
        self.w = widget
        self.rtl = rtl
        self.visual_rtl = visual_rtl
        self.p = palette
        self.zoom = zoom
        self.ui_scale = ui_scale
        self._fonts = fonts
        self.doc_family = doc_family
        self.mono_family = mono_family
        self.links = links
        self._fmt: dict = {}
        self._blocks: dict = {}
        self._windows: list[tk.Widget] = []

    # -- metrics ----------------------------------------------------------- #

    def _z(self, value: float) -> int:
        return max(0, int(round(value * self.zoom * self.ui_scale)))

    def _usable_width(self) -> int:
        width = self.w.winfo_width()
        if width < 80:
            width = 760
        return max(240, width - 2 * int(26 * self.ui_scale) - 8)

    # -- fonts / tags ------------------------------------------------------ #

    def _font(self, px: int, bold: bool, italic: bool, mono: bool, strike: bool):
        key = (px, bold, italic, mono, strike)
        font = self._fonts.get(key)
        if font is None:
            font = tkfont.Font(
                family=self.mono_family if mono else self.doc_family,
                size=-px,
                weight="bold" if bold else "normal",
                slant="italic" if italic else "roman",
                overstrike=strike,
            )
            self._fonts[key] = font
        return font

    def _px(self, kind: str) -> int:
        base = 16.0 * self.zoom * self.ui_scale
        if kind == "code":
            return max(9, int(round(14.0 * self.zoom * self.ui_scale)))
        if kind == "caption":
            return max(8, int(round(base * 0.72)))
        return max(9, int(round(base * SIZE_FACTOR.get(kind, 1.0))))

    def _fg(self, kind: str, styles: frozenset, href: str | None) -> str:
        p = self.p
        if "image" in styles:
            return p["muted"]
        if href:
            return p["accent"]
        if "muted" in styles or kind in ("caption", "hr", "h6", "checkbox_off"):
            return p["muted"]
        if kind in ("li_marker", "bar", "checkbox"):
            return p["accent"]
        return p["fg"]

    def fmt(self, kind: str, styles: frozenset = frozenset(), href: str | None = None) -> str:
        key = (kind, frozenset(styles), href)
        tag = self._fmt.get(key)
        if tag is not None:
            return tag

        tag = "mv_f%d" % len(self._fmt)
        mono = kind == "code" or "code" in styles
        bold = "bold" in styles or kind in HEADINGS or kind == "th"
        italic = "italic" in styles or "image" in styles
        font = self._font(self._px("code" if mono else kind), bold, italic, mono, "strike" in styles)

        opts = {"font": font, "foreground": self._fg(kind, styles, href)}
        if "image" in styles:
            opts["background"] = self.p["accent_soft"]
        elif mono:
            opts["background"] = self.p["code_bg"]
        if href:
            opts["underline"] = True
        self.w.tag_configure(tag, **opts)
        if href:
            self.links[tag] = href
        self._fmt[key] = tag
        return tag

    def block(self, name: str, **opts) -> str:
        tag = self._blocks.get(name)
        if tag is not None:
            return tag
        if self.rtl:
            opts.setdefault("justify", "right")
        self.w.tag_configure(name, **opts)
        self._blocks[name] = name
        return name

    # -- block tags -------------------------------------------------------- #

    def _setup_blocks(self) -> None:
        self.block("mv_b_p", spacing1=self._z(2), spacing2=self._z(3),
                   spacing3=self._z(12), lmargin1=0, lmargin2=0)
        for level, above, below in (
            (1, 24, 8),
            (2, 20, 7),
            (3, 16, 6),
            (4, 13, 4),
            (5, 11, 4),
            (6, 11, 4),
        ):
            self.block("mv_b_h%d" % level, spacing1=self._z(above),
                       spacing3=self._z(below), lmargin1=0, lmargin2=0)
        self.block("mv_b_code", spacing1=0, spacing2=0, spacing3=0,
                   lmargin1=self._z(14), lmargin2=self._z(14),
                   background=self.p["code_bg"])
        self.block("mv_b_caption", spacing1=self._z(12), spacing3=0,
                   lmargin1=self._z(14), lmargin2=self._z(14),
                   background=self.p["code_bg"])
        self.block("mv_b_code_gap", spacing3=self._z(14))
        self.block("mv_b_hr", spacing1=self._z(12), spacing3=self._z(12),
                   lmargin1=0, lmargin2=0)
        self.block("mv_b_table", spacing1=0, spacing3=self._z(2), lmargin1=0, lmargin2=0)

    def _quote_block(self, depth: int) -> str:
        return self.block(
            "mv_b_quote%d" % depth,
            spacing1=self._z(3),
            spacing2=self._z(2),
            spacing3=self._z(3),
            lmargin1=self._z(6 + depth * 12),
            lmargin2=self._z(6 + depth * 12),
            rmargin=self._z(8),
            background=self.p["quote_bg"],
        )

    def _li_block(self, level: int, marker: str) -> str:
        indent = self._z(8 + level * 22)
        font = self._font(self._px("body"), False, False, False, False)
        hang = font.measure(marker + "   ")
        return self.block(
            "mv_b_li%d_%d" % (level, len(marker)),
            spacing2=self._z(2),
            spacing3=self._z(4),
            lmargin1=indent,
            lmargin2=indent + hang,
        )

    # -- writing ----------------------------------------------------------- #

    def render(self, blocks: list[dict], keep_scroll: bool = True) -> None:
        w = self.w
        offset = w.yview()[0] if keep_scroll else 0.0
        w.configure(state="normal")
        for child in self._windows:
            try:
                child.destroy()
            except tk.TclError:
                pass
        self._windows.clear()
        w.delete("1.0", "end")
        for tag in [t for t in w.tag_names() if t.startswith("mv_")]:
            w.tag_delete(tag)
        self._fmt.clear()
        self._blocks.clear()
        self.links.clear()
        self._setup_blocks()

        for b in blocks:
            self._block(b)

        w.configure(state="disabled")
        w.yview_moveto(offset)

    def _write(self, tokens: list, kind: str, block_tag: str, suffix=None) -> None:
        if self.visual_rtl and kind != "code":
            tokens = visual_runs(tokens)
        for text, styles, href in tokens:
            if not text:
                continue
            if "image" in styles:
                self.w.insert("end", "▣ ", (block_tag, self.fmt("body", frozenset({"muted"}))))
                self.w.insert("end", text, (block_tag, self.fmt("body", frozenset({"image"}), href)))
            else:
                self.w.insert("end", text, (block_tag, self.fmt(kind, styles, href)))
        if suffix is not None:
            text, styles, href = suffix
            self.w.insert("end", text, (block_tag, self.fmt(kind, styles, href)))

    def _line(self, tokens: list, kind: str, block_tag: str, suffix=None) -> None:
        self._write(tokens, kind, block_tag, suffix)
        self.w.insert("end", "\n", block_tag)

    def _rule(self, before: int = 4, after: int = 4) -> None:
        height = max(1, int(self.ui_scale))
        frame = tk.Frame(self.w, bg=self.p["border"],
                         height=height, width=self._usable_width())
        self._windows.append(frame)
        self.w.window_create("end", window=frame, align="center",
                             pady=self._z(after))
        self.w.insert("end", "\n")

    def _block(self, b: dict) -> None:
        kind = b["kind"]
        if kind == "heading":
            level = b["level"]
            self._line(b["tokens"], "h%d" % level, "mv_b_h%d" % level)
            if level <= 2:
                self._rule()
        elif kind == "para":
            toks: list = []
            for idx, line in enumerate(b["lines"]):
                if idx:
                    toks.append(("\n" if b["hard"][idx - 1] else " ", frozenset(), None))
                toks.extend(line)
            self._line(toks, "body", "mv_b_p")
        elif kind == "code":
            self._code(b)
        elif kind == "quote":
            self._quote(b["blocks"])
        elif kind == "list":
            self._list(b["entries"])
        elif kind == "table":
            self._table(b)
        elif kind == "hr":
            self._rule(before=10, after=10)

    # -- code -------------------------------------------------------------- #

    def _code_capacity(self) -> int:
        font = self._font(self._px("code"), False, False, True, False)
        char = max(1, font.measure("M"))
        return max(20, (self._usable_width() - 2 * self._z(14)) // char)

    def _code_line(self, line: str) -> None:
        body = "  " + line
        body += " " * max(0, self._code_capacity() - len(body))
        self.w.insert("end", body, ("mv_b_code", self.fmt("code")))
        self.w.insert("end", "\n", "mv_b_code")

    def _code(self, b: dict) -> None:
        lang = (b.get("lang") or "").strip()
        if lang:
            self.w.insert("end", lang.upper(), ("mv_b_caption", self.fmt("caption")))
            self.w.insert("end", "\n", "mv_b_caption")
        self._code_line("")
        for line in b["text"].split("\n"):
            self._code_line(line)
        self._code_line("")
        self.w.insert("end", "\n", "mv_b_code_gap")

    # -- quotes ------------------------------------------------------------ #

    def _quote(self, blocks: list[dict], depth: int = 1) -> None:
        tag = self._quote_block(depth)
        for b in blocks:
            kind = b["kind"]
            if kind == "para":
                toks: list = []
                for idx, line in enumerate(b["lines"]):
                    if idx:
                        toks.append((" ", frozenset(), None))
                    toks.extend(line)
                self._quote_line(toks, tag)
            elif kind == "heading":
                self._quote_line(b["tokens"], tag)
            elif kind == "list":
                self._list(b["entries"], block_override=tag)
            elif kind == "code":
                self._code(b)
            elif kind == "quote":
                self._quote(b["blocks"], depth + 1)

    def _quote_line(self, tokens: list, tag: str) -> None:
        if self.rtl:
            self._write(tokens, "body", tag)
            self.w.insert("end", " ▐", (tag, self.fmt("bar")))
        else:
            self.w.insert("end", "▐  ", (tag, self.fmt("bar")))
            self._write(tokens, "body", tag)
        self.w.insert("end", "\n", tag)

    # -- lists ------------------------------------------------------------- #

    def _list(self, entries: list[dict], block_override: str | None = None) -> None:
        for e in entries:
            checked = e["checked"]
            if checked is True:
                marker, kind = "☑", "checkbox"
            elif checked is False:
                marker, kind = "☐", "checkbox_off"
            elif e["ordered"]:
                marker, kind = "%d." % e["number"], "li_marker"
            else:
                marker, kind = "•", "li_marker"

            block_tag = block_override or self._li_block(e["level"], marker)
            if not self.rtl:
                self.w.insert("end", marker, (block_tag, self.fmt(kind)))
                self.w.insert("end", "   ", (block_tag, self.fmt(kind)))

            toks: list = []
            for idx, line in enumerate(e["tokens"]):
                if idx:
                    toks.append((" ", frozenset(), None))
                toks.extend(line)
            if checked:
                toks = [(t, s | {"muted"}, h) for t, s, h in toks]
            self._write(toks, "body", block_tag)

            if self.rtl:
                self.w.insert("end", " " + marker, (block_tag, self.fmt(kind)))
            self.w.insert("end", "\n", block_tag)

    # -- tables ------------------------------------------------------------ #

    def _table(self, b: dict) -> None:
        p = self.p
        rows = [b["head"]] + b["rows"]
        ncols = max((len(r) for r in rows), default=0)
        if not ncols:
            return

        aligns = list(b["aligns"]) + [""] * (ncols - len(b["aligns"]))
        wrap = max(90, self._usable_width() // ncols - self._z(24))
        head_font = self._font(self._px("body"), True, False, False, False)
        body_font = self._font(self._px("body"), False, False, False, False)
        mono_font = self._font(self._px("code"), False, False, True, False)

        outer = tk.Frame(self.w, bg=p["border"])
        grid = tk.Frame(outer, bg=p["border"])
        grid.pack(padx=max(1, self._z(1)), pady=max(1, self._z(1)))

        for ri, row in enumerate(rows):
            head = ri == 0
            if head:
                bg = p["table_head"]
            elif ri % 2 == 1:
                bg = p["table_stripe"]
            else:
                bg = p["bg"]
            for ci in range(ncols):
                tokens = row[ci] if ci < len(row) else []
                text = "".join(t for t, _s, _h in tokens).strip()
                mono = bool(tokens) and all("code" in s for _t, s, _h in tokens)
                align = aligns[ci]
                anchor = {"right": "e", "center": "center"}.get(align, "w")
                justify = {"right": "right", "center": "center"}.get(align, "left")
                label = tk.Label(
                    grid,
                    text=text,
                    bg=bg,
                    fg=p["fg"],
                    font=mono_font if mono else (head_font if head else body_font),
                    anchor=anchor,
                    justify=justify,
                    wraplength=wrap,
                    padx=self._z(9),
                    pady=self._z(6),
                )
                label.grid(row=ri, column=ci, sticky="nsew",
                           padx=(0, max(1, self._z(1))),
                           pady=(0, max(1, self._z(1))))

        self._windows.append(outer)
        self.w.window_create("end", window=outer, align="center", pady=self._z(4))
        self.w.insert("end", "\n", "mv_b_table")
