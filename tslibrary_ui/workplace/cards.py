"""Workplace cards with inline Open actions and personal-entry editing."""

from PySide6.QtCore import QPersistentModelIndex, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPen

from ..graphics.typography import sans
from ..library.cards import CatalogDelegate, CatalogGrid


class WorkplaceDelegate(CatalogDelegate):
    @staticmethod
    def menu_rect(rect, entry):
        return QRectF(rect.right() - 49, rect.top() + 62, 24, 26)

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
        p.setFont(sans(10, .2))
        p.setPen(QColor("#aab99a"))
        source = ("PINNED · " if entry.favorite else "") + ("PERSONAL" if entry.source == "personal" else "FROM COLLECTION")
        p.drawText(QRectF(option.rect).adjusted(75, 55, -63, -135),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, source)
        draw_menu_dots(p, self.menu_rect(option.rect, entry))

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
    remove_requested = Signal(object)
    context_requested = Signal(object, object)
    row_height = 216

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(WorkplaceDelegate(self))
        self.setAccessibleDescription("Focus a card and press Space or Enter to open it. Press F2 to edit a personal entry.")
        self._pressed_index = QPersistentModelIndex()
        self._pressed_action = None
        self.dense = False

    def set_dense(self, dense):
        if self.dense == dense:
            return
        self.dense = dense
        self.row_height = 80 if dense else 216
        self.setItemDelegate(WorkplaceListDelegate(self) if dense else WorkplaceDelegate(self))
        self._fit_columns()
        self.doItemsLayout()

    def _fit_columns(self):
        if getattr(self, "dense", False):
            self.setGridSize(QSize(max(1, self.viewport().width() - 18), self.row_height))
        else:
            super()._fit_columns()

    def _action_at(self, point):
        index = self.indexAt(point)
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            rect = self.visualRect(index)
            delegate = self.itemDelegate()
            if delegate.menu_rect(rect, entry).contains(point):
                return index, "menu"
            if delegate.open_rect(rect, entry).contains(point):
                return index, "open"
            if delegate.edit_rect(rect, entry).contains(point):
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
                entry = index.data(Qt.ItemDataRole.UserRole)
                if action == "menu":
                    self.context_requested.emit(entry, self.viewport().mapToGlobal(event.position().toPoint()))
                else:
                    signal = self.open_requested if action == "open" else self.edit_requested
                    signal.emit(entry)
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
        if entry and event.key() == Qt.Key.Key_Delete:
            if entry.source == "personal" and not event.isAutoRepeat():
                self.remove_requested.emit(entry)
            event.accept()
            return
        if entry and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_F2):
            if not event.isAutoRepeat():
                if event.key() == Qt.Key.Key_Space:
                    self.open_requested.emit(entry)
                elif entry.source == "personal":
                    self.edit_requested.emit(entry)
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos()) if event.reason() == event.Reason.Mouse else self.currentIndex()
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry:
            self.setCurrentIndex(index)
            self.context_requested.emit(entry, event.globalPos())
            event.accept()


class WorkplaceListDelegate(CatalogDelegate):
    @staticmethod
    def open_rect(rect, entry):
        return QRectF(rect.right() - 140, rect.top() + 16, 92, 35)

    @staticmethod
    def edit_rect(rect, entry):
        return QRectF()

    @staticmethod
    def menu_rect(rect, entry):
        return QRectF(rect.right() - 40, rect.top() + 16, 26, 35)

    def paint(self, p, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(0, 0, -8, -8)
        p.setBrush(QColor("#273223" if option.state & self._selected_flag() else "#1d241c"))
        p.setPen(QPen(QColor("#46523b"), 1))
        p.drawRoundedRect(rect, 6, 6)
        symbol = entry.icon if entry.icon is not None and not entry.icon.isNull() else self.fallback_icons[entry.kind]
        symbol.paint(p, int(rect.left() + 15), int(rect.top() + 20), 26, 26)
        width = max(1, int(rect.width() - 220))
        p.setPen(QColor("#eee8dc"))
        p.setFont(sans(14))
        title = ("Pinned · " if entry.favorite else "") + entry.name
        p.drawText(QRectF(rect.left() + 55, rect.top() + 10, width, 24), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, width))
        p.setPen(QColor("#b2bca5" if entry.available else "#d4af81"))
        p.setFont(sans(12))
        p.drawText(QRectF(rect.left() + 55, rect.top() + 37, width, 23), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(entry.detail, Qt.TextElideMode.ElideRight, width))
        button = self.open_rect(option.rect, entry)
        p.setBrush(QColor("#c9b18c"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(button, 5, 5)
        p.setPen(QColor("#20251c"))
        p.drawText(button, Qt.AlignmentFlag.AlignCenter, "Open")
        p.setPen(QColor("#c9b18c"))
        draw_menu_dots(p, self.menu_rect(option.rect, entry))
        p.restore()

    @staticmethod
    def _selected_flag():
        from PySide6.QtWidgets import QStyle
        return QStyle.StateFlag.State_Selected


def draw_menu_dots(painter, rect):
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#d3c29f"))
    for offset in (-5, 0, 5):
        painter.drawEllipse(rect.center() + QPointF(offset, 0), 1.3, 1.3)
