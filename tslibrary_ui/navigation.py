"""UI preview navigation only. This controller does not authenticate admins."""

from contextlib import nullcontext

from PySide6.QtCore import QObject, Qt, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from .admin import AdminWindow
from .library import LibraryWindow
from .main_window import MainWindow
from .state import LibrarySession, WorkplaceConfig, replace_catalog
from .storage import StorageError, catalog_data
from .catalog_refresh import CatalogRefresh
from .team_config import SharedJsonCatalogStore
from .welcome import LoginWindow
from .window_state import WindowStateManager


class PreviewController(QObject):
    def __init__(self, *, session=None, repository=None, window_settings=None):
        super().__init__()
        self.repository = repository
        self.session = (session if session is not None else repository.load_catalog()
                        if repository is not None else LibrarySession())
        config = repository.load_workplace() if repository is not None else WorkplaceConfig()
        self._catalog_unsaved = False
        self.welcome = LoginWindow()
        self.admin = AdminWindow(session=self.session)
        self.library = LibraryWindow(session=self.session)
        self.main_window = MainWindow(session=self.session, config=config, repository=repository)
        self.window_state = WindowStateManager(
            (self.welcome, self.main_window, self.admin, self.library),
            settings=window_settings, parent=self)
        self.admin.catalog_changed.connect(self._save_catalog)
        settings = self.admin.settings_page
        settings.bind_repository(repository)
        settings.create_requested.connect(self.create_team)
        settings.open_requested.connect(self.open_team)
        settings.refresh_requested.connect(self.reload_admin_catalog)
        settings.retry_requested.connect(self._save_catalog)
        self.admin.documentation_page.write_guard = lambda: (
            self.repository.catalog_store.write_transaction()
            if isinstance(getattr(self.repository, "catalog_store", None), SharedJsonCatalogStore)
            else nullcontext())
        self.admin.documentation_page.persist_change = lambda: self._save_catalog(raise_errors=True)
        self._refresh_job = None
        self._refresh_manual = False
        self._refresh_expected = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self._poll_catalog)
        if isinstance(getattr(repository, "catalog_store", None), SharedJsonCatalogStore):
            self._refresh_timer.start()
            settings.set_status("Connected to the team catalog. Shared changes are checked every 5 seconds while no editor is open.")
        self.main_window.back_requested.connect(self.show_welcome)
        if repository is not None:
            self._catalog_status("SHARED CATALOG · SAVED")
        self.welcome.sign_in_requested.connect(self.show_admin)
        self.welcome.open_requested.connect(self.show_main)
        self.admin.back_requested.connect(self.show_welcome)
        self.library.back_requested.connect(self.show_welcome)

    def activate_current_window(self):
        """Restore the current page or dialog when TSLibrary is opened again."""
        window = QApplication.activeModalWidget() or QApplication.activeWindow()
        if window is None or not window.isVisible():
            window = next((candidate for candidate in (
                self.main_window, self.admin, self.library, self.welcome)
                if candidate.isVisible()), self.welcome)
        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
        window.show()
        window.raise_()
        window.activateWindow()
        QApplication.alert(window)

    def show_admin(self, _username="", _password=""):
        # This is a layout preview, not an authentication or authorization gate.
        self.welcome.password_field.edit.clear()
        self.welcome.password_field.toggle.setChecked(False)
        self.admin.show()
        self.library.hide()
        self.main_window.hide()
        self.welcome.hide()
        self.admin.raise_()
        self.admin.activateWindow()
        self._poll_catalog()

    def show_welcome(self):
        if self.admin.documentation_page._busy():
            return
        self.welcome.show()
        self.admin.hide()
        self.library.hide()
        self.main_window.hide()
        self.welcome.raise_()
        self.welcome.activateWindow()

    def show_library(self):
        self.library.show()
        self.welcome.hide()
        self.admin.hide()
        self.main_window.hide()
        self.library.raise_()
        self.library.activateWindow()

    def show_main(self):
        if self.repository is not None and not self._catalog_unsaved:
            self.main_window.reload_catalog()
        self.main_window.show()
        self.welcome.hide()
        self.admin.hide()
        self.library.hide()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _catalog_status(self, text):
        for page in (self.admin.applications_page, self.admin.websites_page,
                     self.admin.phone_apps_page, self.admin.licenses_page,
                     self.admin.documentation_page):
            page.storage_status.setText(text + (" · KEYS SESSION ONLY" if page is self.admin.licenses_page else ""))

    def _admin_busy(self):
        return self.admin.documentation_page._busy() or any(
            dialog.isVisible() for dialog in self.admin.findChildren(QDialog))

    def _refresh_views(self):
        self.admin.licenses_page.refresh_categories()
        for page in self.admin.pages.values():
            page.refresh()
        self.admin.refresh_related_entries()
        self.main_window.refresh()
        self.library.refresh()

    def _confirm_catalog_switch(self):
        if self._admin_busy():
            QMessageBox.information(self.admin, "An editor is open", "Close open editors and documentation windows before reloading or changing the team configuration.")
            return False
        if self._catalog_unsaved or self.admin.settings_page.dirty:
            return QMessageBox.question(self.admin, "Discard unsaved changes?",
                "There are unsaved catalog changes or documentation settings. Export a catalog backup from Data tools to keep catalog drafts. Continue and discard these changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
        return True

    def open_team(self, path):
        if self.repository is None or not self._confirm_catalog_switch():
            return False
        try:
            loaded = self.repository.select_team(path)
        except StorageError as error:
            self.admin.settings_page.set_status(str(error), unsaved=self._catalog_unsaved)
            return False
        self._team_selected(loaded, keep_keys=False)
        return True

    def create_team(self, path):
        if self.repository is None or self._admin_busy():
            return False
        if self.admin.settings_page.dirty:
            self.admin.settings_page.set_status("Save the documentation settings before creating a team configuration.")
            return False
        try:
            loaded = self.repository.create_team(path, self.session)
        except StorageError as error:
            self.admin.settings_page.set_status(str(error), unsaved=self._catalog_unsaved)
            return False
        self._team_selected(loaded, keep_keys=True)
        return True

    def _team_selected(self, loaded, *, keep_keys):
        # Invalidate any read still in flight for the previous catalog.
        self._refresh_expected = None
        replace_catalog(self.session, loaded, keep_session_keys=keep_keys)
        self._catalog_unsaved = False
        self.main_window.catalog_reload_blocked = False
        self.admin.settings_page.reload_settings()
        self._refresh_views()
        self._catalog_status("TEAM CATALOG · SAVED")
        self.admin.settings_page.set_status("Connected. Changes are saved to the shared catalog. Other admins refresh automatically while no editor is open.")
        self._refresh_timer.start()

    def _poll_catalog(self):
        if (self.admin.isVisible() and not self._catalog_unsaved and not self._admin_busy()
                and not self.admin.settings_page.dirty):
            self._start_catalog_refresh(manual=False)

    def reload_admin_catalog(self):
        if self.repository is None or not self._confirm_catalog_switch():
            return
        self._start_catalog_refresh(manual=True)

    def _start_catalog_refresh(self, *, manual):
        if self._refresh_job is not None:
            return
        store = getattr(self.repository, "catalog_store", None)
        if isinstance(store, SharedJsonCatalogStore):
            self._refresh_expected = catalog_data(self.session)
            self._refresh_revision = store._revision
            self._refresh_manual = manual
            job = CatalogRefresh(store)
            job.signals.finished.connect(self._catalog_read_finished)
            self._refresh_job = job
            QThreadPool.globalInstance().start(job)
        elif manual:
            try:
                loaded = self.repository.load_catalog()
            except StorageError as error:
                self.admin.settings_page.set_status(str(error), unsaved=self._catalog_unsaved)
                return
            self._accept_catalog_reload(loaded, manual=True)

    def _catalog_read_finished(self, job, raw, error):
        if job is not self._refresh_job:
            return
        self._refresh_job = None
        manual = self._refresh_manual
        # A draft may have started, a save may have finished, or the team may
        # have changed while the network read was running. Never replace it.
        if (job.store is not getattr(self.repository, "catalog_store", None)
                or job.store._revision != self._refresh_revision
                or self._refresh_expected != catalog_data(self.session)
                or self._admin_busy() or (self._catalog_unsaved and not manual)
                or (self.admin.settings_page.dirty and not manual)):
            return
        if error is None:
            try:
                loaded = job.store.accept_snapshot(raw)
            except StorageError as failure:
                error = failure
        if error is not None:
            self._catalog_status("TEAM CATALOG · UNAVAILABLE")
            self.admin.settings_page.set_status(str(error), unsaved=self._catalog_unsaved)
            return
        self._accept_catalog_reload(loaded, manual=manual)

    def _accept_catalog_reload(self, loaded, *, manual):
        changed = catalog_data(loaded) != catalog_data(self.session)
        if changed:
            replace_catalog(self.session, loaded)
        self._catalog_unsaved = False
        self.main_window.catalog_reload_blocked = False
        if manual:
            self.admin.settings_page.reload_settings()
        if changed or manual:
            self._refresh_views()
        self._catalog_status("SHARED CATALOG · SAVED")
        self.admin.settings_page.set_status("Catalog is up to date. Shared changes are checked every 5 seconds while no editor is open.")

    def _save_catalog(self, *, raise_errors=False):
        if self.repository is None:
            self.main_window.refresh()
            return
        try:
            self.repository.save_catalog(self.session)
        except StorageError as error:
            if raise_errors:
                raise
            self._catalog_unsaved = True
            self.main_window.catalog_reload_blocked = True
            self._catalog_status("CATALOG CHANGES NOT SAVED")
            self.admin.settings_page.set_status(str(error), unsaved=True)
            QMessageBox.warning(self.admin, "Could not save shared catalog",
                                f"{error}\n\nChanges are still in this session but have not been saved.")
            return
        self._catalog_unsaved = False
        self.main_window.catalog_reload_blocked = False
        self._catalog_status("SHARED CATALOG · SAVED")
        self.admin.settings_page.set_status("Catalog changes saved.")
        self.main_window.refresh()
