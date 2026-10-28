"""Browse real documentation folders/files and stage link targets without saving."""

from PySide6.QtCore import Qt, QSignalBlocker, QThreadPool, Signal
from PySide6.QtWidgets import QHeaderView, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..graphics.icons import admin_icon
from ..relationships import EntryRef
from ..shared.forms import action
from .browser_files import ReadDirectory
from .models import DocumentationCatalog, DocumentationItem, item_name
from .navigation import DocumentationStatus


KIND_ROLE = Qt.ItemDataRole.UserRole + 1


class DocumentationPicker(QWidget):
    selection_changed = Signal(object, bool)

    def __init__(self, catalog, selected=(), pending=(), parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.pending = {entry.id: entry for entry in pending}
        self.records = {entry.name.casefold(): entry for entry in [*catalog.items, *pending]}
        self.selected = set(selected)
        self.nodes, self.jobs, self.loaded = {}, {}, set()
        self.query = ""
        self.generation = 0
        self.search_loaded = False
        self.last_error = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setObjectName("documentationPicker")
        self.tree.setAccessibleName("Documentation folders and files; check to connect")
        self.tree.setHeaderLabels(["DOCUMENTATION", "TYPE"])
        self.tree.setIndentation(20)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.root = self.tree.invisibleRootItem()
        self.nodes[""] = self.root
        for entry in sorted(self.records.values(), key=lambda entry: (entry.name.count("/"), entry.name.casefold())):
            self._node(entry.name, entry.kind)
        self.root.setExpanded(True)
        layout.addWidget(self.tree, 1)
        footer = QHBoxLayout()
        self.status = DocumentationStatus()
        self.status.setFixedHeight(22)
        footer.addWidget(self.status, 1)
        refresh = action("Refresh")
        refresh.setFixedHeight(34)
        refresh.clicked.connect(self.reload)
        footer.addWidget(refresh)
        layout.addLayout(footer)
        self.tree.itemChanged.connect(self._checked)
        self.tree.itemExpanded.connect(self._expanded)
        self._load("")

    def _node(self, path, kind):
        key = path.casefold()
        if key in self.nodes:
            return self.nodes[key]
        parent, _, leaf = path.rpartition("/")
        host = self._node(parent, "folder") if parent else self.root
        node = QTreeWidgetItem(host, [leaf, "Folder" if kind == "folder" else "File"])
        self.nodes[key] = node
        node.setData(0, Qt.ItemDataRole.UserRole, path)
        node.setData(0, KIND_ROLE, kind)
        node.setIcon(0, admin_icon("folder", "#c9b18c") if kind == "folder" else admin_icon("documentation"))
        node.setToolTip(0, path)
        node.setFlags(node.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        record = self.records.get(key)
        ref = EntryRef("documentation", record.id) if record else None
        node.setCheckState(0, Qt.CheckState.Checked if ref in self.selected else Qt.CheckState.Unchecked)
        if kind == "folder":
            node.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        return node

    def _checked(self, node, column):
        path = node.data(0, Qt.ItemDataRole.UserRole)
        if not path or column != 0:
            return
        checked = node.checkState(0) == Qt.CheckState.Checked
        record = self.records.get(path.casefold())
        if record is None:
            if not checked:
                return
            try:
                record = DocumentationItem(item_name(path), kind=node.data(0, KIND_ROLE))
            except ValueError as error:
                with QSignalBlocker(self.tree):
                    node.setCheckState(0, Qt.CheckState.Unchecked)
                self.status.setText(str(error))
                self.status.setToolTip(str(error))
                return
            self.records[path.casefold()] = record
            self.pending[record.id] = record
        self.selection_changed.emit(EntryRef("documentation", record.id), checked)

    def set_selected(self, refs):
        self.selected = set(refs)
        with QSignalBlocker(self.tree):
            for key, node in self.nodes.items():
                record = self.records.get(key)
                if record is not None:
                    ref = EntryRef("documentation", record.id)
                    node.setCheckState(0, Qt.CheckState.Checked if ref in self.selected else Qt.CheckState.Unchecked)

    def _expanded(self, node):
        if node.data(0, KIND_ROLE) == "folder" or node is self.root:
            self._load(node.data(0, Qt.ItemDataRole.UserRole))

    def _load(self, path, *, recursive=False):
        key = (path.casefold(), recursive)
        if key in self.loaded:
            return
        self.loaded.add(key)
        snapshot = DocumentationCatalog(self.catalog.parent_path, self.catalog.root_name, list(self.catalog.items))
        job = ReadDirectory(snapshot, path, recursive)
        self.jobs[id(job)] = (job, self.generation, path, recursive)
        job.signals.finished.connect(self._read)
        QThreadPool.globalInstance().start(job)
        self._status()

    def _read(self, job, entries, error):
        details = self.jobs.pop(id(job), None)
        if details is None or details[1] != self.generation:
            return
        _, _, path, recursive = details
        self.last_error = error
        if error:
            self.loaded.discard((path.casefold(), recursive))
            if recursive:
                self.search_loaded = False
        else:
            with QSignalBlocker(self.tree):
                for entry in sorted(entries, key=lambda entry: (entry["path"].count("/"), not entry["folder"], entry["path"].casefold())):
                    self._node(entry["path"], "folder" if entry["folder"] else "file")
                parent = self.nodes.get(path.casefold())
                if parent is not None and not parent.childCount():
                    parent.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless)
                self.tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.set_selected(self.selected)
        self._filter()
        self._status()

    def _status(self):
        loading = any(details[1] == self.generation for details in self.jobs.values())
        text = "Loading documentation…" if loading else self.last_error or "Check a file or folder to connect it."
        self.status.setText(text)
        self.status.setToolTip(text)

    def search(self, text):
        self.query = text.strip().casefold()
        if self.query and not self.search_loaded:
            self.search_loaded = True
            self._load("", recursive=True)
        self._filter()

    def _filter(self):
        with QSignalBlocker(self.tree):
            for key, node in sorted(self.nodes.items(), key=lambda pair: pair[0].count("/"), reverse=True):
                visible = not self.query or self.query in key or any(not node.child(index).isHidden() for index in range(node.childCount()))
                node.setHidden(not visible if node is not self.root else False)
                if self.query and visible:
                    node.setExpanded(True)

    def reload(self):
        self.generation += 1
        self.loaded.clear()
        self.last_error = ""
        self.search_loaded = bool(self.query)
        self._load("", recursive=bool(self.query))
        # Reload expanded branches, preserving staged checks even if offline.
        if not self.query:
            for node in list(self.nodes.values()):
                if node is not self.root and node.isExpanded():
                    self._expanded(node)
