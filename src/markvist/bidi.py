"""Visual reordering for right-to-left paragraphs.

Tk has no bidirectional text support before 9.1, so a Persian or Arabic
paragraph is drawn in logical order - the first letter ends up leftmost, which
reads backwards. This module reorders a line's style runs into *visual* order so
a left-to-right renderer shows the paragraph the way a reader expects.

It is deliberately small, not a full Unicode bidi implementation:

* runs are split into right-to-left (Arabic/Hebrew), left-to-right (Latin,
  digits) and neutral characters, which inherit the surrounding direction;
* in a right-to-left paragraph the run order is reversed and each
  right-to-left run is reversed character by character;
* combining marks stay attached to their base letter, and brackets are mirrored.

Because the text really is reversed, copying from such a line yields reversed
characters. Only use it for read-only display.
"""

from __future__ import annotations

import re
import unicodedata

from .markdown import RTL_CHARS_RE

WORD_RE = re.compile(r"[A-Za-z0-9_]")

MIRROR = {
    "(": ")",
    ")": "(",
    "[": "]",
    "]": "[",
    "{": "}",
    "}": "{",
    "<": ">",
    ">": "<",
    "«": "»",
    "»": "«",
}


def clusters(text: str) -> list[str]:
    """Split text into base characters with their combining marks attached."""
    out: list[str] = []
    for ch in text:
        if out and unicodedata.combining(ch):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def _direction(cluster: str) -> str:
    if RTL_CHARS_RE.search(cluster):
        return "rtl"
    if WORD_RE.search(cluster):
        return "ltr"
    return "neutral"


def visual_runs(tokens: list) -> list:
    """Reorder (text, styles, href) runs into visual order for an RTL paragraph."""
    items = []
    for text, styles, href in tokens:
        for cluster in clusters(text):
            items.append((cluster, styles, href))

    if not items:
        return tokens

    # Group into direction runs. Neutrals (spaces, punctuation) form their own
    # runs so that reversing the run order keeps them between the right words.
    runs: list[tuple[str, list]] = []
    current = None
    for cluster, styles, href in items:
        direction = _direction(cluster)
        if direction != current:
            runs.append((direction, []))
            current = direction
        runs[-1][1].append((cluster, styles, href))

    ordered: list = []
    for direction, group in reversed(runs):
        sequence = reversed(group) if direction == "rtl" else group
        for cluster, styles, href in sequence:
            ordered.append((MIRROR.get(cluster, cluster), styles, href))

    # Merge neighbours that share styling so the text widget does fewer inserts.
    merged: list = []
    for text, styles, href in ordered:
        if merged and merged[-1][1] == styles and merged[-1][2] == href:
            merged[-1] = (merged[-1][0] + text, styles, href)
        else:
            merged.append((text, styles, href))
    return merged
