"""Find the background-noise level where ASR starts to fail.

Adds synthetic noise to a clean clip at several SNR levels, transcribes each
variant with the configured engine, and reports character error rate against
the clean transcript. Used to calibrate the BGM warning thresholds.

Usage:
    python tools/bgm_limit.py <clean.wav> [--snr 20,15,10,5,0,-5]
"""
from __future__ import annotations

import argparse
import difflib
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from multivoice import asr, bgm, config  # noqa: E402


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise SystemExit("expects 16-bit PCM wav")
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0, rate


def write_wav(path: Path, data: np.ndarray, rate: int) -> None:
    clipped = np.clip(data, -1.0, 1.0)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes((clipped * 32767).astype("<i2").tobytes())


def add_noise(signal: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, signal.shape).astype(np.float32)
    # shape it slightly toward pink so it is closer to music/room noise than white
    for _ in range(2):
        noise = np.convolve(noise, np.ones(3, dtype=np.float32) / 3, mode="same")
    signal_power = float(np.mean(signal ** 2)) or 1e-9
    noise_power = float(np.mean(noise ** 2)) or 1e-9
    target = signal_power / (10 ** (snr_db / 10.0))
    return signal + noise * np.sqrt(target / noise_power)


def cer(reference: str, hypothesis: str) -> float:
    matcher = difflib.SequenceMatcher(None, reference, hypothesis)
    return round(1.0 - matcher.ratio(), 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio")
    parser.add_argument("--snr", default="20,15,10,5,0,-5")
    args = parser.parse_args()

    clean_path = Path(args.audio)
    signal, rate = read_wav(clean_path)
    cfg = config.load()

    if cfg.vad.get("enabled", True):
        cfg.vad["enabled"] = False  # measure the model, not the slicer

    engine = asr.build(cfg)
    clean_text = "".join(s.text for s in engine.transcribe(clean_path)[0])
    print(f"clean transcript: {clean_text}\n")
    print(f"{'SNR':>5} {'gap':>6} {'CER':>6}  text")
    print("-" * 70)

    rng = np.random.default_rng(20261116)
    work = clean_path.parent / "noisy"
    work.mkdir(exist_ok=True)

    for snr in [float(x) for x in args.snr.split(",")]:
        mixed = add_noise(signal, snr, rng)
        target = work / f"snr{snr:+.0f}.wav"
        write_wav(target, mixed, rate)
        text = "".join(s.text for s in engine.transcribe(target)[0])
        info = bgm.analyze(target)
        print(f"{snr:5.0f} {info['gap_db']:6.1f} {cer(clean_text, text):6.3f}  {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
