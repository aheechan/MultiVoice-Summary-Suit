"""System tray application (English/Chinese UI)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSize, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
)

from .. import __version__, discover, glossary, ingest, pipeline, settings
from ..config import PROJECT_ROOT, Config
from . import i18n
from .panel import Panel
from .providers_ui import ProviderManagerDialog
from .review import ReviewDialog

ASSETS = PROJECT_ROOT / "assets"

AUDIO_FILTER = (
    "Media files (*.mp4 *.mkv *.mov *.webm *.mp3 *.wav *.m4a *.flac *.aac);;"
    "All files (*.*)"
)

TRANSCRIBE_STAGES = ("asr", "correct", "translate")
GENERATE_STAGES = ("extract", "generate")


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48):
        path = ASSETS / f"icon-{size}.png"
        if path.exists():
            icon.addFile(str(path), QSize(size, size))
    detailed = ASSETS / "icon.svg"
    if detailed.exists():
        icon.addFile(str(detailed))
    return icon


class Worker(QThread):
    done = Signal(str, str, str)   # output dir, stage, output kind
    failed = Signal(str)
    progress = Signal(int, str)

    def __init__(self, source: Path, cfg: Config, stages: tuple[str, ...],
                 stage: str, outputs: tuple[str, ...] = ("a", "b", "c")):
        super().__init__()
        self.source = source
        self.cfg = cfg
        self.stages = stages
        self.stage = stage
        self.outputs = outputs

    def run(self) -> None:  # noqa: D401
        try:
            out = pipeline.run(
                self.source, self.cfg, stages=self.stages, outputs=self.outputs,
                on_progress=lambda value, key: self.progress.emit(value, key),
            )
            self.done.emit(str(out), self.stage, ",".join(self.outputs))
        except Exception as exc:
            self.failed.emit(str(exc))


class DiscoverWorker(QThread):
    finished_ok = Signal(int)
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg

    def run(self) -> None:  # noqa: D401
        try:
            lex = glossary.load()
            result = discover.run(lex, self.cfg, per_topic=6)
            self.finished_ok.emit(int(result.get("queued", 0)))
        except Exception:
            self.finished_ok.emit(0)


class PrefetchWorker(QThread):
    finished_ok = Signal(int)

    def __init__(self, cfg: Config, limit: int):
        super().__init__()
        self.cfg = cfg
        self.limit = limit

    def run(self) -> None:  # noqa: D401
        try:
            from .. import prefetch

            lex = glossary.load()
            self.finished_ok.emit(prefetch.warm(lex, self.cfg, self.limit))
        except Exception:
            self.finished_ok.emit(0)


class UrlWorker(QThread):
    ready = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, cfg: Config):
        super().__init__()
        self.url = url
        self.cfg = cfg

    def run(self) -> None:  # noqa: D401
        try:
            target = ingest.fetch_url(self.url, self.cfg.work / "_downloads")
            self.ready.emit(str(target))
        except Exception as exc:
            self.failed.emit(str(exc))


class SettingsDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle(i18n.t("settings").rstrip("…"))
        self.setWindowIcon(app_icon())
        prefs = settings.load()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        kb_box = QGroupBox(i18n.t("knowledge_base"))
        kb_form = QFormLayout(kb_box)
        kb_form.setSpacing(8)

        self.auto = QCheckBox(i18n.t("auto_research"))
        self.auto.setChecked(bool(prefs.get("auto_research", True)))
        self.discover = QCheckBox(i18n.t("auto_discover"))
        self.discover.setChecked(bool(prefs.get("auto_discover", True)))

        self.limit = QSpinBox()
        self.limit.setRange(0, 12)
        self.limit.setValue(int(prefs.get("max_terms", 6)))

        kb_form.addRow(self.auto)
        kb_form.addRow(self.discover)
        kb_form.addRow(i18n.t("max_lookups"), self.limit)

        self.export_button = QPushButton(i18n.t("export"))
        self.export_button.clicked.connect(self.export_kb)
        kb_form.addRow(self.export_button)
        layout.addWidget(kb_box)

        model_box = QGroupBox(i18n.t("models_section"))
        model_form = QFormLayout(model_box)
        model_form.setSpacing(8)
        active = (cfg.llm.get("order") or ["—"])[0]
        self.active_label = QLabel(i18n.t("current_provider", name=active))
        self.manage = QPushButton(i18n.t("manage_providers"))
        self.manage.clicked.connect(self.open_providers)
        model_form.addRow(self.active_label)
        model_form.addRow(self.manage)
        layout.addWidget(model_box)

        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def open_providers(self) -> None:
        ProviderManagerDialog(self.cfg, self).exec()
        active = (self.cfg.llm.get("order") or ["—"])[0]
        self.active_label.setText(i18n.t("current_provider", name=active))

    def export_kb(self) -> None:
        default = str(PROJECT_ROOT / "glossary-export.json")
        path, _ = QFileDialog.getSaveFileName(
            self, i18n.t("export"), default, "JSON files (*.json)"
        )
        if not path:
            return
        lex = glossary.load()
        lex.export(Path(path))
        QMessageBox.information(
            self, i18n.t("app_name"),
            i18n.t("export_done", count=len(lex.entries), path=path),
        )

    def values(self) -> dict:
        return {
            "auto_research": self.auto.isChecked(),
            "auto_discover": self.discover.isChecked(),
            "max_terms": self.limit.value(),
        }


class TrayApp(QSystemTrayIcon):
    TRANSCRIBE_STAGES = TRANSCRIBE_STAGES

    def __init__(self, cfg: Config):
        super().__init__(app_icon())
        self.cfg = cfg
        self.worker: Worker | None = None
        self.discover_worker: DiscoverWorker | None = None
        self.url_worker: UrlWorker | None = None
        self.prefetch_worker: PrefetchWorker | None = None

        self.last_source: Path | None = None
        self.last_output: Path | None = None
        self.transcript_ready = False
        self.outputs_ready = False
        self.panel_status = ""
        self.panel: Panel | None = None
        self.review_dialog: ReviewDialog | None = None

        prefs = settings.load()
        i18n.set_language(prefs.get("language", "en"))

        self.setToolTip(i18n.t("app_name"))
        self.menu = QMenu()
        self.output_actions: dict[str, QAction] = {}
        self.build_menu()
        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)
        self.panel_status = i18n.t("status_idle")
        self._refresh()

    # ------------------------------------------------------------------ menu
    def build_menu(self) -> None:
        self.menu.clear()
        self.output_actions = {}

        self.action_run = QAction(i18n.t("transcribe"), self)
        self.action_run.triggered.connect(self.pick_file)

        self.action_url = QAction(i18n.t("from_url"), self)
        self.action_url.triggered.connect(self.pick_url)

        self.action_generators: dict[str, QAction] = {}
        for kind, label, desc in (
            ("a", "gen_a", "gen_a_desc"),
            ("b", "gen_b", "gen_b_desc"),
            ("c", "gen_c", "gen_c_desc"),
        ):
            action = QAction(f"{i18n.t(label)} — {i18n.t(desc)}", self)
            action.triggered.connect(lambda _=False, k=kind: self.generate_outputs(k))
            self.action_generators[kind] = action

        self.action_panel = QAction(i18n.t("panel"), self)
        self.action_panel.triggered.connect(self.open_panel)

        self.action_review = QAction(i18n.t("review", n=0), self)
        self.action_review.triggered.connect(self.open_review)

        self.output_menu = QMenu(i18n.t("open_output"), self.menu)
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

        self.action_output_dir = QAction(i18n.t("open_output"), self)
        self.action_output_dir.triggered.connect(lambda: self._open(self.cfg.output))

        self.action_settings = QAction(i18n.t("settings"), self)
        self.action_settings.triggered.connect(self.show_settings)

        self.provider_menu = QMenu(i18n.t("providers"), self.menu)
        active = (self.cfg.llm.get("order") or [""])[0]
        for item in self.cfg.llm.get("providers", []):
            name = item.get("name", "")
            action = self.provider_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == active)
            action.triggered.connect(lambda _=False, n=name: self.select_provider(n))
        self.provider_menu.addSeparator()
        manage = self.provider_menu.addAction(i18n.t("manage_providers"))
        manage.triggered.connect(self.show_providers)

        self.action_language = QAction(i18n.t("language"), self)
        self.action_language.triggered.connect(self.toggle_language)

        self.action_about = QAction(f"{i18n.t('about')} — {__version__}", self)
        self.action_about.triggered.connect(self.show_about)

        self.action_status = QAction(i18n.t("status_idle"), self)
        self.action_status.setEnabled(False)

        self.action_quit = QAction(i18n.t("quit"), self)
        self.action_quit.triggered.connect(self.quit)

        self.menu.addAction(self.action_run)
        self.menu.addAction(self.action_url)
        self.menu.addSeparator()
        for kind in ("a", "b", "c"):
            self.menu.addAction(self.action_generators[kind])
        self.menu.addSeparator()
        self.menu.addAction(self.action_status)
        self.menu.addSeparator()
        self.menu.addAction(self.action_panel)
        self.menu.addAction(self.action_review)
        self.menu.addMenu(self.output_menu)
        self.menu.addAction(self.action_output_dir)
        self.menu.addSeparator()
        self.menu.addMenu(self.provider_menu)
        self.menu.addAction(self.action_settings)
        self.menu.addAction(self.action_language)
        self.menu.addAction(self.action_about)
        self.menu.addSeparator()
        self.menu.addAction(self.action_quit)

    def retranslate(self) -> None:
        self.build_menu()
        self.setContextMenu(self.menu)
        if self.panel is not None:
            self.panel.retranslate()
        self._refresh()

    def toggle_language(self) -> None:
        target = "zh" if i18n.language() == "en" else "en"
        settings.save({"language": target})
        i18n.set_language(target)
        self.retranslate()

    # ------------------------------------------------------------------ state
    def _refresh(self) -> None:
        busy = bool(self.worker and self.worker.isRunning())
        self.action_run.setEnabled(not busy)
        for action in self.action_generators.values():
            action.setEnabled(not busy and self.transcript_ready)
        for key, action in self.output_actions.items():
            action.setEnabled(self._output_path(key) is not None)
        try:
            pending = len(glossary.load().pending)
        except Exception:
            pending = 0
        self.action_review.setText(i18n.t("review", n=pending))
        self.action_review.setEnabled(pending > 0)
        if self.panel is not None:
            self.panel.refresh()

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
        # Clicking the tray icon (or the overflow arrow) opens the panel directly.
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_panel()

    # ------------------------------------------------------------------ actions
    def open_panel(self) -> None:
        if self.panel is None:
            self.panel = Panel(self)
        self.panel.retranslate()
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def open_review(self) -> None:
        try:
            self.review_dialog = ReviewDialog(self.cfg, self.panel)
            self.warm_review(3)
            self.review_dialog.exec()
            self.review_dialog = None
            self._refresh()
        except Exception:
            import traceback

            log = PROJECT_ROOT / "work" / "tray-error.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as handle:
                traceback.print_exc(file=handle)

    def pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, i18n.t("transcribe"), "", AUDIO_FILTER)
        if path:
            self.start_job(Path(path), TRANSCRIBE_STAGES, "transcribe")

    def pick_url(self) -> None:
        url, ok = QInputDialog.getText(
            None, i18n.t("from_url"), i18n.t("url_prompt")
        )
        if ok and url.strip():
            self.start_url(url.strip())

    def start_url(self, url: str) -> None:
        if self.url_worker and self.url_worker.isRunning():
            return
        self.panel_status = i18n.t("downloading")
        if self.panel is not None:
            self.panel.set_progress(2, i18n.t("downloading"))
        self.showMessage(i18n.t("app_name"), i18n.t("url_hint"),
                         QSystemTrayIcon.MessageIcon.Information, 5000)

        self.url_worker = UrlWorker(url, self.cfg)
        self.url_worker.ready.connect(
            lambda path: self.start_job(Path(path), TRANSCRIBE_STAGES, "transcribe")
        )
        self.url_worker.failed.connect(self.on_error)
        self.url_worker.start()

    def start_job(self, source: Path, stages: tuple[str, ...], stage: str,
                  outputs: tuple[str, ...] = ("a", "b", "c")) -> None:
        if self.worker and self.worker.isRunning():
            self.showMessage(i18n.t("app_name"), i18n.t("working_alert"),
                             QSystemTrayIcon.MessageIcon.Warning, 4000)
            return

        self.last_source = source
        self.panel_status = i18n.t("status_working", name=source.name)
        self.action_status.setText(self.panel_status)
        self.showMessage(i18n.t("app_name"), i18n.t("started", name=source.name),
                         QSystemTrayIcon.MessageIcon.Information, 3000)

        self.worker = Worker(source, self.cfg, stages, stage, outputs)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_error)
        self.worker.progress.connect(self.on_progress)
        self.worker.start()
        if self.panel is not None:
            self.panel.set_progress(0, i18n.t("stage_audio"))
        self._refresh()

    def on_progress(self, value: int, key: str) -> None:
        message = i18n.t(f"stage_{key}")
        self.panel_status = message
        self.action_status.setText(message)
        if self.panel is not None:
            self.panel.set_progress(value, message)

    def on_done(self, output: str, stage: str, kinds: str) -> None:
        self.last_output = Path(output)
        if stage == "transcribe":
            self.transcript_ready = True
            self.panel_status = i18n.t("status_transcript")
            self.action_status.setText(self.panel_status)
            self.showMessage(i18n.t("app_name"), i18n.t("transcript_ready_msg"),
                             QSystemTrayIcon.MessageIcon.Information, 8000)
        else:
            self.outputs_ready = True
            labels = {"a": "gen_a", "b": "gen_b", "c": "gen_c"}
            kind_label = i18n.t(labels.get(kinds.split(",")[0], "gen_a"))
            self.panel_status = i18n.t("status_outputs")
            self.action_status.setText(self.panel_status)
            self.showMessage(i18n.t("app_name"),
                             i18n.t("outputs_ready", kind=kind_label),
                             QSystemTrayIcon.MessageIcon.Information, 8000)
        self.setToolTip(i18n.t("app_name"))
        if self.panel is not None:
            self.panel.clear_progress()
        self._refresh()

    def on_error(self, message: str) -> None:
        self.panel_status = i18n.t("status_failed")
        self.action_status.setText(self.panel_status)
        if self.panel is not None:
            self.panel.clear_progress()
        self.showMessage(i18n.t("app_name"),
                         i18n.t("failed_msg", message=message[:300]),
                         QSystemTrayIcon.MessageIcon.Critical, 8000)
        self._refresh()

    def generate_outputs(self, kind: str = "a") -> None:
        if not self.last_source or not self.transcript_ready:
            self.showMessage(i18n.t("app_name"), i18n.t("gen_hint"),
                             QSystemTrayIcon.MessageIcon.Warning, 4000)
            return
        self.start_job(self.last_source, GENERATE_STAGES, "generate", (kind,))

    def open_output(self, kind: str) -> None:
        path = self._output_path(kind)
        if path is None:
            self.showMessage(i18n.t("app_name"), i18n.t("gen_hint"),
                             QSystemTrayIcon.MessageIcon.Warning, 4000)
            return
        self._open(path)

    # ------------------------------------------------------------------ misc
    def show_providers(self) -> None:
        ProviderManagerDialog(self.cfg, self.panel).exec()
        self.retranslate()

    def select_provider(self, name: str) -> None:
        settings.save({"provider": name})
        self.cfg.llm["order"] = [name]
        self.retranslate()
        self.showMessage(i18n.t("app_name"), i18n.t("current_provider", name=name),
                         QSystemTrayIcon.MessageIcon.Information, 4000)

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.cfg)
        if not dialog.exec():
            return
        prefs = settings.save(dialog.values())
        self.cfg.research["enabled"] = prefs["auto_research"]
        self.cfg.research["max_terms"] = prefs["max_terms"]
        if self.panel is not None:
            self.panel.retranslate()
        self.showMessage(i18n.t("app_name"), i18n.t("settings_saved"),
                         QSystemTrayIcon.MessageIcon.Information, 4000)

    def show_about(self) -> None:
        QMessageBox.information(
            None, i18n.t("about"),
            i18n.t("about_text", name=i18n.t("app_name"), version=__version__),
        )

    def _open(self, path: Path) -> None:
        if path.is_dir():
            path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def check_pending(self) -> None:
        lex = glossary.load()
        lex.prune_pending()
        self._refresh()
        count = len(lex.pending)
        if count:
            self.showMessage(i18n.t("app_name"), i18n.t("review", n=count),
                             QSystemTrayIcon.MessageIcon.Information, 9000)

    def run_discovery(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        if self.discover_worker and self.discover_worker.isRunning():
            return
        self.discover_worker = DiscoverWorker(self.cfg)
        self.discover_worker.finished_ok.connect(lambda _: self._refresh())
        self.discover_worker.start()

    def warm_review(self, limit: int) -> None:
        """Preload bilingual search summaries so the review dialog opens instantly."""
        if self.prefetch_worker and self.prefetch_worker.isRunning():
            return
        self.prefetch_worker = PrefetchWorker(self.cfg, limit)
        self.prefetch_worker.finished_ok.connect(lambda _: self._refresh())
        self.prefetch_worker.start()

    def quit(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        QApplication.quit()


def run_tray(cfg: Config, initial: Path | None = None, show_panel: bool = False,
             show_review: bool = False) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(i18n.t("app_name"))
    app.setQuitOnLastWindowClosed(False)

    selftest = bool(os.environ.get("MVS_TRAY_SELFTEST"))
    if not selftest and not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available on this session.", file=sys.stderr)
        return 1

    tray = TrayApp(cfg)
    tray.show()

    if show_panel:
        QTimer.singleShot(300, tray.open_panel)
    if show_review:
        QTimer.singleShot(600, tray.open_review)

    QTimer.singleShot(4000, tray.check_pending)
    daily = QTimer(tray)
    daily.setInterval(24 * 60 * 60 * 1000)
    daily.timeout.connect(tray.check_pending)
    daily.start()

    prefs = settings.load()
    if prefs.get("auto_discover", True):
        QTimer.singleShot(15000, tray.run_discovery)

    QTimer.singleShot(8000, lambda: tray.warm_review(6))

    QTimer.singleShot(
        1200,
        lambda: tray.showMessage(i18n.t("app_name"), i18n.t("tray_hint"),
                                 QSystemTrayIcon.MessageIcon.Information, 9000),
    )

    if selftest:
        QTimer.singleShot(1500, app.quit)

    return app.exec()


def main() -> int:
    import traceback

    from ..config import load

    initial = None
    show_panel = False
    argv = sys.argv[1:]
    if "--input" in argv:
        index = argv.index("--input")
        if index + 1 < len(argv):
            initial = Path(argv[index + 1])
    if "--panel" in argv:
        show_panel = True
    show_review = "--review" in argv

    log = PROJECT_ROOT / "work" / "tray-error.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log.open("a", encoding="utf-8") as handle:
            handle.write(f"main() entered {initial} panel={show_panel} review={show_review}\n")
        return run_tray(load(), initial, show_panel, show_review)
    except Exception:
        with log.open("a", encoding="utf-8") as handle:
            traceback.print_exc(file=handle)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
