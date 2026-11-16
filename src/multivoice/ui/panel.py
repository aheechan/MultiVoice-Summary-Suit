"""Main control panel (works even when the tray icon is hidden)."""
from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
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
QPushButton#output { padding: 10px 14px; }
"""


class Panel(QWidget):
    def __init__(self, tray):
        super().__init__()
        self.tray = tray
        self.setWindowTitle(i18n.t("app_name"))
        self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        card = QFrame()
        card.setObjectName("card")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(18, 16, 18, 16)
        inner.setSpacing(6)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        self.status = QLabel()
        self.status.setObjectName("status")
        inner.addWidget(self.title)
        inner.addWidget(self.subtitle)
        inner.addWidget(self.status)
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
            button.setObjectName("output")
            button.setMinimumHeight(52)
            button.clicked.connect(lambda _=False, k=kind: self.tray.generate_outputs(k))
            self.output_buttons[kind] = button
            root.addWidget(button)

        self.btn_review = QPushButton()
        self.btn_review.clicked.connect(self.tray.open_review)
        root.addWidget(self.btn_review)

        self.btn_outputs = QPushButton()
        self.btn_outputs.clicked.connect(lambda: self.tray._open(self.tray.cfg.output))
        root.addWidget(self.btn_outputs)

        self.btn_settings = QPushButton()
        self.btn_settings.clicked.connect(self.tray.show_settings)
        root.addWidget(self.btn_settings)

        self.btn_lang = QPushButton()
        self.btn_lang.clicked.connect(self.tray.toggle_language)
        root.addWidget(self.btn_lang)

        self.btn_about = QPushButton()
        self.btn_about.clicked.connect(self.tray.show_about)
        root.addWidget(self.btn_about)

        self.btn_quit = QPushButton()
        self.btn_quit.clicked.connect(self.tray.quit)
        root.addWidget(self.btn_quit)

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
            self.output_buttons[kind].setText(f"{i18n.t(label)}\n{i18n.t(desc)}")
        self.btn_outputs.setText(i18n.t("open_output"))
        self.btn_settings.setText(i18n.t("settings"))
        self.btn_lang.setText(i18n.t("language"))
        self.btn_about.setText(i18n.t("about"))
        self.btn_quit.setText(i18n.t("quit"))
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
        self.btn_review.setText(i18n.t("review", n=count))
        self.btn_review.setEnabled(count > 0)

    def closeEvent(self, event):  # keep running in tray
        event.ignore()
        self.hide()
