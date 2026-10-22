"""Live overview of selected Collection entries, independent of search filters."""

from PySide6.QtCore import QPersistentModelIndex, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QListView, QStyle,
    QStyledItemDelegate, QToolTip, QVBoxLayout,
)

from ..graphics.icons import admin_icon
from ..graphics.typography import sans
from ..library.models import CatalogModel
from ..shared.forms import caption


class SelectionDelegate(QStyledItemDelegate):
    @staticmethod
    def remove_rect(rect):
        return QRectF(rect.right() - 30, rect.top() + 15, 28, 28)

    def helpEvent(self, event, view, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry and self.remove_rect(option.rect).contains(event.pos()):
            QToolTip.showText(event.globalPos(), f"Remove {entry.name} from your workplace", view)
            return True
        return super().helpEvent(event, view, option, index)

    def paint(self, painter, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        p = painter
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_HasFocus:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#6b7d55"), 1))
            p.drawRoundedRect(QRectF(option.rect).adjusted(.5, .5, -.5, -.5), 5, 5)
        symbol = entry.icon if entry.icon is not None and not entry.icon.isNull() else admin_icon(entry.kind)
        symbol.paint(p, option.rect.left() + 1, option.rect.top() + 15, 22, 22)
        text = QRectF(option.rect).adjusted(34, 6, -38, -2)
        p.setFont(sans(12))
        p.setPen(QColor("#e1e2d0"))
        title = p.fontMetrics().elidedText(entry.name, Qt.TextElideMode.ElideRight, int(text.width()))
        p.drawText(QRectF(text.left(), text.top(), text.width(), 22), Qt.AlignmentFlag.AlignVCenter, title)
        p.setFont(sans(9))
        p.setPen(QColor("#a4b390"))
        p.drawText(text.adjusted(0, 24, 0, 0), Qt.AlignmentFlag.AlignTop, entry.type_label)
        button = self.remove_rect(option.rect)
        p.setPen(QPen(QColor("#4b5a3b"), 1))
        p.setBrush(QColor("#303d26" if option.state & QStyle.StateFlag.State_MouseOver else "#26301f"))
        p.drawRoundedRect(button.adjusted(.5, .5, -.5, -.5), 5, 5)
        p.setPen(QPen(QColor("#cfb88f"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        center = button.center()
        p.drawLine(center + QPointF(-3.5, -3.5), center + QPointF(3.5, 3.5))
        p.drawLine(center + QPointF(-3.5, 3.5), center + QPointF(3.5, -3.5))
        p.restore()

    def sizeHint(self, option, index):
        return QSize(100, 58)


class SelectionList(QListView):
    remove_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed_index = QPersistentModelIndex()
        self.setMouseTracking(True)
        self.setAccessibleDescription("Selected Collection entries. Focus an entry and press Delete to remove it from your workplace.")

    def _remove_index(self, point):
        index = self.indexAt(point)
        if index.isValid() and SelectionDelegate.remove_rect(self.visualRect(index)).contains(point):
            return index
        return None

    def mousePressEvent(self, event):
        self._pressed_index = QPersistentModelIndex()
        index = self._remove_index(event.position().toPoint())
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
            index = self._remove_index(event.position().toPoint())
            if index is not None and index == pressed:
                self.remove_requested.emit(index.data(Qt.ItemDataRole.UserRole))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor
                                  if self._remove_index(event.position().toPoint()) is not None
                                  else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self.currentIndex().isValid():
            if not event.isAutoRepeat():
                self.remove_requested.emit(self.currentIndex().data(Qt.ItemDataRole.UserRole))
            event.accept()
            return
        super().keyPressEvent(event)


class SelectionSidebar(QFrame):
    remove_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("selectionSidebar")
        self.setFixedWidth(260)
        root = QVBoxLayout(self)
        root.setContentsMargins(19, 21, 17, 17)
        root.setSpacing(10)
        root.addWidget(caption("YOUR WORKPLACE PICKS", "workplaceEyebrow", wrap=False))
        heading = QHBoxLayout()
        heading.addWidget(caption("Selected", "selectionHeading", wrap=False), 1)
        self.count_label = caption("0", "selectionCount", wrap=False)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_label.setMinimumSize(27, 27)
        heading.addWidget(self.count_label)
        root.addLayout(heading)
        self.summary_label = caption("", "workplaceMuted")
        root.addWidget(self.summary_label)
        self.model = CatalogModel(self)
        self.list = SelectionList()
        self.list.remove_requested.connect(self.remove_requested.emit)
        self.list.setObjectName("selectionList")
        self.list.setAccessibleName("Selected Collection entries in your workplace")
        self.list.setModel(self.model)
        self.list.setItemDelegate(SelectionDelegate(self.list))
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setUniformItemSizes(True)
        root.addWidget(self.list, 1)
        self.empty_label = caption("Nothing selected yet.\nAdd entries using the buttons in the cards.",
                                   "workplaceDescription")
        root.addWidget(self.empty_label, 1)
        root.addWidget(caption("Collection items in your workplace.", "workplaceMuted"))

    def refresh(self, entries):
        scroll = self.list.verticalScrollBar().value()
        current_index = self.list.currentIndex()
        current = current_index.data(Qt.ItemDataRole.UserRole)
        current_row = current_index.row()
        selected = sorted((entry for entry in entries if entry.added),
                          key=lambda entry: (entry.kind, entry.name.casefold()))
        self.model.replace(selected)
        if current is not None and selected:
            row = next((row for row, entry in enumerate(selected)
                        if (entry.id, entry.kind) == (current.id, current.kind)),
                       min(current_row, len(selected) - 1))
            self.list.setCurrentIndex(self.model.index(row, 0))
        self.count_label.setText(str(len(selected)))
        apps = sum(entry.kind == "applications" for entry in selected)
        sites = len(selected) - apps
        self.summary_label.setText(f"{apps} {'application' if apps == 1 else 'applications'} · "
                                   f"{sites} {'website' if sites == 1 else 'websites'}")
        self.list.setVisible(bool(selected))
        self.empty_label.setVisible(not selected)
        self.list.doItemsLayout()
        self.list.verticalScrollBar().setValue(scroll)
