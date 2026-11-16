from __future__ import annotations

import json
import re
from datetime import date

from . import search
from .config import Config, PROJECT_ROOT
from .glossary import Glossary
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "research.zh.txt"

GENERIC = {
    "视频", "内容", "工作", "产品", "公司", "市场", "用户", "功能", "版本",
    "价格", "模型", "行业", "技术", "问题", "时间", "今天", "今年",
}

# A term that ends with a function word is a bad span, not an entity.
STOP_SUFFIX = set("又就才还也都很是 的了着过和与在把被吗呢吧啊")
PUNCT = set("，。！？、；：（）【】《》“”‘’·…—")


def _parse(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def looks_like_entity(term: str) -> bool:
    term = term.strip()
    if len(term) < 2 or len(term) > 8:
        return False
    if term in GENERIC or term.isdigit():
        return False
    if term[-1] in STOP_SUFFIX or term[0] in STOP_SUFFIX:
        return False
    if any(ch in PUNCT or ch.isspace() for ch in term):
        return False
    return True


def research_term(term: str, glossary: Glossary, cfg: Config) -> dict | None:
    """Look up one term on the fly and store it with a validity window."""
    existing = glossary.find(term)
    if existing is not None:
        # Never overwrite a human-curated entry with an auto-generated one.
        if not existing.get("auto"):
            return existing
        if not glossary.is_stale(existing):
            return existing

    results = search.bing(f"{term} 是什么意思", limit=5)
    if not results:
        results = search.bing(term, limit=5)
    # A real entity should show up in at least one result title; otherwise the
    # term is probably an ASR artefact and must not enter the lexicon.
    if not results or not any(term in item["title"] for item in results):
        return None
    evidence = search.format_results(results)

    template = PROMPT.read_text(encoding="utf-8")
    prompt = (
        template.replace("{{TODAY}}", date.today().isoformat())
        .replace("{{TERM}}", term)
        .replace("{{EVIDENCE}}", evidence)
    )
    try:
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=1024)
        data = _parse(answer)
    except Exception:
        return None

    if data.get("definition") in ("资料不足", "", None):
        return None
    if data.get("confidence") == "low":
        return None

    entry = glossary.add(
        term,
        aliases=[a for a in data.get("aliases", []) if isinstance(a, str)],
        definition=data.get("definition", ""),
        en=data.get("en", ""),
        category=data.get("category", "other"),
        kind=data.get("kind", "other"),
        ttl_days=data.get("ttl_days"),
        confidence=data.get("confidence", "low"),
        sources=[item["url"] for item in results[:3]],
        auto=True,
    )
    return entry


def ensure_terms(
    terms: list[str], glossary: Glossary, cfg: Config, limit: int = 6
) -> list[dict]:
    """Research at most `limit` unknown or stale terms for this job."""
    budget = int(cfg.research.get("max_terms", limit))
    done: list[dict] = []
    for term in terms:
        if budget <= 0:
            break
        if not looks_like_entity(term):
            continue
        if not glossary.needs_research(term):
            continue
        entry = research_term(term, glossary, cfg)
        if entry:
            done.append(entry)
            budget -= 1
        else:
            glossary.queue(term, reason="no reliable source")
    return done
