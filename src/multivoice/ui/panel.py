"""Main control panel (works even when the tray icon is hidden)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
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

STYLE = """
QWidget { background: #04060d; color: #dceeff; font-family: 'Segoe UI', sans-serif; }
QFrame#card { background: #070b16; border: 1px solid #16243f; border-radius: 14px; }
QLabel#title { font-size: 18px; font-weight: 600; color: #eaf7ff; }
QLabel#subtitle { color: #7f93ad; font-size: 12px; }
QLabel#status { color: #9fd8ff; font-size: 12px; }
QLabel#section { color: #6f86a6; font-size: 11px; letter-spacing: 1px; }
QPushButton {
    background: #10203c; color: #dceeff; border: 1px solid #1f3b6b;
    border-radius: 8px; padding: 10px 14px; text-align: left;
}
QPushButton:hover { background: #16305a; border-color: #3d7bff; }
QPushButton:disabled { color: #4a5a70; border-color: #16243f; background: #080d18; }
QPushButton#primary { background: #1d4ed8; border-color: #3d7bff; font-weight: 600; }
QPushButton#primary:hover { background: #2563eb; }
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
QLabel#step { color: #7f93ad; font-size: 11px; }
"""


class Panel(QWidget):
    def __init__(self, tray):
        super().__init__()
        self.tray = tray
        self.setWindowTitle(i18n.t("app_name"))
        self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(470)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

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

        buttons_col.addWidget(self.btn_review)
        buttons_col.addWidget(self.btn_lang)
        inner.addLayout(buttons_col)

        root.addWidget(card)

        self.btn_transcribe = QPushButton()
        self.btn_transcribe.setObjectName("primary")
        self.btn_transcribe.clicked.connect(self.tray.pick_file)
        root.addWidget(self.btn_transcribe)

        self.section = QLabel()
        self.section.setObjectName("section")
        self.section.setWordWrap(True)
        root.addWidget(self.section)

        self.output_buttons = {}
        for kind in ("a", "b", "c"):
            button = QPushButton()
            button.setMinimumHeight(52)
            button.setEnabled(False)
            button.clicked.connect(lambda _=False, k=kind: self.tray.generate_outputs(k))
            self.output_buttons[kind] = button
            root.addWidget(button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        self.progress.hide()
        self.step = QLabel()
        self.step.setObjectName("step")
        self.step.hide()
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

    def retranslate(self) -> None:
        self.setWindowTitle(i18n.t("app_name"))
        self.title.setText(i18n.t("app_name"))
        self.subtitle.setText(i18n.t("subtitle"))
        self.btn_transcribe.setText(i18n.t("transcribe"))
        self.section.setText(i18n.t("gen_hint").upper())
        for kind, label, desc in (
            ("a", "gen_a", "gen_a_desc"),
            ("b", "gen_b", "gen_b_desc"),
            ("c", "gen_c", "gen_c_desc"),
        ):
            button = self.output_buttons[kind]
            button.setText(f"{i18n.t(label)}\n{i18n.t(desc)}")
            button.setStyleSheet("text-align: left;")
        self.btn_outputs.setText(i18n.t("open_output"))
        self.btn_settings.setText(i18n.t("settings").rstrip("…"))
        self.btn_about.setText(i18n.t("about"))
        self.btn_lang.setText(i18n.t("language"))
        self.btn_lang.setToolTip(i18n.t("language"))
        self.btn_review.setToolTip(i18n.t("review", n=0))
        self.refresh()

    def refresh(self) -> None:
        self.status.setText(getattr(self.tray, "panel_status", i18n.t("status_idle")))
        ready = self.tray.transcript_ready
        for button in self.output_buttons.values():
            button.setEnabled(ready)
        try:
            count = len(glossary.load().pending)
        except Exception:
            count = 0
        self.btn_review.setText(str(count))
        self.btn_review.setEnabled(count > 0)
        self.btn_review.setToolTip(i18n.t("review", n=count))

    def set_progress(self, value: int, message: str) -> None:
        self.progress.show()
        self.step.show()
        self.progress.setValue(max(0, min(100, value)))
        self.step.setText(message)

    def clear_progress(self) -> None:
        self.progress.hide()
        self.step.hide()
        self.progress.setValue(0)
        self.step.clear()

    def closeEvent(self, event):  # keep running in tray
        event.ignore()
        self.hide()
