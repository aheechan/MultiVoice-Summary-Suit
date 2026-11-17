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


def research_term(term: str, glossary: Glossary, cfg: Config) -> tuple[dict | None, bool]:
    """Look up one term on the fly.

    Returns (entry, ambiguous). `ambiguous` is True when search found something
    but the model could not confirm it; False means there is no such thing.
    """
    existing = glossary.find(term)
    if existing is not None:
        if not existing.get("auto"):
            return existing, False
        if not glossary.is_stale(existing):
            return existing, False

    results = search.bing(f"{term} 是什么意思", limit=5)
    if results is None:
        # Request failed: do not conclude anything about the term.
        return None, True
    if not results:
        results = search.bing(term, limit=5)
        if results is None:
            return None, True
    if not results or not any(term in item["title"] for item in results):
        return None, False
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
        return None, True

    if data.get("definition") in ("资料不足", "", None):
        return None, True
    if data.get("confidence") == "low":
        return None, True

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
    return entry, False


def triage(terms: list[str], cfg: Config, context: str = "") -> list[str]:
    """Split candidates into proper nouns (worth a lexicon entry) and ordinary phrases."""
    terms = [t for t in terms if t]
    if not terms or cfg is None:
        return terms
    prompt = (
        "下面是一段口播转写里抽出的词。请把它们分成两类：\n"
        "A. 专有名词：人名、地名、机构、产品/版本、作品、具体事件名——值得建词条；\n"
        "B. 其余：网络流行语、形容词短语、常见名词组合、口语表达——识别正确，不需要建词条。\n\n"
        "只输出 JSON：{\"entity\": [...], \"common\": [...]}\n"
        f"上下文片段：{context[:400]}\n"
        f"词表：{json.dumps(terms, ensure_ascii=False)}"
    )
    try:
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=400)
        start, end = answer.find("{"), answer.rfind("}")
        data = json.loads(answer[start:end + 1])
        entity = [t for t in data.get("entity", []) if t in terms]
        return entity or terms
    except Exception:
        return terms


def queue_candidates(
    terms: list[str], glossary: Glossary, limit: int = 8,
    reason: str = "from-job", context: str = "", source: str = "", when: str = "",
    positions: dict[str, str] | None = None,
) -> list[str]:
    """Queue unknown terms for human review instead of writing them silently."""
    queued: list[str] = []
    for term in terms:
        if len(queued) >= limit:
            break
        if not looks_like_entity(term):
            continue
        if glossary.find(term) is not None:
            continue
        if any(term in entry.get("aliases", []) for entry in glossary.entries):
            continue
        if term in glossary.corrections:
            continue
        if glossary.is_rejected(term):
            continue
        snippet = ""
        if context:
            position = context.find(term)
            if position >= 0:
                snippet = context[max(0, position - 60):position + len(term) + 60]
        already = any(item["term"] == term for item in glossary.pending)
        glossary.queue(term, reason=reason)
        if snippet or source or when or positions:
            for item in glossary.pending:
                if item["term"] == term:
                    if snippet:
                        item["context"] = snippet
                    if source:
                        item["source"] = source
                    if when:
                        # Reflect the job that most recently mentioned it.
                        item["seen_at"] = when
                    if positions and term in positions:
                        item["video_at"] = positions[term]
            glossary.save()
        if already:
            continue
        queued.append(term)
    return queued


def suggest_correction(term: str, context: str, cfg: Config) -> str:
    """Ask the model whether a term is a mis-recognition of a similar name."""
    if cfg is None:
        return ""
    if context:
        body = (
            "下面是一段转写文本的片段，其中出现了词条「" + term + "」。\n"
            f"上下文：{context}\n\n"
            "请判断这个词条是否很可能是另一个相近词（人名、地名、专有名词）的误识别。"
            "如果很可能写错了，只输出正确写法；如果识别无误，原样输出该词条。"
            "不要解释，不要标点。"
        )
    else:
        body = (
            f"「{term}」来自一段中文音频转写，可能是同音字或近音字写错。"
            "如果你确信存在更常见的正确写法（人名、地名、专有名词），只输出那个写法；"
            "否则原样输出该词条。不要解释，不要标点。"
        )
    try:
        answer = chat([{"role": "user", "content": body}], cfg,
                      temperature=0.0, max_tokens=32)
        candidate = answer.strip().strip("。.,，")
        return candidate if candidate and candidate != term else ""
    except Exception:
        return ""


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
        entry, ambiguous = research_term(term, glossary, cfg)
        if entry:
            done.append(entry)
            glossary.resolve_pending(term)
            budget -= 1
        elif ambiguous:
            # Search found something but the model could not confirm it.
            glossary.queue(term, reason="unconfirmed")
        # otherwise: no such term anywhere -> drop silently
    return done
