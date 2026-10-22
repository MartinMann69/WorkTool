"""Add/edit a phone app by name and confirm list-entry removal."""

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from ..shared.confirmation import ConfirmDeleteDialog
from ..shared.forms import action, caption
from .models import PhoneApp


class PhoneAppDialog(QDialog):
    def __init__(self, parent=None, *, phone_app=None):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        title = "Edit phone app" if phone_app else "Add phone app"
        self.setWindowTitle(f"TSLibrary — {title}")
        self.setMinimumWidth(480)
        self.resize(560, 310)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)
        layout.addWidget(caption("PHONE APPS  /  APP DETAILS" if phone_app else
                                 "PHONE APPS  /  NEW APP", "adminEyebrow"))
        layout.addWidget(caption(title, "dialogHeading"))
        layout.addWidget(caption("Keep track of the phone apps you have. Only a name is needed."))
        layout.addSpacing(8)
        name_label = caption("App name", "fieldLabel")
        layout.addWidget(name_label)
        self.name_edit = QLineEdit(phone_app.name if phone_app else "")
        self.name_edit.setObjectName("dialogInput")
        self.name_edit.setAccessibleName("App name")
        self.name_edit.setPlaceholderText("e.g. Microsoft Teams")
        self.name_edit.setMaxLength(150)
        self.name_edit.setClearButtonEnabled(True)
        name_label.setBuddy(self.name_edit)
        layout.addWidget(self.name_edit)
        self.error = caption("", "formError")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = action("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        self.save_button = action("Save changes" if phone_app else "Add phone app", "adminPrimary")
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.name_edit.returnPressed.connect(self._save)
        self.name_edit.setFocus()

    def _save(self):
        if not self.name_edit.text().strip():
            self.error.setText("Enter an app name.")
            self.name_edit.setFocus()
            return
        self.error.clear()
        self.accept()

    def phone_app(self):
        return PhoneApp(self.name_edit.text().strip())


class DeletePhoneAppDialog(ConfirmDeleteDialog):
    def __init__(self, phone_app, parent=None):
        super().__init__("Remove phone app", f'Remove “{phone_app.name}” from the phone app list?',
                         parent, section="PHONE APPS")
