import unittest

from multivoice.vad import Span, merge_spans


class MergeSpansTests(unittest.TestCase):
    def test_single_long_span_is_split(self):
        """Loud-music audio yields one span; it must still be cut to 30 s."""
        spans = [Span(0.595, 453.83), Span(454.67, 455.10)]
        chunks = merge_spans(spans, max_seconds=30.0)
        self.assertGreater(len(chunks), 10)
        self.assertLessEqual(max(c.duration for c in chunks), 30.01)
        self.assertAlmostEqual(chunks[0].start, 0.595, places=2)
        self.assertAlmostEqual(chunks[-1].end, 455.10, places=2)

    def test_no_gap_is_lost(self):
        spans = [Span(0.0, 10.0), Span(10.0, 20.0), Span(20.0, 25.0)]
        chunks = merge_spans(spans, max_seconds=30.0)
        self.assertAlmostEqual(chunks[0].start, 0.0)
        self.assertAlmostEqual(chunks[-1].end, 25.0)


if __name__ == "__main__":
    unittest.main()
