"""Job-cache inspection and cleanup (work/<hash> folders)."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .config import Config

JOB_ARTIFACTS = (
    "audio.wav",
    "segments.raw.json",
    "segments.corrected.json",
    "context.json",
    "units.json",
    "manifest.json",
)


def _jobs(cfg: Config) -> list[dict]:
    jobs: list[dict] = []
    if not cfg.work.exists():
        return jobs
    for path in cfg.work.iterdir():
        if not path.is_dir() or path.name.startswith("_"):
            continue
        manifest = path / "manifest.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        try:
            updated = datetime.fromisoformat(data.get("updated", ""))
        except ValueError:
            updated = datetime.fromtimestamp(manifest.stat().st_mtime)
        jobs.append({
            "path": path,
            "name": path.name,
            "output_dir": data.get("output_dir", ""),
            "source": data.get("source", ""),
            "updated": updated,
            "size": size,
        })
    return jobs


def stats(cfg: Config) -> dict:
    jobs = _jobs(cfg)
    return {
        "jobs": len(jobs),
        "bytes": sum(job["size"] for job in jobs),
        "oldest": min((job["updated"] for job in jobs), default=None),
        "newest": max((job["updated"] for job in jobs), default=None),
    }


def clean(cfg: Config, days: int | None = None) -> dict:
    """Delete job folders older than `days`; days=None removes every cached job."""
    removed = 0
    freed = 0
    for job in _jobs(cfg):
        if days is not None:
            age = (datetime.now() - job["updated"]).days
            if age < days:
                continue
        try:
            shutil.rmtree(job["path"])
            removed += 1
            freed += job["size"]
        except OSError:
            continue
    return {"removed": removed, "bytes": freed}
