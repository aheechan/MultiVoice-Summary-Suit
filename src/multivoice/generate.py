from __future__ import annotations

import json
import re

from .asr import Segment
from .config import Config, PROJECT_ROOT
from .llm import chat

META = re.compile(r"原文|误作|应为|实为|结合上下文|此处|音译|校注|注[:：]")
PAREN = re.compile(r"[（(][^（）()]{0,240}[）)]")


def _strip_notes(text: str) -> str:
    """Drop editorial parentheses such as '（原文误作…）' from the body."""

    def repl(match: re.Match) -> str:
        inner = match.group(0)[1:-1]
        return "" if META.search(inner) else match.group(0)

    return re.sub(r"[ \t]{2,}", " ", PAREN.sub(repl, text))


def _prompt(name: str) -> str:
    return (PROJECT_ROOT / "prompts" / name).read_text(encoding="utf-8")


def _guard(text: str, source: str, ratio: float, floor: int = 60) -> str:
    """Reject output that grew far beyond its source: that is fabrication, not editing."""
    text = _strip_notes(text)
    if not text.strip():
        return ""
    if len(text) > max(floor, int(len(source) * ratio)):
        return ""
    return text


def _fallback_brief(units: list[dict]) -> str:
    lines = ["**要点**", ""]
    for unit in units[:8]:
        title = (unit.get("title") or unit.get("detail") or "").strip()
        if title:
            lines.append(f"- {title[:60]}")
    return "\n".join(lines)


def _fallback_report(units: list[dict]) -> str:
    blocks = ["# 知识点清单", ""]
    for index, unit in enumerate(units, 1):
        blocks.append(f"## {index}. {(unit.get('title') or '未命名').strip()}")
        detail = (unit.get("detail") or "").strip()
        if detail:
            blocks.append(detail)
        evidence = unit.get("evidence") or []
        if evidence:
            blocks.append("")
            blocks.append("原文依据：" + "；".join(str(e) for e in evidence[:2]))
        blocks.append("")
    return "\n".join(blocks)


def clean_script(segments: list[Segment], cfg: Config) -> str:
    body = "\n".join(seg.text for seg in segments)
    prompt = _prompt("clean.zh.txt").replace("{{TEXT}}", body)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=4096)
    return _guard(answer, body, ratio=1.3) or body.strip()


def report(units: list[dict], cfg: Config, transcript: str = "") -> str:
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = _prompt("report.zh.txt").replace("{{UNITS}}", payload)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=6000)
    return _guard(answer, transcript or payload, ratio=1.6) or _fallback_report(units)


def brief(units: list[dict], cfg: Config, transcript: str = "") -> str:
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = _prompt("brief.zh.txt").replace("{{UNITS}}", payload)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=2000)
    return _guard(answer, transcript or payload, ratio=1.0) or _fallback_brief(units)


def english_doc(text: str, cfg: Config) -> str:
    """Translate a finished deliverable into English, keeping its structure."""
    if not text.strip():
        return ""
    prompt = (
        "Translate the following document into natural, professional English. "
        "Keep the markdown headings, bullet lists and paragraph breaks. "
        "Do not summarise or add content. "
        "Never replace a proper noun with a more famous lookalike; keep Latin-script "
        "names exactly as written. Output only the translation.\n\n" + text
    )
    return chat([{"role": "user", "content": prompt}], cfg, max_tokens=12000)


def chinese_doc(text: str, cfg: Config) -> str:
    """Translate a finished deliverable into Chinese, keeping its structure."""
    if not text.strip():
        return ""
    prompt = (
        "把下面这份文档翻译成自然、专业的中文。保留 Markdown 标题、列表和段落结构，"
        "不要总结、不要增删内容。英文人名、公司名、产品名、机构名一律保留英文原文，"
        "不要音译成中文。只输出译文。\n\n" + text
    )
    return chat([{"role": "user", "content": prompt}], cfg, max_tokens=12000)


def expand_draft(segments: list[Segment], units: list[dict], cfg: Config,
                 glossary_text: str = "", reference: str = "") -> str:
    """Rewrite the script with background added for non-common-sense points."""
    body = "\n".join(seg.text for seg in segments)
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = (
        _prompt("expand.zh.txt")
        .replace("{{TEXT}}", body)
        .replace("{{UNITS}}", payload)
        .replace("{{GLOSSARY}}", glossary_text or "（无）")
        .replace("{{REFERENCE}}", reference or "（无）")
    )
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=12000)
    target = max(800, int(len(body) * 2.6))
    if len(answer) > int(target * 1.2):
        # The model tends to over-write; condense once to the intended length.
        answer = chat(
            [{"role": "user", "content":
              f"把下面这篇稿件压缩到约 {target} 字，保留所有背景说明和专有名词解释，"
              "删除重复、空话和铺陈。只输出压缩后的正文。\n\n" + answer}],
            cfg, max_tokens=8000,
        )
    return _guard(answer, body, ratio=3.0, floor=int(target * 1.6)) or body.strip()
