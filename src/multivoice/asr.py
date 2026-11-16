from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Config, resolve_model


@dataclass
class Segment:
    index: int
    start: float
    end: float
    text: str
    lang: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def transcribe(audio: Path, cfg: Config) -> tuple[list[Segment], str]:
    """Return segments and the detected language."""
    engine = str(cfg.asr.get("engine", "qwen3")).lower()
    if engine == "qwen3":
        return _qwen3(audio, cfg)
    if engine == "whisper":
        return _whisper(audio, cfg)
    raise RuntimeError(f"unknown asr engine: {engine}")


def _qwen3(audio: Path, cfg: Config) -> tuple[list[Segment], str]:
    try:
        from qwen_asr import Qwen3ASRModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("qwen3 engine requires: pip install qwen-asr") from exc

    model_path = resolve_model(cfg, cfg.asr.get("model"))
    if model_path is None or not Path(model_path).exists():
        raise RuntimeError(f"ASR model not found: {model_path}")

    model = Qwen3ASRModel.from_pretrained(
        str(model_path), device_map=cfg.asr.get("device", "cuda")
    )
    language = cfg.asr.get("language", "auto")
    result = model.transcribe(
        audio=str(audio),
        language=None if language in (None, "", "auto") else language,
    )[0]

    text = (result.text or "").strip()
    lang = getattr(result, "language", "") or ""
    # Without a forced aligner the engine returns one block; keep it as one segment.
    return [Segment(index=0, start=0.0, end=0.0, text=text, lang=lang)], lang


def _whisper(audio: Path, cfg: Config) -> tuple[list[Segment], str]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("whisper engine requires: pip install faster-whisper") from exc

    model_path = resolve_model(cfg, cfg.asr.get("model"))
    model = WhisperModel(
        str(model_path) if model_path else "large-v3",
        device=cfg.asr.get("device", "cuda"),
        compute_type="float16",
    )
    segments, info = model.transcribe(str(audio), vad_filter=True)
    items = [
        Segment(index=i, start=s.start, end=s.end, text=s.text.strip(), lang=info.language)
        for i, s in enumerate(segments)
    ]
    return items, info.language
