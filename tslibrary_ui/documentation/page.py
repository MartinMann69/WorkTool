"""Documentation inventory, storage settings, and public read-only access."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QGridLayout, QHeaderView, QLabel, QLineEdit

from ..graphics.icons import admin_icon
from ..shared.catalog_page import CatalogPage
from ..shared.confirmation import ConfirmDeleteDialog
from ..shared.controls import TrashButton
from ..shared.forms import action, caption
from ..shared.tables import button_cell, cell, preserve_selection
from .dialogs import DocumentationItemDialog, DocumentationFilesDialog
from .files import DocumentationError, DocumentationFiles
from .models import DocumentationItem


class DocumentationPage(CatalogPage):
    changed = Signal()
    refresh_requested = Signal()
    title = "Documentation"
    description = "Shared guides and reference files, organised in named folders."
    empty_title = "A place for your team's knowledge."
    empty_description_text = "Choose a shared location, then add your first documentation item."
    add_text = "Add item"
    empty_action = "Add your first item"
    search_text = "Search documentation"
    headers = ("ITEM / FOLDER", "")

    def __init__(self, session, parent=None, *, editable=True):
        self.session, self.editable = session, editable
        self.files_dialog = None
        super().__init__(parent)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 238 if editable else 135)
        self.table.cellDoubleClicked.connect(self._open_row)
        self.add_requested.connect(self.add_item)
        if not editable:
            self.breadcrumb.setText("YOUR WORKPLACE  /  DOCUMENTATION")
            for badge in self.findChildren(QLabel):
                if badge.objectName() == "adminBadge":
                    badge.setText("READ ONLY")
            self.add_button.setText("Refresh")
            self.add_button.setIcon(admin_icon("documentation"))
            self.add_requested.disconnect(self.add_item)
            self.add_requested.connect(self.refresh_requested.emit)
            self.empty_button.hide()
            self.empty_description_text = "Shared documentation will appear here when your administrator adds it."
            self.storage_status.setText("SHARED DOCUMENTATION")
        self.refresh()

    @property
    def catalog(self):
        return self.session.documentation

    def _build_toolbar(self):
        if self.editable:
            panel = QFrame()
            panel.setObjectName("documentationSettings")
            grid = QGridLayout(panel)
            grid.setContentsMargins(16, 13, 16, 13)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(8)
            grid.addWidget(caption("Shared location", "fieldLabel"), 0, 0)
            self.location_edit = QLineEdit(self.catalog.parent_path)
            self.location_edit.setObjectName("dialogInput")
            self.location_edit.setAccessibleName("Shared documentation parent folder")
            self.location_edit.setPlaceholderText("A shared drive or cloud-synced folder")
            grid.addWidget(self.location_edit, 0, 1)
            self.browse_button = action("Browse…")
            self.browse_button.clicked.connect(self.browse_location)
            grid.addWidget(self.browse_button, 0, 2)
            grid.addWidget(caption("Root folder name", "fieldLabel"), 1, 0)
            self.root_name_edit = QLineEdit(self.catalog.root_name)
            self.root_name_edit.setObjectName("dialogInput")
            self.root_name_edit.setAccessibleName("Documentation root folder name")
            self.root_name_edit.setMaxLength(120)
            grid.addWidget(self.root_name_edit, 1, 1)
            self.save_location_button = action("Save location", "adminPrimary")
            self.save_location_button.clicked.connect(self.save_location)
            grid.addWidget(self.save_location_button, 1, 2)
            self.settings_message = caption("Share this folder with your team through your drive or cloud service.", "adminMuted")
            grid.addWidget(self.settings_message, 2, 0, 1, 3)
            grid.setColumnStretch(1, 1)
            panel.setMinimumHeight(panel.minimumSizeHint().height())
            self.content_layout.addWidget(panel)
            self.content_layout.addSpacing(18)
        super()._build_toolbar()

    def browse_location(self):
        path = QFileDialog.getExistingDirectory(self, "Choose shared or cloud-synced folder", self.location_edit.text())
        if path:
            self.location_edit.setText(path)

    def save_location(self):
        if not self.editable or self._busy():
            return
        try:
            DocumentationFiles(self.catalog).configure(self.location_edit.text().strip(), self.root_name_edit.text().strip())
        except (OSError, ValueError, DocumentationError) as error:
            self.settings_message.setText(str(error))
            return
        self.settings_message.setText("Documentation folder ready. Sharing uses your drive or cloud service's permissions.")
        self.changed.emit()
        self.refresh()

    def _busy(self):
        return self.files_dialog is not None and self.files_dialog.busy

    def add_item(self, item=None):
        if not self.editable or self._busy():
            return
        dialog = DocumentationItemDialog(self, item=item)
        self.item_dialog = dialog
        self.editing.emit(dialog, item)
        dialog.accepted.connect(lambda: self._save_item(dialog, item))
        dialog.open()

    def _save_item(self, dialog, item):
        try:
            files = DocumentationFiles(self.catalog)
            if item is None:
                files.create_item(dialog.name)
                item = DocumentationItem(dialog.name)
                self.catalog.items.append(item)
            else:
                files.rename_item(item, dialog.name)
        except (OSError, ValueError, DocumentationError) as error:
            dialog.error.setText(str(error))
            dialog.show()
            return
        self.entry_saved.emit(dialog, item)
        self.refresh()
        self.changed.emit()
        self.open_item(item)

    def open_item(self, item):
        if self._busy():
            self.files_dialog.raise_()
            return
        dialog = DocumentationFilesDialog(self.catalog, item, self, editable=self.editable)
        self.files_dialog = dialog
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.open()

    def _open_row(self, row, column):
        identifier = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        item = next((item for item in self.catalog.items if item.id == identifier), None)
        if item is not None:
            self.open_item(item)

    def confirm_remove(self, item):
        if not self.editable or self._busy():
            return
        dialog = ConfirmDeleteDialog("Remove documentation item", f'Remove “{item.name}” from TSLibrary?\nThe folder and its files are kept in the shared location.', self, section="DOCUMENTATION")
        self.remove_dialog = dialog
        dialog.accepted.connect(lambda: self._remove(item))
        dialog.open()

    def _remove(self, item):
        self.catalog.items[:] = [entry for entry in self.catalog.items if entry.id != item.id]
        self.refresh()
        self.changed.emit()

    @preserve_selection
    def refresh(self, *_):
        if not hasattr(self, "table"):
            return
        query = self.search.text().strip().casefold()
        items = [item for item in self.catalog.items if query in item.name.casefold()]
        if self.sort_select.currentIndex():
            items.sort(key=lambda item: item.name.casefold())
        else:
            items.reverse()
        # Cell widgets are deleted later by Qt. Hide them immediately so a
        # second refresh or resize cannot briefly paint old row actions.
        for row in range(self.table.rowCount()):
            previous = self.table.cellWidget(row, 1)
            if previous is not None:
                previous.hide()
        self.table.clearContents()
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            name = cell(item.name)
            name.setData(Qt.ItemDataRole.UserRole, item.id)
            name.setToolTip(f"{self.catalog.root_name}/{item.name}")
            name.setIcon(admin_icon("documentation"))
            self.table.setItem(row, 0, name)
            files = action("Files")
            files.clicked.connect(lambda checked=False, entry=item: self.open_item(entry))
            buttons = [files]
            if self.editable:
                rename = action("Edit")
                rename.clicked.connect(lambda checked=False, entry=item: self.add_item(entry))
                remove = TrashButton(f"Remove documentation item: {item.name}")
                remove.clicked.connect(lambda checked=False, entry=item: self.confirm_remove(entry))
                buttons.extend([rename, remove])
            self.table.setCellWidget(row, 1, button_cell(*buttons))
        self.content_stack.setCurrentWidget(self.table if items else self.empty_state)
        self.empty_heading.setText("No matching documentation." if self.catalog.items else self.empty_title)
        self.empty_description.setText("Try another item name." if self.catalog.items else self.empty_description_text)
        self.empty_button.setVisible(self.editable and not self.catalog.items)
        self.count_label.setText(f"Showing {len(items)} of {len(self.catalog.items)} documentation items")

    def reload_settings(self):
        if self.editable:
            self.location_edit.setText(self.catalog.parent_path)
            self.root_name_edit.setText(self.catalog.root_name)
        self.refresh()
