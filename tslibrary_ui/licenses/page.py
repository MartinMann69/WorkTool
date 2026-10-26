"""Licenses tab: row rendering, search, and add/edit/delete behavior."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QHeaderView

from ..shared.catalog_page import CatalogPage
from ..shared.controls import TrashButton
from ..shared.tables import button_cell, cell, preserve_selection
from .models import LibraryItem, count_text
from .item_dialog import ItemDialog, DeleteItemDialog
from .window import LicenseWindow


class LicensesPage(CatalogPage):
    changed = Signal()
    title = 'Licenses'
    description = 'Keep your license counts and keys organised by item.'
    empty_title = 'Keep your licenses in one place.'
    empty_description_text = 'Add an item, then keep its licenses together in one place.'
    add_text = 'Add item'
    empty_action = 'Add your first item'
    search_text = 'Search licensed items'
    headers = ('ITEM NAME', 'CATEGORY', 'AVAILABLE', 'USED', '')
    has_categories = True

    def __init__(self, items: list[LibraryItem], parent=None):
        self.items = items
        super().__init__(parent)
        for column, width in [(2, 100), (3, 90), (4, 204)]:
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.table.cellDoubleClicked.connect(self._open_row)
        self.add_requested.connect(self.add_item)
        self.refresh_categories()
        self.refresh()

    def add_item(self):
        dialog = ItemDialog(self)
        self.item_dialog = dialog
        self.editing.emit(dialog, None)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._save_item(dialog))
        dialog.open()

    def _save_item(self, dialog):
        item = dialog.item()
        self.items.append(item)
        self.entry_saved.emit(dialog, item)
        self.changed.emit()
        self.refresh_categories()
        self.refresh()
        self.open_licenses(item)

    def refresh_categories(self):
        previous = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItems(["All categories"] + sorted(
            {entry.category for entry in self.items}, key=str.casefold))
        index = self.category_filter.findText(previous)
        self.category_filter.setCurrentIndex(max(0, index))
        self.category_filter.blockSignals(False)

    @preserve_selection
    def refresh(self, *_):
        query = self.search.text().strip().casefold()
        category = self.category_filter.currentText()
        visible = [item for item in self.items
                   if (not query or query in f"{item.name} {item.category} {item.owner} {item.renewal_date}".casefold())
                   and (category == "All categories" or item.category == category)]
        visible.sort(key=lambda item: item.name.casefold() if self.sort_select.currentIndex()
                     else -self.items.index(item))
        self.table.setRowCount(len(visible))
        for row, item in enumerate(visible):
            name = cell(item.name)
            name.setData(Qt.ItemDataRole.UserRole, item.id)
            name.setToolTip(f"{item.owner or 'No owner'} · {item.renewal_date or 'No renewal date'} · {item.renewal_status()}")
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, cell(item.category))
            self.table.setItem(row, 2, cell(item.available_text, True))
            used_cell = cell(item.used_text, True)
            if item.has_unlimited:
                used_cell.setToolTip("Usage is tracked for limited entries only. Unlimited keys have no used count.")
            self.table.setItem(row, 3, used_cell)
            button = QPushButton("Manage licenses  →")
            button.setObjectName("emptyAction")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked, entry=item: self.open_licenses(entry))
            delete = TrashButton(f"Delete item: {item.name}")
            delete.clicked.connect(lambda checked, entry=item: self.confirm_delete_item(entry))
            self.table.setCellWidget(row, 4, button_cell(button, delete))
        self.content_stack.setCurrentWidget(self.table if visible else self.empty_state)
        self.empty_heading.setText("No matching items." if self.items else self.empty_title)
        self.empty_description.setText("Try another search or category." if self.items else
                                       self.empty_description_text)
        self.empty_button.setVisible(not self.items)
        count = len(self.items)
        available = sum(item.available for item in self.items)
        entries = [entry for item in self.items for entry in item.licenses]
        finite = [entry for entry in entries if not entry.unlimited]
        used = None if entries and not finite else sum(entry.used for entry in finite)
        used_label = "tracked used" if finite and any(entry.unlimited for entry in entries) else "used"
        item_word = "item" if count == 1 else "items"
        self.count_label.setText(f"Showing {len(visible)} of {count} {item_word} · "
                                 f"{count_text(available)} available · {count_text(used)} {used_label}")
        from datetime import date
        due = [item for item in self.items if item.renewal_date
               and (date.fromisoformat(item.renewal_date) - date.today()).days <= 30]
        self.subtitle.setText(self.description + (f" {len(due)} renewal(s) due or overdue within 30 days." if due else ""))

    def _open_row(self, row, _column):
        item_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.open_licenses(next(item for item in self.items if item.id == item_id))

    def open_licenses(self, item):
        dialog = LicenseWindow(item, self)
        self.license_window = dialog
        dialog.editing.connect(self.editing.emit)
        dialog.entry_saved.connect(self.entry_saved.emit)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.details_changed.connect(self.refresh_categories)
        dialog.changed.connect(self.refresh)
        dialog.changed.connect(self.changed.emit)
        dialog.open()

    def confirm_delete_item(self, item):
        dialog = DeleteItemDialog(item, self)
        self.delete_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._delete_item(item.id))
        dialog.open()

    def _delete_item(self, item_id):
        # Match the stable ID, so items with the same name remain independent.
        self.items[:] = [item for item in self.items if item.id != item_id]
        self.refresh_categories()
        self.refresh()
        self.changed.emit()
