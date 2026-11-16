from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "configs"


@dataclass
class Config:
    work: Path
    output: Path
    models_root: Path
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    asr: dict = field(default_factory=dict)
    align: dict = field(default_factory=dict)
    separate: dict = field(default_factory=dict)
    llm: dict = field(default_factory=dict)
    vad: dict = field(default_factory=dict)
    verify: dict = field(default_factory=dict)
    research: dict = field(default_factory=dict)
    languages: list = field(default_factory=lambda: ["zh", "en"])


def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _pick(config_dir: Path, name: str) -> dict:
    real = config_dir / f"{name}.toml"
    example = config_dir / f"{name}.example.toml"
    return _read_toml(real) or _read_toml(example)


def load(config_dir: str | Path | None = None) -> Config:
    directory = Path(
        config_dir or os.environ.get("MVS_CONFIG_DIR") or DEFAULT_CONFIG_DIR
    )
    paths = _pick(directory, "paths")
    models = _pick(directory, "models")

    workspace = paths.get("workspace", {})
    model_root = Path(
        models.get("models", {}).get("root")
        or paths.get("models", {}).get("root")
        or r"D:/Local Repositories/_models"
    )

    cfg = Config(
        work=Path(workspace.get("work", r"D:/Local Repositories/MultiVoice-Summary-Suit/work")),
        output=Path(workspace.get("output", r"D:/Local Repositories/MultiVoice-Summary-Suit/output")),
        models_root=model_root,
        ffmpeg=paths.get("tools", {}).get("ffmpeg", "ffmpeg"),
        ffprobe=paths.get("tools", {}).get("ffprobe", "ffprobe"),
        asr=models.get("asr", {}),
        align=models.get("align", {}),
        separate=models.get("separate", {}),
        llm=models.get("llm", {}),
        vad=models.get("vad", {}),
        verify=models.get("verify", {}),
        research=models.get("research", {}),
        languages=list(paths.get("output", {}).get("languages", ["zh", "en"])),
    )

    prefs = settings.load()
    cfg.research["enabled"] = bool(prefs.get("auto_research", True))
    cfg.research["max_terms"] = int(prefs.get("max_terms", 6))

    provider = prefs.get("provider")
    if provider:
        names = {p.get("name") for p in cfg.llm.get("providers", [])}
        if provider in names:
            cfg.llm["order"] = [provider]

    return cfg


def resolve_model(cfg: Config, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else cfg.models_root / path
