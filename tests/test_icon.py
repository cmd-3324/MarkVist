import struct
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from markvist.icon import ICON_NAME, PNG_SIGNATURE, ico_entries, ico_png, icon_path


def png_size(data: bytes) -> tuple[int, int]:
    width, height = struct.unpack_from(">II", data, 16)
    return width, height


class IconPathTest(unittest.TestCase):
    def test_finds_the_icon_in_the_project(self):
        path = icon_path()
        self.assertIsNotNone(path)
        self.assertEqual(path.name, ICON_NAME)
        self.assertTrue(path.is_file())

    def test_finds_the_icon_in_a_bundle(self):
        with TemporaryDirectory() as tmp:
            bundled = Path(tmp) / ICON_NAME
            bundled.write_bytes((ROOT / ICON_NAME).read_bytes())
            saved = getattr(sys, "_MEIPASS", None)
            sys._MEIPASS = tmp
            try:
                self.assertEqual(icon_path(), bundled)
            finally:
                if saved is None:
                    del sys._MEIPASS
                else:
                    sys._MEIPASS = saved


class IcoDecodeTest(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / ICON_NAME

    def test_entries_are_listed(self):
        entries = ico_entries(self.path.read_bytes())
        self.assertTrue(entries)
        self.assertTrue(all(bits == 32 for _w, _h, bits, _s, _o in entries))
        self.assertIn(256, [w for w, _h, _b, _s, _o in entries])

    def test_decodes_to_a_png(self):
        data = ico_png(self.path)
        self.assertIsNotNone(data)
        self.assertTrue(data.startswith(PNG_SIGNATURE))
        width, height = png_size(data)
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 32)

    def test_size_preference_is_honoured(self):
        data = ico_png(self.path, size=16)
        self.assertIsNotNone(data)
        self.assertEqual(png_size(data), (16, 16))

    def test_rejects_a_file_that_is_not_an_icon(self):
        with TemporaryDirectory() as tmp:
            fake = Path(tmp) / "fake.ico"
            fake.write_bytes(b"not an icon at all")
            self.assertIsNone(ico_png(fake))
            self.assertEqual(ico_entries(b"nope"), [])

    def test_missing_file_returns_none(self):
        self.assertIsNone(ico_png(ROOT / "does-not-exist.ico"))


if __name__ == "__main__":
    unittest.main()
