"""Markdown parsing into plain block structures plus inline style runs.

No rendering happens here, so this module stays importable without a display.
"""

from __future__ import annotations

import re

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([\w#+.-]*)\s*$")
ATX_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
SETEXT1_RE = re.compile(r"^ {0,3}=+\s*$")
SETEXT2_RE = re.compile(r"^ {0,3}-{2,}\s*$")
HR_RE = re.compile(r"^ {0,3}((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})$")
QUOTE_RE = re.compile(r"^ {0,3}>\s?")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])(\s+|$)(.*)$")
TASK_RE = re.compile(r"^\[([ xX])\]\s+")
BLOCK_START_RE = re.compile(r"^ {0,3}(#{1,6}\s|>|`{3,}|~{3,}|([-*+]|\d{1,9}[.)])\s)")
HARD_BREAK_RE = re.compile(r"( {2,}|\\)$")

INLINE_RE = re.compile(
    r"`(?P<code>[^`\n]+)`"
    r"|!\[(?P<alt>[^\]]*)\]\((?P<isrc>[^)\s]+)(?:\s+\"(?P<ititle>[^\"]*)\")?\)"
    r"|\[(?P<label>[^\]]+)\]\((?P<href>[^)\s]+)(?:\s+\"(?P<htitle>[^\"]*)\")?\)"
)

EMPH_RE = re.compile(
    r"(?P<strong>\*\*|__)(?=\S)(?P<strong_body>.+?)(?<=\S)\1"
    r"|~~(?=\S)(?P<strike_body>.+?)(?<=\S)~~"
    r"|(?<![\w*])\*(?=\S)(?P<em_body>.+?)(?<=\S)\*(?![\w*])"
    r"|(?<![\w])_(?=\S)(?P<em2_body>.+?)(?<=\S)_(?![\w])",
    re.S,
)

# Persian / Arabic / Hebrew ranges, used for direction auto-detection.
RTL_CHARS_RE = re.compile(
    r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)
LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)

SCHEME_RE = re.compile(r"^([a-z][a-z0-9+.-]*):", re.I)
SAFE_SCHEMES = {"http", "https", "mailto"}


def detect_rtl(text: str) -> bool:
    """True when a meaningful share of the letters are Persian/Arabic/Hebrew."""
    rtl = len(RTL_CHARS_RE.findall(text))
    if not rtl:
        return False
    letters = len(LETTER_RE.findall(text))
    return rtl / max(1, letters) >= 0.3


def safe_url(url: str) -> str | None:
    """Return the URL when it is safe to open, otherwise None."""
    value = url.strip()
    match = SCHEME_RE.match(value)
    if match and match.group(1).lower() not in SAFE_SCHEMES:
        return None
    return value


def _text_tokens(text: str, styles: frozenset, href: str | None, out: list) -> None:
    pos = 0
    for m in EMPH_RE.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], styles, href))
        if m.group("strong_body") is not None:
            _text_tokens(m.group("strong_body"), styles | {"bold"}, href, out)
        elif m.group("strike_body") is not None:
            _text_tokens(m.group("strike_body"), styles | {"strike"}, href, out)
        elif m.group("em_body") is not None:
            _text_tokens(m.group("em_body"), styles | {"italic"}, href, out)
        else:
            _text_tokens(m.group("em2_body"), styles | {"italic"}, href, out)
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], styles, href))


def parse_inline(text: str, styles: frozenset = frozenset(), href: str | None = None) -> list:
    """Return a list of (text, styles, href) runs."""
    out: list = []
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            _text_tokens(text[pos:m.start()], styles, href, out)
        if m.group("code") is not None:
            out.append((m.group("code").strip(), styles | {"code"}, href))
        elif m.group("isrc") is not None:
            label = m.group("alt") or m.group("isrc")
            out.append((label, styles | {"image"}, safe_url(m.group("isrc"))))
        else:
            _text_tokens(m.group("label"), styles, safe_url(m.group("href")), out)
        pos = m.end()
    if pos < len(text):
        _text_tokens(text[pos:], styles, href, out)
    return out


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_table_sep(line: str) -> bool:
    if "|" not in line and not re.match(r"^\s*:?-+:?\s*$", line):
        return False
    cells = _split_row(line)
    return bool(cells) and all(re.match(r"^:?-+:?$", c) for c in cells)


def _is_block_start(line: str) -> bool:
    return bool(BLOCK_START_RE.match(line) or HR_RE.match(line))


def _parse_list(lines: list[str], i: int) -> tuple[list[dict], int]:
    entries: list[dict] = []
    base_indent = None
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n and (LIST_RE.match(lines[j]) or re.match(r"^\s{2,}\S", lines[j])):
                i = j
                continue
            break
        m = LIST_RE.match(line)
        if m:
            indent = len(m.group(1))
            if base_indent is None:
                base_indent = indent
            level = max(0, (indent - base_indent) // 2)
            marker = m.group(2)
            ordered = marker[0].isdigit()
            # A bullet list followed by a numbered list is two lists, not one.
            if level == 0 and entries and ordered != entries[0]["ordered"]:
                break
            number = int(re.match(r"\d+", marker).group()) if ordered else 0
            text = m.group(4)
            checked = None
            t = TASK_RE.match(text)
            if t:
                checked = t.group(1).lower() == "x"
                text = text[t.end():]
            entries.append(
                {
                    "level": level,
                    "ordered": ordered,
                    "number": number,
                    "checked": checked,
                    "lines": [text],
                }
            )
            i += 1
            continue
        if re.match(r"^\s{2,}\S", line) and entries:
            entries[-1]["lines"].append(line.strip())
            i += 1
            continue
        break

    for e in entries:
        e["tokens"] = [parse_inline(x) for x in e["lines"]]
    return entries, i


def parse_markdown(src: str) -> list[dict]:
    """Parse Markdown text into a list of block dictionaries."""
    lines = src.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[dict] = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            lang = m.group(2)
            close = re.compile(r"^ {0,3}" + re.escape(marker) + r"{3,}\s*$")
            buf: list[str] = []
            i += 1
            while i < n and not close.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1
            blocks.append({"kind": "code", "lang": lang, "text": "\n".join(buf)})
            continue

        m = ATX_RE.match(line)
        if m:
            blocks.append(
                {"kind": "heading", "level": len(m.group(1)), "tokens": parse_inline(m.group(2))}
            )
            i += 1
            continue

        if i + 1 < n and line.strip():
            if SETEXT1_RE.match(lines[i + 1]):
                blocks.append({"kind": "heading", "level": 1, "tokens": parse_inline(line.strip())})
                i += 2
                continue
            if SETEXT2_RE.match(lines[i + 1]):
                blocks.append({"kind": "heading", "level": 2, "tokens": parse_inline(line.strip())})
                i += 2
                continue

        if HR_RE.match(line):
            blocks.append({"kind": "hr"})
            i += 1
            continue

        if QUOTE_RE.match(line):
            buf = []
            while i < n and QUOTE_RE.match(lines[i]):
                buf.append(QUOTE_RE.sub("", lines[i], count=1))
                i += 1
            blocks.append({"kind": "quote", "blocks": parse_markdown("\n".join(buf))})
            continue

        if "|" in line and i + 1 < n and _is_table_sep(lines[i + 1]):
            head = [parse_inline(c) for c in _split_row(line)]
            aligns = []
            for c in _split_row(lines[i + 1]):
                left = c.startswith(":")
                right = c.endswith(":")
                aligns.append(
                    "center" if left and right else "right" if right else "left" if left else ""
                )
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append([parse_inline(c) for c in _split_row(lines[i])])
                i += 1
            blocks.append({"kind": "table", "head": head, "aligns": aligns, "rows": rows})
            continue

        if LIST_RE.match(line):
            entries, i = _parse_list(lines, i)
            blocks.append({"kind": "list", "entries": entries})
            continue

        para = []
        while i < n and lines[i].strip() and not (para and _is_block_start(lines[i])):
            para.append(lines[i])
            i += 1
        blocks.append(
            {
                "kind": "para",
                "lines": [parse_inline(l.rstrip("\\")) for l in para],
                "hard": [bool(HARD_BREAK_RE.search(l)) for l in para],
            }
        )

    return blocks
