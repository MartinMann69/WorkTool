"""UI preview navigation only. This controller does not authenticate admins."""

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from .admin import AdminWindow
from .library import LibraryWindow
from .main_window import MainWindow
from .state import LibrarySession, WorkplaceConfig
from .storage import StorageError
from .welcome import LoginWindow


class PreviewController(QObject):
    def __init__(self, *, session=None, repository=None):
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
        self.admin.catalog_changed.connect(self._save_catalog)
        self.main_window.back_requested.connect(self.show_welcome)
        if repository is not None:
            self._catalog_status("SHARED CATALOG · SAVED LOCALLY")
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

    def show_welcome(self):
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
                     self.admin.phone_apps_page, self.admin.licenses_page):
            page.storage_status.setText(text + (" · KEYS SESSION ONLY" if page is self.admin.licenses_page else ""))

    def _save_catalog(self):
        if self.repository is None:
            self.main_window.refresh()
            return
        try:
            self.repository.save_catalog(self.session)
        except StorageError as error:
            self._catalog_unsaved = True
            self.main_window.catalog_reload_blocked = True
            self._catalog_status("CATALOG CHANGES NOT SAVED")
            QMessageBox.warning(self.admin, "Could not save shared catalog",
                                f"{error}\n\nChanges are still in this session but have not been saved.")
            return
        self._catalog_unsaved = False
        self.main_window.catalog_reload_blocked = False
        self._catalog_status("SHARED CATALOG · SAVED LOCALLY")
        self.main_window.refresh()
