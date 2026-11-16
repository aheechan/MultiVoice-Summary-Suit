"""Quick sanity check for the configured correction model.

Sends a few sentences with known ASR-style errors and prints what the model
returns, so model quality can be judged before wiring it into a long run.

Usage:
    python tools/llm_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from multivoice import config, llm  # noqa: E402

CASES = [
    "我们团队最近在做一个语音转雪的项目，主要是把音平文件转成文字。",
    "这个模型的准去率还不错，但是对专有名词的识别有待提高。",
    "他头也不抬：你先走，我留下来掩护你们撤退。顾永兴撤走了。",
]


def main() -> int:
    cfg = config.load()
    template = (ROOT / "prompts" / "correct.zh.txt").read_text(encoding="utf-8")
    for index, text in enumerate(CASES, 1):
        prompt = template.replace("{{GLOSSARY}}", "（无）").replace("{{TEXT}}", text)
        answer = llm.chat([{"role": "user", "content": prompt}], cfg,
                          temperature=0.0, max_tokens=512)
        print(f"--- case {index}")
        print(f"in : {text}")
        print(f"out: {answer}")
        print(f"same: {answer.strip() == text.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
