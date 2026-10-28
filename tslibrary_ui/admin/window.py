"""Admin shell: compose feature pages and route sidebar navigation.

Editing, searching, and row rendering live in each feature's page.py.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView, QHBoxLayout, QStackedWidget, QTableWidgetItem, QWidget

from ..applications.page import ApplicationsPage
from ..graphics.icons import admin_icon
from ..licenses.page import LicensesPage
from ..library.page import LibraryPage
from ..phone_apps.page import PhoneAppsPage
from ..documentation.page import DocumentationPage
from ..state import LibrarySession
from ..relationships import ENTRY_TYPES, EntryRef, catalog_entries, replace_links, valid_links
from ..shared.tables import button_cell
from ..styles import load_stylesheets
from ..websites.page import WebsitesPage
from .sidebar import AdminSidebar
from .transfers import AdminDataTools
from .relationships import RelatedEntriesEditor, row_links_button, materialize_documentation
from .settings import SettingsPage


class AdminWindow(AdminDataTools, QWidget):
    back_requested = Signal()
    catalog_changed = Signal()
    LICENSES_PAGE = "Licenses"

    def __init__(self, parent=None, *, session=None):
        super().__init__(parent)
        self.session = session if session is not None else LibrarySession()
        # Upgrade existing direct links before any edit or deletion can split
        # the group around its original connecting entry.
        self.session.links[:] = valid_links(self.session)
        self.setObjectName("adminWindow")
        self.setWindowTitle("TSLibrary — Administration")
        self.setMinimumSize(1000, 680)
        self.resize(1320, 850)
        self.setStyleSheet(load_stylesheets("base", "admin"))
        self.setWindowIcon(admin_icon("library", "#c9b18c"))
        self.licenses_page = LicensesPage(self.session.items)
        self.applications_page = ApplicationsPage(self.session.applications)
        self.phone_apps_page = PhoneAppsPage(self.session.phone_apps)
        self.websites_page = WebsitesPage(self.session.websites)
        self.documentation_page = DocumentationPage(self.session)
        self.full_library_page = LibraryPage(session=self.session)
        self.settings_page = SettingsPage(self.session)
        self.pages = {
            "Full library": self.full_library_page,
            "Licenses": self.licenses_page,
            "Applications": self.applications_page,
            "Phone apps": self.phone_apps_page,
            "Websites": self.websites_page,
            "Documentation": self.documentation_page,
            "Settings": self.settings_page,
        }
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = AdminSidebar(self.pages)
        self._setup_data_tools()
        self.sidebar.page_requested.connect(self.set_page)
        self.sidebar.back_requested.connect(self.back_requested.emit)
        root.addWidget(self.sidebar)
        self.page_stack = QStackedWidget()
        for page in self.pages.values():
            self.page_stack.addWidget(page)
        root.addWidget(self.page_stack, 1)
        self.relationship_pages = {}
        for kind, (_, page_name) in ENTRY_TYPES.items():
            page = self.pages[page_name]
            self.relationship_pages[kind] = page
            page.links_column = page.table.columnCount()
            page.table.setColumnCount(page.links_column + 1)
            page.table.setHorizontalHeaderItem(page.links_column, QTableWidgetItem("LINKS"))
            page.table.horizontalHeader().setSectionResizeMode(page.links_column, QHeaderView.ResizeMode.Fixed)
            page.table.setColumnWidth(page.links_column, 112)
            page.editing.connect(lambda dialog, entry, entry_kind=kind: self._prepare_editor(entry_kind, dialog, entry))
            page.entry_saved.connect(lambda dialog, entry, entry_kind=kind: self._save_editor_links(entry_kind, dialog, entry))
            page.refreshed.connect(lambda entry_kind=kind: self._refresh_row_links(entry_kind))
            page.changed.connect(self._catalog_edited)
            self._refresh_row_links(kind)
        self._inventory_sort_index = 0
        self.settings_page.changed.connect(self._catalog_edited)
        self.documentation_page.filesystem_changed.connect(self.refresh_related_entries)
        self.documentation_page.filesystem_changed.connect(self.full_library_page.refresh)
        self.set_page(self.LICENSES_PAGE)

    def _catalog_edited(self):
        # Remove both directions when an inventory record is deleted.
        self.session.links[:] = valid_links(self.session)
        self.refresh_related_entries()
        self.catalog_changed.emit()

    def refresh_related_entries(self):
        for kind in self.relationship_pages:
            self._refresh_row_links(kind)

    def _prepare_editor(self, kind, dialog, entry):
        dialog.entry_kind = kind
        source = EntryRef(kind, entry.id) if entry is not None else None
        dialog.related_editor = RelatedEntriesEditor(self.session, source, dialog)
        # Keep link selection with the fields, above validation and Save/Cancel.
        layout = dialog.layout()
        layout.insertWidget(layout.count() - 2, dialog.related_editor)

    def _save_editor_links(self, kind, dialog, entry):
        editor = dialog.related_editor
        selected = materialize_documentation(self.session, editor.selected_refs, editor.pending_documentation)
        replace_links(self.session, EntryRef(kind, entry.id), selected)
        if kind != "documentation":
            self.documentation_page.refresh()

    def _refresh_row_links(self, kind):
        page = self.relationship_pages[kind]
        table, column = page.table, page.links_column
        has_links = False
        for row in range(table.rowCount()):
            previous = table.cellWidget(row, column)
            if previous is not None:
                previous.hide()
                table.removeCellWidget(row, column)
            identifier = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if not isinstance(identifier, str):
                continue  # An inferred documentation folder has no catalog record.
            source = EntryRef(kind, identifier)
            button = row_links_button(self.session, source, self.navigate_to_entry, table)
            if button is not None:
                table.setCellWidget(row, column, button_cell(button))
                has_links = True
        table.setColumnHidden(column, not has_links)

    def navigate_to_entry(self, ref):
        entry = catalog_entries(self.session).get(ref)
        if entry is None:
            self.refresh_related_entries()
            return False
        page = self.pages[ENTRY_TYPES[ref.kind][1]]
        self.set_page(ENTRY_TYPES[ref.kind][1])
        if hasattr(page, "reveal_entry"):
            page.reveal_entry(ref.id)
        # Clear only filters that would hide the destination.
        def target_row():
            return next((row for row in range(page.table.rowCount())
                         if page.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == ref.id), None)
        if target_row() is None:
            page.search.clear()
            if page.has_categories:
                page.category_filter.setCurrentIndex(0)
            page.refresh()
        row = target_row()
        if row is None:
            return False
        page.table.setCurrentCell(row, 0)
        page.table.selectRow(row)
        page.table.scrollToItem(page.table.item(row, 0))
        page.table.setFocus()
        if ref.kind == "license":
            page.open_licenses(entry)
        elif ref.kind == "documentation":
            page.open_item(entry)
        return True

    @property
    def current_page(self):
        return self.page_stack.currentWidget()

    def set_page(self, name):
        page = self.pages[name]
        # Inventory tabs share their name/recent sort. The combined library has
        # its own sort options, so keep that choice independent of these tabs.
        if hasattr(self.current_page, "sort_select") and self.current_page is not self.full_library_page:
            self._inventory_sort_index = self.current_page.sort_select.currentIndex()
        if hasattr(page, "sort_select") and page is not self.full_library_page:
            page.sort_select.setCurrentIndex(self._inventory_sort_index)
        self.sidebar.nav_buttons[name].setChecked(True)
        self.page_stack.setCurrentWidget(page)
        page.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 26 if self.width() < 1150 else 38
        from ..graphics.shelf import ShelfArtwork
        for illustration in self.sidebar.findChildren(ShelfArtwork):
            illustration.setVisible(self.height() >= 790)
        for page in self.pages.values():
            page.content_layout.setContentsMargins(margin, 30, margin, 23)
            if hasattr(page, "set_compact_header"):
                page.set_compact_header(self.height() < 740)

    def closeEvent(self, event):
        if self.documentation_page._busy():
            self.documentation_page._import_message = "A file operation is in progress. Please wait for it to finish."
            self.documentation_page._update_file_message()
            event.ignore()
            return
        super().closeEvent(event)
