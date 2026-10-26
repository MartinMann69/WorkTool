"""Websites tab: row rendering, search, and add/edit/delete behavior."""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import QPushButton, QHeaderView

from ..shared.catalog_page import CatalogPage
from ..shared.controls import TrashButton
from ..shared.tables import button_cell, cell, preserve_selection
from .models import Website
from .dialogs import WebsiteDialog, DeleteWebsiteDialog


class WebsitesPage(CatalogPage):
    changed = Signal()
    title = 'Websites'
    description = 'Website links for the user library.'
    empty_title = 'A home for useful websites.'
    empty_description_text = 'Add a website address and give it a name for your users.'
    add_text = 'Add website'
    empty_action = 'Add your first website'
    search_text = 'Search websites'
    headers = ('WEBSITE', 'URL', '')

    def __init__(self, entries: list[Website], parent=None):
        self.websites = entries
        super().__init__(parent)
        self.table.setIconSize(QSize(32, 32))
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 220)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 142)
        self.table.cellDoubleClicked.connect(self._edit_website_row)
        self.add_requested.connect(self.add_website)
        self.refresh()

    def add_website(self, website=None):
        dialog = WebsiteDialog(self, website=website)
        self.website_dialog = dialog
        self.editing.emit(dialog, website)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._save_website(dialog, website))
        dialog.open()

    def _save_website(self, dialog, original):
        updated = dialog.website()
        if original is None:
            self.websites.append(updated)
        else:
            original.name = updated.name
            original.url = updated.url
            original.icon = updated.icon
        self.entry_saved.emit(dialog, original if original is not None else updated)
        self.refresh()
        self.changed.emit()

    @preserve_selection
    def refresh(self, *_):
        query = self.search.text().strip().casefold()
        visible = [entry for entry in self.websites
                   if not query or query in f"{entry.name} {entry.url}".casefold()]
        visible.sort(key=lambda entry: entry.name.casefold() if self.sort_select.currentIndex()
                     else -self.websites.index(entry))
        self.table.setRowCount(len(visible))
        for row, entry in enumerate(visible):
            name = cell(entry.name)
            name.setIcon(entry.icon)
            name.setToolTip(entry.name)
            name.setData(Qt.ItemDataRole.UserRole, entry.id)
            self.table.setItem(row, 0, name)
            url = cell(entry.url)
            url.setToolTip(entry.url)
            self.table.setItem(row, 1, url)
            edit = QPushButton("Edit")
            edit.setObjectName("emptyAction")
            edit.setCursor(Qt.CursorShape.PointingHandCursor)
            edit.clicked.connect(lambda checked, current=entry: self.add_website(current))
            remove = TrashButton(f"Remove website: {entry.name}")
            remove.clicked.connect(lambda checked, current=entry: self.confirm_remove_website(current))
            self.table.setCellWidget(row, 2, button_cell(edit, remove))
        self.content_stack.setCurrentWidget(self.table if visible else self.empty_state)
        self.empty_heading.setText("No matching websites." if self.websites else self.empty_title)
        self.empty_description.setText("Try another name or website address." if self.websites else
                                       self.empty_description_text)
        self.empty_button.setVisible(not self.websites)
        word = "website" if len(self.websites) == 1 else "websites"
        self.count_label.setText(f"Showing {len(visible)} of {len(self.websites)} {word}")

    def _edit_website_row(self, row, _column):
        website_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        website = next(entry for entry in self.websites if entry.id == website_id)
        self.add_website(website)

    def confirm_remove_website(self, website):
        dialog = DeleteWebsiteDialog(website, self)
        self.remove_website_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._remove_website(website.id))
        dialog.open()

    def _remove_website(self, website_id):
        self.websites[:] = [entry for entry in self.websites if entry.id != website_id]
        self.refresh()
        self.changed.emit()
