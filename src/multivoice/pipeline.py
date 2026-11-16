from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import asr, correct, generate, ingest, structure
from .config import Config


def _job_dir(cfg: Config, source: Path) -> Path:
    digest = ingest.sha256_file(source)[:10]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = cfg.work / f"{stamp}-{digest}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(
    source: Path,
    cfg: Config,
    *,
    language: str = "auto",
    stages: tuple[str, ...] = ("asr", "correct", "extract", "generate"),
) -> Path:
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(source)

    job = _job_dir(cfg, source)
    out = cfg.output / job.name
    audio = job / "audio.wav"
    ingest.extract_audio(source, audio, cfg.ffmpeg)

    segments, detected = asr.transcribe(audio, cfg)
    _write(job / "segments.raw.json",
           json.dumps([s.to_dict() for s in segments], ensure_ascii=False, indent=2))

    if "correct" in stages:
        segments = correct.correct_segments(segments, cfg)
        _write(job / "segments.corrected.json",
               json.dumps([s.to_dict() for s in segments], ensure_ascii=False, indent=2))

    transcript = "\n".join(seg.text for seg in segments)
    _write(job / "transcript.txt", transcript)

    units: list[dict] = []
    if "extract" in stages:
        units = structure.extract_units(segments, cfg)
        _write(job / "units.json", json.dumps(units, ensure_ascii=False, indent=2))

    if "generate" in stages and units:
        _write(out / "a-script.md", generate.clean_script(segments, cfg))
        _write(out / "b-report.md", generate.report(units, cfg))
        _write(out / "c-brief.md", generate.brief(units, cfg))

    manifest = {
        "source": str(source),
        "language": detected,
        "job": job.name,
        "segments": len(segments),
        "units": len(units),
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    _write(job / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return out
