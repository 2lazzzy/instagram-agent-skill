#!/usr/bin/env python3
"""
ig_text.py - language-neutral text measurements the locale code reuses.

Display width (Hangul, CJK and emoji take two columns on a phone screen, Latin
takes one), emoji counted as what a person sees rather than as code points,
and width-aware cutting and wrapping so a box drawn around Korean text lines up.
"""

import re
import unicodedata

ZWJ = "‍"
VS16 = "️"
_SKIN = range(0x1F3FB, 0x1F400)
_RI = range(0x1F1E6, 0x1F200)

# Pictographic ranges. Arrows (U+2190-21FF) are deliberately excluded: in
# Korean and English captions alike, "->" style arrows are punctuation.
_PICTO = [
    (0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF), (0x231A, 0x231B),
    (0x23E9, 0x23FA), (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3297),
    (0x3299, 0x3299),
]


def is_pictographic(ch):
    cp = ord(ch)
    return any(a <= cp <= b for a, b in _PICTO)


def emoji_clusters(text):
    """Every emoji as one item: skin tones, VS16, ZWJ families and flags
    stay attached to their base, so 👩‍💻 is one emoji and not three."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        cp = ord(ch)
        if cp in _RI and i + 1 < n and ord(text[i + 1]) in _RI:
            out.append(text[i:i + 2])
            i += 2
            continue
        if not is_pictographic(ch):
            i += 1
            continue
        j = i + 1
        while j < n:
            c = ord(text[j])
            if text[j] == VS16 or c in _SKIN:
                j += 1
            elif text[j] == ZWJ and j + 1 < n and is_pictographic(text[j + 1]):
                j += 2
            else:
                break
        out.append(text[i:j])
        i = j
    return out


def char_width(ch):
    if ch in (ZWJ, VS16) or unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    if ord(ch) in _SKIN:
        return 0
    if is_pictographic(ch) or unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def display_width(text):
    return sum(char_width(c) for c in text)


def cut_width(text, width):
    """The longest prefix whose display width fits in `width`."""
    total = 0
    for i, ch in enumerate(text):
        w = char_width(ch)
        if total + w > width:
            return text[:i]
        total += w
    return text


def wrap_width(text, width):
    """Wrap one paragraph to `width` columns. Breaks at spaces when it can,
    and inside a word only when a single word is wider than the line."""
    lines, line = [], ""
    for word in re.split(r"(\s+)", text):
        if not word:
            continue
        if word.isspace():
            if line:
                line += " "
            continue
        candidate = line + word
        if display_width(candidate) <= width:
            line = candidate
            continue
        if line.strip():
            lines.append(line.rstrip())
            line = ""
        while display_width(word) > width:
            head = cut_width(word, width)
            lines.append(head)
            word = word[len(head):]
        line = word
    if line.strip() or not lines:
        lines.append(line.rstrip())
    return lines


def pad_width(text, width):
    return text + " " * max(0, width - display_width(text))
