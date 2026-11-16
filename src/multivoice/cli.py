from __future__ import annotations

import argparse
import socket
import sys
import urllib.parse
from pathlib import Path

from . import config, ingest, pipeline


def _ok(label: str, value: str) -> None:
    print(f"[ OK ] {label}: {value}")


def _bad(label: str, value: str) -> None:
    print(f"[FAIL] {label}: {value}")


def _warn(label: str, value: str) -> None:
    print(f"[WARN] {label}: {value}")


def doctor(cfg: config.Config) -> int:
    failures = 0

    for tool in (cfg.ffmpeg, cfg.ffprobe):
        if ingest.ensure_tool(tool):
            _ok("tool", tool)
        else:
            _bad("tool", f"{tool} not found in PATH")
            failures += 1

    if cfg.work.exists():
        _ok("work", str(cfg.work))
    else:
        _warn("work", f"{cfg.work} does not exist yet")

    for name in ("paths", "models"):
        real = config.DEFAULT_CONFIG_DIR / f"{name}.toml"
        if real.exists():
            _ok("config", str(real))
        else:
            _warn("config", f"{real} missing, falling back to {name}.example.toml")

    model_path = config.resolve_model(cfg, cfg.asr.get("model"))
    if model_path and Path(model_path).exists():
        _ok("asr model", str(model_path))
    else:
        _bad("asr model", f"{model_path} not found")
        failures += 1

    base = str(cfg.llm.get("base_url", ""))
    if not base:
        _bad("llm", "base_url is empty")
        failures += 1
    else:
        parsed = urllib.parse.urlparse(base)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            with socket.create_connection((host, port), timeout=2):
                _ok("llm endpoint", f"{host}:{port}")
        except OSError:
            _warn("llm endpoint", f"{host}:{port} unreachable (start it before running)")

    print()
    print("doctor:", "FAILED" if failures else "ready")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mvs", description="MultiVoice-Summary-Suit")
    parser.add_argument("--config-dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check tools, config and models")

    run_parser = sub.add_parser("run", help="process one file or URL")
    run_parser.add_argument("--input", required=True)
    run_parser.add_argument("--lang", default="auto")
    run_parser.add_argument(
        "--stages", default="asr,correct,translate,extract,generate",
        help="comma separated: asr,correct,translate,extract,generate",
    )
    run_parser.add_argument(
        "--no-resume", action="store_true", help="ignore cached job artifacts"
    )

    args = parser.parse_args(argv)
    cfg = config.load(args.config_dir)

    if args.command == "doctor":
        return doctor(cfg)

    stages = tuple(s.strip() for s in args.stages.split(",") if s.strip())
    out = pipeline.run(
        Path(args.input), cfg, language=args.lang, stages=stages,
        resume=not args.no_resume,
    )
    print(f"done -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
