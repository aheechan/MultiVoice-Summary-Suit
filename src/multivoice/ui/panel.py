"""Main control panel (works even when the tray icon is hidden)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import glossary
from ..config import PROJECT_ROOT
from . import i18n

ASSETS = PROJECT_ROOT / "assets"
MEDIA_SUFFIXES = {
    ".mp4", ".mkv", ".mov", ".webm", ".mp3", ".wav", ".m4a", ".flac", ".aac",
}

STYLE = """
QWidget { background: #04060d; color: #dceeff; font-family: 'Segoe UI', sans-serif; }
QFrame#card { background: #070b16; border: 1px solid #16243f; border-radius: 14px; }
QLabel#title { font-size: 18px; font-weight: 600; color: #eaf7ff; }
QLabel#subtitle { color: #7f93ad; font-size: 12px; }
QLabel#status { color: #9fd8ff; font-size: 12px; }
QLabel#info { color: #6f86a6; font-size: 11px; }
QLabel#step { color: #7f93ad; font-size: 11px; }
QLabel#badge_label { color: #7f93ad; font-size: 10px; }
QLabel#next {
    color: #9fe3ff; font-size: 12px; font-weight: 600;
    background: #0b1a30; border: 1px solid #2b57c8; border-radius: 7px;
    padding: 7px 10px;
}
QPushButton[ready="true"] { border-color: #3d7bff; background: #132a4d; }
QPushButton[ready="true"]:hover { background: #1a3866; }
QPushButton {
    background: #10203c; color: #dceeff; border: 1px solid #1f3b6b;
    border-radius: 8px; padding: 10px 14px; text-align: left;
}
QPushButton:hover { background: #16305a; border-color: #3d7bff; }
QPushButton:disabled { color: #4a5a70; border-color: #16243f; background: #080d18; }
QPushButton#primary { background: #1d4ed8; border-color: #3d7bff; font-weight: 600; }
QPushButton#primary:hover { background: #2563eb; }
QPushButton#url {
    background: #0d1b33; border: 1px solid #24467f; font-size: 12px;
    padding: 0px; text-align: center;
}
QPushButton#circle {
    background: #0d1b33; border: 1px solid #24467f; border-radius: 19px;
    font-size: 12px; font-weight: 600; padding: 0px; text-align: center;
}
QPushButton#circle:hover { background: #16305a; border-color: #3d7bff; }
QPushButton#small {
    background: transparent; border: 1px solid #1b3055; border-radius: 7px;
    color: #9fb6d4; font-size: 12px; padding: 6px 8px; text-align: center;
}
QPushButton#small:hover { color: #eaf7ff; border-color: #3d7bff; }
QProgressBar {
    background: #0a1220; border: 1px solid #182b4a; border-radius: 5px;
    height: 8px; text-align: center; color: transparent;
}
QProgressBar::chunk { background: #2f6bff; border-radius: 4px; }
"""


class Panel(QWidget):
    def __init__(self, tray):
        super().__init__()
        self.tray = tray
        self.setWindowTitle(i18n.t("app_name"))
        self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(480)
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(10)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(ASSETS / "icon.png"))
        if not pixmap.isNull():
            self.logo.setPixmap(pixmap.scaled(
                72, 72, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        root.addWidget(self.logo)

        card = QFrame()
        card.setObjectName("card")
        inner = QHBoxLayout(card)
        inner.setContentsMargins(18, 16, 14, 16)
        inner.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        self.status = QLabel()
        self.status.setObjectName("status")
        text_col.addWidget(self.title)
        text_col.addWidget(self.subtitle)
        text_col.addWidget(self.status)
        inner.addLayout(text_col, 1)

        buttons_col = QHBoxLayout()
        buttons_col.setSpacing(8)
        self.btn_review = QPushButton("0")
        self.btn_review.setObjectName("circle")
        self.btn_review.setFixedSize(38, 38)
        self.btn_review.clicked.connect(self.tray.open_review)

        self.btn_lang = QPushButton()
        self.btn_lang.setObjectName("circle")
        self.btn_lang.setFixedSize(38, 38)
        self.btn_lang.clicked.connect(self.tray.toggle_language)

        review_col = QVBoxLayout()
        review_col.setSpacing(2)
        review_col.addWidget(self.btn_review, 0, Qt.AlignmentFlag.AlignHCenter)
        self.badge_label = QLabel()
        self.badge_label.setObjectName("badge_label")
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        review_col.addWidget(self.badge_label)
        buttons_col.addLayout(review_col)
        buttons_col.addWidget(self.btn_lang, 0, Qt.AlignmentFlag.AlignTop)
        inner.addLayout(buttons_col)

        root.addWidget(card)

        self.info = QLabel()
        self.info.setObjectName("info")
        self.info.setWordWrap(True)
        root.addWidget(self.info)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_transcribe = QPushButton()
        self.btn_transcribe.setObjectName("primary")
        self.btn_transcribe.clicked.connect(self.tray.pick_file)

        self.btn_url = QPushButton()
        self.btn_url.setObjectName("url")
        self.btn_url.setFixedWidth(96)
        self.btn_url.clicked.connect(self.tray.pick_url)

        row.addWidget(self.btn_transcribe, 1)
        row.addWidget(self.btn_url)
        root.addLayout(row)

        self.next_step = QLabel()
        self.next_step.setObjectName("next")
        self.next_step.setWordWrap(True)
        self.next_step.hide()
        root.addWidget(self.next_step)

        self.output_buttons = {}
        for kind in ("a", "b", "c", "d"):
            button = QPushButton()
            button.setMinimumHeight(52)
            button.setEnabled(False)
            button.setStyleSheet("text-align: left;")
            button.clicked.connect(lambda _=False, k=kind: self.tray.generate_outputs(k))
            self.output_buttons[kind] = button
            root.addWidget(button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.step = QLabel()
        self.step.setObjectName("step")
        root.addWidget(self.progress)
        root.addWidget(self.step)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.btn_outputs = QPushButton()
        self.btn_outputs.setObjectName("small")
        self.btn_outputs.clicked.connect(lambda: self.tray._open(self.tray.cfg.output))

        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("small")
        self.btn_settings.clicked.connect(self.tray.show_settings)

        self.btn_about = QPushButton()
        self.btn_about.setObjectName("small")
        self.btn_about.clicked.connect(self.tray.show_about)

        bottom.addWidget(self.btn_outputs)
        bottom.addWidget(self.btn_settings)
        bottom.addWidget(self.btn_about)
        root.addLayout(bottom)

        root.addStretch(1)
        self.retranslate()
        self.refresh()

    # ------------------------------------------------------------------ dnd
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in MEDIA_SUFFIXES:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in MEDIA_SUFFIXES:
                self.tray.start_job(path, self.tray.TRANSCRIBE_STAGES, "transcribe")
                event.acceptProposedAction()
                return
        event.ignore()

    # ------------------------------------------------------------------ ui
    def retranslate(self) -> None:
        self.setWindowTitle(i18n.t("app_name"))
        self.title.setText(i18n.t("app_name"))
        self.subtitle.setText(i18n.t("subtitle"))
        self.btn_transcribe.setText(i18n.t("transcribe"))
        self.btn_url.setText(i18n.t("from_url"))
        for kind, label, desc in (
            ("a", "gen_a", "gen_a_desc"),
            ("b", "gen_expand", "gen_expand_desc"),
            ("c", "gen_report", "gen_b_desc"),
            ("d", "gen_brief", "gen_c_desc"),
        ):
            self.output_buttons[kind].setText(f"{i18n.t(label)}\n{i18n.t(desc)}")
        self.badge_label.setText(i18n.t("terms_badge"))
        self.btn_outputs.setText(i18n.t("open_output"))
        self.btn_settings.setText(i18n.t("settings").rstrip("…"))
        self.btn_about.setText(i18n.t("about"))
        self.btn_lang.setText(i18n.t("language"))
        self.refresh()
        if not self.progress.property("active"):
            self.set_idle()

    def refresh(self) -> None:
        self.status.setText(getattr(self.tray, "panel_status", i18n.t("status_idle")))
        ready = self.tray.transcript_ready
        busy = bool(getattr(self.tray, "worker", None) and self.tray.worker.isRunning())

        for button in self.output_buttons.values():
            button.setEnabled(ready)
            button.setProperty("ready", ready)
            button.style().unpolish(button)
            button.style().polish(button)

        if busy:
            self.next_step.setText(i18n.t("step2_hint_transcribing"))
            self.next_step.show()
        elif ready:
            self.next_step.setText(i18n.t("step2_hint"))
            self.next_step.show()
        else:
            self.next_step.hide()

        try:
            count = len(glossary.load().pending)
        except Exception:
            count = 0
        self.btn_review.setText(str(count))
        self.btn_review.setEnabled(count > 0)
        self.btn_review.setToolTip(i18n.t("review", n=count))
        self.info.setText(i18n.t("review_info", n=count) if count else "")

    def set_progress(self, value: int, message: str) -> None:
        self.progress.setProperty("active", True)
        self.progress.setValue(max(0, min(100, value)))
        self.step.setText(f"{message} · {value}%")

    def set_idle(self) -> None:
        self.progress.setProperty("active", False)
        self.progress.setValue(0)
        self.step.setText(i18n.t("idle_progress") + " · 0%")

    def clear_progress(self) -> None:
        self.set_idle()

    def closeEvent(self, event):  # keep running in tray
        event.ignore()
        self.hide()
