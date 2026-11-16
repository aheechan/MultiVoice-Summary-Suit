"""Render icon SVGs to PNG sizes for the tray and installers."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def render(svg: Path, size: int, target: Path) -> None:
    renderer = QSvgRenderer(str(svg))
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    image.save(str(target))


def main() -> int:
    detailed = ASSETS / "icon.svg"
    compact = ASSETS / "icon-small.svg"
    tiny = ASSETS / "icon-16.svg"

    render(detailed, 256, ASSETS / "icon.png")
    render(detailed, 128, ASSETS / "icon-128.png")
    render(detailed, 64, ASSETS / "icon-64.png")

    # Small sizes use simplified artwork so the center ring survives.
    render(tiny, 16, ASSETS / "icon-16.png")
    for size in (24, 32, 48):
        render(compact, size, ASSETS / f"icon-{size}.png")

    print("rendered icons in", ASSETS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
