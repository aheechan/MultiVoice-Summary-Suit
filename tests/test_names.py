import unittest

from multivoice import names
from multivoice.generate import _strip_notes


class StripNotesTests(unittest.TestCase):
    def test_editorial_parentheses_removed(self):
        text = "英国约克郡（原文误作莱约克郡）有一百五十人"
        self.assertNotIn("原文误作", _strip_notes(text))
        self.assertIn("英国约克郡", _strip_notes(text))

    def test_normal_parentheses_kept(self):
        text = "蒸汽机（瓦特改良）改变了生产"
        self.assertEqual(_strip_notes(text), text)


class NameAuditParseTests(unittest.TestCase):
    def test_parse_filters_non_objects(self):
        answer = '[{"wrong":"甲","right":"乙","confidence":"high"}, "junk"]'
        parsed = names._parse(answer)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["right"], "乙")

    def test_parse_without_json(self):
        self.assertEqual(names._parse("没有结果"), [])


if __name__ == "__main__":
    unittest.main()
