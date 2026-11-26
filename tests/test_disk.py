import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from markvist.disk import (
    FileFormat,
    detect_format,
    read_document,
    read_text,
    signature,
    write_document,
)
from markvist.document import Document


class DetectFormatTest(unittest.TestCase):
    def test_lf(self):
        self.assertEqual(detect_format(b"a\nb\n").newline, "\n")

    def test_crlf(self):
        self.assertEqual(detect_format(b"a\r\nb\r\n").newline, "\r\n")

    def test_lone_cr(self):
        self.assertEqual(detect_format(b"a\rb\r").newline, "\r")

    def test_first_newline_wins(self):
        self.assertEqual(detect_format(b"a\r\nb\n\n").newline, "\r\n")
        self.assertEqual(detect_format(b"a\nb\r\n").newline, "\n")

    def test_no_newline_gets_the_platform_default(self):
        self.assertEqual(detect_format(b"abc").newline, os.linesep)

    def test_bom_is_remembered(self):
        self.assertEqual(detect_format(b"\xef\xbb\xbfhi\n").encoding, "utf-8-sig")
        self.assertEqual(detect_format(b"hi\n").encoding, "utf-8")


class ReadWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "note.md"

    def tearDown(self):
        self.tmp.cleanup()

    def leftovers(self):
        return sorted(p.name for p in self.dir.iterdir() if p.name != "note.md")

    def test_crlf_file_keeps_crlf(self):
        self.path.write_bytes(b"one\r\ntwo\r\n")
        text, fmt = read_document(self.path)
        self.assertEqual(text, "one\ntwo\n")  # the editor only ever sees \n
        self.assertEqual(fmt.newline, "\r\n")
        write_document(self.path, text, fmt)
        self.assertEqual(self.path.read_bytes(), b"one\r\ntwo\r\n")

    def test_lf_file_keeps_lf(self):
        self.path.write_bytes(b"one\ntwo\n")
        text, fmt = read_document(self.path)
        write_document(self.path, text, fmt)
        self.assertEqual(self.path.read_bytes(), b"one\ntwo\n")
        self.assertNotIn(b"\r", self.path.read_bytes())

    def test_bom_survives_a_save(self):
        self.path.write_bytes(b"\xef\xbb\xbfhi\n")
        text, fmt = read_document(self.path)
        self.assertEqual(text, "hi\n")
        write_document(self.path, text, fmt)
        self.assertEqual(self.path.read_bytes(), b"\xef\xbb\xbfhi\n")

    def test_editor_line_endings_are_normalised_to_the_file(self):
        write_document(self.path, "a\r\nb", FileFormat("utf-8", "\n"))
        self.assertEqual(self.path.read_bytes(), b"a\nb")
        write_document(self.path, "a\nb", FileFormat("utf-8", "\r\n"))
        self.assertEqual(self.path.read_bytes(), b"a\r\nb")

    def test_new_file_is_created_with_the_platform_default(self):
        body = "hello" + "\n" + "world" + "\n"
        write_document(self.path, body)
        self.assertEqual(read_text(self.path), body)
        self.assertIn(os.linesep.encode(), self.path.read_bytes())

    def test_no_temporary_file_is_left_behind(self):
        write_document(self.path, "x\n")
        self.assertEqual(self.leftovers(), [])

    def test_failed_replace_keeps_the_previous_file(self):
        self.path.write_bytes(b"old\n")
        with patch("markvist.disk.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                write_document(self.path, "new\n", FileFormat("utf-8", "\n"))
        self.assertEqual(self.path.read_bytes(), b"old\n")
        self.assertEqual(self.leftovers(), [])

    def test_unencodable_text_never_touches_the_file(self):
        self.path.write_bytes(b"old\n")
        with self.assertRaises(UnicodeEncodeError):
            write_document(self.path, "broken \ud800\n")
        self.assertEqual(self.path.read_bytes(), b"old\n")
        self.assertEqual(self.leftovers(), [])

    def test_write_updates_the_signature(self):
        self.path.write_bytes(b"a\n")
        before = signature(self.path)
        write_document(self.path, "much longer text\n", FileFormat("utf-8", "\n"))
        self.assertNotEqual(signature(self.path), before)

    def test_non_utf8_file_is_read_and_saved_as_utf8(self):
        self.path.write_bytes(b"caf\xe9\n")
        text, fmt = read_document(self.path)
        self.assertTrue(text.startswith("caf"))
        self.assertEqual(fmt.encoding, "utf-8")
        write_document(self.path, "cafe\n", fmt)
        self.assertEqual(self.path.read_bytes(), b"cafe\n")


class DocumentFormatTest(unittest.TestCase):
    def test_commit_remembers_the_format(self):
        doc = Document(text="x", saved_text="x")
        self.assertIsNone(doc.fmt)
        fmt = FileFormat("utf-8-sig", "\r\n")
        doc.commit("x", fmt=fmt)
        self.assertIs(doc.fmt, fmt)

    def test_commit_keeps_the_format_when_none_is_given(self):
        fmt = FileFormat("utf-8", "\r\n")
        doc = Document(text="x", saved_text="x", fmt=fmt)
        doc.commit("y")
        self.assertIs(doc.fmt, fmt)

    def test_dirty_document_keeps_its_original_format(self):
        doc = Document(text="a", saved_text="a", fmt=FileFormat("utf-8", "\n"))
        doc.update("a\nb")
        self.assertEqual(doc.fmt.newline, "\n")


if __name__ == "__main__":
    unittest.main()
