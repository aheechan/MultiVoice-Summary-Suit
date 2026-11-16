from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

WINDOW_SECONDS = 0.05

# Calibrated against tools/bgm_limit.py on 2026-11-16 (Qwen3-ASR 0.6B, 16 kHz):
# gap 23 dB -> CER 4%, 19 dB -> 2%, 14 dB -> 12% (proper nouns break),
# 10 dB -> 9%, 5.5 dB -> 20%, 2.5 dB -> 73% (unusable).
CLEAN_DB = 20.0
LIGHT_DB = 14.0
HEAVY_DB = 8.0


def _rms_db(frames: bytes, width: int) -> float:
    if not frames:
        return -120.0
    if width == 2:
        values = struct.unpack(f"<{len(frames) // 2}h", frames)
        peak = 32768.0
    elif width == 4:
        values = struct.unpack(f"<{len(frames) // 4}i", frames)
        peak = 2147483648.0
    else:
        return -120.0
    if not values:
        return -120.0
    mean_square = sum(v * v for v in values) / len(values)
    if mean_square <= 0:
        return -120.0
    return 20.0 * math.log10(math.sqrt(mean_square) / peak)


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return -120.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(ratio * (len(ordered) - 1)))))
    return ordered[index]


def analyze(audio: Path) -> dict:
    """Estimate how far the speech level sits above the background floor.

    Continuous music keeps the floor high, so the 90th/10th percentile gap
    shrinks as the BGM gets louder. This works without needing silent pauses.
    """
    with wave.open(str(audio), "rb") as handle:
        width = handle.getsampwidth()
        rate = handle.getframerate()
        total = handle.getnframes()
        step = max(1, int(rate * WINDOW_SECONDS))
        levels: list[float] = []
        for start in range(0, total, step):
            handle.setpos(start)
            chunk = handle.readframes(step)
            if not chunk:
                break
            level = _rms_db(chunk, width)
            if level > -119.0:
                levels.append(level)

    if len(levels) < 4:
        return {
            "speech_db": -120.0, "floor_db": -120.0, "gap_db": None,
            "verdict": "unknown", "advice": "音频太短，无法评估背景噪声",
            "windows": len(levels),
        }

    floor_db = _percentile(levels, 0.10)
    speech_db = _percentile(levels, 0.90)
    gap = speech_db - floor_db

    if gap >= CLEAN_DB:
        verdict, advice = "clean", "背景干净，可直接识别"
    elif gap >= LIGHT_DB:
        verdict, advice = "light", "有背景音乐，正文基本准确，专有名词建议核对"
    elif gap >= HEAVY_DB:
        verdict, advice = "heavy", "背景音乐偏响，人名、地名、数字容易错，务必核对专名"
    else:
        verdict, advice = "severe", "语音与背景接近，句子结构会崩，建议先做人声分离或换清晰音源"

    return {
        "speech_db": round(speech_db, 1),
        "floor_db": round(floor_db, 1),
        "gap_db": round(gap, 1),
        "verdict": verdict,
        "advice": advice,
        "windows": len(levels),
    }
