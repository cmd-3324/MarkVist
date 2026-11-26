"""The application icon: one .ico for the window, its dialogs and the build."""

from __future__ import annotations

import base64
import struct
import sys
import tkinter as tk
import zlib
from pathlib import Path

ICON_NAME = "PYTHON_LOGO.ico"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


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


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def _png_from_bgra(width: int, height: int, bgra: bytes) -> bytes:
    """Turn a 32-bit BMP from an icon into a PNG, flipping it the right way up."""
    rows = []
    stride = width * 4
    for y in range(height - 1, -1, -1):  # icon rows are stored bottom-up
        row = bytearray(bgra[y * stride:(y + 1) * stride])
        row[0::4], row[2::4] = row[2::4], row[0::4]  # BGRA -> RGBA
        rows.append(b"\x00" + bytes(row))  # filter type 0 per scanline
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + _chunk(b"IEND", b"")
    )


def ico_entries(raw: bytes) -> list[tuple[int, int, int, int, int]]:
    """(width, height, bit_count, size, offset) for each image in an .ico."""
    if len(raw) < 6 or raw[:4] != b"\x00\x00\x01\x00":
        return []
    count = struct.unpack_from("<H", raw, 4)[0]
    entries = []
    for i in range(count):
        start = 6 + i * 16
        if start + 16 > len(raw):
            break
        width, height, _colors, _reserved, _planes, bits, size, offset = struct.unpack_from(
            "<BBBBHHII", raw, start
        )
        entries.append((width or 256, height or 256, bits, size, offset))
    return entries


def ico_png(path: Path, size: int = 0) -> bytes | None:
    """Decode an .ico's largest (or closest to size) image to PNG bytes.

    Tk can draw PNG everywhere but only reads .ico on Windows, so the same
    icon file works on Linux and macOS through this conversion.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    entries = ico_entries(raw)
    if not entries:
        return None

    def rank(entry: tuple[int, int, int, int, int]) -> tuple[int, int]:
        width = entry[0]
        return (0 if size and width == size else 1, -width)

    for width, height, bits, count, offset in sorted(entries, key=rank):
        blob = raw[offset:offset + count]
        if blob.startswith(PNG_SIGNATURE):
            return blob  # already a PNG-compressed entry
        if bits != 32 or not blob:
            continue
        data = blob[40:]  # skip the BITMAPINFOHEADER
        if len(data) < width * height * 4:
            continue
        return _png_from_bgra(width, height, data)
    return None


def apply_icon(window) -> None:
    """Give a window and its future dialogs the app icon instead of Tk's feather."""
    path = icon_path()
    if path is None:
        return
    try:
        window.iconbitmap(str(path))  # this window
        window.iconbitmap(default=str(path))  # and every toplevel opened later
        return
    except Exception:  # a Tk build without .ico support
        pass
    data = ico_png(path, size=64)
    if data is None:
        return
    try:
        image = tk.PhotoImage(
            master=window, format="png", data=base64.b64encode(data).decode("ascii")
        )
        window.iconphoto(True, image)
        window._markvist_icon = image  # Tk keeps no reference of its own
    except Exception:
        pass
