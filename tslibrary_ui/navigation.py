"""UI preview navigation only. This controller does not authenticate admins."""

from PySide6.QtCore import QObject

from .admin import AdminWindow
from .library import LibraryWindow
from .main_window import MainWindow
from .state import LibrarySession
from .welcome import LoginWindow


class PreviewController(QObject):
    def __init__(self, *, session=None):
        super().__init__()
        self.session = session if session is not None else LibrarySession()
        self.welcome = LoginWindow()
        self.admin = AdminWindow(session=self.session)
        self.library = LibraryWindow(session=self.session)
        self.main_window = MainWindow()
        self.welcome.sign_in_requested.connect(self.show_admin)
        self.welcome.open_requested.connect(self.show_main)
        self.admin.back_requested.connect(self.show_welcome)
        self.library.back_requested.connect(self.show_welcome)

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
        self.main_window.show()
        self.welcome.hide()
        self.admin.hide()
        self.library.hide()
        self.main_window.raise_()
        self.main_window.activateWindow()
