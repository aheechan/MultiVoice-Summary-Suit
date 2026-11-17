from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

from . import search, sources
from .config import Config, PROJECT_ROOT
from .glossary import Glossary, DEFAULT_PATH
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "review_summary.zh.txt"
CACHE_PATH = Path(DEFAULT_PATH).with_name("review_cache.json")
TTL_DAYS = 7


def _read_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_cache(data: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def drop_cache(term: str) -> None:
    data = _read_cache()
    if term in data:
        data.pop(term)
        _write_cache(data)


def cached(term: str) -> dict | None:
    entry = _read_cache().get(term)
    if not entry:
        return None
    try:
        age = (date.today() - datetime.fromisoformat(entry["at"]).date()).days
    except (KeyError, ValueError):
        return None
    return entry if age <= TTL_DAYS else None


def _summary(term: str, cfg: Config, zh: list[dict], en: list[dict]) -> tuple[str, str]:
    template = PROMPT.read_text(encoding="utf-8")
    prompt = (
        template.replace("{{TERM}}", term)
        .replace("{{ZH}}", search.format_results(zh) or "（无）")
        .replace("{{EN}}", search.format_results(en) or "（无）")
    )
    try:
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=512)
        start, end = answer.find("{"), answer.rfind("}")
        data = json.loads(answer[start:end + 1])
        return data.get("zh", "").strip(), data.get("en", "").strip()
    except Exception:
        return "", ""


def _summary_from_evidence(term: str, cfg: Config, evidence: list[dict]) -> tuple[str, str]:
    template = PROMPT.read_text(encoding="utf-8")
    zh_lines, en_lines = [], []
    for item in evidence:
        line = f"[{item['source']}] {item['title']}: {item['snippet'][:400]}"
        if "en" in item["source"].lower():
            en_lines.append(line)
        else:
            zh_lines.append(line)
    prompt = (
        template.replace("{{TERM}}", term)
        .replace("{{ZH}}", "\n".join(zh_lines) or "（无）")
        .replace("{{EN}}", "\n".join(en_lines) or "（无）")
    )
    try:
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=600)
        start, end = answer.find("{"), answer.rfind("}")
        data = json.loads(answer[start:end + 1])
        return data.get("zh", "").strip(), data.get("en", "").strip()
    except Exception:
        return "", ""


def _probable_name(term: str) -> bool:
    """Short or generic strings (朱志, Harness, V4) must never be auto-imported."""
    if any("\u4e00" <= char <= "\u9fff" for char in term):
        return len(term) >= 3
    return len(term.split()) >= 2 and len(term) >= 5


def _similar_known(term: str, lex) -> str:
    """Find a near-identical known term (same length, mostly same characters)."""
    candidates = [entry["term"] for entry in lex.entries]
    candidates += [item["term"] for item in lex.pending if item["term"] != term]
    best, best_score = "", 0.0
    for candidate in candidates:
        if len(candidate) != len(term) or candidate == term:
            continue
        score = sum(1 for a, b in zip(term, candidate) if a == b) / len(term)
        if score > best_score:
            best, best_score = candidate, score
    return best if best_score >= 0.6 else ""


PLACE_SUFFIX = ("村", "镇", "县", "市", "省", "区", "遗址", "寺", "山", "河", "湖")


def _same_kind(term: str, candidate: str) -> bool:
    """Place names must stay place names; bare names are never auto-corrected."""
    if term.endswith(PLACE_SUFFIX):
        return candidate.endswith(PLACE_SUFFIX)
    return False


def _suggest(term: str, cfg: Config) -> str:
    """Contextual guess first, then a local near-identical term match."""
    from . import glossary as glossary_module
    from . import research

    lex = glossary_module.load()
    context = ""
    for item in lex.pending:
        if item["term"] == term:
            context = item.get("context", "")
            break

    similar = _similar_known(term, lex)
    if similar and sources.collect(similar):
        return similar

    # Search-engine suggestions: take the prefix that has the same length and
    # verify it against real sources (this is how 张居中 becomes 张居正).
    for suggestion in sources.baidu_suggest(term):
        candidate = suggestion[:len(term)]
        if candidate and candidate != term and sources.collect(candidate):
            if _same_kind(term, candidate) or (
                len(candidate) == len(term)
                and sum(1 for a, b in zip(term, candidate) if a == b) >= 2
            ):
                return candidate

    if context:
        suggestion = research.suggest_correction(term, context, cfg)
        if suggestion and suggestion != term and sources.collect(suggestion):
            return suggestion
        return ""

    # No context stored: only place names may be auto-corrected from a model guess.
    suggestion = research.suggest_correction(term, "", cfg)
    if suggestion and suggestion != term and _same_kind(term, suggestion) \
            and sources.collect(suggestion):
        return suggestion
    return ""


def _llm_suggestion(term: str, cfg: Config) -> str:
    """Raw model guess, shown to the user even when it is not auto-adopted."""
    from . import glossary as glossary_module
    from . import research

    lex = glossary_module.load()
    context = ""
    for item in lex.pending:
        if item["term"] == term:
            context = item.get("context", "")
            break
    return research.suggest_correction(term, context, cfg)


def _context_of(term: str) -> str:
    from . import glossary as glossary_module

    lex = glossary_module.load()
    for item in lex.pending:
        if item["term"] == term:
            return item.get("context", "")
    return ""


def _try_correction(term: str, cfg: Config, suggestion: str) -> str:
    """If the suggested spelling has real evidence, adopt it with an alias."""
    from . import glossary as glossary_module

    if not suggestion or not sources.collect(suggestion):
        # One retry: search endpoints rate-limit aggressively.
        import time

        time.sleep(0.8)
        if not suggestion or not sources.collect(suggestion):
            return ""
    lex = glossary_module.load()
    build(suggestion, cfg)  # one level of recursion
    lex = glossary_module.load()  # build() may have written a new entry
    entry = lex.find(suggestion)
    if entry is None:
        return ""
    # Drop a now-superseded auto entry for the misheard spelling.
    old = lex.find(term)
    if old is not None and old.get("auto"):
        lex.entries = [e for e in lex.entries if e["term"] != term]
    lex.resolve_pending(term)
    lex.save()
    return suggestion


def build(term: str, cfg: Config) -> dict | None:
    """Collect multi-source evidence, summarise it, and auto-save exact matches."""
    from . import glossary as glossary_module

    evidence = sources.collect(term)
    exact = sources.has_exact(evidence) if evidence else None

    # A term in the transcript may still be a mishearing even when the spelling
    # happens to match a real but unrelated entry. Prefer the context-backed
    # candidate when it is corroborated by at least two sources.
    context = _context_of(term)
    if context and exact:
        suggestion = _suggest(term, cfg)
        if suggestion and len(sources.collect(suggestion)) >= 2:
            corrected = _try_correction(term, cfg, suggestion)
            if corrected:
                record = {
                    "zh": [], "en": [], "evidence": [],
                    "summary_zh": "", "summary_en": "",
                    "empty": True, "corrected_to": corrected,
                    "suggest": "",
                    "at": date.today().isoformat(),
                }
                data = _read_cache()
                data[term] = record
                _write_cache(data)
                return record

    # Without an exact source match, try to fix a likely homophone first.
    if not exact:
        suggestion = _suggest(term, cfg)
        corrected = _try_correction(term, cfg, suggestion) if suggestion else ""
        if not corrected and not evidence and not suggestion:
            suggestion = _llm_suggestion(term, cfg)
        if corrected or not evidence:
            record = {
                "zh": [], "en": [], "evidence": evidence or [],
                "summary_zh": "", "summary_en": "",
                "empty": True,
                "suggest": "" if corrected else suggestion,
                "corrected_to": corrected,
                "at": date.today().isoformat(),
            }
            data = _read_cache()
            data[term] = record
            _write_cache(data)
            return record

    summary_zh, summary_en = _summary_from_evidence(term, cfg, evidence)
    record = {
        "zh": [item["title"] for item in evidence if "zh" in item["source"].lower()][:3],
        "en": [item["title"] for item in evidence if "en" in item["source"].lower()][:3],
        "evidence": evidence,
        "summary_zh": summary_zh,
        "summary_en": summary_en,
        "empty": False,
        "at": date.today().isoformat(),
    }

    exact = sources.has_exact(evidence)
    if exact and exact["source"].split(" ")[0] in ("Wikipedia", "Baidu") and _probable_name(term):
        lex = glossary_module.load()
        if lex.find(term) is None:
            lex.add(
                term,
                definition=exact["snippet"][:400],
                en=summary_en,
                category="other",
                domain="other",
                confidence="high",
                sources=[exact["url"]],
                auto=True,
            )
            lex.resolve_pending(term)
            record["auto_entry"] = True

    data = _read_cache()
    data[term] = record
    _write_cache(data)
    return record


def pending_terms(glossary: Glossary) -> list[str]:
    return [item["term"] for item in glossary.pending]


def warm(glossary: Glossary, cfg: Config, limit: int = 6) -> int:
    """Fill the cache for terms that do not have a fresh entry yet."""
    done = 0
    for term in pending_terms(glossary):
        if done >= limit:
            break
        if cached(term) is not None:
            continue
        if build(term, cfg) is not None:
            done += 1
    return done
