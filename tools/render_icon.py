"""Render the single icon SVG to every size used by the tray and installers."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SVG = ASSETS / "icon.svg"
SIZES = (16, 24, 32, 48, 64, 128, 256)


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
    for size in SIZES:
        name = "icon.png" if size == 256 else f"icon-{size}.png"
        render(size, ASSETS / name)
    print("rendered:", ", ".join(f"{s}px" for s in SIZES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
