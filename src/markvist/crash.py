"""What to do when something goes wrong: a log file and a plain answer.

A windowed build has no console, so an exception that escapes a Tk callback used
to vanish into a traceback nobody could see. Every uncaught exception is now
appended to ``crash.log`` beside ``config.json``, and the person in front of the
screen gets one sentence, a friendly explanation and the path to that file.
"""

from __future__ import annotations

import platform
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from . import __version__
from .prefs import config_path
from .theme import APP_NAME

LOG_NAME = "crash.log"
MAX_LOG_BYTES = 64 * 1024  # a few dozen reports; the log never grows unbounded
MAX_DIALOGS = 3  # a failing loop would otherwise bury the window in popups
SEPARATOR = "-" * 60
RECORD_SEP = SEPARATOR + "\n\n"  # ends each report, so trimming keeps whole ones


def crash_log_path() -> Path:
    """The crash log lives beside config.json, so uninstalling the exe keeps it."""
    return config_path().parent / LOG_NAME


def toolkit_version() -> str:
    """The Tk version, or a note when this build has no Tk at all."""
    try:
        import tkinter

        return "Tk %s" % tkinter.TkVersion
    except Exception:  # pragma: no cover - only on a Tk-less Python
        return "Tk unavailable"


def describe(exc: BaseException) -> str:
    """One sentence about what went wrong, in words that suggest what to do."""
    if isinstance(exc, PermissionError):
        return (
            "Windows would not let markvist touch that file. It may be open in "
            "another program, or the folder may be read-only."
        )
    if isinstance(exc, FileNotFoundError):
        return "That file or folder is no longer there: something moved or deleted it."
    if isinstance(exc, IsADirectoryError):
        return "That path is a folder, and markvist expected a file."
    if isinstance(exc, UnicodeError):
        return (
            "That file is not text markvist can read. It may use another encoding, "
            "or not be a text file at all."
        )
    if isinstance(exc, MemoryError):
        return "markvist ran out of memory. Closing a few tabs may be enough."
    if isinstance(exc, OSError):
        reason = getattr(exc, "strerror", None) or str(exc) or "no reason given"
        return "A file operation failed: %s." % reason.rstrip(".")
    return "Something unexpected went wrong: %s: %s." % (type(exc).__name__, exc)


def dialog_message(exc: BaseException, path: Path | None, context: str = "") -> str:
    """The dialog text: what happened, what it means, where the details went."""
    where = " while handling %s" % context if context else ""
    lines = [
        "markvist hit an unexpected problem%s." % where,
        "",
        describe(exc),
        "",
        "You can carry on working. If a button or pane stops answering, close "
        "markvist and open it again.",
        "",
    ]
    if path is not None:
        lines.append("The full details were written to:")
        lines.append(str(path))
    else:
        lines.append(
            "The details could not be written to a log file, so this message is "
            "all there is."
        )
    return "\n".join(lines)


def format_report(
    exc_info: tuple, context: str = "", when: datetime | None = None
) -> str:
    """One crash record: what, where, on what, and the traceback."""
    etype, value, tb = exc_info
    stamp = (when or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    trace = "".join(traceback.format_exception(etype, value, tb)).rstrip()
    header = "\n".join(
        [
            "%s %s" % (APP_NAME, __version__),
            "when: %s" % stamp,
            "where: %s" % (context or "unknown"),
            "python: %s  %s" % (platform.python_version(), toolkit_version()),
            "platform: %s" % platform.platform(),
        ]
    )
    return "%s\n\n%s\n%s" % (header, trace, RECORD_SEP)


def trim_log(text: str, limit: int = MAX_LOG_BYTES) -> str:
    """Keep the newest whole reports when the log outgrows its budget."""
    if len(text) <= limit:
        return text
    records = [piece for piece in text.split(RECORD_SEP) if piece.strip()]
    kept: list[str] = []
    total = 0
    for record in reversed(records):
        piece = record + RECORD_SEP
        if kept and total + len(piece) > limit:
            break
        kept.append(piece)  # the newest record is kept even when it is huge
        total += len(piece)
    return "".join(reversed(kept))


def record(
    exc_info: tuple,
    context: str = "",
    path: Path | None = None,
    when: datetime | None = None,
    limit: int = MAX_LOG_BYTES,
) -> Path | None:
    """Append a report, returning where it went, or None if nothing could be written."""
    target = Path(path) if path is not None else crash_log_path()
    try:
        try:
            existing = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            existing = ""
        target.parent.mkdir(parents=True, exist_ok=True)
        text = trim_log(existing + format_report(exc_info, context, when), limit)
        target.write_text(text, encoding="utf-8", newline="")
    except OSError:
        return None
    return target


class Reporter:
    """Writes reports and remembers how many dialogs the person has already seen."""

    def __init__(self, path: Path | None = None, limit: int = MAX_LOG_BYTES) -> None:
        self.path = Path(path) if path is not None else None
        self.limit = limit
        self.count = 0

    def handle(self, exc_info: tuple, context: str = "") -> Path | None:
        """Record one failure and return where it went."""
        self.count += 1
        return record(exc_info, context=context, path=self.path, limit=self.limit)

    @property
    def wants_dialog(self) -> bool:
        """True while saying so out loud is still help rather than noise."""
        return self.count <= MAX_DIALOGS


def install_excepthooks(reporter: Reporter, notify=None) -> None:
    """Send uncaught exceptions to the log, and say so on the main thread.

    ``notify(exc_info, context, path)`` is called for a main-thread crash only: a
    Tk dialog cannot safely be raised from a background thread, so a failing
    thread is logged without interrupting the window.
    """

    def main_hook(etype, value, tb) -> None:
        exc_info = (etype, value, tb)
        path = reporter.handle(exc_info, "the main thread")
        if notify is not None and reporter.wants_dialog:
            notify(exc_info, "the main thread", path)

    def thread_hook(args) -> None:
        exc_info = (args.exc_type, args.exc_value, args.exc_traceback)
        thread = getattr(args, "thread", None)
        reporter.handle(exc_info, getattr(thread, "name", None) or "a background thread")

    sys.excepthook = main_hook
    threading.excepthook = thread_hook
