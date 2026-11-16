from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import (asr, bgm, classify, correct, generate, glossary, ingest,
               normalize, research, structure, translate, vad, verify)
from .asr import Segment
from .config import Config

ALL_STAGES = ("asr", "correct", "translate", "extract", "generate")

# ASR engines report language names or odd codes ("ch", "Chinese", "zh-cn").
LANG_ALIASES = {
    "ch": "zh", "cn": "zh", "chi": "zh", "zho": "zh", "zh-cn": "zh", "zh-tw": "zh",
    "chinese": "zh", "mandarin": "zh", "yue": "zh",
    "eng": "en", "english": "en",
    "jpn": "ja", "japanese": "ja",
    "kor": "ko", "korean": "ko",
}


def _norm_lang(code: str) -> str:
    value = (code or "").strip().lower().replace("_", "-")
    if not value or value == "auto":
        return ""
    if value in LANG_ALIASES:
        return LANG_ALIASES[value]
    return value[:2]


def _job_dir(cfg: Config, source: Path) -> Path:
    """Stable job id = content hash, so re-runs resume instead of duplicating."""
    digest = ingest.sha256_file(source)[:12]
    path = cfg.work / digest
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_segments(path: Path) -> list[Segment]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Segment(**item) for item in data]


def _transcribe_chunked(audio: Path, cfg: Config, job: Path) -> tuple[list[Segment], str]:
    """Split on speech boundaries, transcribe each chunk, keep global timestamps."""
    engine = asr.build(cfg)
    spans = vad.detect_speech_spans(
        audio,
        cfg.ffmpeg,
        noise_db=float(cfg.vad.get("noise_db", -32)),
        min_silence=float(cfg.vad.get("min_silence", 0.45)),
    )
    chunks = vad.merge_spans(
        spans,
        max_seconds=float(cfg.vad.get("max_seconds", 30)),
    )
    if not chunks:
        chunks = [vad.Span(0.0, vad._duration(audio, cfg.ffmpeg))]

    segments: list[Segment] = []
    language = ""
    for index, span in enumerate(chunks):
        chunk_path = job / "chunks" / f"{index:03d}.wav"
        vad.cut(audio, span, chunk_path, cfg.ffmpeg)
        items, lang = engine.transcribe(chunk_path)
        language = language or lang
        for item in items:
            start = span.start + item.start
            end = span.start + (item.end if item.end > 0 else span.duration)
            segments.append(
                Segment(len(segments), start, end, item.text, item.lang or lang)
            )
    return segments, language


def run(
    source: Path,
    cfg: Config,
    *,
    language: str = "auto",
    stages: tuple[str, ...] = ALL_STAGES,
    resume: bool = True,
) -> Path:
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(source)

    job = _job_dir(cfg, source)
    out = cfg.output / job.name
    lex = glossary.load()

    audio = job / "audio.wav"
    if not (resume and audio.exists()):
        ingest.extract_audio(source, audio, cfg.ffmpeg)

    raw_json = job / "segments.raw.json"
    fixed_json = job / "segments.corrected.json"
    manifest_path = job / "manifest.json"
    detected = ""
    normalized_count = 0
    if resume and manifest_path.exists():
        try:
            detected = json.loads(manifest_path.read_text(encoding="utf-8")).get("language", "")
        except json.JSONDecodeError:
            detected = ""

    if resume and fixed_json.exists():
        segments = _read_segments(fixed_json)
    else:
        if resume and raw_json.exists():
            segments = _read_segments(raw_json)
        else:
            if cfg.vad.get("enabled", True):
                segments, detected = _transcribe_chunked(audio, cfg, job)
            else:
                segments, detected = asr.transcribe(audio, cfg)
            segments, normalized_count = normalize.normalize_segments(segments)
            _write(raw_json, json.dumps([s.to_dict() for s in segments],
                                        ensure_ascii=False, indent=2))

    context: dict = {"domain": "other", "label": "其他", "terms": []}
    evidence = ""
    glossary_text = "（无）"
    alias_changes: list = []
    researched: list = []
    already_corrected = bool(resume and fixed_json.exists())
    if "correct" in stages and not already_corrected:
        if resume and (job / "context.json").exists():
            saved = json.loads((job / "context.json").read_text(encoding="utf-8"))
            context = saved.get("classify", context)
            evidence = saved.get("evidence", "")
            glossary_text = saved.get("glossary", glossary_text)
            alias_changes = saved.get("aliases", [])
            researched = saved.get("researched", [])
        else:
            # 1) deterministic alias repair from the local lexicon
            for segment in segments:
                fixed, changes = lex.apply(segment.text)
                if changes:
                    segment.text = fixed
                    alias_changes.extend(changes)

            head = "\n".join(seg.text for seg in segments)[:3000]

            # 2) classify the content, then research unknown or stale terms on the fly
            context = classify.classify(head, cfg)
            candidates = list(context["terms"])
            candidates += [entry["term"] for entry in lex.match(head)]
            researched = research.ensure_terms(candidates, lex, cfg)
            glossary_text, _ = lex.context_for(head)

            # 3) encyclopedia facts for hard entities
            evidence, items = verify.build_evidence(context["terms"], cfg)
            findings = verify.suggest(items, evidence)

            _write(job / "context.json", json.dumps({
                "classify": context,
                "evidence": evidence,
                "findings": findings,
                "glossary": glossary_text,
                "aliases": alias_changes,
                "researched": [e["term"] for e in researched],
            }, ensure_ascii=False, indent=2))
            if findings:
                _write(out / "verification.md", verify.to_markdown(findings))

        segments = correct.correct_segments(
            segments, cfg,
            domain=context.get("label", ""),
            evidence=evidence,
            glossary_text=glossary_text,
        )
        _write(fixed_json, json.dumps([s.to_dict() for s in segments],
                                      ensure_ascii=False, indent=2))

    transcript = "\n".join(seg.text for seg in segments)
    _write(job / "transcript.txt", transcript)

    background = bgm.analyze(audio)
    _write(job / "bgm.json", json.dumps(background, ensure_ascii=False, indent=2))

    source_lang = _norm_lang(detected) or "zh"
    if "translate" in stages:
        paras = translate.paragraphs(segments, source_lang)
        for target in cfg.languages:
            if target == source_lang:
                continue
            translated = translate.translate_paragraphs(paras, source_lang, target, cfg)
            translate.write_bilingual(out / "text", paras, translated, source_lang, target)

    units: list[dict] = []
    units_json = job / "units.json"
    if "extract" in stages:
        if resume and units_json.exists():
            units = json.loads(units_json.read_text(encoding="utf-8"))
        else:
            units = structure.extract_units(segments, cfg)
            _write(units_json, json.dumps(units, ensure_ascii=False, indent=2))

    if "generate" in stages and units:
        transcript_text = "\n".join(seg.text for seg in segments)
        _write(out / "a-script.md", generate.clean_script(segments, cfg))
        _write(out / "b-report.md", generate.report(units, cfg, transcript_text))
        _write(out / "c-brief.md", generate.brief(units, cfg, transcript_text))

    manifest = {
        "source": str(source),
        "language": source_lang,
        "job": job.name,
        "domain": context.get("domain", "other"),
        "segments": len(segments),
        "units": len(units),
        "bgm": background,
        "aliases_repaired": [f"{a}->{b}" for a, b in alias_changes],
        "terms_researched": [e["term"] for e in researched],
        "updated": datetime.now().isoformat(timespec="seconds"),
    }
    _write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    return out
