from __future__ import annotations

import json
import unittest
import unittest.mock

from multivoice import classify, generate, verify
from multivoice.asr import Segment


class GuardTests(unittest.TestCase):
    def test_clean_script_rejects_expansion(self):
        source = "第一句。第二句。"
        segments = [Segment(0, 0.0, 1.0, source)]
        with unittest.mock.patch.object(generate, "chat", return_value="啊" * 500):
            out = generate.clean_script(segments, cfg=None)
        self.assertEqual(out, source)

    def test_clean_script_keeps_normal_output(self):
        source = "第一句。第二句。"
        segments = [Segment(0, 0.0, 1.0, source)]
        with unittest.mock.patch.object(generate, "chat", return_value="整理后的两句话。"):
            out = generate.clean_script(segments, cfg=None)
        self.assertEqual(out, "整理后的两句话。")

    def test_brief_rejects_long_output(self):
        units = [{"id": "k1", "title": "短标题", "detail": "细节"}]
        with unittest.mock.patch.object(generate, "chat", return_value="很长的快报" * 50):
            out = generate.brief(units, cfg=None, transcript="原文本")
        self.assertIn("短标题", out)
        self.assertNotIn("很长的快报", out)

    def test_empty_answer_falls_back(self):
        segments = [Segment(0, 0.0, 1.0, "原文")]
        with unittest.mock.patch.object(generate, "chat", return_value="   "):
            self.assertEqual(generate.clean_script(segments, cfg=None), "原文")


class VerifyTests(unittest.TestCase):
    def make_items(self):
        return [
            {
                "term": "红线",
                "lang": "zh",
                "hits": [{
                    "title": "红线女",
                    "snippet": "袁世凱原定年号为「洪宪」，与红线并无关系。",
                }],
            },
            {
                "term": "袁世凯",
                "lang": "zh",
                "hits": [{"title": "袁世凯", "snippet": "原定年号为「洪宪」。"}],
            },
        ]

    def test_flags_term_without_exact_entry(self):
        items = self.make_items()
        evidence = verify.wiki.format_evidence(items)
        findings = verify.suggest(items, evidence)
        terms = {f["term"] for f in findings}
        self.assertIn("红线", terms)

    def test_ignores_term_with_exact_entry(self):
        items = self.make_items()
        findings = verify.suggest(items, verify.wiki.format_evidence(items))
        self.assertNotIn("袁世凯", {f["term"] for f in findings})

    def test_markdown_lists_terms(self):
        md = verify.to_markdown([{"term": "红线", "candidates": []}])
        self.assertIn("红线", md)
        self.assertIn("待确认", md)


class ClassifyTests(unittest.TestCase):
    def test_parses_json_answer(self):
        answer = json.dumps({"domain": "history", "terms": ["袁世凯"]}, ensure_ascii=False)
        with unittest.mock.patch.object(classify, "chat", return_value=answer):
            result = classify.classify("some text", cfg=None)
        self.assertEqual(result["domain"], "history")
        self.assertEqual(result["terms"], ["袁世凯"])

    def test_falls_back_on_error(self):
        with unittest.mock.patch.object(classify, "chat", side_effect=RuntimeError("down")):
            result = classify.classify("some text", cfg=None)
        self.assertEqual(result["domain"], "other")
        self.assertEqual(result["terms"], [])

    def test_unknown_domain_maps_to_other(self):
        answer = json.dumps({"domain": "astrology", "terms": []})
        with unittest.mock.patch.object(classify, "chat", return_value=answer):
            self.assertEqual(classify.classify("x", cfg=None)["domain"], "other")


if __name__ == "__main__":
    unittest.main()
