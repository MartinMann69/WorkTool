"""Folder navigator and readable document-name cells for large inventories."""

from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt, QSignalBlocker
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QLabel, QSizePolicy, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTreeWidget, QTreeWidgetItem

from ..graphics.icons import admin_icon
from ..graphics.typography import sans


PARENT_ROLE = Qt.ItemDataRole.UserRole + 1
FOLDER_ROLE = Qt.ItemDataRole.UserRole + 2
FILE_ROLE = Qt.ItemDataRole.UserRole + 3


class DocumentationStatus(QLabel):
    """Single-line footer status; long messages remain available as a tooltip."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("adminMuted")
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        text = self.fontMetrics().elidedText(self.text().replace("\n", " "), Qt.TextElideMode.ElideRight, self.contentsRect().width())
        painter.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


@dataclass(frozen=True)
class BrowserRow:
    path: str
    entry: object
    folder: bool
    descendants: int = 0
    file: bool = False
    size: int = 0
    modified: float = 0


def browse_rows(entries, folder="", query="", alphabetical=False, disk_entries=()):
    """A directory listing normally; explicit recursive results when searching.

    Registered files/folders and actual directory contents merge into the same
    list without duplicating paths or treating linked files as folders.
    """
    parents = {}
    records = {entry.name.casefold(): entry for entry in entries}
    for entry in entries:
        parts = entry.name.split("/")
        for depth in range(1, len(parts) + (entry.kind == "folder")):
            path = "/".join(parts[:depth])
            parents.setdefault(path.casefold(), path)
    def row(path, entry=None):
        key = path.casefold()
        is_folder = key in parents
        count = sum(item.name.casefold().startswith(key + "/") for item in entries) if is_folder else 0
        return BrowserRow(path, entry, is_folder, count)
    scope = folder.casefold()
    result = {key: row(path, records.get(key)) for key, path in parents.items()}
    for entry in entries:
        if entry.kind == "file":
            result[entry.name.casefold()] = BrowserRow(entry.name, entry, False, file=True)
    for disk in disk_entries:
        key = disk["path"].casefold()
        if key not in result or (key in records and records[key].kind == "file"):
            result[key] = BrowserRow(disk["path"], records.get(key), disk["folder"], file=not disk["folder"],
                                     size=disk["size"], modified=disk["modified"])
    result = [item for item in result.values() if (not scope or item.path.casefold().startswith(scope + "/"))
              and (query in item.path.casefold() if query else item.path.rpartition("/")[0].casefold() == scope)]
    return sorted(result, key=lambda item: (not item.folder,
                  item.path.casefold() if item.folder or alphabetical else -item.modified))


class DocumentationFolders(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("documentationFolders")
        self.setAccessibleName("Documentation folders")
        self.setHeaderHidden(True)
        self.setIndentation(15)
        self.setUniformRowHeights(True)
        self.setMinimumWidth(120)
        self.setMaximumWidth(230)
        self._paths = None

    def rebuild(self, entries, selected, extra_paths=()):
        canonical = {}
        for name in [item.name if item.kind == "folder" else item.name.rpartition("/")[0] for item in entries] + list(extra_paths):
            for index in range(1, len(name.split("/")) + 1):
                path = "/".join(name.split("/")[:index])
                if not path:
                    continue
                canonical.setdefault(path.casefold(), path)
        paths = set(canonical.values())
        if paths == self._paths:
            return selected
        expanded = {item.data(0, Qt.ItemDataRole.UserRole) for item in self.items_by_path.values() if item.isExpanded()} if self._paths is not None else {""}
        self._paths = paths
        with QSignalBlocker(self):
            self.clear()
            root = QTreeWidgetItem(self, ["Home"])
            root.setData(0, Qt.ItemDataRole.UserRole, "")
            root.setIcon(0, admin_icon("folder", "#c9b18c"))
            root.setToolTip(0, "Browse top-level documentation folders")
            self.items_by_path = {"": root}
            for path in sorted(paths, key=lambda text: (text.count("/"), text.casefold())):
                parent, _, leaf = path.rpartition("/")
                parent = canonical.get(parent.casefold(), "")
                item = QTreeWidgetItem(self.items_by_path[parent], [leaf])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                item.setIcon(0, admin_icon("folder", "#c9b18c"))
                item.setToolTip(0, path.replace("/", " / "))
                self.items_by_path[path] = item
            for path in expanded:
                if path in self.items_by_path:
                    self.items_by_path[path].setExpanded(True)
            if selected not in self.items_by_path:
                selected = canonical.get(selected.casefold(), "")
            self.setCurrentItem(self.items_by_path[selected])
        return selected

    def select_path(self, path):
        match = next((key for key in self.items_by_path if key.casefold() == path.casefold()), "")
        item = self.items_by_path[match]
        ancestor = item.parent()
        while ancestor is not None:
            ancestor.setExpanded(True)
            ancestor = ancestor.parent()
        self.setCurrentItem(item)
        self.scrollToItem(item)


class DocumentationNameDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.text = ""
        style = styled.widget.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, styled, styled.widget).adjusted(2, 0, -8, 0)
        parent = index.data(PARENT_ROLE) or "Documentation"
        painter.save()
        painter.setFont(sans(14))
        painter.setPen(styled.palette.color(QPalette.ColorRole.HighlightedText) if option.state & QStyle.StateFlag.State_Selected else QColor("#ecefdf"))
        title = painter.fontMetrics().elidedText(str(index.data()), Qt.TextElideMode.ElideRight, max(0, rect.width()))
        painter.drawText(QRect(rect.left(), rect.center().y() - 21, rect.width(), 23), Qt.AlignmentFlag.AlignVCenter, title)
        painter.setFont(sans(12))
        painter.setPen(QColor("#bec7b1"))
        location = painter.fontMetrics().elidedText(parent.replace("/", " / "), Qt.TextElideMode.ElideRight, max(0, rect.width()))
        painter.drawText(QRect(rect.left(), rect.center().y() + 3, rect.width(), 20), Qt.AlignmentFlag.AlignVCenter, location)
        painter.restore()
