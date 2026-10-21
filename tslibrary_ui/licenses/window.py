"""Manage one item's licenses, keys, counts, and quick usage updates."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QWidget, QTableWidget, QHeaderView,
)

from ..shared.forms import action, caption
from ..shared.controls import TrashButton
from ..shared.tables import setup_table, cell, button_cell
from .models import count_text
from .item_dialog import ItemDialog
from .entry_dialog import LicenseEntryDialog, DeleteLicenseDialog


class LicenseWindow(QDialog):
    changed = Signal()
    details_changed = Signal()

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("inventoryDialog")
        self.setWindowTitle(f"TSLibrary — Manage licenses · {item.name}")
        self.setMinimumSize(960, 560)
        self.resize(1080, 660)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(14)
        layout.addWidget(caption("LICENSES  /  LICENSE ENTRIES", "adminEyebrow"))
        details_row = QHBoxLayout()
        details = QVBoxLayout()
        details.setSpacing(7)
        self.item_title = caption(item.name, "dialogHeading")
        self.category_label = caption(item.category)
        details.addWidget(self.item_title)
        details.addWidget(self.category_label)
        details_row.addLayout(details, 1)
        details_row.addSpacing(16)
        self.edit_item_button = action("Edit item")
        self.edit_item_button.clicked.connect(self.edit_item)
        details_row.addWidget(self.edit_item_button)
        layout.addLayout(details_row)
        top = QHBoxLayout()
        self.summary_label = caption("", "licenseSummary")
        self.summary_label.setWordWrap(False)
        top.addWidget(self.summary_label)
        top.addStretch()
        self.add_button = action("+  Add license entry", "adminPrimary")
        self.add_button.clicked.connect(self.add_entry)
        top.addWidget(self.add_button)
        layout.addLayout(top)
        self.empty_label = caption("No license entries yet. Add an entry to track available and used licenses.")
        layout.addWidget(self.empty_label)
        layout.addWidget(caption("Quick update: + marks one license as used; − returns one to available.",
                                 "adminMuted"))
        self.table = QTableWidget()
        setup_table(self.table, ["LICENSE LABEL", "TRACKING TYPE", "AVAILABLE", "USED", "LICENSE KEY", ""])
        for column, width in [(1, 160), (2, 100), (3, 146), (5, 122)]:
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        layout.addWidget(self.table, 1)
        bottom = QHBoxLayout()
        session_note = caption("Preview session · changes are not saved.", "adminMuted")
        session_note.setWordWrap(False)
        bottom.addWidget(session_note)
        bottom.addStretch()
        close = action("Done")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        layout.addLayout(bottom)
        self.refresh()

    def add_entry(self):
        self._open_editor()

    def confirm_delete_entry(self, entry):
        dialog = DeleteLicenseDialog(entry, self)
        self.delete_entry_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._delete_entry(entry))
        dialog.open()

    def _delete_entry(self, entry):
        index = next((index for index, candidate in enumerate(self.item.licenses)
                      if candidate is entry), None)
        if index is None:
            return
        del self.item.licenses[index]
        self.refresh()
        self.changed.emit()

    def edit_item(self):
        dialog = ItemDialog(self, item=self.item)
        self.details_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._save_details(dialog))
        dialog.open()

    def _save_details(self, dialog):
        self.item.name, self.item.category = dialog.details()
        self.setWindowTitle(f"TSLibrary — Manage licenses · {self.item.name}")
        self.item_title.setText(self.item.name)
        self.category_label.setText(self.item.category)
        self.details_changed.emit()
        self.changed.emit()

    def _open_editor(self, index=None):
        dialog = LicenseEntryDialog(self, self.item.licenses[index] if index is not None else None)
        self.entry_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._save_entry(dialog, index))
        dialog.open()

    def _save_entry(self, dialog, index):
        if index is None:
            self.item.licenses.append(dialog.entry())
        else:
            self.item.licenses[index] = dialog.entry()
        self.refresh()
        self.changed.emit()

    def refresh(self):
        self.empty_label.setVisible(not self.item.licenses)
        self.table.setRowCount(len(self.item.licenses))
        self.usage_controls = []
        for row, entry in enumerate(self.item.licenses):
            self.table.setItem(row, 0, cell(entry.label))
            self.table.setItem(row, 1, cell("Unlimited key" if entry.unlimited else
                                           "Count + license key" if entry.key else "Count only"))
            self.table.setItem(row, 2, cell(entry.available_text, True))
            usage = QWidget()
            usage_row = QHBoxLayout(usage)
            usage_row.setContentsMargins(7, 0, 7, 0)
            usage_row.setSpacing(6)
            release = action("−", "countStep")
            release.setFixedSize(30, 30)
            release.setAccessibleName(f"Return one used license for {entry.label}")
            release.setToolTip("Return one license to available")
            release.clicked.connect(lambda checked, index=row: self._change_usage(index, -1))
            used_count = caption(entry.used_text, "usedCount")
            used_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
            used_count.setWordWrap(False)
            use = action("+", "countStep")
            use.setFixedSize(30, 30)
            use.setAccessibleName(f"Use one available license for {entry.label}")
            use.setToolTip("Mark one available license as used")
            use.clicked.connect(lambda checked, index=row: self._change_usage(index, 1))
            usage_row.addWidget(release)
            usage_row.addWidget(used_count, 1)
            usage_row.addWidget(use)
            self.usage_controls.append((release, used_count, use))
            self.table.setCellWidget(row, 3, usage)
            if entry.key:
                key_shell = QWidget()
                key_layout = QHBoxLayout(key_shell)
                key_layout.setContentsMargins(5, 4, 5, 4)
                key_view = QLineEdit(entry.key)
                key_view.setReadOnly(True)
                key_view.setEchoMode(QLineEdit.EchoMode.Password)
                key_view.setAccessibleName(f"License key for {entry.label}")
                key_view.setMinimumWidth(30)
                key_layout.addWidget(key_view, 1)
                toggle = action("Show key")
                toggle.setMinimumHeight(30)
                toggle.setCheckable(True)
                toggle.toggled.connect(lambda visible, view=key_view, button=toggle: (
                    view.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password),
                    button.setText("Hide key" if visible else "Show key")))
                key_layout.addWidget(toggle)
                self.table.setCellWidget(row, 4, key_shell)
            else:
                self.table.removeCellWidget(row, 4)
                self.table.setItem(row, 4, cell("—"))
            edit = action("Edit")
            edit.setMinimumHeight(32)
            edit.clicked.connect(lambda checked, index=row: self._open_editor(index))
            delete = TrashButton(f"Delete license entry: {entry.label}")
            delete.clicked.connect(lambda checked, selected=entry: self.confirm_delete_entry(selected))
            self.table.setCellWidget(row, 5, button_cell(edit, delete))
        self._update_counts()

    def _update_counts(self):
        used_label = "tracked used" if self.item.has_unlimited and self.item.used is not None else "used"
        self.summary_label.setText(f"{self.item.available_text} available · {count_text(self.item.used)} "
                                   f"{used_label} · {count_text(self.item.total)} total")
        for row, entry in enumerate(self.item.licenses):
            release, count_label, use = self.usage_controls[row]
            self.table.item(row, 2).setText(entry.available_text)
            count_label.setText(entry.used_text)
            release.setVisible(not entry.unlimited)
            use.setVisible(not entry.unlimited)
            release.setEnabled(entry.can_change_usage(-1))
            use.setEnabled(entry.can_change_usage(1))

    def _change_usage(self, row, change):
        entry = self.item.licenses[row]
        if not entry.change_usage(change):
            return
        self._update_counts()
        self.changed.emit()
