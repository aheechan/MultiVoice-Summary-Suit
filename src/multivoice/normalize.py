from __future__ import annotations

import re

# ASR often renders Latin+digit names with Chinese numerals: V4 -> V四, Work8 -> Work八.
LETTER_DIGIT = re.compile(r"([A-Za-z])([一二三四五六七八九])")
# Years spoken digit by digit: 二零二六 -> 2026 (only when followed by 年).
SPOKEN_YEAR = re.compile(r"(?<!\d)([零一二三四五六七八九]{4})(?=年)")

CN_DIGIT = {
    "零": "0", "一": "1", "二": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
}


def normalize(text: str) -> str:
    """Apply deterministic fixes that never change meaning."""
    text = LETTER_DIGIT.sub(lambda m: m.group(1) + CN_DIGIT[m.group(2)], text)
    text = SPOKEN_YEAR.sub(lambda m: "".join(CN_DIGIT[c] for c in m.group(1)), text)
    return text


def normalize_segments(segments):
    """Return segments with normalized text and the number of changed segments."""
    changed = 0
    for seg in segments:
        fixed = normalize(seg.text)
        if fixed != seg.text:
            changed += 1
            seg.text = fixed
    return segments, changed
