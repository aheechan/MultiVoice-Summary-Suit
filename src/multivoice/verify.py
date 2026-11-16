from __future__ import annotations

import re

from . import wiki
from .config import Config

QUOTED = re.compile(r"[「“\"']([^」”\"']{1,16})[」”\"']")


def _mentions(snippet: str, anchors: set[str]) -> bool:
    """Match simplified/traditional variants by comparing the first two characters."""
    for anchor in anchors:
        if anchor in snippet:
            return True
        if len(anchor) >= 2 and anchor[:2] in snippet:
            return True
    return False


def build_evidence(terms: list[str], cfg: Config) -> tuple[str, list[dict]]:
    """Collect encyclopedia snippets used to fact-check the transcript."""
    if not cfg.verify.get("enabled", True) or not terms:
        return "（未启用联网核验）", []

    langs = cfg.verify.get("wiki_lang", ["zh", "en"])
    max_terms = int(cfg.verify.get("max_terms", 8))
    items = wiki.evidence_for(terms[:max_terms], langs)
    return wiki.format_evidence(items), items


def suggest(items: list[dict], evidence: str) -> list[dict]:
    """List terms that have no exact encyclopedia entry.

    We deliberately do not guess replacements: an unverified suggestion is worse
    than no suggestion. The evidence block still goes to the model.
    """
    exact_terms = {
        item["term"]
        for item in items
        if any(hit["title"].strip() == item["term"] for hit in item["hits"])
    }
    return [
        {"term": item["term"], "candidates": []}
        for item in items
        if len(item["term"]) >= 2 and item["term"] not in exact_terms
    ]


def to_markdown(findings: list[dict]) -> str:
    if not findings:
        return ""
    lines = ["# 待确认的专有名词", "", "以下词语没有在检索资料中找到对应条目，请人工核对：", ""]
    for item in findings:
        lines.append(f"- **{item['term']}**")
    return "\n".join(lines) + "\n"
