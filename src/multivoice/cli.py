from __future__ import annotations

import argparse
import socket
import sys
import tempfile
import urllib.parse
from pathlib import Path

from . import bgm, config, ingest, pipeline, vad


def _ok(label: str, value: str) -> None:
    print(f"[ OK ] {label}: {value}")


def _bad(label: str, value: str) -> None:
    print(f"[FAIL] {label}: {value}")


def _warn(label: str, value: str) -> None:
    print(f"[WARN] {label}: {value}")


def probe_file(source: Path, cfg: config.Config) -> int:
    """Report speech chunks and background-music level without running ASR."""
    work = Path(tempfile.mkdtemp(prefix="mvs-probe-"))
    audio = work / "audio.wav"
    ingest.extract_audio(source, audio, cfg.ffmpeg)

    spans = vad.detect_speech_spans(audio, cfg.ffmpeg)
    chunks = vad.merge_spans(spans, max_seconds=30.0)
    info = bgm.analyze(audio)
    duration = sum(s.duration for s in chunks)

    print(f"file      : {source.name}")
    print(f"speech    : {duration:.1f}s in {len(chunks)} chunk(s)")
    print(f"speech dB : {info['speech_db']}")
    print(f"floor dB  : {info['floor_db']}")
    print(f"gap       : {info['gap_db']} dB")
    print(f"verdict   : {info['verdict']}")
    print(f"advice    : {info['advice']}")
    for index, chunk in enumerate(chunks):
        print(f"  chunk {index}: {chunk.start:6.2f}s -> {chunk.end:6.2f}s")
    return 0


def glossary_command(args, cfg: config.Config) -> int:
    from . import glossary, research

    lex = glossary.load()
    command = args.glossary_command

    if command == "list":
        if not lex.entries:
            print("(empty)")
            return 0
        for entry in lex.entries:
            flag = "STALE" if lex.is_stale(entry) else "ok"
            print(f"[{flag}] {entry['term']:<18} {entry.get('kind', ''):<10} "
                  f"{entry.get('topic', ''):<10} {entry.get('last_verified', '')}")
            print(f"        {entry.get('definition', '')}")
        return 0

    if command == "stale":
        stale = [e for e in lex.entries if lex.is_stale(e)]
        for entry in stale:
            print(f"{entry['term']}  (verified {entry.get('last_verified', '?')})")
        if not stale:
            print("(nothing stale)")
        return 0

    if command == "add":
        entry = lex.add(
            args.term,
            aliases=args.alias,
            definition=args.definition,
            en=args.en,
            kind=args.kind,
            topic=args.topic,
        )
        print(f"saved: {entry['term']} kind={entry['kind']} ttl={entry['ttl_days']}")
        return 0

    if command == "research":
        entry = research.research_term(args.term, lex, cfg)
        if entry is None:
            print("no reliable result; entry not saved")
            return 1
        print(f"saved: {entry['term']} kind={entry['kind']} ttl={entry['ttl_days']}")
        print(entry.get("definition", ""))
        return 0

    return 0


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

    probe_parser = sub.add_parser("probe", help="report speech chunks and BGM level")
    probe_parser.add_argument("--input", required=True)

    tray_parser = sub.add_parser("tray", help="start the system tray app")
    tray_parser.add_argument("--input", default=None, help="start a job immediately")

    gloss = sub.add_parser("glossary", help="manage the slang/term lexicon")
    gloss_sub = gloss.add_subparsers(dest="glossary_command", required=True)
    gloss_sub.add_parser("list", help="show every entry")
    gloss_sub.add_parser("stale", help="show entries that need re-checking")
    add_parser = gloss_sub.add_parser("add", help="add or update an entry")
    add_parser.add_argument("--term", required=True)
    add_parser.add_argument("--alias", action="append", default=[])
    add_parser.add_argument("--definition", default="")
    add_parser.add_argument("--en", default="")
    add_parser.add_argument("--kind", default="other")
    add_parser.add_argument("--topic", default="")
    research_parser = gloss_sub.add_parser("research", help="look a term up on the web")
    research_parser.add_argument("--term", required=True)

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

    if args.command == "probe":
        return probe_file(Path(args.input), cfg)

    if args.command == "tray":
        from .ui.tray import run_tray

        initial = Path(args.input) if args.input else None
        return run_tray(cfg, initial)

    if args.command == "glossary":
        return glossary_command(args, cfg)

    stages = tuple(s.strip() for s in args.stages.split(",") if s.strip())
    out = pipeline.run(
        Path(args.input), cfg, language=args.lang, stages=stages,
        resume=not args.no_resume,
    )
    print(f"done -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
