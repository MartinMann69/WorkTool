"""TSLibrary bookshelf mark and compact wordmark."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .typography import serif


def draw_library_mark(painter: QPainter, rect: QRectF, color: str) -> None:
    """Three book spines and a shelf, with the proportions of a shoji frame."""
    painter.save()
    painter.translate(rect.x(), rect.y())
    painter.scale(rect.width() / 32, rect.height() / 32)
    painter.setPen(QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(3, 6, 5, 18), .7, .7)
    painter.drawRoundedRect(QRectF(11, 6, 5, 18), .7, .7)
    painter.drawLine(QPointF(20, 7), QPointF(26, 23))
    painter.drawLine(QPointF(24, 5.5), QPointF(30, 21.5))
    painter.drawLine(QPointF(20, 7), QPointF(24, 5.5))
    painter.drawLine(QPointF(26, 23), QPointF(30, 21.5))
    painter.drawLine(QPointF(2, 28), QPointF(30, 28))
    painter.restore()


class BrandMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(216, 42)
        self.setAccessibleName("TSLibrary")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_library_mark(p, QRectF(0, 5, 31, 31), "#c9b18c")
        p.setFont(serif(24))
        p.setPen(QColor("#eee8db"))
        p.drawText(QPointF(44, 30), "TSLibrary")
