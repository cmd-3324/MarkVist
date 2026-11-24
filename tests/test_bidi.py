import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from markvist.bidi import clusters, visual_runs

BODY = frozenset()


def text_of(tokens):
    return "".join(t for t, _s, _h in tokens)


class VisualRunsTest(unittest.TestCase):
    def test_pure_rtl_is_reversed_for_display(self):
        self.assertEqual(text_of(visual_runs([("سلام", BODY, None)])), "مالس")

    def test_runs_swap_but_latin_stays_readable(self):
        tokens = [("سلام", BODY, None), (" abc ", BODY, None), ("دنیا", BODY, None)]
        self.assertEqual(text_of(visual_runs(tokens)), "ایند abc مالس")

    def test_combining_marks_stay_with_base(self):
        tokens = [("اِ", BODY, None)]
        self.assertEqual(text_of(visual_runs(tokens)), "اِ")

    def test_brackets_are_mirrored(self):
        self.assertEqual(text_of(visual_runs([("(سلام)", BODY, None)])), "(مالس)")

    def test_styles_survive_reordering(self):
        bold = frozenset({"bold"})
        out = visual_runs([("سلام", bold, None), (" دنیا", BODY, None)])
        self.assertTrue(any(styles == bold for _t, styles, _h in out))
        self.assertEqual(text_of(out), "ایند مالس")

    def test_links_survive_reordering(self):
        out = visual_runs([("سلام", BODY, "https://example.com")])
        self.assertTrue(any(href == "https://example.com" for _t, _s, href in out))

    def test_clusters_attach_marks(self):
        # alef + kasra (combining) then a Latin letter
        self.assertEqual(clusters("\u0627\u0650b"), ["\u0627\u0650", "b"])

    def test_empty_input(self):
        self.assertEqual(visual_runs([]), [])


if __name__ == "__main__":
    unittest.main()
