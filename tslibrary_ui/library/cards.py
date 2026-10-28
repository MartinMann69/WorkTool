"""Responsive Qt item-view cards; the model owns entries, never card widgets."""

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QAbstractItemView, QListView, QStyle, QStyledItemDelegate

from ..graphics.icons import admin_icon
from ..graphics.typography import sans
from .models import KINDS


class CatalogDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fallback_icons = {kind: admin_icon("licenses" if kind == "licenses"
                              else kind.replace("_", " "), color)
                               for kind, (_, _, color) in KINDS.items()}

    def paint(self, painter, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        p = painter
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(0, 0, -14, -14)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        focused = bool(option.state & QStyle.StateFlag.State_HasFocus)
        p.setBrush(QColor("#293224" if selected else "#232b20" if hover else "#1d241c"))
        p.setPen(QPen(QColor("#bdab83" if selected or focused else "#596348" if hover else "#35402e"), 1))
        p.drawRoundedRect(rect.adjusted(.5, .5, -.5, -.5), 9, 9)
        x, y = rect.x() + 21, rect.y() + 22
        color = KINDS[entry.kind][2]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2c3526"))
        p.drawRoundedRect(QRectF(x, y, 42, 42), 9, 9)
        symbol = entry.icon if entry.icon is not None and not entry.icon.isNull() else self.fallback_icons[entry.kind]
        symbol.paint(p, int(x + 9), int(y + 9), 24, 24)
        p.setFont(sans(12, .3))
        p.setPen(QColor(color))
        p.drawText(QRectF(x + 54, y, rect.width() - 94, 42),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, entry.type_label.upper())
        p.setFont(sans(17))
        p.setPen(QColor("#e9e4d6"))
        title = p.fontMetrics().elidedText(entry.name, Qt.TextElideMode.ElideRight, int(rect.width() - 42))
        p.drawText(QRectF(x, y + 62, rect.width() - 42, 24), Qt.AlignmentFlag.AlignVCenter, title)
        p.setFont(sans(14))
        p.setPen(QColor("#c0cbb3"))
        detail = p.fontMetrics().elidedText(entry.detail, Qt.TextElideMode.ElideRight, int(rect.width() - 42))
        p.drawText(QRectF(x, y + 95, rect.width() - 42, 20), Qt.AlignmentFlag.AlignVCenter, detail)
        p.restore()

    def sizeHint(self, option, index):
        return QSize(max(1, self.parent().gridSize().width()), self.parent().row_height)


class CatalogGrid(QListView):
    row_height = 184

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("libraryGrid")
        self.setAccessibleName("Library resources")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setItemDelegate(CatalogDelegate(self))
        self.setSpacing(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_columns()
        QTimer.singleShot(0, self._fit_columns)

    def _fit_columns(self):
        # Reserve the native scrollbar extent while IconMode reflows. Qt can
        # otherwise wrap a full-width final column onto the next row.
        gutter = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent) + 2
        width = max(1, self.viewport().width() - gutter)
        columns = max(1, width // 275)
        size = QSize(max(1, width // columns), self.row_height)
        if self.gridSize() != size:
            self.setGridSize(size)
