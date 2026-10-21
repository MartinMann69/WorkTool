"""UI preview navigation only. This controller does not authenticate admins."""

from PySide6.QtCore import QObject

from .admin import AdminWindow
from .welcome import LoginWindow


class PreviewController(QObject):
    def __init__(self):
        super().__init__()
        self.welcome = LoginWindow()
        self.admin = AdminWindow()
        self.welcome.sign_in_requested.connect(self.show_admin)
        self.admin.back_requested.connect(self.show_welcome)

    def show_admin(self, _username="", _password=""):
        # This is a layout preview, not an authentication or authorization gate.
        self.welcome.password_field.edit.clear()
        self.welcome.password_field.toggle.setChecked(False)
        self.admin.show()
        self.welcome.hide()
        self.admin.raise_()
        self.admin.activateWindow()

    def show_welcome(self):
        self.welcome.show()
        self.admin.hide()
        self.welcome.raise_()
        self.welcome.activateWindow()
