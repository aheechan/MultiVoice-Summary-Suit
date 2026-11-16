"""Render assets/icon.svg to PNG and ICO for the tray and installers."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "icon.svg"


def render(size: int, target: Path) -> None:
    renderer = QSvgRenderer(str(SVG))
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    image.save(str(target))


def main() -> int:
    assets = ROOT / "assets"
    render(256, assets / "icon.png")
    render(64, assets / "icon-64.png")
    render(32, assets / "icon-32.png")
    render(16, assets / "icon-16.png")
    print("wrote", assets / "icon.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
