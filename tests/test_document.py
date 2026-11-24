import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from markvist.document import UNTITLED, Document


class DocumentTest(unittest.TestCase):
    def test_untitled_name(self):
        self.assertEqual(Document().name, UNTITLED)

    def test_name_from_path(self):
        self.assertEqual(Document(path=Path("notes.md")).name, "notes.md")

    def test_update_tracks_dirty(self):
        doc = Document(text="a", saved_text="a")
        doc.update("a")
        self.assertFalse(doc.dirty)
        doc.update("b")
        self.assertTrue(doc.dirty)
        doc.update("a")
        self.assertFalse(doc.dirty)

    def test_commit_clears_dirty_and_sets_path(self):
        doc = Document(text="x", saved_text="", dirty=True)
        doc.commit("x", Path("new.md"))
        self.assertFalse(doc.dirty)
        self.assertEqual(doc.name, "new.md")
        self.assertEqual(doc.saved_text, "x")

    def test_label_marks_dirty(self):
        doc = Document(path=Path("a.md"), dirty=True)
        self.assertTrue(doc.label.startswith("●"))
        self.assertTrue(doc.label.endswith("a.md"))


if __name__ == "__main__":
    unittest.main()
