"""Reading Markdown files, watching them for outside edits, keeping backups."""

from __future__ import annotations

import shutil
from pathlib import Path

Signature = tuple[int, int]  # (st_mtime_ns, st_size)


def signature(path: Path | None) -> Signature | None:
    """Fingerprint a file's on-disk state, or None when the file is gone."""
    if path is None:
        return None
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def read_text(path: Path) -> str:
    """Read a Markdown file, tolerating a BOM and stray bytes."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def same_file(a: Path, b: Path) -> bool:
    """True when two paths point at the same file."""
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return a == b


def backup(path: Path) -> Path | None:
    """Copy the file's current contents beside it as <name>.bak."""
    target = path.with_name(path.name + ".bak")
    try:
        shutil.copy2(path, target)
    except OSError:
        return None
    return target
