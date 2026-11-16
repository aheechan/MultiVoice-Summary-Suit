from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import asr, correct, generate, ingest, structure, translate
from .asr import Segment
from .config import Config

ALL_STAGES = ("asr", "correct", "translate", "extract", "generate")


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

    audio = job / "audio.wav"
    if not (resume and audio.exists()):
        ingest.extract_audio(source, audio, cfg.ffmpeg)

    raw_json = job / "segments.raw.json"
    fixed_json = job / "segments.corrected.json"

    if resume and fixed_json.exists():
        segments = _read_segments(fixed_json)
        detected = json.loads((job / "manifest.json").read_text(encoding="utf-8")).get("language", "")
    else:
        if resume and raw_json.exists():
            segments = _read_segments(raw_json)
            detected = ""
        else:
            segments, detected = asr.transcribe(audio, cfg)
            _write(raw_json, json.dumps([s.to_dict() for s in segments],
                                        ensure_ascii=False, indent=2))

        if "correct" in stages:
            segments = correct.correct_segments(segments, cfg)
            _write(fixed_json, json.dumps([s.to_dict() for s in segments],
                                          ensure_ascii=False, indent=2))

    transcript = "\n".join(seg.text for seg in segments)
    _write(job / "transcript.txt", transcript)

    source_lang = (detected or "").lower()[:2] or "zh"
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
        _write(out / "a-script.md", generate.clean_script(segments, cfg))
        _write(out / "b-report.md", generate.report(units, cfg))
        _write(out / "c-brief.md", generate.brief(units, cfg))

    manifest = {
        "source": str(source),
        "language": source_lang,
        "job": job.name,
        "segments": len(segments),
        "units": len(units),
        "updated": datetime.now().isoformat(timespec="seconds"),
    }
    _write(job / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return out
