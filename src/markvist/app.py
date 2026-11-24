"""The markvist window: toolbar, tabs, panes, menus and file handling."""

from __future__ import annotations

import re
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox

from .document import Document
from .markdown import detect_rtl, parse_markdown
from .prefs import read_config, write_config
from .render import PreviewRenderer
from .theme import (
    APP_NAME,
    DIRECTION_LABELS,
    EDITOR_FONTS,
    MAX_TABS,
    MD_SUFFIXES,
    MODES,
    PALETTES,
    READING_FONTS,
)
from .widgets import ViewSwitch


def tk_supports_bidi() -> bool:
    """Tk gained bidirectional text support in 9.1."""
    try:
        major, minor = (int(part) for part in str(tk.TkVersion).split(".")[:2])
    except (TypeError, ValueError, StopIteration):
        return False
    return (major, minor) >= (9, 1)


def pick_family(*candidates: str, fallback: str, available: set[str]) -> str:
    for name in candidates:
        if name in available:
            return name
    return fallback


class Markvist:
    def __init__(self, root: tk.Tk, path: str | None = None):
        self.root = root
        self.docs: list[Document] = []
        self.active = 0
        self.shown: int | None = None  # which document currently sits in the editor
        self.recent: list[str] = []

        self.mode = "split"
        self.theme = "light"
        self.zoom = 1.0
        self.autosave = True
        self.direction = "auto"
        self.rtl = False
        self.visual_rtl = True
        self.bidi_supported = tk_supports_bidi()
        self.doc_family = ""
        self.editor_font = ""
        self.fonts: dict = {}
        self.links: dict = {}
        self._render_job = None
        self._preview_width = 0
        self._autosave_job = None
        self._loading = False

        self._load_prefs()

        self.ui_scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self._families = set(tkfont.families())
        self.app_family = pick_family(
            "Segoe UI", "Inter", "Helvetica Neue",
            fallback="TkDefaultFont", available=self._families,
        )
        if self.doc_family not in self._families:
            self.doc_family = self.app_family
        self.mono_family = (
            self.editor_font if self.editor_font in self._families
            else pick_family("Cascadia Mono", "Cascadia Code", "Consolas", "JetBrains Mono",
                             "Courier New", fallback="TkFixedFont", available=self._families)
        )
        self.palette = PALETTES[self.theme]

        self._build_ui()
        self._paint()
        self._apply_fonts()

        if path:
            self._open_paths([path])
        else:
            self._show_welcome()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # -- preferences ------------------------------------------------------- #

    def _load_prefs(self) -> None:
        self._geometry = "1120x780"
        data = read_config()
        if data.get("theme") in PALETTES:
            self.theme = data["theme"]
        if data.get("mode") in MODES:
            self.mode = data["mode"]
        if data.get("direction") in ("auto", "ltr", "rtl"):
            self.direction = data["direction"]
        try:
            self.zoom = min(2.4, max(0.6, float(data.get("zoom", 1.0))))
        except (TypeError, ValueError):
            pass
        self.autosave = bool(data.get("autosave", True))
        self.visual_rtl = bool(data.get("visual_rtl", True))
        if isinstance(data.get("read_font"), str):
            self.doc_family = data["read_font"]
        if isinstance(data.get("editor_font"), str):
            self.editor_font = data["editor_font"]
        if isinstance(data.get("geometry"), str):
            self._geometry = data["geometry"]
        if isinstance(data.get("recent"), list):
            self.recent = [r for r in data["recent"] if isinstance(r, str)][:8]

    def save_prefs(self) -> None:
        data = {
            "theme": self.theme,
            "mode": self.mode,
            "zoom": round(self.zoom, 2),
            "autosave": self.autosave,
            "direction": self.direction,
            "visual_rtl": self.visual_rtl,
            "read_font": self.doc_family,
            "editor_font": self.mono_family,
            "recent": self.recent,
        }
        try:
            data["geometry"] = self.root.geometry()
        except tk.TclError:
            pass
        write_config(data)

    def _remember_recent(self, path: Path) -> None:
        value = str(path)
        self.recent = [value] + [r for r in self.recent if r != value]
        self.recent = self.recent[:8]
        self.save_prefs()

    # -- widgets ----------------------------------------------------------- #

    def _build_ui(self) -> None:
        root = self.root
        root.title(APP_NAME)
        root.geometry(self._geometry)
        root.minsize(760, 460)

        self._build_menu()

        # toolbar ---------------------------------------------------------- #
        self.toolbar = tk.Frame(root, height=int(44 * self.ui_scale))
        self.toolbar.pack_propagate(False)

        self.brand_mark = tk.Label(self.toolbar, text="M", width=2, height=1)
        self.brand_mark.pack(side="left", padx=(10, 6), pady=9)
        self.brand = tk.Label(self.toolbar, text="markvist")
        self.brand.pack(side="left", padx=(0, 12))

        self.new_btn = self._button(self.toolbar, "+", self.new_file, width=2)
        self.new_btn.pack(side="left", pady=7)
        self.open_btn = self._button(self.toolbar, "Open .md", self.open_file)
        self.open_btn.pack(side="left", padx=(6, 0), pady=7)

        self.file_label = tk.Label(self.toolbar, text="markvist", anchor="w", width=22)
        self.file_label.pack(side="left", padx=(12, 4))

        self.dirty_label = tk.Label(self.toolbar, text="●")
        self.dirty_label.pack(side="left")

        spacer = tk.Frame(self.toolbar)
        spacer.pack(side="left", fill="x", expand=True)

        self.save_btn = self._button(self.toolbar, "Save", self.save_file)
        self.save_btn.pack(side="right", padx=(6, 10), pady=7)

        self.theme_btn = self._button(self.toolbar, "☾", self.toggle_theme, width=3)
        self.theme_btn.pack(side="right", padx=4)

        self.zoom_in_btn = self._button(self.toolbar, "+", lambda: self.zoom_by(0.1), width=2)
        self.zoom_in_btn.pack(side="right")
        self.zoom_label = tk.Label(self.toolbar, text="100%", width=5)
        self.zoom_label.pack(side="right")
        self.zoom_out_btn = self._button(self.toolbar, "−", lambda: self.zoom_by(-0.1), width=2)
        self.zoom_out_btn.pack(side="right")

        self.view_switch = ViewSwitch(
            self.toolbar, self.palette, self.ui_scale, self.mono_family, on_pick=self.set_mode
        )
        self.view_switch.pack(side="right", padx=(0, 10), pady=7)
        self.view_switch.sync(self.mode)

        # content: tab strip + panes or start screen ----------------------- #
        self.content = tk.Frame(root)

        self.tabbar = tk.Frame(self.content, height=int(30 * self.ui_scale))
        self.tabbar.pack_propagate(False)

        self.paned = tk.PanedWindow(self.content, orient="horizontal", bd=0, sashwidth=6,
                                    sashrelief="flat")

        self.editor_frame = tk.Frame(self.paned)
        self.preview_frame = tk.Frame(self.paned)

        self.editor = tk.Text(
            self.editor_frame,
            wrap="word",
            undo=True,
            bd=0,
            highlightthickness=0,
            padx=int(18 * self.ui_scale),
            pady=int(16 * self.ui_scale),
            insertwidth=2,
            spacing1=1,
            tabs=("2c",),
        )
        self.editor_scroll = tk.Scrollbar(self.editor_frame, command=self.editor.yview, width=11)
        self.editor.configure(yscrollcommand=self.editor_scroll.set)
        self.editor_scroll.pack(side="right", fill="y")
        self.editor.pack(side="left", fill="both", expand=True)

        self.preview = tk.Text(
            self.preview_frame,
            wrap="word",
            bd=0,
            highlightthickness=0,
            padx=int(26 * self.ui_scale),
            pady=int(20 * self.ui_scale),
            cursor="arrow",
            state="disabled",
            takefocus=1,
        )
        self.preview_scroll = tk.Scrollbar(self.preview_frame, command=self.preview.yview, width=11)
        self.preview.configure(yscrollcommand=self.preview_scroll.set)
        self.preview_scroll.pack(side="right", fill="y")
        self.preview.pack(side="left", fill="both", expand=True)

        self.preview.bind("<Button-1>", self._on_preview_click)
        self.preview.bind("<Motion>", self._on_preview_motion)
        self.preview.bind("<Configure>", self._on_preview_resize)
        for key in ("<Up>", "<Down>", "<Prior>", "<Next>", "<Home>", "<End>"):
            self.preview.bind(key, self._on_preview_key)
        for widget in (self.editor, self.preview):
            widget.bind("<MouseWheel>", self._on_wheel)
            if sys.platform != "win32":
                widget.bind("<Button-4>", self._on_wheel)
                widget.bind("<Button-5>", self._on_wheel)
        # Fallback for when the event is delivered somewhere else entirely
        # (Tk sends wheel events to the focused widget, not the hovered one).
        self.root.bind_all("<MouseWheel>", self._on_wheel)
        if sys.platform != "win32":
            self.root.bind_all("<Button-4>", self._on_wheel)
            self.root.bind_all("<Button-5>", self._on_wheel)

        self.editor.bind("<<Modified>>", self._on_modified)
        self.editor.bind("<Tab>", self._on_tab)

        # start screen ---------------------------------------------------- #
        self.welcome = tk.Frame(self.content)
        self.welcome_inner = tk.Frame(self.welcome)
        self.welcome_inner.place(relx=0.5, rely=0.44, anchor="center")
        self.welcome_title = tk.Label(self.welcome_inner, text="markvist")
        self.welcome_title.pack()
        self.welcome_sub = tk.Label(
            self.welcome_inner, text="Open a Markdown file, or start a new one."
        )
        self.welcome_sub.pack(pady=(2, 16))
        welcome_row = tk.Frame(self.welcome_inner)
        welcome_row.pack()
        self.welcome_buttons = [
            self._button(welcome_row, "New file", self.new_file),
            self._button(welcome_row, "Open file…", self.open_file),
            self._button(welcome_row, "Open folder…", self.open_folder),
        ]
        for button in self.welcome_buttons:
            button.pack(side="left", padx=4)
        self.recent_frame = tk.Frame(self.welcome_inner)
        self.recent_frame.pack(pady=(18, 0))

        # status bar ------------------------------------------------------ #
        self.status = tk.Frame(root, height=int(26 * self.ui_scale))
        self.status.pack_propagate(False)
        self.stats_label = tk.Label(self.status, text="", anchor="w")
        self.stats_label.pack(side="left", padx=(14, 10))
        self.dir_label = tk.Label(self.status, text="", anchor="w")
        self.dir_label.pack(side="left")
        self.hint_label = tk.Label(
            self.status,
            text="Ctrl+N new · Ctrl+O open · Ctrl+S save · Ctrl+=/− zoom · Ctrl+E mode · Ctrl+W close",
            anchor="e",
        )
        self.hint_label.pack(side="right", padx=(10, 14))

        self.toolbar.pack(side="top", fill="x")
        self.status.pack(side="bottom", fill="x")
        self.content.pack(side="top", fill="both", expand=True)

        self._bind_shortcuts()

    def _button(self, parent, text, command, width=None):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bd=0,
            padx=10,
            pady=4,
            highlightthickness=0,
            cursor="hand2",
            width=width,
            takefocus=0,
        )

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New file", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="Open…", accelerator="Ctrl+O", command=self.open_file)
        file_menu.add_command(label="Open folder…", accelerator="Ctrl+Shift+O",
                              command=self.open_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_command(label="Save as…", accelerator="Ctrl+Shift+S",
                              command=lambda: self.save_file(save_as=True))
        file_menu.add_separator()
        file_menu.add_command(label="Close tab", accelerator="Ctrl+W", command=self.close_tab)
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Read only", accelerator="Ctrl+E",
                              command=lambda: self.set_mode("read"))
        view_menu.add_command(label="Split", command=lambda: self.set_mode("split"))
        view_menu.add_command(label="Edit only", command=lambda: self.set_mode("edit"))
        view_menu.add_separator()
        view_menu.add_command(label="Next tab", accelerator="Ctrl+Tab", command=self.next_tab)
        view_menu.add_command(label="Previous tab", command=self.previous_tab)
        view_menu.add_separator()
        view_menu.add_command(label="Zoom in", accelerator="Ctrl+=", command=lambda: self.zoom_by(0.1))
        view_menu.add_command(label="Zoom out", accelerator="Ctrl+-", command=lambda: self.zoom_by(-0.1))
        view_menu.add_command(label="Reset zoom", accelerator="Ctrl+0", command=lambda: self.set_zoom(1.0))
        view_menu.add_separator()

        self.autosave_var = tk.BooleanVar(value=self.autosave)
        view_menu.add_checkbutton(label="Auto save", variable=self.autosave_var,
                                  command=self.set_autosave)

        font_menu = tk.Menu(view_menu, tearoff=0)
        self.read_font_var = tk.StringVar(value=self.doc_family)
        reading = tk.Menu(font_menu, tearoff=0)
        for name in [f for f in READING_FONTS if f in self._families] or [self.doc_family]:
            reading.add_radiobutton(label=name, value=name, variable=self.read_font_var,
                                    command=lambda n=name: self.set_read_font(n))
        font_menu.add_cascade(label="Reading font", menu=reading)

        self.editor_font_var = tk.StringVar(value=self.mono_family)
        editing = tk.Menu(font_menu, tearoff=0)
        for name in [f for f in EDITOR_FONTS if f in self._families] or [self.mono_family]:
            editing.add_radiobutton(label=name, value=name, variable=self.editor_font_var,
                                    command=lambda n=name: self.set_editor_font(n))
        font_menu.add_cascade(label="Editor font", menu=editing)
        view_menu.add_cascade(label="Font", menu=font_menu)

        self.direction_var = tk.StringVar(value=self.direction)
        direction_menu = tk.Menu(view_menu, tearoff=0)
        for value, label in DIRECTION_LABELS:
            direction_menu.add_radiobutton(label=label, value=value, variable=self.direction_var,
                                           command=lambda v=value: self.set_direction(v))
        view_menu.add_cascade(label="Text direction", menu=direction_menu)

        self.visual_rtl_var = tk.BooleanVar(value=self.visual_rtl)
        view_menu.add_checkbutton(label="Visual RTL preview", variable=self.visual_rtl_var,
                                  command=self.set_visual_rtl)

        view_menu.add_separator()
        view_menu.add_command(label="Light theme", command=lambda: self.set_theme("light"))
        view_menu.add_command(label="Dark theme", command=lambda: self.set_theme("dark"))
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Keyboard shortcuts", command=self.show_help)
        help_menu.add_command(label="About RTL support", command=self.show_rtl_help)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.configure(menu=menubar)
        self.menubar = menubar

    def _bind_shortcuts(self) -> None:
        root = self.root
        root.bind_all("<Control-o>", lambda _e: self._then_break(self.open_file))
        root.bind_all("<Control-O>", lambda _e: self._then_break(self.open_folder))
        root.bind_all("<Control-n>", lambda _e: self._then_break(self.new_file))
        root.bind_all("<Control-N>", lambda _e: self._then_break(self.new_file))
        root.bind_all("<Control-s>", lambda _e: self._then_break(self.save_file))
        root.bind_all("<Control-S>", lambda _e: self._then_break(lambda: self.save_file(True)))
        root.bind_all("<Control-w>", lambda _e: self._then_break(self.close_tab))
        root.bind_all("<Control-W>", lambda _e: self._then_break(self.close_tab))
        root.bind_all("<Control-e>", lambda _e: self._then_break(self.cycle_mode))
        root.bind_all("<Control-t>", lambda _e: self._then_break(self.toggle_theme))
        root.bind_all("<Control-Tab>", lambda _e: self._then_break(self.next_tab))
        root.bind_all("<Control-Shift-Tab>", lambda _e: self._then_break(self.previous_tab))
        for seq in ("<Control-equal>", "<Control-plus>", "<Control-KP_Add>"):
            root.bind_all(seq, lambda _e: self._then_break(lambda: self.zoom_by(0.1)))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>", "<Control-underscore>"):
            root.bind_all(seq, lambda _e: self._then_break(lambda: self.zoom_by(-0.1)))
        for seq in ("<Control-Key-0>", "<Control-KP_0>"):
            root.bind_all(seq, lambda _e: self._then_break(lambda: self.set_zoom(1.0)))

    @staticmethod
    def _then_break(fn):
        fn()
        return "break"

    # -- theme ------------------------------------------------------------- #

    def _paint(self) -> None:
        p = self.palette
        self.root.configure(bg=p["bg"])
        self.toolbar.configure(bg=p["bg_soft"])
        self.status.configure(bg=p["bg_soft"])
        self.content.configure(bg=p["bg"])
        self.tabbar.configure(bg=p["bg_soft"])
        self.paned.configure(bg=p["border"])
        self.editor_frame.configure(bg=p["bg_soft"])
        self.preview_frame.configure(bg=p["bg"])
        self.welcome.configure(bg=p["bg"])
        self.welcome_inner.configure(bg=p["bg"])
        self.recent_frame.configure(bg=p["bg"])

        self.welcome_title.configure(bg=p["bg"], fg=p["fg"],
                                     font=(self.app_family, -int(30 * self.ui_scale), "bold"))
        self.welcome_sub.configure(bg=p["bg"], fg=p["muted"],
                                   font=(self.app_family, -int(13 * self.ui_scale)))

        self.brand.configure(bg=p["bg_soft"], fg=p["fg"],
                             font=(self.app_family, -int(14 * self.ui_scale), "bold"))
        self.brand_mark.configure(bg=p["accent"], fg=p["bg"],
                                  font=(self.app_family, -int(12 * self.ui_scale), "bold"))
        self.file_label.configure(bg=p["bg_soft"], fg=p["muted"],
                                  font=(self.app_family, -int(12 * self.ui_scale)))
        self.dirty_label.configure(bg=p["bg_soft"], fg=p["accent"],
                                   font=(self.app_family, -int(12 * self.ui_scale)))
        self.zoom_label.configure(bg=p["bg_soft"], fg=p["muted"],
                                  font=(self.app_family, -int(12 * self.ui_scale)))
        self.stats_label.configure(bg=p["bg_soft"], fg=p["muted"],
                                   font=(self.app_family, -int(11 * self.ui_scale)))
        self.hint_label.configure(bg=p["bg_soft"], fg=p["muted"],
                                  font=(self.app_family, -int(11 * self.ui_scale)))
        self.dir_label.configure(bg=p["bg_soft"], fg=p["accent"],
                                 font=(self.app_family, -int(11 * self.ui_scale), "bold"))

        buttons = [
            self.open_btn, self.new_btn, self.save_btn, self.theme_btn,
            self.zoom_in_btn, self.zoom_out_btn, *self.welcome_buttons,
        ]
        for btn in buttons:
            btn.configure(
                bg=p["bg"],
                fg=p["fg"],
                activebackground=p["bg_inset"],
                activeforeground=p["fg"],
                font=(self.app_family, -int(12 * self.ui_scale)),
                disabledforeground=p["muted"],
            )

        for scroll in (self.editor_scroll, self.preview_scroll):
            scroll.configure(
                bg=p["bg_inset"],
                troughcolor=p["bg_soft"] if scroll is self.editor_scroll else p["bg"],
                activebackground=p["border"],
                highlightthickness=0,
                bd=0,
                relief="flat",
                width=11,
            )

        self.editor.configure(
            bg=p["bg_soft"],
            fg=p["fg"],
            insertbackground=p["accent"],
            selectbackground=p["accent_soft"],
            selectforeground=p["fg"],
        )
        self.preview.configure(
            bg=p["bg"],
            fg=p["fg"],
            selectbackground=p["accent_soft"],
            selectforeground=p["fg"],
        )
        self.theme_btn.configure(text="☾" if self.theme == "light" else "☀")
        self.view_switch.set_palette(p)
        self.view_switch.sync(self.mode)

        self._rebuild_tabs()
        self._build_recent()
        self._update_title()

    def set_theme(self, theme: str) -> None:
        if theme not in PALETTES:
            return
        self.theme = theme
        self.palette = PALETTES[theme]
        self.fonts.clear()
        self._paint()
        self.render_preview()
        self.save_prefs()

    def toggle_theme(self) -> None:
        self.set_theme("dark" if self.theme == "light" else "light")

    # -- zoom / fonts ------------------------------------------------------ #

    def _apply_fonts(self) -> None:
        size = -max(9, int(round(13.5 * self.zoom * self.ui_scale)))
        self.editor.configure(font=(self.mono_family, size))
        self.zoom_label.configure(text="%d%%" % round(self.zoom * 100))

    def set_zoom(self, value: float) -> None:
        value = min(2.4, max(0.6, round(value, 2)))
        if abs(value - self.zoom) < 1e-6:
            return
        self.zoom = value
        self.fonts.clear()
        self._apply_fonts()
        self.render_preview()
        self.save_prefs()

    def zoom_by(self, delta: float) -> None:
        self.set_zoom(round(self.zoom + delta, 2))

    def set_read_font(self, name: str) -> None:
        self.doc_family = name
        self.fonts.clear()
        self.render_preview()
        self.save_prefs()

    def set_editor_font(self, name: str) -> None:
        self.mono_family = name
        self.fonts.clear()
        self._apply_fonts()
        self.render_preview()
        self.save_prefs()

    # -- direction / autosave ---------------------------------------------- #

    def set_direction(self, direction: str) -> None:
        if direction not in ("auto", "ltr", "rtl"):
            return
        self.direction = direction
        self.direction_var.set(direction)
        self.render_preview()
        self.save_prefs()

    def set_visual_rtl(self) -> None:
        self.visual_rtl = self.visual_rtl_var.get()
        self.render_preview()
        self.save_prefs()

    def effective_rtl(self, text: str) -> bool:
        if self.direction == "rtl":
            return True
        if self.direction == "ltr":
            return False
        return detect_rtl(text)

    def _apply_editor_direction(self) -> None:
        self.editor.tag_configure("mv_dir", justify="right" if self.rtl else "left")
        if self.rtl:
            self.editor.tag_add("mv_dir", "1.0", "end")
        else:
            self.editor.tag_remove("mv_dir", "1.0", "end")

    def set_autosave(self) -> None:
        self.autosave = self.autosave_var.get()
        self.save_prefs()
        self._flash("Auto save on" if self.autosave else "Auto save off")

    def _schedule_autosave(self) -> None:
        doc = self._doc()
        if not self.autosave or doc is None or doc.path is None:
            return
        if self._autosave_job is not None:
            try:
                self.root.after_cancel(self._autosave_job)
            except tk.TclError:
                pass
        self._autosave_job = self.root.after(900, self._autosave_now)

    def _autosave_now(self) -> None:
        self._autosave_job = None
        doc = self._doc()
        if self.autosave and doc is not None and doc.dirty and doc.path is not None:
            self.save_file()

    # -- mode -------------------------------------------------------------- #

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            return
        self.mode = mode
        self.view_switch.sync(mode)
        self._apply_mode()
        self._paint()
        self.save_prefs()

    def cycle_mode(self) -> None:
        self.set_mode(MODES[(MODES.index(self.mode) + 1) % len(MODES)])

    def _apply_mode(self) -> None:
        paned = self.paned
        present = {str(p) for p in paned.panes()}
        want_editor = self.mode in ("split", "edit")
        want_preview = self.mode in ("read", "split")

        if want_editor and str(self.editor_frame) not in present:
            paned.add(self.editor_frame, minsize=260)
        if want_preview and str(self.preview_frame) not in present:
            paned.add(self.preview_frame, minsize=260)
        if not want_editor and str(self.editor_frame) in present:
            paned.forget(self.editor_frame)
        if not want_preview and str(self.preview_frame) in present:
            paned.forget(self.preview_frame)

        self.editor.configure(state="normal" if want_editor else "disabled")
        if want_editor:
            self.editor.focus_set()
        elif want_preview:
            self.preview.focus_set()

    # -- tabs and documents ------------------------------------------------ #

    def _doc(self) -> Document | None:
        if 0 <= self.active < len(self.docs):
            return self.docs[self.active]
        return None

    def _stash(self) -> None:
        """Copy the editor contents back into the document it belongs to."""
        if self.shown is None or not 0 <= self.shown < len(self.docs):
            return
        self.docs[self.shown].update(self.editor.get("1.0", "end-1c"))

    def _show_workspace(self) -> None:
        self.welcome.pack_forget()
        if not self.paned.winfo_ismapped():
            self.paned.pack(side="top", fill="both", expand=True)
        if not self.tabbar.winfo_ismapped():
            self.tabbar.pack(side="top", fill="x", before=self.paned)

    def _show_welcome(self) -> None:
        self.paned.pack_forget()
        self.tabbar.pack_forget()
        if not self.welcome.winfo_ismapped():
            self.welcome.pack(side="top", fill="both", expand=True)
        self._build_recent()
        self._update_title()

    def _activate(self, index: int, stash: bool = True) -> None:
        if not self.docs:
            return
        if stash:
            self._stash()
        self.active = max(0, min(index, len(self.docs) - 1))
        doc = self.docs[self.active]

        self._loading = True
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", doc.text)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self._loading = False

        self.shown = self.active
        self._show_workspace()
        self._apply_mode()
        self._rebuild_tabs()
        self._update_title()
        self.render_preview()
        self.preview.yview_moveto(0)
        self.update_stats()

    def next_tab(self) -> None:
        if len(self.docs) > 1:
            self._activate((self.active + 1) % len(self.docs))

    def previous_tab(self) -> None:
        if len(self.docs) > 1:
            self._activate((self.active - 1) % len(self.docs))

    def _rebuild_tabs(self) -> None:
        p = self.palette
        for child in self.tabbar.winfo_children():
            child.destroy()
        if not self.docs:
            if self.tabbar.winfo_ismapped():
                self.tabbar.pack_forget()
            return
        if not self.tabbar.winfo_ismapped():
            if self.paned.winfo_ismapped():
                self.tabbar.pack(side="top", fill="x", before=self.paned)
            else:
                self.tabbar.pack(side="top", fill="x")

        for index, doc in enumerate(self.docs):
            active = index == self.active
            bg = p["bg"] if active else p["bg_soft"]
            fg = p["fg"] if active else p["muted"]

            tab = tk.Frame(self.tabbar, bg=bg, bd=0, highlightthickness=0)
            tab.pack(side="left", padx=(2, 0), pady=(4, 0), fill="y")

            label = tk.Label(
                tab, text=doc.label, bg=bg, fg=fg, padx=10, pady=4, cursor="hand2",
                font=(self.app_family, -int(12 * self.ui_scale), "bold" if active else "normal"),
            )
            label.pack(side="left")

            close = tk.Label(tab, text="×", bg=bg, fg=p["muted"], padx=6, pady=4, cursor="hand2",
                             font=(self.app_family, -int(13 * self.ui_scale)))
            close.pack(side="left")

            label.bind("<Button-1>", lambda _e, i=index: self._activate(i))
            tab.bind("<Button-1>", lambda _e, i=index: self._activate(i))
            close.bind("<Button-1>", lambda _e, i=index: self.close_tab(i))
            close.bind("<Enter>", lambda _e, w=close, pal=p: w.configure(fg=pal["fg"]))
            close.bind("<Leave>", lambda _e, w=close, pal=p: w.configure(fg=pal["muted"]))

    def new_file(self) -> None:
        if len(self.docs) >= MAX_TABS:
            self._warn_limit()
            return
        self._stash()
        self.docs.append(Document())
        self._activate(len(self.docs) - 1)
        self._flash("New file")

    def _warn_limit(self) -> None:
        messagebox.showwarning(
            "Tab limit",
            "markvist keeps at most %d files open. Close a tab first." % MAX_TABS,
            parent=self.root,
        )

    def open_file(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Open Markdown file",
            filetypes=[("Markdown", "*.md *.markdown *.mdown *.mkd")],
        )
        if paths:
            self._open_paths(paths)

    def open_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title="Open a folder of Markdown files")
        if not folder:
            return
        root = Path(folder)
        try:
            files = sorted(
                (p for p in root.iterdir() if p.is_file() and p.suffix.lower() in MD_SUFFIXES),
                key=lambda p: p.name.lower(),
            )
        except OSError as exc:
            messagebox.showerror("Could not read folder", str(exc), parent=self.root)
            return

        if not files:
            messagebox.showinfo(
                "No Markdown files",
                "There are no .md files directly inside %s." % root.name,
                parent=self.root,
            )
            return
        self._folder_picker(root, files)

    def _folder_picker(self, folder: Path, files: list[Path]) -> None:
        p = self.palette
        win = tk.Toplevel(self.root)
        win.title("Open from %s" % folder.name)
        win.transient(self.root)
        win.configure(bg=p["bg"])
        win.geometry("520x440")
        win.minsize(360, 300)

        head = tk.Label(
            win, text="%d Markdown file%s in %s" % (len(files), "" if len(files) == 1 else "s",
                                                    folder.name),
            bg=p["bg"], fg=p["muted"], anchor="w",
            font=(self.app_family, -int(12 * self.ui_scale)),
        )
        head.pack(fill="x", padx=14, pady=(12, 6))

        body = tk.Frame(win, bg=p["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        listbox = tk.Listbox(
            body, selectmode="extended", activestyle="none", bd=0, highlightthickness=0,
            bg=p["bg_soft"], fg=p["fg"], selectbackground=p["accent_soft"], selectforeground=p["fg"],
            font=(self.app_family, -int(12 * self.ui_scale)),
        )
        scroll = tk.Scrollbar(body, command=listbox.yview, width=11, bd=0, relief="flat",
                              highlightthickness=0, bg=p["bg_inset"], troughcolor=p["bg_soft"])
        listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        listbox.pack(side="left", fill="both", expand=True)

        for path in files:
            listbox.insert("end", path.name)

        def open_selected(_event=None):
            chosen = [files[i] for i in listbox.curselection()]
            if not chosen:
                return
            win.destroy()
            self._open_paths(chosen)

        footer = tk.Frame(win, bg=p["bg"])
        footer.pack(fill="x", padx=12, pady=(0, 12))
        open_btn = tk.Button(footer, text="Open", command=open_selected, bd=0, padx=14, pady=4,
                             bg=p["accent"], fg=p["bg"], cursor="hand2", takefocus=0,
                             font=(self.app_family, -int(12 * self.ui_scale), "bold"))
        open_btn.pack(side="right")
        cancel = tk.Button(footer, text="Cancel", command=win.destroy, bd=0, padx=14, pady=4,
                           bg=p["bg_soft"], fg=p["fg"], cursor="hand2", takefocus=0,
                           font=(self.app_family, -int(12 * self.ui_scale)))
        cancel.pack(side="right", padx=(0, 6))

        listbox.bind("<Double-Button-1>", open_selected)
        listbox.bind("<Return>", open_selected)
        win.bind("<Escape>", lambda _e: win.destroy())
        win.grab_set()
        listbox.focus_set()

    def _open_paths(self, paths) -> None:
        limit_warned = False
        opened = 0
        last_index = self.active

        for raw in paths:
            p = Path(raw)
            if p.suffix.lower() not in MD_SUFFIXES:
                continue

            existing = next(
                (i for i, doc in enumerate(self.docs)
                 if doc.path is not None and doc.path.resolve() == p.resolve()),
                None,
            )
            if existing is not None:
                last_index = existing
                continue

            if len(self.docs) >= MAX_TABS:
                if not limit_warned:
                    self._warn_limit()
                    limit_warned = True
                break

            try:
                text = p.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    messagebox.showerror("Could not open file", str(exc), parent=self.root)
                    continue
            except OSError as exc:
                messagebox.showerror("Could not open file", str(exc), parent=self.root)
                continue

            self.docs.append(Document(path=p, text=text, saved_text=text))
            self._remember_recent(p)
            last_index = len(self.docs) - 1
            opened += 1

        if self.docs:
            self._activate(last_index)
        else:
            self._show_welcome()
        if opened:
            self._flash("Opened %d file%s" % (opened, "" if opened == 1 else "s"))

    def load_path(self, path: str) -> None:
        """Open a single file (used by the command line)."""
        self._open_paths([path])

    def close_tab(self, index: int | None = None) -> None:
        if not self.docs:
            return
        index = self.active if index is None else index
        if not 0 <= index < len(self.docs):
            return

        doc = self.docs[index]
        if index == self.active:
            self._stash()
        if doc.dirty and not self._confirm_discard(doc):
            return

        del self.docs[index]
        if not self.docs:
            self.active = 0
            self.shown = None
            self._loading = True
            self.editor.delete("1.0", "end")
            self._loading = False
            self._rebuild_tabs()
            self._show_welcome()
            self.render_preview()
            return

        if index < self.active:
            self.active -= 1
        else:
            self.active = min(self.active, len(self.docs) - 1)
        self.shown = None
        self._activate(self.active, stash=False)

    # -- start screen ------------------------------------------------------ #

    def _build_recent(self) -> None:
        p = self.palette
        for child in self.recent_frame.winfo_children():
            child.destroy()

        recents = [Path(r) for r in self.recent if Path(r).exists()][:5]
        if not recents:
            return

        tk.Label(
            self.recent_frame, text="Recent", bg=p["bg"], fg=p["muted"], anchor="w",
            font=(self.app_family, -int(11 * self.ui_scale), "bold"),
        ).pack(anchor="w")
        for path in recents:
            label = tk.Label(
                self.recent_frame, text=path.name, bg=p["bg"], fg=p["accent"], anchor="w",
                cursor="hand2", font=(self.app_family, -int(12 * self.ui_scale)),
            )
            label.pack(fill="x", pady=1)
            label.bind("<Button-1>", lambda _e, pt=path: self._open_paths([pt]))

    # -- content ----------------------------------------------------------- #

    def _update_title(self) -> None:
        doc = self._doc()
        if doc is None:
            self.file_label.configure(text="markvist")
            self.dirty_label.configure(text="")
            self.root.title(APP_NAME)
            self.save_btn.configure(state="disabled")
            return
        name = doc.name
        self.file_label.configure(text=name)
        self.dirty_label.configure(text="●" if doc.dirty else "")
        self.root.title(("%s%s — %s" % ("• " if doc.dirty else "", name, APP_NAME)))
        self.save_btn.configure(state="normal" if doc.dirty else "disabled")

    def _on_modified(self, _event=None) -> None:
        if self._loading:
            self.editor.edit_modified(False)
            return
        self.editor.edit_modified(False)
        self._mark_dirty()

    def _on_tab(self, _event=None) -> str:
        self.editor.insert("insert", "    ")
        self._mark_dirty()
        return "break"

    def _mark_dirty(self) -> None:
        doc = self._doc()
        if doc is None:
            return
        was_dirty = doc.dirty
        self._stash()
        self._update_title()
        if doc.dirty != was_dirty:
            self._rebuild_tabs()
        self.update_stats()
        if self._render_job is not None:
            try:
                self.root.after_cancel(self._render_job)
            except tk.TclError:
                pass
        self._render_job = self.root.after(120, self._render_soon)
        self._schedule_autosave()

    def _render_soon(self) -> None:
        self._render_job = None
        self.render_preview()

    def _on_preview_resize(self, event) -> None:
        """Re-render after a resize so rules and tables match the new width."""
        if abs(event.width - self._preview_width) < 4:
            return
        self._preview_width = event.width
        if self._render_job is not None:
            try:
                self.root.after_cancel(self._render_job)
            except tk.TclError:
                pass
        self._render_job = self.root.after(180, self._render_soon)

    def update_stats(self) -> None:
        text = self.editor.get("1.0", "end-1c") if self.docs else ""
        words = len(re.findall(r"\S+", text)) if text else 0
        minutes = max(1, round(words / 220))
        self.stats_label.configure(
            text="%s words · %s chars · ~%d min read" % (f"{words:,}", f"{len(text):,}", minutes)
        )

    def render_preview(self) -> None:
        text = self.editor.get("1.0", "end-1c") if self.docs else ""
        self.rtl = self.effective_rtl(text)
        PreviewRenderer(
            self.preview,
            self.palette,
            self.zoom,
            self.ui_scale,
            self.fonts,
            self.doc_family,
            self.mono_family,
            self.links,
            rtl=self.rtl,
            visual_rtl=self.rtl and self.visual_rtl and not self.bidi_supported,
        ).render(parse_markdown(text))
        self._apply_editor_direction()
        self._update_direction_badge()

    def _update_direction_badge(self) -> None:
        if not self.rtl:
            text = ""
        elif self.bidi_supported:
            text = "RTL"
        elif self.visual_rtl:
            text = "RTL · preview visual order"
        else:
            text = "RTL · order unsupported by Tk"
        self.dir_label.configure(text=text)

    # -- files ------------------------------------------------------------- #

    def save_file(self, save_as: bool = False) -> bool:
        doc = self._doc()
        if doc is None:
            return False

        content = self.editor.get("1.0", "end-1c")
        path = doc.path

        if path is None or save_as:
            chosen = filedialog.asksaveasfilename(
                parent=self.root,
                title="Save Markdown file",
                defaultextension=".md",
                initialfile=path.name if path else "untitled.md",
                filetypes=[("Markdown", "*.md")],
            )
            if not chosen:
                return False
            path = Path(chosen)
            if path.suffix.lower() not in MD_SUFFIXES:
                path = path.with_suffix(".md")

        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Could not save file", str(exc), parent=self.root)
            return False

        doc.commit(content, path)
        self._remember_recent(path)
        self._rebuild_tabs()
        self._update_title()
        self._flash("Saved %s" % path.name)
        return True

    def _confirm_discard(self, doc: Document) -> bool:
        if not doc.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            "Save changes to %s before closing?" % doc.name,
            parent=self.root,
        )
        if answer is None:
            return False
        if answer:
            self._activate(self.docs.index(doc), stash=False)
            return self.save_file()
        return True

    def on_close(self) -> None:
        self._stash()
        dirty = [doc for doc in self.docs if doc.dirty]
        if dirty:
            answer = messagebox.askyesnocancel(
                "Unsaved changes",
                "Save changes to %d file%s before closing?"
                % (len(dirty), "" if len(dirty) == 1 else "s"),
                parent=self.root,
            )
            if answer is None:
                return
            if answer:
                for doc in dirty:
                    self._activate(self.docs.index(doc), stash=False)
                    if not self.save_file():
                        return

        for job in (self._render_job, self._autosave_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self.save_prefs()
        self.root.destroy()

    # -- misc -------------------------------------------------------------- #

    def _flash(self, message: str) -> None:
        self.stats_label.configure(text=message)
        self.root.after(2200, self._restore_stats)

    def _restore_stats(self) -> None:
        try:
            if self.root.winfo_exists():
                self.update_stats()
        except tk.TclError:
            pass

    def _on_preview_key(self, event) -> str:
        """Arrow / page keys scroll the rendered view instead of moving a caret."""
        steps = {"Up": -1, "Down": 1}
        pages = {"Prior": -1, "Next": 1}
        if event.keysym in steps:
            self.preview.yview_scroll(steps[event.keysym], "units")
        elif event.keysym in pages:
            self.preview.yview_scroll(pages[event.keysym], "pages")
        elif event.keysym == "Home":
            self.preview.yview_moveto(0.0)
        elif event.keysym == "End":
            self.preview.yview_moveto(1.0)
        return "break"

    def _pane_under_pointer(self, x_root: int, y_root: int):
        """Return the editor or preview pane at a screen position, else None.

        Uses the frame rectangles (which include each pane's scrollbar) rather
        than Tk hit-testing, so it does not depend on window visibility.
        """
        for frame, pane in ((self.editor_frame, self.editor),
                            (self.preview_frame, self.preview)):
            if not frame.winfo_ismapped():
                continue
            x, y = frame.winfo_rootx(), frame.winfo_rooty()
            if x <= x_root < x + frame.winfo_width() \
                    and y <= y_root < y + frame.winfo_height():
                return pane
        return None

    def _on_wheel(self, event):
        """Scroll the pane under the cursor, regardless of which one has focus."""
        widget = getattr(event, "widget", None)
        if widget is not None and widget.winfo_toplevel() is not self.root:
            return None  # a dialog is on top; leave its own scrolling alone
        target = self._pane_under_pointer(getattr(event, "x_root", 0),
                                         getattr(event, "y_root", 0))
        if target is None:
            return None
        number = getattr(event, "num", None)
        if number in (4, 5):
            step = -1 if number == 4 else 1
        else:
            delta = getattr(event, "delta", 0) or 0
            if not delta:
                return "break"
            step = (-1 if delta > 0 else 1) * max(1, abs(delta) // 120)
        target.yview_scroll(step, "units")
        return "break"

    def _on_preview_click(self, event):
        self.preview.focus_set()
        index = self.preview.index("@%d,%d" % (event.x, event.y))
        for name in self.preview.tag_names(index):
            url = self.links.get(name)
            if url and not url.startswith("#"):
                webbrowser.open(url)
                break
        return "break"

    def _on_preview_motion(self, event):
        index = self.preview.index("@%d,%d" % (event.x, event.y))
        over_link = any(self.links.get(n) for n in self.preview.tag_names(index))
        self.preview.configure(cursor="hand2" if over_link else "arrow")

    def show_help(self) -> None:
        messagebox.showinfo(
            "Keyboard shortcuts",
            "Ctrl+N   new file\n"
            "Ctrl+O   open file(s)\n"
            "Ctrl+Shift+O   open a folder of .md files\n"
            "Ctrl+S   save\n"
            "Ctrl+Shift+S   save as\n"
            "Ctrl+W   close tab\n"
            "Ctrl+Tab   next tab\n"
            "Ctrl+=   zoom in\n"
            "Ctrl+-   zoom out\n"
            "Ctrl+0   reset zoom\n"
            "Ctrl+E   cycle book / split / code\n"
            "Ctrl+T   switch theme\n\n"
            "Up to %d files can be open at once." % MAX_TABS,
            parent=self.root,
        )

    def show_rtl_help(self) -> None:
        version = "Tk %s" % tk.TkVersion
        if self.bidi_supported:
            state = (
                "This Tk build supports bidirectional text, so Persian, Arabic and Hebrew "
                "render natively and the status badge simply reads RTL."
            )
        elif self.visual_rtl:
            state = (
                "This Tk build (%s) has no bidirectional text support, so the preview "
                "reorders RTL runs into visual order before drawing them. The badge says "
                "\"preview visual order\" because that is all it is: the source pane still "
                "shows the file's logical order, and copying text from the preview yields "
                "reversed characters." % version
            )
        else:
            state = (
                "This Tk build (%s) has no bidirectional text support and the visual "
                "preview is off, so RTL text is drawn left to right in logical order and "
                "reads mirrored." % version
            )
        messagebox.showinfo(
            "RTL support",
            state + "\n\nNative bidi support arrived in Tk 9.1 (September 2026).",
            parent=self.root,
        )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except tk.TclError:
        pass

    Markvist(root, argv[0] if argv else None)
    root.mainloop()
    return 0
