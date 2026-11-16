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
    """Flag terms with no exact encyclopedia entry but plausible alternatives.

    Candidates are only taken from snippets that also mention another entity
    from the transcript, which keeps unrelated quoted words out.
    """
    all_terms = {item["term"] for item in items}
    findings: list[dict] = []
    for item in items:
        term = item["term"]
        if len(term) < 2:
            continue
        if any(hit["title"].strip() == term for hit in item["hits"]):
            continue

        anchors = all_terms - {term}
        candidates: list[str] = []
        for source in items:
            for hit in source["hits"]:
                if not _mentions(hit["snippet"], anchors):
                    continue
                for quoted in QUOTED.findall(hit["snippet"]):
                    if quoted and quoted != term and quoted not in all_terms:
                        if quoted not in candidates:
                            candidates.append(quoted)
        if candidates:
            findings.append({"term": term, "candidates": candidates[:3]})
    return findings


def to_markdown(findings: list[dict]) -> str:
    if not findings:
        return ""
    lines = ["# 待确认的专有名词", "", "以下词语未在检索资料中出现，请人工核对：", ""]
    for item in findings:
        lines.append(f"- **{item['term']}** → 可能应为：{' / '.join(item['candidates'])}")
    return "\n".join(lines) + "\n"
