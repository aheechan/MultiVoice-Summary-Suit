from __future__ import annotations

import json
import re

from . import search
from .config import Config, PROJECT_ROOT
from .glossary import Glossary
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "glossary.zh.txt"


def _parse(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def draft(term: str, cfg: Config) -> tuple[dict, list[dict]]:
    """Search the web for a term and ask the model to draft a lexicon entry."""
    results = search.bing(f"{term} 是什么意思 梗", limit=5)
    evidence = search.format_results(results)

    template = PROMPT.read_text(encoding="utf-8")
    prompt = template.replace("{{TERM}}", term).replace("{{EVIDENCE}}", evidence)
    answer = chat([{"role": "user", "content": prompt}], cfg,
                  temperature=0.0, max_tokens=1024)
    data = _parse(answer)
    data["sources"] = [item["url"] for item in results[:3]]
    return data, results


def learn(term: str, glossary: Glossary, cfg: Config) -> dict:
    data, _ = draft(term, cfg)
    entry = glossary.add(
        term,
        aliases=[a for a in data.get("aliases", []) if isinstance(a, str)],
        definition=data.get("definition", ""),
        en=data.get("en", ""),
        category=data.get("category", "other"),
        sources=data.get("sources", []),
        auto=True,
    )
    return entry
