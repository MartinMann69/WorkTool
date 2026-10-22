"""Admin data tools; shared catalog restore is kept out of normal user menus."""

from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from ..shared.forms import action
from ..storage import StorageError
from ..transfers import export_backup, import_backup, recovery_path, export_catalog_csv


class AdminDataTools:
    def _setup_data_tools(self):
        button = action("Data tools", "backButton")
        menu = QMenu(button)
        button.setMenu(menu)
        menu.addAction("Export catalog backup…", self.export_catalog)
        menu.addAction("Restore catalog backup…", self.restore_catalog)
        menu.addAction("Export catalog CSV…", self.export_csv)
        self.sidebar.layout().insertWidget(self.sidebar.layout().count() - 1, button)

    def export_catalog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export catalog backup", "TSLibrary-catalog.json", "JSON (*.json)")
        if path:
            try:
                export_backup(path, self.session, catalog=True)
            except StorageError as error:
                QMessageBox.warning(self, "Could not export backup", str(error))

    def restore_catalog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restore catalog backup", "", "JSON (*.json)")
        if not path:
            return
        try:
            loaded = import_backup(path, catalog=True)
            if QMessageBox.question(self, "Restore shared catalog", "Replace the shared catalog with this backup?\nLicense key values are excluded. A recovery backup will be saved beside it.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            export_backup(recovery_path(path), self.session, catalog=True)
            # Close dialogs bound to old records before replacing the inventory.
            for page, names in [(self.licenses_page, ("license_window", "item_dialog", "delete_dialog")),
                                (self.applications_page, ("application_dialog", "remove_application_dialog")),
                                (self.phone_apps_page, ("phone_app_dialog", "remove_phone_app_dialog")),
                                (self.websites_page, ("website_dialog", "remove_website_dialog"))]:
                for name in names:
                    dialog = getattr(page, name, None)
                    if dialog is not None:
                        try:
                            dialog.close()
                        except RuntimeError:
                            pass
            for field in ("applications", "websites", "phone_apps", "items"):
                getattr(self.session, field)[:] = getattr(loaded, field)
            self.licenses_page.refresh_categories()
            for page in self.pages.values():
                page.refresh()
            self.catalog_changed.emit()
        except StorageError as error:
            QMessageBox.warning(self, "Could not restore catalog", str(error))

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export catalog CSV", "TSLibrary-catalog.csv", "CSV (*.csv)")
        if path:
            try:
                export_catalog_csv(path, self.session)
            except StorageError as error:
                QMessageBox.warning(self, "Could not export CSV", str(error))
