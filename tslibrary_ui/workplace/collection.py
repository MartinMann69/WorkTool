"""Collection cards with an inline, keyboard-accessible workplace toggle."""

from PySide6.QtCore import QPersistentModelIndex, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QPen

from ..graphics.typography import sans
from ..library.cards import CatalogDelegate, CatalogGrid
from ..library.models import CatalogModel


class CollectionModel(CatalogModel):
    toggle_requested = Signal(object)

    def flags(self, index):
        flags = super().flags(index)
        return flags | Qt.ItemFlag.ItemIsUserCheckable if index.isValid() else flags

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        entry = super().data(index, Qt.ItemDataRole.UserRole)
        if entry is not None:
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if entry.added else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.AccessibleDescriptionRole:
                return (f"{entry.name}. {entry.type_label}. {entry.detail}. "
                        f"{'In your workplace. Press Space to remove.' if entry.added else 'Press Space to add to your workplace.'}")
        return super().data(index, role)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        entry = self.data(index, Qt.ItemDataRole.UserRole)
        if entry is None or role != Qt.ItemDataRole.CheckStateRole:
            return False
        checked = value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
        if checked != entry.added:
            self.toggle_requested.emit(entry)
        return True


class CollectionDelegate(CatalogDelegate):
    def editorEvent(self, event, model, option, index):
        # The view handles the visible button; don't expose an invisible native
        # checkbox hit area elsewhere in the custom-painted card.
        return False

    @staticmethod
    def action_rect(rect):
        return QRectF(rect.left() + 20, rect.top() + 150, max(0, rect.width() - 54), 34)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        p = painter
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        rect = self.action_rect(option.rect)
        p.setBrush(QColor("#35452c" if entry.added else "#2b3324"))
        p.setPen(QPen(QColor("#7d9068" if entry.added else "#8a7e60"), 1))
        p.drawRoundedRect(rect.adjusted(.5, .5, -.5, -.5), 5, 5)
        color = QColor("#d3dfc4" if entry.added else "#d5bf98")
        p.setPen(QPen(color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        x, y = rect.left() + 16, rect.center().y()
        p.drawLine(QPointF(x - 4, y), QPointF(x + 4, y))
        if not entry.added:
            p.drawLine(QPointF(x, y - 4), QPointF(x, y + 4))
        p.setFont(sans(11))
        p.setPen(color)
        text = "Remove from workplace" if entry.added else "Add to workplace"
        text = p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width() - 43))
        p.drawText(rect.adjusted(32, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter, text)
        if entry.added:
            # A check in the card corner distinguishes saved selections from focus.
            check = QPainterPath()
            corner_x, corner_y = option.rect.right() - 32, option.rect.top() + 12
            check.moveTo(corner_x - 6, corner_y)
            check.lineTo(corner_x - 3, corner_y + 3)
            check.lineTo(corner_x + 3, corner_y - 3)
            p.setPen(QPen(QColor("#b7cea1"), 1.6))
            p.drawPath(check)
        p.restore()


class CollectionGrid(CatalogGrid):
    row_height = 216

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(CollectionDelegate(self))
        self._pressed_index = QPersistentModelIndex()

    def _action_index(self, point):
        index = self.indexAt(point)
        if index.isValid() and CollectionDelegate.action_rect(self.visualRect(index)).contains(point):
            return index
        return None

    def mousePressEvent(self, event):
        self._pressed_index = QPersistentModelIndex()
        index = self._action_index(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and index is not None:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.setCurrentIndex(index)
            self._pressed_index = QPersistentModelIndex(index)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        pressed = self._pressed_index
        self._pressed_index = QPersistentModelIndex()
        if pressed.isValid() and event.button() == Qt.MouseButton.LeftButton:
            index = self._action_index(event.position().toPoint())
            if index is not None and index == pressed:
                self._toggle(index)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._action_index(event.position().toPoint()) is not None:
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor
                                  if self._action_index(event.position().toPoint()) is not None
                                  else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and self.currentIndex().isValid():
            if not event.isAutoRepeat():
                self._toggle(self.currentIndex())
            event.accept()
            return
        super().keyPressEvent(event)

    def _toggle(self, index):
        current = index.data(Qt.ItemDataRole.CheckStateRole)
        self.model().setData(index, Qt.CheckState.Unchecked if current == Qt.CheckState.Checked
                             else Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
