"""Render the project's own bookshelf mark into a multi-resolution Windows icon."""

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from tslibrary_ui.app import create_app
from tslibrary_ui.graphics.brand import draw_library_mark

app = create_app()
image = QImage(256, 256, QImage.Format.Format_ARGB32)
image.fill(QColor("#181b18"))
painter = QPainter(image)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
draw_library_mark(painter, QRectF(36, 36, 184, 184), "#c9b18c")
painter.end()
if not image.save(str(ROOT / "packaging" / "TSLibrary.ico")):
    raise RuntimeError("Windows icon could not be saved")
