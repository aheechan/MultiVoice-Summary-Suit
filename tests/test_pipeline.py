from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from multivoice import config, correct, generate, pipeline, structure, translate
from multivoice.asr import Segment


def fake_chat(messages, cfg, **kwargs):
    prompt = messages[0]["content"]
    if "JSON" in prompt:
        return json.dumps([
            {
                "id": "k1",
                "type": "claim",
                "title": "测试知识点",
                "detail": "细节",
                "evidence": ["原句"],
                "confidence": "high",
            }
        ], ensure_ascii=False)
    return "处理后的文本"


class TranslateTests(unittest.TestCase):
    def test_paragraphs_respect_limit(self):
        segments = [Segment(i, 0.0, 1.0, "句子" * 60) for i in range(4)]
        paras = translate.paragraphs(segments, "zh", max_chars=300)
        self.assertGreater(len(paras), 1)
        for para in paras:
            self.assertLessEqual(len(para), 240 + 120)

    def test_english_joins_with_space(self):
        segments = [Segment(0, 0.0, 1.0, "hello"), Segment(1, 1.0, 2.0, "world")]
        self.assertEqual(translate.paragraphs(segments, "en"), ["hello world"])


class FakeEngine:
    def transcribe(self, audio):
        return [Segment(0, 0.0, 2.0, "这是测试。")], "zh"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mvs-test-"))
        self.src = self.tmp / "tone.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             "-ac", "1", "-ar", "16000", str(self.src)],
            check=True, capture_output=True,
        )
        self.cfg = config.Config(
            work=self.tmp / "work",
            output=self.tmp / "out",
            models_root=self.tmp / "models",
            languages=["zh", "en"],
        )
        self.patches = [
            unittest.mock.patch.object(pipeline.asr, "build", return_value=FakeEngine()),
            unittest.mock.patch.object(correct, "chat", fake_chat),
            unittest.mock.patch.object(structure, "chat", fake_chat),
            unittest.mock.patch.object(generate, "chat", fake_chat),
            unittest.mock.patch.object(translate, "chat", fake_chat),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_full_run_creates_outputs(self):
        out = pipeline.run(self.src, self.cfg)
        self.assertTrue((out / "a-script.md").exists())
        self.assertTrue((out / "b-report.md").exists())
        self.assertTrue((out / "c-brief.md").exists())
        self.assertTrue((out / "text" / "original.txt").exists())
        self.assertTrue((out / "text" / "translated.en.txt").exists())
        self.assertTrue((out / "text" / "bilingual.zh-en.txt").exists())

    def test_second_run_resumes(self):
        pipeline.run(self.src, self.cfg)
        jobs = list((self.tmp / "work").iterdir())
        self.assertEqual(len(jobs), 1)
        pipeline.run(self.src, self.cfg)
        self.assertEqual(len(list((self.tmp / "work").iterdir())), 1)
        manifest = json.loads((jobs[0] / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["segments"], 1)


if __name__ == "__main__":
    unittest.main()
