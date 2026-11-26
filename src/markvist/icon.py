"""The application icon: window and taskbar picture, and the built exe's icon."""

from __future__ import annotations

import sys
from pathlib import Path

ICON_NAME = "PYTHON_LOGO.ico"


def icon_path() -> Path | None:
    """Find the .ico beside the sources, or inside a PyInstaller bundle."""
    roots: list[Path] = []
    bundle = getattr(sys, "_MEIPASS", None)  # where a onefile build unpacks itself
    if bundle:
        roots.append(Path(bundle))
    here = Path(__file__).resolve().parent
    roots.extend((here, here.parents[1]))  # the package, then the project root
    for root in roots:
        candidate = root / ICON_NAME
        if candidate.is_file():
            return candidate
    return None


def apply_icon(window) -> None:
    """Give every toplevel the app icon instead of Tk's default feather."""
    path = icon_path()
    if path is None:
        return
    try:
        window.iconbitmap(default=str(path))
    except Exception:  # a Tk build without .ico support keeps its own icon
        pass
