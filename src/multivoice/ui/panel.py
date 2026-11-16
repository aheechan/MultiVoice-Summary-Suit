"""Main control panel: works even when the tray icon is hidden."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import glossary
from ..config import PROJECT_ROOT

ASSETS = PROJECT_ROOT / "assets"

STYLE = """
QWidget { background: #04060d; color: #dceeff; font-family: 'Segoe UI', sans-serif; }
QFrame#card { background: #070b16; border: 1px solid #16243f; border-radius: 14px; }
QLabel#title { font-size: 18px; font-weight: 600; color: #eaf7ff; }
QLabel#subtitle { color: #7f93ad; font-size: 12px; }
QLabel#status { color: #9fd8ff; font-size: 12px; }
QPushButton {
    background: #10203c; color: #dceeff; border: 1px solid #1f3b6b;
    border-radius: 8px; padding: 9px 14px; text-align: left;
}
QPushButton:hover { background: #16305a; border-color: #3d7bff; }
QPushButton:disabled { color: #4a5a70; border-color: #16243f; background: #080d18; }
QPushButton#primary { background: #1d4ed8; border-color: #3d7bff; font-weight: 600; }
QPushButton#primary:hover { background: #2563eb; }
"""


class Panel(QWidget):
    def __init__(self, tray):
        super().__init__()
        self.tray = tray
        self.setWindowTitle("MultiVoice Summary Suit")
        self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("MultiVoice Summary Suit")
        title.setObjectName("title")
        subtitle = QLabel("Speech → transcript → spoken script, report and brief")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.status = QLabel("Idle")
        self.status.setObjectName("status")
        layout.addWidget(self.status)

        root.addWidget(card)

        self.btn_transcribe = QPushButton("Transcribe file…")
        self.btn_transcribe.setObjectName("primary")
        self.btn_transcribe.clicked.connect(self.tray.pick_file)

        self.btn_generate = QPushButton("Generate outputs (a / b / c)")
        self.btn_generate.clicked.connect(self.tray.generate_outputs)

        self.btn_review = QPushButton("Review pending terms (0)")
        self.btn_review.clicked.connect(self.tray.open_review)

        self.btn_outputs = QPushButton("Open output folder")
        self.btn_outputs.clicked.connect(lambda: self.tray._open(self.tray.cfg.output))

        self.btn_settings = QPushButton("Settings…")
        self.btn_settings.clicked.connect(self.tray.show_settings)

        self.btn_about = QPushButton("About")
        self.btn_about.clicked.connect(self.tray.show_about)

        self.btn_quit = QPushButton("Quit")
        self.btn_quit.clicked.connect(self.tray.quit)

        for button in (self.btn_transcribe, self.btn_generate, self.btn_review,
                       self.btn_outputs, self.btn_settings, self.btn_about, self.btn_quit):
            layout_widget = QHBoxLayout()
            layout_widget.addWidget(button)
            root.addLayout(layout_widget)

        root.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        text = getattr(self.tray, "panel_status", "Idle")
        self.status.setText(text)
        self.btn_generate.setEnabled(self.tray.transcript_ready)
        try:
            count = len(glossary.load().pending)
        except Exception:
            count = 0
        self.btn_review.setText(f"Review pending terms ({count})")
        self.btn_review.setEnabled(count > 0)

    def closeEvent(self, event):  # keep running in tray
        event.ignore()
        self.hide()
