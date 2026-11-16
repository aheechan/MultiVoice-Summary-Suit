"""System tray application (English UI)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from .. import __version__, pipeline
from ..config import PROJECT_ROOT, Config

ASSETS = PROJECT_ROOT / "assets"
APP_NAME = "MultiVoice Summary Suit"

AUDIO_FILTER = (
    "Media files (*.mp4 *.mkv *.mov *.webm *.mp3 *.wav *.m4a *.flac *.aac);;"
    "All files (*.*)"
)

TRANSCRIBE_STAGES = ("asr", "correct", "translate")
GENERATE_STAGES = ("extract", "generate")


class Worker(QThread):
    done = Signal(str, str)   # output dir, stage
    failed = Signal(str)

    def __init__(self, source: Path, cfg: Config, stages: tuple[str, ...], stage: str):
        super().__init__()
        self.source = source
        self.cfg = cfg
        self.stages = stages
        self.stage = stage

    def run(self) -> None:  # noqa: D401
        try:
            out = pipeline.run(self.source, self.cfg, stages=self.stages)
            self.done.emit(str(out), self.stage)
        except Exception as exc:  # surface any pipeline failure in the tray
            self.failed.emit(str(exc))


class TrayApp(QSystemTrayIcon):
    def __init__(self, cfg: Config):
        super().__init__(QIcon(str(ASSETS / "icon.svg")))
        self.cfg = cfg
        self.worker: Worker | None = None

        self.last_source: Path | None = None
        self.last_output: Path | None = None
        self.transcript_ready = False
        self.outputs_ready = False

        self.setToolTip(APP_NAME)

        self.menu = QMenu()

        self.action_run = QAction("Transcribe file…", self)
        self.action_run.triggered.connect(self.pick_file)

        self.action_generate = QAction("Generate outputs (a / b / c)", self)
        self.action_generate.triggered.connect(self.generate_outputs)

        self.output_menu = QMenu("Open outputs", self.menu)
        self.output_actions: dict[str, QAction] = {}
        for key, label in (
            ("original", "Transcript · original"),
            ("translated", "Transcript · translation"),
            ("bilingual", "Transcript · side by side"),
            ("a", "A · Spoken script"),
            ("b", "B · Knowledge report"),
            ("c", "C · Brief"),
        ):
            action = QAction(label, self)
            action.triggered.connect(lambda _=False, k=key: self.open_output(k))
            self.output_actions[key] = action
            self.output_menu.addAction(action)

        self.action_output_dir = QAction("Open output folder", self)
        self.action_output_dir.triggered.connect(lambda: self._open(self.cfg.output))

        self.action_config = QAction("Open config folder", self)
        self.action_config.triggered.connect(lambda: self._open(PROJECT_ROOT / "configs"))

        self.action_about = QAction(f"About {APP_NAME} {__version__}", self)
        self.action_about.triggered.connect(self.show_about)

        self.action_status = QAction("Idle", self)
        self.action_status.setEnabled(False)

        self.action_quit = QAction("Quit", self)
        self.action_quit.triggered.connect(self.quit)

        self.menu.addAction(self.action_run)
        self.menu.addAction(self.action_generate)
        self.menu.addSeparator()
        self.menu.addAction(self.action_status)
        self.menu.addSeparator()
        self.menu.addMenu(self.output_menu)
        self.menu.addAction(self.action_output_dir)
        self.menu.addAction(self.action_config)
        self.menu.addAction(self.action_about)
        self.menu.addSeparator()
        self.menu.addAction(self.action_quit)

        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)
        self._refresh()

    # ------------------------------------------------------------------ state
    def _refresh(self) -> None:
        busy = bool(self.worker and self.worker.isRunning())
        self.action_run.setEnabled(not busy)
        self.action_generate.setEnabled(not busy and self.transcript_ready)
        for key, action in self.output_actions.items():
            action.setEnabled(self._output_path(key) is not None)

    def _output_path(self, kind: str) -> Path | None:
        out = self.last_output
        if not out or not out.exists():
            return None
        if kind in ("a", "b", "c"):
            names = {"a": "a-script.md", "b": "b-report.md", "c": "c-brief.md"}
            path = out / names[kind]
            return path if path.exists() else None

        text_dir = out / "text"
        if not text_dir.exists():
            return None
        if kind == "original":
            path = text_dir / "original.txt"
            return path if path.exists() else None
        if kind == "translated":
            found = sorted(text_dir.glob("translated.*.txt"))
            return found[0] if found else None
        found = sorted(text_dir.glob("bilingual.*.txt"))
        return found[0] if found else None

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.menu.popup(self.geometry().center())

    # ------------------------------------------------------------------ actions
    def pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Choose a file", "", AUDIO_FILTER)
        if path:
            self.start_job(Path(path), TRANSCRIBE_STAGES, "transcribe")

    def start_job(self, source: Path, stages: tuple[str, ...], stage: str) -> None:
        if self.worker and self.worker.isRunning():
            self.showMessage(APP_NAME, "A job is already running.",
                             QSystemTrayIcon.MessageIcon.Warning, 4000)
            return

        self.last_source = source
        self.action_status.setText(f"Working: {source.name}")
        self.setToolTip(f"{APP_NAME} — working on {source.name}")
        self.showMessage(APP_NAME, f"Started: {source.name}",
                         QSystemTrayIcon.MessageIcon.Information, 3000)

        self.worker = Worker(source, self.cfg, stages, stage)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_error)
        self.worker.start()
        self._refresh()

    def on_done(self, output: str, stage: str) -> None:
        self.last_output = Path(output)
        if stage == "transcribe":
            self.transcript_ready = True
            self.action_status.setText("Transcript ready")
            self.showMessage(
                APP_NAME,
                "Transcript ready.\nOpen the transcript to review it, then run "
                "\"Generate outputs (a / b / c)\".",
                QSystemTrayIcon.MessageIcon.Information, 8000,
            )
        else:
            self.outputs_ready = True
            self.action_status.setText("Outputs ready")
            self.showMessage(
                APP_NAME,
                "Outputs ready: spoken script, knowledge report and brief.",
                QSystemTrayIcon.MessageIcon.Information, 8000,
            )
        self.setToolTip(APP_NAME)
        self._refresh()

    def on_error(self, message: str) -> None:
        self.action_status.setText("Failed")
        self.setToolTip(APP_NAME)
        self.showMessage(APP_NAME, f"Job failed:\n{message[:300]}",
                         QSystemTrayIcon.MessageIcon.Critical, 8000)
        self._refresh()

    def generate_outputs(self) -> None:
        if not self.last_source or not self.transcript_ready:
            self.showMessage(APP_NAME, "Transcribe a file first.",
                             QSystemTrayIcon.MessageIcon.Warning, 4000)
            return
        self.start_job(self.last_source, GENERATE_STAGES, "generate")

    def open_output(self, kind: str) -> None:
        path = self._output_path(kind)
        if path is None:
            self.showMessage(APP_NAME, "That output is not available yet.",
                             QSystemTrayIcon.MessageIcon.Warning, 4000)
            return
        self._open(path)

    def show_about(self) -> None:
        QMessageBox.information(
            None,
            f"About {APP_NAME}",
            f"{APP_NAME} {__version__}\n\n"
            "Turns multilingual speech into clean transcripts,\n"
            "knowledge reports and short briefs.\n\n"
            "Workflow:\n"
            "1. Transcribe file…\n"
            "2. Review the bilingual transcript\n"
            "3. Generate outputs (a / b / c)\n\n"
            "All processing stays on this machine unless a cloud\n"
            "provider is enabled in configs/models.toml.",
        )

    def _open(self, path: Path) -> None:
        if path.is_dir():
            path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def quit(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        QApplication.quit()


def run_tray(cfg: Config, initial: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    selftest = bool(os.environ.get("MVS_TRAY_SELFTEST"))
    if not selftest and not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available on this session.", file=sys.stderr)
        return 1

    tray = TrayApp(cfg)
    tray.show()

    if initial is not None:
        QTimer.singleShot(200, lambda: tray.start_job(initial, TRANSCRIBE_STAGES, "transcribe"))

    if selftest:
        QTimer.singleShot(1500, app.quit)

    return app.exec()


def main() -> int:
    import traceback

    from ..config import load

    initial = None
    argv = sys.argv[1:]
    if "--input" in argv:
        index = argv.index("--input")
        if index + 1 < len(argv):
            initial = Path(argv[index + 1])

    log = PROJECT_ROOT / "work" / "tray-error.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log.open("a", encoding="utf-8") as handle:
            handle.write(f"main() entered {initial}\n")
        return run_tray(load(), initial)
    except Exception:
        with log.open("a", encoding="utf-8") as handle:
            traceback.print_exc(file=handle)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
