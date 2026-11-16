from __future__ import annotations

from pathlib import Path

from .asr import Segment
from .config import PROJECT_ROOT, Config
from .llm import chat

LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어"}

TEMPLATES = {
    ("zh", "en"): "translate.zh2en.txt",
    ("en", "zh"): "translate.en2zh.txt",
}


def paragraphs(segments: list[Segment], lang: str = "zh", max_chars: int = 800) -> list[str]:
    """Group segments into readable paragraphs without breaking mid-sentence."""
    separator = "" if lang == "zh" else " "
    result: list[str] = []
    buffer: list[str] = []
    size = 0
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        buffer.append(text)
        size += len(text)
        if size >= max_chars:
            result.append(separator.join(buffer))
            buffer, size = [], 0
    if buffer:
        result.append(separator.join(buffer))
    return result


def _translate_one(text: str, source: str, target: str, cfg: Config) -> str:
    template_path = TEMPLATES.get((source, target))
    if template_path:
        template = (PROJECT_ROOT / "prompts" / template_path).read_text(encoding="utf-8")
        prompt = template.replace("{{TEXT}}", text)
    else:
        prompt = (
            f"Translate the following {LANG_NAMES.get(source, source)} text into "
            f"{LANG_NAMES.get(target, target)}. Keep the meaning, tone and paragraph "
            f"structure. Output only the translation.\n\n{text}"
        )
    return chat([{"role": "user", "content": prompt}], cfg, temperature=0.1,
                max_tokens=max(512, len(text) * 2))


def translate_paragraphs(
    paras: list[str], source: str, target: str, cfg: Config
) -> list[str]:
    return [_translate_one(p, source, target, cfg) for p in paras]


def write_bilingual(
    directory: Path,
    paras: list[str],
    translated: list[str],
    source: str,
    target: str,
) -> dict[str, Path]:
    """Write original / translated / side-by-side files."""
    directory.mkdir(parents=True, exist_ok=True)
    original = directory / "original.txt"
    translation = directory / f"translated.{target}.txt"
    side_by_side = directory / f"bilingual.{source}-{target}.txt"

    original.write_text("\n\n".join(paras), encoding="utf-8")
    translation.write_text("\n\n".join(translated), encoding="utf-8")

    pairs = []
    for left, right in zip(paras, translated):
        pairs.append(f"【{source}】\n{left}\n\n【{target}】\n{right}")
    side_by_side.write_text("\n\n---\n\n".join(pairs), encoding="utf-8")

    return {
        "original": original,
        "translated": translation,
        "bilingual": side_by_side,
    }
