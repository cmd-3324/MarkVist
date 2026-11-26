"""A single open document (one tab)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .disk import FileFormat, Signature

UNTITLED = "untitled.md"


@dataclass
class Document:
    path: Path | None = None
    text: str = ""
    saved_text: str = ""
    dirty: bool = False
    title: str | None = None  # name of an untitled buffer
    disk_sig: Signature | None = None  # state of the file we last read or wrote
    conflict: bool = False  # the file moved on since: never overwrite it silently
    fmt: FileFormat | None = None  # line endings and BOM to write back

    @property
    def name(self) -> str:
        if self.path is not None:
            return self.path.name
        return self.title or UNTITLED

    @property
    def label(self) -> str:
        """Name plus a dot for unsaved changes, or a warning when the file moved on."""
        if self.conflict:
            return "⚠ " + self.name
        return ("● " if self.dirty else "") + self.name

    def update(self, text: str) -> None:
        self.text = text
        self.dirty = text != self.saved_text

    def commit(self, text: str, path: Path | None = None,
               fmt: FileFormat | None = None) -> None:
        """Record text that has just been written to disk."""
        self.text = text
        self.saved_text = text
        self.dirty = False
        self.conflict = False
        if path is not None:
            self.path = path
        if fmt is not None:
            self.fmt = fmt
