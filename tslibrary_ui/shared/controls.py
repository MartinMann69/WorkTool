"""Shared controls for the dark TSLibrary interface."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QPushButton, QSpinBox, QStyle, QStyleOptionButton,
)


class TrashButton(QPushButton):
    def __init__(self, description, parent=None):
        super().__init__(parent)
        self.setObjectName("trashButton")
        self.setAutoDefault(False)
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(description)
        self.setToolTip(description)
        pixmap = QPixmap(40, 40)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#d7a088"), 1.25, Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(5, 5, 10, 12), 1, 1)
        p.drawLine(QPointF(3, 5), QPointF(17, 5))
        p.drawRoundedRect(QRectF(7, 2, 6, 3), 1, 1)
        p.drawLine(QPointF(8, 8), QPointF(8, 14))
        p.drawLine(QPointF(12, 8), QPointF(12, 14))
        p.end()
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(20, 20))


class FilterCombo(QComboBox):
    """Keep dropdown arrows legible on the dark palette on every platform."""

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#b7bba4"), 1.1, Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        x, y = self.width() - 18, self.height() / 2
        p.drawLine(QPointF(x - 3, y - 1.5), QPointF(x, y + 1.5))
        p.drawLine(QPointF(x, y + 1.5), QPointF(x + 3, y - 1.5))


class CountSpinBox(QSpinBox):
    """Visible plus/minus affordances for dark license-count controls."""

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = self.width() - 14
        for y, enabled, plus in [(self.height() * .25, self.value() < self.maximum(), True),
                                 (self.height() * .75, self.value() > self.minimum(), False)]:
            p.setPen(QPen(QColor("#c6ccb4" if enabled else "#59614d"), 1.1))
            p.drawLine(QPointF(x - 3, y), QPointF(x + 3, y))
            if plus:
                p.drawLine(QPointF(x, y - 3), QPointF(x, y + 3))


class CheckBox(QCheckBox):
    """Native checkbox behavior with a legible mark on the dark stylesheet."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            option = QStyleOptionButton()
            self.initStyleOption(option)
            rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor("#20251c"), 1.7, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(QPointF(rect.left() + 3, rect.top() + 8),
                       QPointF(rect.left() + 6, rect.top() + 11))
            p.drawLine(QPointF(rect.left() + 6, rect.top() + 11),
                       QPointF(rect.left() + 12, rect.top() + 4))
