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


class Engine:
    """Loads the model once and transcribes many chunks."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._model = None
        self._kind = str(cfg.asr.get("engine", "qwen3")).lower()

    def load(self) -> None:
        if self._model is not None:
            return
        if self._kind == "qwen3":
            self._model = _load_qwen3(self.cfg)
        elif self._kind == "whisper":
            self._model = _load_whisper(self.cfg)
        else:
            raise RuntimeError(f"unknown asr engine: {self._kind}")

    def transcribe(self, audio: Path) -> tuple[list[Segment], str]:
        self.load()
        if self._kind == "qwen3":
            return _run_qwen3(self._model, audio, self.cfg)
        return _run_whisper(self._model, audio, self.cfg)


def build(cfg: Config) -> Engine:
    return Engine(cfg)


def transcribe(audio: Path, cfg: Config) -> tuple[list[Segment], str]:
    """One-shot helper kept for simple callers and tests."""
    return Engine(cfg).transcribe(audio)


def _load_qwen3(cfg: Config):
    try:
        from qwen_asr import Qwen3ASRModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("qwen3 engine requires: pip install qwen-asr") from exc

    model_path = resolve_model(cfg, cfg.asr.get("model"))
    if model_path is None or not Path(model_path).exists():
        raise RuntimeError(f"ASR model not found: {model_path}")
    return Qwen3ASRModel.from_pretrained(
        str(model_path), device_map=cfg.asr.get("device", "cuda")
    )


def _run_qwen3(model, audio: Path, cfg: Config) -> tuple[list[Segment], str]:
    language = cfg.asr.get("language", "auto")
    result = model.transcribe(
        audio=str(audio),
        language=None if language in (None, "", "auto") else language,
    )[0]
    text = (result.text or "").strip()
    lang = getattr(result, "language", "") or ""
    return [Segment(0, 0.0, 0.0, text, lang)], lang


def _load_whisper(cfg: Config):
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("whisper engine requires: pip install faster-whisper") from exc

    model_path = resolve_model(cfg, cfg.asr.get("model"))
    return WhisperModel(
        str(model_path) if model_path else "large-v3",
        device=cfg.asr.get("device", "cuda"),
        compute_type="float16",
    )


def _run_whisper(model, audio: Path, cfg: Config) -> tuple[list[Segment], str]:
    segments, info = model.transcribe(str(audio), vad_filter=True)
    items = [
        Segment(i, s.start, s.end, s.text.strip(), info.language)
        for i, s in enumerate(segments)
    ]
    return items, info.language
