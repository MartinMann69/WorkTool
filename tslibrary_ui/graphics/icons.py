"""Qt-native welcome and admin icons; file and website icons live in their features."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from .brand import draw_library_mark


def icon(name: str, color: str = "#9b9c89", size: int = 20) -> QIcon:
    """Small, crisp Qt-native icons that follow the display's pixel density."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 20, size / 20)
    p.setPen(QPen(QColor(color), 1.25, Qt.PenStyle.SolidLine,
                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if name == "user":
        p.drawEllipse(QPointF(10, 6), 3, 3)
        path = QPainterPath(QPointF(4, 17))
        path.lineTo(4, 15)
        path.cubicTo(4, 10, 16, 10, 16, 15)
        path.lineTo(16, 17)
        p.drawPath(path)
    elif name == "lock":
        p.drawRoundedRect(QRectF(4, 8.5, 12, 9), 2, 2)
        path = QPainterPath(QPointF(6.5, 8.5))
        path.lineTo(6.5, 6)
        path.cubicTo(6.5, 1.5, 13.5, 1.5, 13.5, 6)
        path.lineTo(13.5, 8.5)
        p.drawPath(path)
        p.drawLine(QPointF(10, 12), QPointF(10, 14))
    elif name in ("eye", "eye-off"):
        path = QPainterPath(QPointF(2, 10))
        path.cubicTo(6, 3, 14, 3, 18, 10)
        path.cubicTo(14, 17, 6, 17, 2, 10)
        p.drawPath(path)
        p.drawEllipse(QPointF(10, 10), 2.4, 2.4)
        if name == "eye-off":
            p.drawLine(QPointF(3, 3), QPointF(17, 17))
    elif name == "arrow":
        p.drawLine(QPointF(3, 10), QPointF(17, 10))
        p.drawLine(QPointF(12, 5), QPointF(17, 10))
        p.drawLine(QPointF(12, 15), QPointF(17, 10))
    elif name == "leaf":
        path = QPainterPath(QPointF(4, 16))
        path.cubicTo(0, 5, 12, 3, 17, 3)
        path.cubicTo(17, 13, 13, 18, 6, 15)
        path.moveTo(3, 18)
        path.quadTo(8, 10, 13, 7)
        p.drawPath(path)
    p.end()
    return QIcon(pixmap)


def admin_icon(kind, color="#a6ae96"):
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 1.2, Qt.PenStyle.SolidLine,
                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind in ("library", "items"):
        draw_library_mark(p, QRectF(1, 1, 18, 18), color)
    elif kind == "licenses":
        p.drawEllipse(QPointF(6, 7), 3.5, 3.5)
        p.drawLine(QPointF(8.5, 9.5), QPointF(16, 17))
        p.drawLine(QPointF(12, 13), QPointF(14.5, 10.5))
        p.drawLine(QPointF(14, 15), QPointF(16.5, 12.5))
    elif kind == "applications":
        p.drawRoundedRect(QRectF(2.5, 3, 15, 14), 1.5, 1.5)
        p.drawLine(QPointF(2.5, 7), QPointF(17.5, 7))
        for x in (5, 7.5, 10):
            p.drawPoint(QPointF(x, 5))
    elif kind == "websites":
        p.drawEllipse(QPointF(10, 10), 7, 7)
        p.drawEllipse(QRectF(6.5, 3, 7, 14))
        p.drawLine(QPointF(3, 10), QPointF(17, 10))
    elif kind == "search":
        p.drawEllipse(QPointF(8.5, 8.5), 5, 5)
        p.drawLine(QPointF(12.5, 12.5), QPointF(17, 17))
    elif kind == "plus":
        p.drawLine(QPointF(10, 4), QPointF(10, 16))
        p.drawLine(QPointF(4, 10), QPointF(16, 10))
    elif kind == "back":
        p.drawLine(QPointF(4, 10), QPointF(17, 10))
        p.drawLine(QPointF(4, 10), QPointF(9, 5))
        p.drawLine(QPointF(4, 10), QPointF(9, 15))
    p.end()
    return QIcon(pixmap)
