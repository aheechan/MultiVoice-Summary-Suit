from __future__ import annotations

import json
import re

from . import search
from .config import Config, PROJECT_ROOT
from .glossary import Glossary
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "discover.zh.txt"


def _parse_list(text: str) -> list[str]:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    return [item for item in data if isinstance(item, str)]


def propose_terms(topic: str, glossary: Glossary, cfg: Config) -> list[str]:
    results = search.bing(f"{topic} 最新 梗 动态", limit=8)
    if not results:
        return []
    known = "、".join(entry["term"] for entry in glossary.entries[:40]) or "（空）"
    template = PROMPT.read_text(encoding="utf-8")
    prompt = (
        template.replace("{{TOPIC}}", topic)
        .replace("{{KNOWN}}", known)
        .replace("{{EVIDENCE}}", search.format_results(results))
    )
    try:
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=512)
        return _parse_list(answer)
    except Exception:
        return []


def _normalize(term: str) -> str:
    return (term.lower().replace("-", "").replace("_", "")
            .replace(" ", "").replace("　", "").strip())


def _acceptable(term: str, known: set[str]) -> bool:
    term = term.strip()
    if not (2 <= len(term) <= 8):
        return False
    if any(ch.isspace() for ch in term):
        return False
    if _normalize(term) in known:
        return False
    # Drop phrases that are descriptions rather than names.
    if any(word in term for word in (
        "系列", "输入", "输出", "价格", "功能", "自动", "缓存", "推理",
        "训练", "接口", "平台", "服务", "模型", "参数",
        "短信", "通知", "伪装", "钓鱼", "回复", "确认", "点击", "邮件",
        "客服", "电话", "链接", "指南", "教程", "方法",
    )):
        return False
    return True


def run(glossary: Glossary, cfg: Config, per_topic: int = 6) -> dict:
    """Queue fresh candidate terms for human review. Never writes entries."""
    topics = list(glossary.topics) or ["deepseek"]
    known = {_normalize(entry["term"]) for entry in glossary.entries}
    added = 0
    for topic in topics:
        terms = propose_terms(topic, glossary, cfg)[:per_topic]
        for term in terms:
            term = term.strip()
            if not _acceptable(term, known):
                continue
            if any(item["term"] == term for item in glossary.pending):
                continue
            glossary.queue(term, reason=f"discovered:{topic}")
            known.add(_normalize(term))
            added += 1
    return {"queued": added, "topics": topics}
