"""Phone apps tab: inventory by name, with no executable or launch behavior."""

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QPushButton, QHeaderView

from ..graphics.icons import admin_icon
from ..shared.catalog_page import CatalogPage
from ..shared.controls import TrashButton
from ..shared.tables import button_cell, cell
from .dialogs import PhoneAppDialog, DeletePhoneAppDialog
from .models import PhoneApp


class PhoneAppsPage(CatalogPage):
    title = "Phone apps"
    description = "A simple inventory of the phone apps you have."
    empty_title = "Your phone apps, together."
    empty_description_text = "Add an app by name to keep track of what you have."
    add_text = "Add phone app"
    empty_action = "Add your first phone app"
    search_text = "Search phone apps"
    headers = ("PHONE APP", "")

    def __init__(self, entries: list[PhoneApp], parent=None):
        self.phone_apps = entries
        super().__init__(parent)
        self.table.setIconSize(QSize(28, 28))
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 142)
        self.table.cellDoubleClicked.connect(self._edit_phone_app_row)
        self.add_requested.connect(self.add_phone_app)
        self.refresh()

    def add_phone_app(self, phone_app=None):
        dialog = PhoneAppDialog(self, phone_app=phone_app)
        self.phone_app_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._save_phone_app(dialog, phone_app))
        dialog.open()

    def _save_phone_app(self, dialog, original):
        updated = dialog.phone_app()
        if original is None:
            self.phone_apps.append(updated)
        else:
            original.name = updated.name
        self.refresh()

    def refresh(self, *_):
        query = self.search.text().strip().casefold()
        visible = [entry for entry in self.phone_apps if query in entry.name.casefold()]
        if self.sort_select.currentIndex():
            visible.sort(key=lambda entry: entry.name.casefold())
        else:
            visible.reverse()
        self.table.setRowCount(len(visible))
        for row, entry in enumerate(visible):
            name = cell(entry.name)
            name.setIcon(admin_icon("phone apps"))
            name.setToolTip(entry.name)
            name.setData(Qt.ItemDataRole.UserRole, entry.id)
            self.table.setItem(row, 0, name)
            edit = QPushButton("Edit")
            edit.setObjectName("emptyAction")
            edit.setCursor(Qt.CursorShape.PointingHandCursor)
            edit.clicked.connect(lambda checked, current=entry: self.add_phone_app(current))
            remove = TrashButton(f"Remove phone app: {entry.name}")
            remove.clicked.connect(lambda checked, current=entry: self.confirm_remove_phone_app(current))
            self.table.setCellWidget(row, 1, button_cell(edit, remove))
        self.content_stack.setCurrentWidget(self.table if visible else self.empty_state)
        self.empty_heading.setText("No matching phone apps." if self.phone_apps else self.empty_title)
        self.empty_description.setText("Try another app name." if self.phone_apps else
                                       self.empty_description_text)
        self.empty_button.setVisible(not self.phone_apps)
        word = "phone app" if len(self.phone_apps) == 1 else "phone apps"
        self.count_label.setText(f"Showing {len(visible)} of {len(self.phone_apps)} {word}")

    def _edit_phone_app_row(self, row, _column):
        app_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        entry = next(entry for entry in self.phone_apps if entry.id == app_id)
        self.add_phone_app(entry)

    def confirm_remove_phone_app(self, phone_app):
        dialog = DeletePhoneAppDialog(phone_app, self)
        self.remove_phone_app_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._remove_phone_app(phone_app.id))
        dialog.open()

    def _remove_phone_app(self, app_id):
        self.phone_apps[:] = [entry for entry in self.phone_apps if entry.id != app_id]
        self.refresh()
