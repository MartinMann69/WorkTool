"""Quick launching and named workspace sets, using the current workplace data."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout,
)

from ..shared.forms import action, caption
from .models import entry_key


class QuickLauncher(QDialog):
    def __init__(self, entries, opener, parent=None):
        super().__init__(parent)
        self.entries, self.opener = entries, opener
        self.setObjectName("inventoryDialog")
        self.setWindowTitle("TSLibrary — Quick launcher")
        self.resize(620, 470)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.addWidget(caption("Find your next tool.", "dialogHeading"))
        self.search = QLineEdit()
        self.search.setObjectName("dialogInput")
        self.search.setPlaceholderText("Search apps and websites…")
        self.search.setAccessibleName("Quick launcher search")
        self.search.installEventFilter(self)
        root.addWidget(self.search)
        self.results = QListWidget()
        self.results.setAccessibleName("Quick launcher results")
        root.addWidget(self.results, 1)
        self.empty = caption("No matching tools. Try a different search.")
        root.addWidget(self.empty)
        row = QHBoxLayout()
        row.addWidget(caption("Enter opens the selected tool · Esc closes", "adminMuted"))
        self.open_button = action("Open", "adminPrimary")
        row.addWidget(self.open_button)
        root.addLayout(row)
        self.search.textChanged.connect(self.refresh)
        self.search.returnPressed.connect(self.open_current)
        self.results.itemActivated.connect(lambda _: self.open_current())
        self.open_button.clicked.connect(self.open_current)
        self.refresh()
        self.search.setFocus()

    def refresh(self):
        words = self.search.text().casefold().split()
        self.results.clear()
        for entry in sorted(self.entries, key=lambda e: (not e.favorite, e.name.casefold())):
            if all(word in f"{entry.name} {entry.detail} {entry.type_label}".casefold() for word in words):
                text = ("Pinned · " if entry.favorite else "") + f"{entry.name}  ·  {entry.type_label}"
                if not entry.available:
                    text += "  ·  unavailable on this PC"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, entry)
                item.setToolTip(entry.detail)
                if entry.icon is not None:
                    item.setIcon(entry.icon)
                self.results.addItem(item)
        self.results.setCurrentRow(0)
        self.empty.setVisible(self.results.count() == 0)
        self.open_button.setEnabled(self.results.count() > 0)

    def open_current(self):
        item = self.results.currentItem()
        if item is not None:
            entry = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
            self.opener(entry)

    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.results.count():
                step = 1 if event.key() == Qt.Key.Key_Down else -1
                row = max(0, min(self.results.count() - 1, self.results.currentRow() + step))
                self.results.setCurrentRow(row)
                return True
        return super().eventFilter(watched, event)


class LaunchSetsDialog(QDialog):
    def __init__(self, entries, config, save, launch, parent=None):
        super().__init__(parent)
        self.entries, self.sets = entries, dict(config.launch_sets)
        self.save_callback, self.launch_callback = save, launch
        self.original = None
        self.setObjectName("inventoryDialog")
        self.setWindowTitle("TSLibrary — Workspace sets")
        self.resize(700, 560)
        root = QVBoxLayout(self)
        root.addWidget(caption("Your workspace sets.", "dialogHeading"))
        root.addWidget(caption("Save a group of tools to open together. Only saved workplace entries are listed."))
        body = QHBoxLayout()
        self.names = QListWidget()
        self.names.setMaximumWidth(210)
        self.names.setAccessibleName("Saved workspace sets")
        body.addWidget(self.names)
        fields = QVBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("dialogInput")
        self.name_edit.setPlaceholderText("Set name, e.g. Design work")
        self.name_edit.setAccessibleName("Workspace set name")
        self.name_edit.setMaxLength(80)
        fields.addWidget(self.name_edit)
        self.tools = QListWidget()
        self.tools.setAccessibleName("Tools in workspace set")
        for entry in entries:
            item = QListWidgetItem(f"{entry.name} · {entry.type_label}")
            item.setData(Qt.ItemDataRole.UserRole, entry_key(entry))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.tools.addItem(item)
        fields.addWidget(self.tools, 1)
        body.addLayout(fields, 1)
        root.addLayout(body, 1)
        self.error = caption("", "formError")
        root.addWidget(self.error)
        row = QHBoxLayout()
        for text, callback in [("New set", self.new_set), ("Delete set", self.delete_set),
                               ("Open set", self.open_set), ("Save set", self.save_set), ("Done", self.accept)]:
            button = action(text, "adminPrimary" if text == "Save set" else "emptyAction")
            button.clicked.connect(callback)
            row.addWidget(button)
        root.addLayout(row)
        self.names.currentTextChanged.connect(self.select_set)
        self.reload_names()

    def reload_names(self):
        self.names.blockSignals(True)
        self.names.clear()
        self.names.addItems(sorted(self.sets, key=str.casefold))
        self.names.blockSignals(False)

    def new_set(self):
        self.original = None
        self.names.setCurrentRow(-1)
        self.name_edit.clear()
        self.error.clear()
        for i in range(self.tools.count()):
            self.tools.item(i).setCheckState(Qt.CheckState.Unchecked)

    def select_set(self, name):
        if name not in self.sets:
            return
        self.original = name
        self.name_edit.setText(name)
        selected = set(self.sets[name])
        missing = selected - {entry_key(entry) for entry in self.entries}
        self.error.setText(f"{len(missing)} unavailable selection(s) will be kept until you edit the set." if missing else "")
        for i in range(self.tools.count()):
            item = self.tools.item(i)
            item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in selected
                               else Qt.CheckState.Unchecked)

    def save_set(self):
        name = self.name_edit.text().strip()
        keys = [self.tools.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.tools.count())
                if self.tools.item(i).checkState() == Qt.CheckState.Checked]
        if not name or not keys:
            self.error.setText("Enter a name and choose at least one tool.")
            return
        if name != self.original and name in self.sets:
            self.error.setText("A set already has that name. Select it to edit it.")
            return
        updated = dict(self.sets)
        if self.original and self.original != name:
            updated.pop(self.original, None)
        updated[name] = keys
        if self.save_callback(updated):
            self.sets, self.original = updated, name
            self.reload_names()
            matches = self.names.findItems(name, Qt.MatchFlag.MatchExactly)
            self.names.setCurrentItem(matches[0])
            self.error.setText("Set saved.")

    def delete_set(self):
        if self.original in self.sets:
            updated = dict(self.sets)
            del updated[self.original]
            if self.save_callback(updated):
                self.sets = updated
                self.reload_names()
                self.new_set()

    def open_set(self):
        if self.original in self.sets:
            self.launch_callback(self.original)
