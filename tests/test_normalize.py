from __future__ import annotations

import unittest

from multivoice.normalize import normalize
from multivoice.asr import Segment
from multivoice.normalize import normalize_segments


class NormalizeTests(unittest.TestCase):
    def test_latin_number_names(self):
        self.assertEqual(normalize("V四Flash 和 V四Pro"), "V4Flash 和 V4Pro")
        self.assertEqual(normalize("Work八D"), "Work8D")

    def test_does_not_touch_numerals_in_words(self):
        self.assertEqual(normalize("V4Pro一起发布"), "V4Pro一起发布")
        self.assertEqual(normalize("统一一下"), "统一一下")

    def test_spoken_years(self):
        self.assertEqual(normalize("二零二六下半年"), "2026下半年")
        self.assertEqual(normalize("二零二五年"), "2025年")

    def test_segments_report_changes(self):
        segments = [
            Segment(0, 0.0, 1.0, "V四Flash"),
            Segment(1, 1.0, 2.0, "没有变化"),
        ]
        _, changed = normalize_segments(segments)
        self.assertEqual(changed, 1)
        self.assertEqual(segments[0].text, "V4Flash")


if __name__ == "__main__":
    unittest.main()
