"""Original, resolution-independent shoji and lantern artwork drawn with Qt."""

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget


def serif(size: int, italic: bool = False) -> QFont:
    font = QFont("Georgia")
    font.setPixelSize(size)
    font.setItalic(italic)
    return font


def sans(size: int, spacing: float = 0) -> QFont:
    font = QFont("Segoe UI")
    font.setPixelSize(size)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


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


class ShojiPanel(QWidget):
    """An abstract architectural composition, with no image files or downloads."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAccessibleName("Original shoji lattice artwork with warm lantern light and bamboo")
        rng = random.Random(18)
        self.grain = [(rng.uniform(0, 580), rng.uniform(140, 580),
                       rng.uniform(.3, .75)) for _ in range(2600)]

    def paintEvent(self, event):
        p = QPainter(self)
        # Paint the background in widget coordinates, so fitting the artwork
        # never exposes a second background around the design canvas.
        background = QLinearGradient(0, 0, self.width(), self.height())
        background.setColorAt(0, QColor("#192019"))
        background.setColorAt(.6, QColor("#111812"))
        background.setColorAt(1, QColor("#171d17"))
        # Extend opaque fills through the final device pixel at fractional DPI.
        # Antialiasing a widget's outer edge can leave a dark half-pixel seam.
        bounds = self.rect().adjusted(0, 0, 1, 1)
        p.fillRect(bounds, background)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Fit the entire composition so branding remains visible at every size.
        scale = min(self.width() / 580, self.height() / 820)
        p.save()
        p.translate((self.width() - 580 * scale) / 2,
                    (self.height() - 820 * scale) / 2)
        p.scale(scale, scale)
        self._scene(p)
        p.restore()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Blend at the actual panel edge, including any extra space created by
        # wide or tall windows, rather than at the scaled illustration's edge.
        edge = QLinearGradient(max(0, self.width() - 80), 0, self.width(), 0)
        edge.setColorAt(0, QColor(24, 27, 24, 0))
        edge.setColorAt(1, QColor("#181b18"))
        p.fillRect(bounds, edge)

    def _scene(self, p):
        # An architectural detail, rather than a literal furnished room.
        halo = QRadialGradient(QPointF(290, 370), 285)
        halo.setColorAt(0, QColor(146, 108, 58, 35))
        halo.setColorAt(1, QColor(146, 108, 58, 0))
        p.fillRect(QRectF(5, 85, 570, 570), halo)
        p.fillRect(QRectF(47, 165, 451, 371), QColor("#302e21"))
        paper = QLinearGradient(60, 190, 478, 510)
        paper.setColorAt(0, QColor("#4a4a35"))
        paper.setColorAt(.48, QColor("#727052"))
        paper.setColorAt(.78, QColor("#9c855a"))
        paper.setColorAt(1, QColor("#685b3c"))
        p.fillRect(QRectF(59, 177, 427, 347), paper)
        glow = QRadialGradient(QPointF(387, 450), 280)
        glow.setColorAt(0, QColor(247, 193, 111, 80))
        glow.setColorAt(1, QColor(247, 193, 111, 0))
        p.fillRect(QRectF(59, 177, 427, 347), glow)

        # Washi-like grain and a restrained dark timber lattice.
        p.save()
        p.setClipRect(QRectF(59, 177, 427, 347))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(237, 218, 166, 30))
        for x, y, r in self.grain:
            p.drawEllipse(QPointF(x, y), r, r)
        for x in (59, 166, 273, 380, 486):
            p.fillRect(QRectF(x - 4, 175, 8, 352), QColor("#292c20"))
            p.fillRect(QRectF(x - 3, 175, 1, 352), QColor(171, 147, 96, 45))
        for y in (177, 246, 315, 384, 453, 524):
            p.fillRect(QRectF(59, y - 2, 427, 4), QColor("#2c2e22"))
            p.fillRect(QRectF(59, y - 2, 427, .7), QColor(194, 164, 106, 35))
        p.restore()

        # A narrow offset screen creates depth without visual clutter.
        p.fillRect(QRectF(28, 144, 16, 414), QColor("#0d140f"))
        p.fillRect(QRectF(30, 144, 1, 414), QColor("#464735"))
        p.fillRect(QRectF(44, 142, 474, 16), QColor("#25291e"))
        p.fillRect(QRectF(47, 146, 470, 1), QColor("#4d4832"))
        p.fillRect(QRectF(47, 536, 470, 13), QColor("#262a1e"))
        p.fillRect(QRectF(47, 538, 470, 1), QColor("#65573a"))

        # Thin timber grain, drawn sparsely so it stays quiet at normal size.
        p.setPen(QPen(QColor(171, 140, 84, 20), .6))
        for row in range(4):
            path = QPainterPath(QPointF(52, 541 + row * 1.7))
            for x in range(52, 510, 5):
                path.lineTo(x, 541 + row * 1.7 + math.sin(x / 40) * .5)
            p.drawPath(path)

        self._bamboo(p)
        self._lantern(p)

        draw_library_mark(p, QRectF(47, 43, 35, 35), "#c9b18c")
        p.setFont(serif(28))
        p.setPen(QColor("#eee8dc"))
        p.drawText(QPointF(98, 72), "TSLibrary")
        p.setFont(sans(8, 2.3))
        p.setPen(QColor("#9ca18b"))
        p.drawText(QPointF(49, 102), "A SPACE OF YOUR OWN")

        p.setFont(sans(9, 2.2))
        p.setPen(QColor("#c2ac86"))
        p.drawText(QPointF(49, 600), "間  /  MAKE A LITTLE ROOM")
        p.setFont(serif(42))
        p.setPen(QColor("#eee8dc"))
        p.drawText(QPointF(47, 652), "Everything,")
        p.setFont(serif(42, True))
        p.drawText(QPointF(47, 703), "in its place.")
        p.setFont(sans(12))
        p.setPen(QColor("#a7ad98"))
        p.drawText(QPointF(49, 736), "A little order. A little room to breathe.")
        p.setPen(QPen(QColor(214, 201, 175, 35), 1))
        p.drawLine(QPointF(47, 772), QPointF(532, 772))
        p.setFont(sans(8, 1.9))
        p.setPen(QColor("#929a81"))
        p.drawText(QPointF(49, 792), "TSLIBRARY  /  QUIETLY ORGANISED")
        p.setFont(QFont("Yu Mincho", 10))
        p.drawText(QPointF(514, 792), "静")

    @staticmethod
    def _bamboo(p):
        p.save()
        p.setPen(QPen(QColor("#252f1e"), 2.5))
        stem = QPainterPath(QPointF(512, 542))
        stem.cubicTo(480, 435, 509, 330, 465, 212)
        p.drawPath(stem)
        branches = [(492, 440, 439, 399), (489, 407, 532, 361),
                    (488, 357, 440, 318), (484, 326, 522, 290),
                    (476, 283, 438, 252)]
        for x, y, ex, ey in branches:
            p.setPen(QPen(QColor("#2b3521"), 1.2))
            p.drawLine(QPointF(x, y), QPointF(ex, ey))
            for t, direction in [(.42, -1), (.64, 1), (.86, -1)]:
                lx, ly = x + (ex - x) * t, y + (ey - y) * t
                p.save()
                p.translate(lx, ly)
                p.rotate(-35 if ex < x else 35)
                leaf = QPainterPath(QPointF(0, 0))
                leaf.cubicTo(-7, -10 * direction, -7, -25 * direction, 0, -37 * direction)
                leaf.cubicTo(4, -20 * direction, 4, -9 * direction, 0, 0)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#293621"))
                p.drawPath(leaf)
                p.restore()
        p.restore()

    @staticmethod
    def _lantern(p):
        p.save()
        p.translate(385, 425)
        p.setPen(QPen(QColor("#373b29"), 1.2))
        p.drawLine(QPointF(0, -248), QPointF(0, -23))
        halo = QRadialGradient(QPointF(0, 30), 115)
        halo.setColorAt(0, QColor(236, 175, 88, 70))
        halo.setColorAt(.5, QColor(236, 175, 88, 20))
        halo.setColorAt(1, QColor(236, 175, 88, 0))
        p.fillRect(QRectF(-115, -85, 230, 230), halo)
        silhouette = QPainterPath()
        silhouette.addRoundedRect(QRectF(-31, -20, 62, 95), 27, 27)
        paper = QLinearGradient(-31, 0, 31, 0)
        paper.setColorAt(0, QColor("#ad946b"))
        paper.setColorAt(.5, QColor("#edcf91"))
        paper.setColorAt(1, QColor("#aa8a59"))
        p.setBrush(paper)
        p.setPen(QPen(QColor("#a58b62"), .7))
        p.drawPath(silhouette)
        p.save()
        p.setClipPath(silhouette)
        p.setPen(QPen(QColor(84, 68, 41, 100), .8))
        for y in range(-16, 77, 7):
            rib = QPainterPath(QPointF(-34, y))
            rib.quadTo(0, y + 7, 34, y)
            p.drawPath(rib)
        p.setPen(QPen(QColor(91, 72, 38, 70), .6))
        p.drawLine(QPointF(-12, -21), QPointF(-12, 77))
        p.drawLine(QPointF(12, -21), QPointF(12, 77))
        p.restore()
        p.setBrush(QColor("#292a1d"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(-17, -23, 34, 8))
        p.drawRoundedRect(QRectF(-23, 75, 46, 7), 3, 3)
        p.restore()
