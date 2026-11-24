import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from markvist.markdown import detect_rtl, parse_inline, parse_markdown, safe_url


class ParseMarkdownTest(unittest.TestCase):
    def kinds(self, source):
        return [b["kind"] for b in parse_markdown(source)]

    def test_block_kinds(self):
        source = (
            "# Title\n\nText.\n\n- a\n- b\n\n1. one\n\n> quote\n\n"
            "| a | b |\n|:--|--:|\n| 1 | 2 |\n\n```py\nx = 1\n```\n\n---\n"
        )
        self.assertEqual(
            self.kinds(source),
            ["heading", "para", "list", "list", "quote", "table", "code", "hr"],
        )

    def test_setext_headings(self):
        blocks = parse_markdown("Title\n=====\n\nSub\n---\n")
        self.assertEqual([b["level"] for b in blocks], [1, 2])

    def test_fence_language_and_body(self):
        code = [b for b in parse_markdown("```python\nprint(1)\n```") if b["kind"] == "code"][0]
        self.assertEqual(code["lang"], "python")
        self.assertEqual(code["text"], "print(1)")

    def test_table_alignment(self):
        table = [b for b in parse_markdown("| a | b | c |\n|:--|--:|:-:|\n| 1 | 2 | 3 |")
                 if b["kind"] == "table"][0]
        self.assertEqual(table["aligns"], ["left", "right", "center"])
        self.assertEqual(len(table["rows"]), 1)

    def test_list_levels_and_tasks(self):
        entries = [b for b in parse_markdown("- a\n  - b\n- [x] done\n- [ ] todo")
                   if b["kind"] == "list"][0]["entries"]
        self.assertEqual([e["level"] for e in entries], [0, 1, 0, 0])
        self.assertEqual([e["checked"] for e in entries], [None, None, True, False])

    def test_ordered_list_numbers(self):
        entries = [b for b in parse_markdown("3. three\n4. four") if b["kind"] == "list"][0]["entries"]
        self.assertEqual([e["number"] for e in entries], [3, 4])

    def test_inline_styles(self):
        runs = parse_inline("a **b** *c* `d` ~~e~~")
        styles = [sorted(s) for _t, s, _h in runs]
        self.assertIn(["bold"], styles)
        self.assertIn(["italic"], styles)
        self.assertIn(["code"], styles)
        self.assertIn(["strike"], styles)

    def test_hard_break_and_paragraph_join(self):
        block = parse_markdown("one  \ntwo")[0]
        self.assertEqual(block["hard"], [True, False])


class UrlSafetyTest(unittest.TestCase):
    def test_allows_http_and_relative(self):
        self.assertEqual(safe_url("https://example.com"), "https://example.com")
        self.assertEqual(safe_url("notes.md"), "notes.md")
        self.assertEqual(safe_url("#anchor"), "#anchor")

    def test_rejects_dangerous_schemes(self):
        for url in ("javascript:alert(1)", "file:///C:/Windows", "data:text/html,x", "vbscript:x"):
            self.assertIsNone(safe_url(url), url)


class DirectionTest(unittest.TestCase):
    def test_persian_is_rtl(self):
        self.assertTrue(detect_rtl("این یک متن فارسی است"))

    def test_english_is_not_rtl(self):
        self.assertFalse(detect_rtl("This is plain English text"))

    def test_mostly_code_is_not_rtl(self):
        self.assertFalse(detect_rtl("def f():\n    return 1  # سلام"))


if __name__ == "__main__":
    unittest.main()
