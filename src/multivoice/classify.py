from __future__ import annotations

import json
import re

from .config import Config, PROJECT_ROOT
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "classify.zh.txt"

DOMAINS = {
    "history": "历史、政治、人物",
    "tech": "科技、编程、产品",
    "business": "商业、财经、管理",
    "science": "科学、医学、自然",
    "law": "法律、政策、制度",
    "education": "教育、课程、学习方法",
    "culture": "文化、艺术、娱乐",
    "life": "生活、健康、日常",
    "other": "其他",
}


def _parse(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def classify(text: str, cfg: Config) -> dict:
    """Identify the content domain and the proper nouns worth verifying."""
    template = PROMPT.read_text(encoding="utf-8")
    prompt = template.replace("{{TEXT}}", text[:3000])
    try:
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=1024)
        data = _parse(answer)
    except Exception:
        return {"domain": "other", "label": DOMAINS["other"], "terms": []}

    domain = data.get("domain", "other")
    if domain not in DOMAINS:
        domain = "other"
    terms = [t for t in data.get("terms", []) if isinstance(t, str) and t.strip()]
    return {"domain": domain, "label": DOMAINS[domain], "terms": terms[:10]}
