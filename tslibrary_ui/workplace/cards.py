"""Workplace cards with inline Open actions and personal-entry editing."""

from PySide6.QtCore import QPersistentModelIndex, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPen

from ..graphics.typography import sans
from ..library.cards import CatalogDelegate, CatalogGrid


class WorkplaceDelegate(CatalogDelegate):
    @staticmethod
    def open_rect(rect, entry):
        return QRectF(rect.left() + 20, rect.top() + 150,
                      max(0, rect.width() - 54 - (68 if entry.source == "personal" else 0)), 34)

    @staticmethod
    def edit_rect(rect, entry):
        return (QRectF(rect.right() - 91, rect.top() + 150, 58, 34)
                if entry.source == "personal" else QRectF())

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        p = painter
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        p.setFont(sans(8, .4))
        p.setPen(QColor("#aab99a"))
        source = "PERSONAL" if entry.source == "personal" else "FROM COLLECTION"
        p.drawText(QRectF(option.rect).adjusted(75, 55, -35, -145),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, source)

        rect = self.open_rect(option.rect, entry)
        p.setBrush(QColor("#c9b18c"))
        p.setPen(QPen(QColor("#c9b18c"), 1))
        p.drawRoundedRect(rect.adjusted(.5, .5, -.5, -.5), 5, 5)
        p.setFont(sans(11))
        p.setPen(QColor("#20251c"))
        p.drawText(rect.adjusted(13, 0, -30, 0), Qt.AlignmentFlag.AlignVCenter,
                   "Open website" if entry.kind == "websites" else "Open application")
        x, y = rect.right() - 15, rect.center().y()
        p.setPen(QPen(QColor("#20251c"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(x - 8, y), QPointF(x, y))
        p.drawLine(QPointF(x - 3, y - 3), QPointF(x, y))
        p.drawLine(QPointF(x - 3, y + 3), QPointF(x, y))

        if entry.source == "personal":
            edit = self.edit_rect(option.rect, entry)
            p.setBrush(QColor("#283222"))
            p.setPen(QPen(QColor("#65734f"), 1))
            p.drawRoundedRect(edit.adjusted(.5, .5, -.5, -.5), 5, 5)
            p.setPen(QColor("#d3d8c3"))
            p.drawText(edit, Qt.AlignmentFlag.AlignCenter, "Edit")
        p.restore()


class WorkplaceGrid(CatalogGrid):
    open_requested = Signal(object)
    edit_requested = Signal(object)
    row_height = 216

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(WorkplaceDelegate(self))
        self.setAccessibleDescription("Focus a card and press Space or Enter to open it. Press F2 to edit a personal entry.")
        self._pressed_index = QPersistentModelIndex()
        self._pressed_action = None

    def _action_at(self, point):
        index = self.indexAt(point)
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            rect = self.visualRect(index)
            if WorkplaceDelegate.open_rect(rect, entry).contains(point):
                return index, "open"
            if WorkplaceDelegate.edit_rect(rect, entry).contains(point):
                return index, "edit"
        return None, None

    def mousePressEvent(self, event):
        self._pressed_index = QPersistentModelIndex()
        self._pressed_action = None
        index, action = self._action_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and index is not None:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.setCurrentIndex(index)
            self._pressed_index = QPersistentModelIndex(index)
            self._pressed_action = action
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        pressed, action = self._pressed_index, self._pressed_action
        self._pressed_index = QPersistentModelIndex()
        self._pressed_action = None
        if pressed.isValid() and event.button() == Qt.MouseButton.LeftButton:
            index, released_action = self._action_at(event.position().toPoint())
            if index is not None and index == pressed and action == released_action:
                signal = self.open_requested if action == "open" else self.edit_requested
                signal.emit(index.data(Qt.ItemDataRole.UserRole))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._action_at(event.position().toPoint())[0] is not None:
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor
                                  if self._action_at(event.position().toPoint())[0] is not None
                                  else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        entry = self.currentIndex().data(Qt.ItemDataRole.UserRole)
        if entry and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_F2):
            if not event.isAutoRepeat():
                if event.key() == Qt.Key.Key_Space:
                    self.open_requested.emit(entry)
                elif entry.source == "personal":
                    self.edit_requested.emit(entry)
            event.accept()
            return
        super().keyPressEvent(event)
