"""Audit proper nouns against collected evidence before the LLM correction pass."""
from __future__ import annotations

import json

from .asr import Segment
from .config import Config
from .llm import chat

PROMPT = """你是专名校对员。下面是一段转写稿、候选专有名词、词条库和检索资料。

任务：判断候选专名是否被听错，并给出正确写法。只依据词条库与检索资料，不要凭印象。

输出 JSON 数组，每项：
{{"wrong": "原文里的写法", "right": "资料里的正确写法", "confidence": "high|medium|low"}}

规则：
1. 只有检索资料或词条库里明确出现正确写法时才给出 high。
2. 资料里没有的，一律 low，不要猜。
3. 不要提出与候选无关的修改。
4. 没有需要修改的就输出 []。只输出 JSON。

【候选】
{terms}

【词条库】
{glossary}

【检索资料】
{evidence}

【原文片段】
{body}
"""


def _parse(answer: str) -> list[dict]:
    start, end = answer.find("["), answer.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(answer[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [item for item in data if isinstance(item, dict)]


def audit(segments: list[Segment], candidates: list[str], evidence: str,
          glossary_text: str, cfg: Config) -> list[tuple[str, str]]:
    """Apply only high-confidence name fixes; everything else stays for review."""
    if not segments or not candidates or not evidence:
        return []
    if evidence.startswith("（未启用"):
        return []

    body = "\n".join(seg.text for seg in segments)[:3000]
    prompt = (
        PROMPT.replace("{terms}", json.dumps(candidates[:8], ensure_ascii=False))
        .replace("{glossary}", glossary_text or "（无）")
        .replace("{evidence}", evidence[:4000])
        .replace("{body}", body)
    )
    try:
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=800)
    except Exception:
        return []

    applied: list[tuple[str, str]] = []
    for item in _parse(answer):
        if str(item.get("confidence", "")).lower() != "high":
            continue
        wrong = str(item.get("wrong", "")).strip()
        right = str(item.get("right", "")).strip()
        if not wrong or not right or wrong == right:
            continue
        if wrong not in body:
            continue
        if right in body and wrong not in body:
            continue
        for segment in segments:
            if wrong in segment.text:
                segment.text = segment.text.replace(wrong, right)
        applied.append((wrong, right))
    return applied
