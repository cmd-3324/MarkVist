"""Reading Markdown files, watching them for outside edits, keeping backups."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

Signature = tuple[int, int]  # (st_mtime_ns, st_size)

BOM_BYTES = b"\xef\xbb\xbf"
DEFAULT_NEWLINE = os.linesep  # a new file gets the platform's convention


@dataclass(frozen=True)
class FileFormat:
    """How a file is stored, so a save can reproduce it instead of guessing."""

    encoding: str = "utf-8"  # "utf-8-sig" when the file begins with a BOM
    newline: str = DEFAULT_NEWLINE  # "\r\n", "\n" or "\r"

    def encode(self, text: str) -> bytes:
        """Bytes for text from the editor, which always uses \\n."""
        body = text.replace("\r\n", "\n").replace("\r", "\n")
        if self.newline != "\n":
            body = body.replace("\n", self.newline)
        return body.encode(self.encoding)  # utf-8-sig writes the BOM back


def detect_format(raw: bytes) -> FileFormat:
    """Work out a file's line endings and BOM from the bytes on disk."""
    encoding = "utf-8-sig" if raw.startswith(BOM_BYTES) else "utf-8"
    spots = [(raw.find(b"\r\n"), "\r\n"), (raw.find(b"\n"), "\n"), (raw.find(b"\r"), "\r")]
    found = [spot for spot in spots if spot[0] != -1]
    if not found:
        return FileFormat(encoding, DEFAULT_NEWLINE)
    # The earliest newline wins; at the same offset the longer marker is real
    # ("\r\n" also matches a lone "\r" and its trailing "\n").
    newline = min(found, key=lambda spot: (spot[0], -len(spot[1])))[1]
    return FileFormat(encoding, newline)


def signature(path: Path | None) -> Signature | None:
    """Fingerprint a file's on-disk state, or None when the file is gone."""
    if path is None:
        return None
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def read_document(path: Path) -> tuple[str, FileFormat]:
    """Read a Markdown file and remember the format it was stored in."""
    raw = path.read_bytes()
    fmt = detect_format(raw)
    try:
        text = raw.decode(fmt.encoding)
    except UnicodeDecodeError:
        # Not UTF-8: read what we can and save the tab back as plain UTF-8.
        fmt = FileFormat("utf-8", fmt.newline)
        text = raw.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n"), fmt


def read_text(path: Path) -> str:
    """Just the text, ignoring the format."""
    return read_document(path)[0]


def write_document(path: Path, text: str, fmt: FileFormat | None = None) -> FileFormat:
    """Write text in the file's own format, atomically.

    The bytes go to a temporary file beside the target and are renamed over it,
    so an interrupted save leaves the previous version intact instead of a
    truncated note, and nothing is ever written half-way.
    """
    fmt = fmt or FileFormat()
    data = fmt.encode(text)  # encode first: a bad character fails before we touch the disk
    target = Path(path)
    try:
        mode = target.stat().st_mode & 0o777
    except OSError:
        mode = None

    fd, tmp_name = tempfile.mkstemp(
        prefix="." + target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            try:
                os.chmod(tmp, mode)
            except OSError:
                pass
        os.replace(tmp, target)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return fmt


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
