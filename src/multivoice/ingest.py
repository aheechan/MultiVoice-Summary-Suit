from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path, ffprobe: str = "ffprobe") -> dict:
    cmd = [
        ffprobe, "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,sample_rate,channels",
        "-of", "json", str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr.strip()}")
    return json.loads(out.stdout)


def extract_audio(src: Path, dst: Path, ffmpeg: str = "ffmpeg") -> Path:
    """Extract a 16 kHz mono wav track; return the output path."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-i", str(src), "-vn",
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[-800:]}")
    return dst


def fetch_url(url: str, outdir: Path) -> Path:
    """Download an audio-bearing resource. Requires the optional yt-dlp package."""
    try:
        import yt_dlp  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "URL input needs yt-dlp: pip install yt-dlp"
        ) from exc

    outdir.mkdir(parents=True, exist_ok=True)
    template = str(outdir / "%(title).120s.%(ext)s")
    options = {"outtmpl": template, "format": "bestaudio/best", "quiet": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        return Path(ydl.prepare_filename(info))


def ensure_tool(name: str) -> bool:
    return shutil.which(name) is not None
