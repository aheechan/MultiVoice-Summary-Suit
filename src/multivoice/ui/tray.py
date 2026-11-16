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


class Worker(QThread):
    finished_ok = Signal(str)
    finished_error = Signal(str)

    def __init__(self, source: Path, cfg: Config):
        super().__init__()
        self.source = source
        self.cfg = cfg

    def run(self) -> None:  # noqa: D401
        try:
            out = pipeline.run(self.source, self.cfg)
            self.finished_ok.emit(str(out))
        except Exception as exc:  # surface any pipeline failure in the tray
            self.finished_error.emit(str(exc))


class TrayApp(QSystemTrayIcon):
    def __init__(self, cfg: Config):
        icon = QIcon(str(ASSETS / "icon.svg"))
        super().__init__(icon)
        self.cfg = cfg
        self.worker: Worker | None = None

        self.setToolTip(APP_NAME)

        self.menu = QMenu()

        self.action_run = QAction("Transcribe file…", self)
        self.action_run.triggered.connect(self.pick_file)

        self.action_output = QAction("Open output folder", self)
        self.action_output.triggered.connect(
            lambda: self._open(self.cfg.output)
        )

        self.action_config = QAction("Open config folder", self)
        self.action_config.triggered.connect(
            lambda: self._open(PROJECT_ROOT / "configs")
        )

        self.action_about = QAction(f"About {APP_NAME} {__version__}", self)
        self.action_about.triggered.connect(self.show_about)

        self.action_status = QAction("Idle", self)
        self.action_status.setEnabled(False)

        self.action_quit = QAction("Quit", self)
        self.action_quit.triggered.connect(self.quit)

        self.menu.addAction(self.action_run)
        self.menu.addSeparator()
        self.menu.addAction(self.action_status)
        self.menu.addSeparator()
        self.menu.addAction(self.action_output)
        self.menu.addAction(self.action_config)
        self.menu.addAction(self.action_about)
        self.menu.addSeparator()
        self.menu.addAction(self.action_quit)

        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)

    # ------------------------------------------------------------------ actions
    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.menu.popup(self.geometry().center())

    def pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Choose a file", "", AUDIO_FILTER)
        if path:
            self.start_job(Path(path))

    def start_job(self, source: Path) -> None:
        if self.worker and self.worker.isRunning():
            self.showMessage(APP_NAME, "A job is already running.", QSystemTrayIcon.MessageIcon.Warning, 4000)
            return

        self.action_run.setEnabled(False)
        self.action_status.setText(f"Working: {source.name}")
        self.setToolTip(f"{APP_NAME} — working on {source.name}")

        self.worker = Worker(source, self.cfg)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.finished_error.connect(self.on_error)
        self.worker.start()

    def on_done(self, output: str) -> None:
        self.action_run.setEnabled(True)
        self.action_status.setText("Done")
        self.setToolTip(APP_NAME)
        self.showMessage(
            APP_NAME,
            f"Finished.\nOutput: {output}",
            QSystemTrayIcon.MessageIcon.Information,
            6000,
        )

    def on_error(self, message: str) -> None:
        self.action_run.setEnabled(True)
        self.action_status.setText("Failed")
        self.setToolTip(APP_NAME)
        self.showMessage(
            APP_NAME,
            f"Job failed:\n{message[:300]}",
            QSystemTrayIcon.MessageIcon.Critical,
            8000,
        )

    def show_about(self) -> None:
        QMessageBox.information(
            None,
            f"About {APP_NAME}",
            f"{APP_NAME} {__version__}\n\n"
            "Turns multilingual speech into clean transcripts,\n"
            "knowledge reports and short briefs.\n\n"
            "All processing stays on this machine unless a\n"
            "cloud provider is enabled in configs/models.toml.",
        )

    def _open(self, path: Path) -> None:
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
        QTimer.singleShot(200, lambda: tray.start_job(initial))

    if selftest:
        QTimer.singleShot(1500, app.quit)

    return app.exec()


def main() -> int:
    import traceback

    from ..config import load

    log = PROJECT_ROOT / "work" / "tray-error.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log.open("a", encoding="utf-8") as handle:
            handle.write("main() entered\n")
        return run_tray(load())
    except Exception:
        with log.open("a", encoding="utf-8") as handle:
            traceback.print_exc(file=handle)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
