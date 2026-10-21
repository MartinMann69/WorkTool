"""Local website icon; makes no network requests."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def website_icon() -> QIcon:
    """A local globe icon; configuring a link makes no network requests."""
    pixmap = QPixmap(80, 80)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#c9b18c"), 1.4))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(20, 20), 14, 14)
    painter.drawEllipse(QRectF(13, 6, 14, 28))
    painter.drawLine(QPointF(6, 20), QPointF(34, 20))
    painter.drawLine(QPointF(8, 13), QPointF(32, 13))
    painter.drawLine(QPointF(8, 27), QPointF(32, 27))
    painter.end()
    return QIcon(pixmap)
