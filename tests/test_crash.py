"""The crash log and the sentence shown instead of a traceback."""

import sys
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from markvist import crash


def capsized() -> None:
    raise ValueError("capsized")


def exc_info() -> tuple:
    try:
        capsized()
    except ValueError:
        return sys.exc_info()


class DescribeTest(unittest.TestCase):
    def test_permission_is_explained(self):
        wording = crash.describe(PermissionError(13, "Permission denied"))
        self.assertIn("would not let markvist touch that file", wording)

    def test_missing_file_is_explained(self):
        wording = crash.describe(FileNotFoundError(2, "No such file"))
        self.assertIn("no longer there", wording)

    def test_a_folder_is_not_a_file(self):
        self.assertIn("is a folder", crash.describe(IsADirectoryError(21, "Is a dir")))

    def test_undecodable_text_is_explained(self):
        try:
            b"\xff\xfe".decode("utf-8")
        except UnicodeDecodeError as exc:
            self.assertIn("not text markvist can read", crash.describe(exc))
        else:  # pragma: no cover - the decode above always fails
            self.fail("decoding should have failed")

    def test_running_out_of_memory_is_explained(self):
        self.assertIn("ran out of memory", crash.describe(MemoryError()))

    def test_a_plain_oserror_keeps_its_reason(self):
        wording = crash.describe(OSError(28, "No space left on device"))
        self.assertIn("No space left on device", wording)

    def test_anything_else_names_the_exception(self):
        wording = crash.describe(ValueError("capsized"))
        self.assertIn("ValueError: capsized", wording)


class DialogTextTest(unittest.TestCase):
    def test_names_the_context_and_the_log(self):
        path = Path("logs") / "crash.log"
        message = crash.dialog_message(ValueError("x"), path, "a window action")
        self.assertIn("while handling a window action", message)
        self.assertIn(str(path), message)  # the exact path, whichever separator
        self.assertIn("carry on working", message)

    def test_says_so_when_nothing_could_be_written(self):
        message = crash.dialog_message(ValueError("x"), None, "a window action")
        self.assertIn("could not be written", message)
        self.assertNotIn("The full details were written to", message)

    def test_without_context_the_sentence_still_reads(self):
        self.assertEqual(
            crash.dialog_message(ValueError("x"), None).splitlines()[0],
            "markvist hit an unexpected problem.",
        )


class ReportTest(unittest.TestCase):
    def test_reports_what_when_where_and_how(self):
        report = crash.format_report(
            exc_info(), "opening a file", when=datetime(2026, 1, 2, 3, 4, 5)
        )
        self.assertTrue(report.startswith("markvist "))
        self.assertIn("when: 2026-01-02 03:04:05", report)
        self.assertIn("where: opening a file", report)
        self.assertIn("python: ", report)
        self.assertIn("Traceback (most recent call last)", report)
        self.assertIn("ValueError: capsized", report)
        self.assertTrue(report.endswith(crash.RECORD_SEP))

    def test_a_report_without_a_context_says_unknown(self):
        self.assertIn("where: unknown", crash.format_report(exc_info()))


class LogFileTest(unittest.TestCase):
    def test_writes_the_report_and_creates_its_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "crash.log"
            wrote = crash.record(exc_info(), "a window action", path=path)
            self.assertEqual(wrote, path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("ValueError: capsized", text)
            self.assertIn("where: a window action", text)

    def test_keeps_earlier_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crash.log"
            crash.record(exc_info(), "first", path=path, when=datetime(2026, 1, 1))
            crash.record(exc_info(), "second", path=path, when=datetime(2026, 1, 2))
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("ValueError: capsized"), 2)
            self.assertLess(text.index("where: first"), text.index("where: second"))

    def test_an_unwritable_path_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "blocker"
            blocker.write_text("a file, not a folder", encoding="utf-8")
            self.assertIsNone(crash.record(exc_info(), path=blocker / "crash.log"))

    def test_trimming_keeps_the_newest_whole_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crash.log"
            for day in range(1, 6):
                crash.record(
                    exc_info(), "day %d" % day, path=path,
                    when=datetime(2026, 1, day), limit=900,
                )
            text = path.read_text(encoding="utf-8")
            self.assertLessEqual(len(text), 1800)  # one report may overrun the budget
            self.assertIn("where: day 5", text)
            self.assertNotIn("where: day 1", text)
            self.assertTrue(text.startswith("markvist "))  # never a half report

    def test_a_small_log_is_left_alone(self):
        text = crash.format_report(exc_info())
        self.assertEqual(crash.trim_log(text, crash.MAX_LOG_BYTES), text)


class ReporterTest(unittest.TestCase):
    def test_counts_and_stops_asking_after_a_few_dialogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporter = crash.Reporter(Path(tmp) / "crash.log")
            self.assertEqual(reporter.count, 0)
            self.assertTrue(reporter.wants_dialog)
            for expected in range(1, crash.MAX_DIALOGS + 2):
                reporter.handle(exc_info(), "a window action")
                self.assertEqual(reporter.count, expected)
                self.assertEqual(reporter.wants_dialog, expected <= crash.MAX_DIALOGS)
            self.assertFalse(reporter.wants_dialog)


class HooksTest(unittest.TestCase):
    def setUp(self):
        self.saved = (sys.excepthook, threading.excepthook)
        self.tmp = tempfile.TemporaryDirectory()
        self.reporter = crash.Reporter(Path(self.tmp.name) / "crash.log")
        self.seen = []

    def tearDown(self):
        sys.excepthook, threading.excepthook = self.saved
        self.tmp.cleanup()

    def test_a_main_thread_crash_is_logged_and_announced(self):
        crash.install_excepthooks(
            self.reporter, lambda info, context, path: self.seen.append((context, path))
        )
        etype, value, tb = exc_info()
        sys.excepthook(etype, value, tb)
        self.assertEqual(len(self.seen), 1)
        self.assertEqual(self.seen[0][0], "the main thread")
        self.assertIn("ValueError: capsized",
                      (Path(self.tmp.name) / "crash.log").read_text(encoding="utf-8"))

    def test_a_background_crash_is_logged_without_a_dialog(self):
        crash.install_excepthooks(
            self.reporter, lambda info, context, path: self.seen.append(context)
        )
        etype, value, tb = exc_info()
        args = SimpleNamespace(
            exc_type=etype, exc_value=value, exc_traceback=tb,
            thread=SimpleNamespace(name="worker-7"),
        )
        threading.excepthook(args)
        self.assertEqual(self.seen, [])
        text = (Path(self.tmp.name) / "crash.log").read_text(encoding="utf-8")
        self.assertIn("where: worker-7", text)


if __name__ == "__main__":
    unittest.main()
