"""Colours, font choices and shared constants."""

APP_NAME = "markvist"
MD_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd"}
MODES = ("read", "split", "edit")
MAX_TABS = 10

PALETTES = {
    "light": {
        "bg": "#ffffff",
        "bg_soft": "#f7f8fa",
        "bg_inset": "#eef1f5",
        "fg": "#191c22",
        "muted": "#6b7280",
        "border": "#e4e7ec",
        "accent": "#4f46e5",
        "accent_soft": "#ececfe",
        "code_bg": "#f5f6f8",
        "quote_bg": "#f5f7fc",
        "table_head": "#eef1f7",
        "table_stripe": "#fafbfd",
    },
    "dark": {
        "bg": "#14161b",
        "bg_soft": "#1a1d24",
        "bg_inset": "#21252e",
        "fg": "#e6e9ef",
        "muted": "#98a0ad",
        "border": "#272c36",
        "accent": "#8b93ff",
        "accent_soft": "#23263a",
        "code_bg": "#1c2029",
        "quote_bg": "#1a1f29",
        "table_head": "#232935",
        "table_stripe": "#171b22",
    },
}

# Relative font size per block kind, multiplied by the body size.
SIZE_FACTOR = {
    "body": 1.0,
    "h1": 2.0,
    "h2": 1.55,
    "h3": 1.26,
    "h4": 1.1,
    "h5": 1.0,
    "h6": 0.92,
    "code": 0.9,
}

READING_FONTS = ("Segoe UI", "Georgia", "Times New Roman", "Tahoma", "Verdana")
EDITOR_FONTS = ("Cascadia Mono", "Consolas", "Courier New", "Lucida Console")

DIRECTION_LABELS = (
    ("auto", "Automatic (detect Persian / Arabic)"),
    ("ltr", "Left to right"),
    ("rtl", "Right to left (RTL)"),
)
