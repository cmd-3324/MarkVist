"""A single open document (one tab)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

UNTITLED = "untitled.md"


@dataclass
class Document:
    path: Path | None = None
    text: str = ""
    saved_text: str = ""
    dirty: bool = False
    title: str | None = None  # name of an untitled buffer

    @property
    def name(self) -> str:
        if self.path is not None:
            return self.path.name
        return self.title or UNTITLED

    @property
    def label(self) -> str:
        """Name plus a dot when there are unsaved changes."""
        return ("● " if self.dirty else "") + self.name

    def update(self, text: str) -> None:
        self.text = text
        self.dirty = text != self.saved_text

    def commit(self, text: str, path: Path | None = None) -> None:
        """Record text that has just been written to disk."""
        self.text = text
        self.saved_text = text
        self.dirty = False
        if path is not None:
            self.path = path
