"""Applications tab: row rendering, search, and add/edit/delete behavior."""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import QPushButton, QHeaderView

from ..shared.catalog_page import CatalogPage
from ..shared.controls import TrashButton
from ..shared.tables import button_cell, cell, preserve_selection
from .models import Application
from .dialogs import ApplicationDialog, DeleteApplicationDialog


class ApplicationsPage(CatalogPage):
    changed = Signal()
    title = 'Applications'
    description = 'Applications for the user library.'
    empty_title = 'Your applications, together.'
    empty_description_text = 'Choose an executable or shortcut to add an application and its icon.'
    add_text = 'Add application'
    empty_action = 'Add your first application'
    search_text = 'Search applications'
    headers = ('APPLICATION', 'LAUNCH TARGET', '')

    def __init__(self, entries: list[Application], parent=None):
        self.applications = entries
        super().__init__(parent)
        self.table.setIconSize(QSize(32, 32))
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 220)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 142)
        self.table.cellDoubleClicked.connect(self._edit_application_row)
        self.add_requested.connect(self.add_application)
        self.refresh()

    def add_application(self, application=None):
        dialog = ApplicationDialog(self, application=application)
        self.application_dialog = dialog
        self.editing.emit(dialog, application)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._save_application(dialog, application))
        dialog.open()

    def _save_application(self, dialog, original):
        updated = dialog.application()
        if original is None:
            self.applications.append(updated)
        else:
            original.name = updated.name
            original.executable = updated.executable
            original.icon = updated.icon
            original.arguments = updated.arguments
            original.target = updated.target
        self.entry_saved.emit(dialog, original if original is not None else updated)
        self.refresh()
        self.changed.emit()

    @preserve_selection
    def refresh(self, *_):
        query = self.search.text().strip().casefold()
        visible = [entry for entry in self.applications
                   if not query or query in f"{entry.name} {entry.launch_target}".casefold()]
        visible.sort(key=lambda entry: entry.name.casefold() if self.sort_select.currentIndex()
                     else -self.applications.index(entry))
        self.table.setRowCount(len(visible))
        for row, entry in enumerate(visible):
            name = cell(entry.name)
            name.setIcon(entry.icon)
            name.setToolTip(entry.name)
            name.setData(Qt.ItemDataRole.UserRole, entry.id)
            self.table.setItem(row, 0, name)
            path = cell(entry.launch_target)
            path.setToolTip(entry.launch_target)
            self.table.setItem(row, 1, path)
            edit = QPushButton("Edit")
            edit.setObjectName("emptyAction")
            edit.setCursor(Qt.CursorShape.PointingHandCursor)
            edit.clicked.connect(lambda checked, current=entry: self.add_application(current))
            remove = TrashButton(f"Remove application: {entry.name}")
            remove.clicked.connect(lambda checked, current=entry: self.confirm_remove_application(current))
            self.table.setCellWidget(row, 2, button_cell(edit, remove))
        self.content_stack.setCurrentWidget(self.table if visible else self.empty_state)
        self.empty_heading.setText("No matching applications." if self.applications else self.empty_title)
        self.empty_description.setText("Try another name or application path." if self.applications else
                                       self.empty_description_text)
        self.empty_button.setVisible(not self.applications)
        word = "application" if len(self.applications) == 1 else "applications"
        self.count_label.setText(f"Showing {len(visible)} of {len(self.applications)} {word}")

    def _edit_application_row(self, row, _column):
        application_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        application = next(entry for entry in self.applications if entry.id == application_id)
        self.add_application(application)

    def confirm_remove_application(self, application):
        dialog = DeleteApplicationDialog(application, self)
        self.remove_application_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._remove_application(application.id))
        dialog.open()

    def _remove_application(self, application_id):
        self.applications[:] = [entry for entry in self.applications if entry.id != application_id]
        self.refresh()
        self.changed.emit()
