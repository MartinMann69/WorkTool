"""Small shoji-inspired artwork for the sidebar and empty states."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from .brand import draw_library_mark


class ShelfArtwork(QWidget):
    """A small shoji-inspired shelf motif, drawn without image assets."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(170, 130)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = QRadialGradient(QPointF(89, 67), 70)
        glow.setColorAt(0, QColor(173, 143, 88, 30))
        glow.setColorAt(1, QColor(173, 143, 88, 0))
        p.fillRect(self.rect(), glow)
        p.setPen(QPen(QColor("#3a4433"), 1))
        p.drawRoundedRect(QRectF(29, 15, 112, 99), 3, 3)
        for x in (57, 85, 113):
            p.drawLine(QPointF(x, 15), QPointF(x, 114))
        for y in (48, 81):
            p.drawLine(QPointF(29, y), QPointF(141, y))
        p.setBrush(QColor("#20271e"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(46, 39, 78, 56), 7, 7)
        draw_library_mark(p, QRectF(62, 43, 45, 45), "#bcaa85")
