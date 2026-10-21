"""Add/edit a website address and confirm list-entry removal."""

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from ..shared.forms import action, caption
from ..shared.confirmation import ConfirmDeleteDialog
from .models import Website
from .icons import website_icon
from .urls import normalize_website_url, website_name


class WebsiteDialog(QDialog):
    def __init__(self, parent=None, *, website=None):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        self.setWindowTitle("TSLibrary — Edit website" if website else "TSLibrary — Add website")
        self.setMinimumWidth(560)
        self.resize(620, 440)
        self._suggested_name = ""
        self._url = ""
        self._icon = QIcon(website.icon) if website else website_icon()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(10)
        layout.addWidget(caption("WEBSITES  /  WEBSITE DETAILS" if website else
                                 "WEBSITES  /  NEW WEBSITE", "adminEyebrow"))
        layout.addWidget(caption("Edit website" if website else "Add website", "dialogHeading"))
        preview = QHBoxLayout()
        preview.setSpacing(16)
        self.icon_preview = QLabel()
        self.icon_preview.setObjectName("applicationIcon")
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_preview.setAccessibleName("Website icon preview")
        self.icon_preview.setPixmap(self._icon.pixmap(QSize(40, 40)))
        preview.addWidget(self.icon_preview)
        self.icon_description = caption("A home for a useful website. Start with its address.")
        preview.addWidget(self.icon_description, 1)
        layout.addLayout(preview)
        layout.addSpacing(8)
        url_label = caption("Website URL", "fieldLabel")
        layout.addWidget(url_label)
        self.url_edit = QLineEdit(website.url if website else "")
        self.url_edit.setObjectName("dialogInput")
        self.url_edit.setAccessibleName("Website URL")
        self.url_edit.setPlaceholderText("https://example.com")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.setInputMethodHints(Qt.InputMethodHint.ImhUrlCharactersOnly)
        url_label.setBuddy(self.url_edit)
        layout.addWidget(self.url_edit)
        layout.addWidget(caption("Enter an http:// or https:// address. Bare domains use https://.",
                                 "adminMuted"))
        name_label = caption("Website name", "fieldLabel")
        layout.addWidget(name_label)
        self.name_edit = QLineEdit(website.name if website else "")
        self.name_edit.setObjectName("dialogInput")
        self.name_edit.setAccessibleName("Website name")
        self.name_edit.setPlaceholderText("Filled from the domain; you can change it")
        self.name_edit.setMaxLength(150)
        name_label.setBuddy(self.name_edit)
        layout.addWidget(self.name_edit)
        self.error = caption("", "formError")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = action("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        self.save_button = action("Save changes" if website else "Add website", "adminPrimary")
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(180)
        self.preview_timer.timeout.connect(self._update_preview)
        self.url_edit.textChanged.connect(lambda _: self.preview_timer.start())
        self.url_edit.returnPressed.connect(self._url_entered)
        self.name_edit.returnPressed.connect(self._save)
        self._update_preview()
        self.url_edit.setFocus()

    def _url_entered(self):
        self.preview_timer.stop()
        self._update_preview()
        self.name_edit.setFocus()

    def _update_preview(self):
        try:
            url = normalize_website_url(self.url_edit.text())
        except ValueError:
            self.icon_description.setText("A home for a useful website. Start with its address.")
            return
        suggested = website_name(url)
        if not self.name_edit.text().strip() or self.name_edit.text() == self._suggested_name:
            self.name_edit.setText(suggested)
        self._suggested_name = suggested
        self.icon_description.setText(suggested)

    def _save(self):
        self.preview_timer.stop()
        try:
            self._url = normalize_website_url(self.url_edit.text())
        except ValueError as error:
            self.error.setText(str(error))
            self.url_edit.setFocus()
            return
        self._update_preview()
        self.error.clear()
        self.accept()

    def website(self):
        return Website(self.name_edit.text().strip() or website_name(self._url),
                       self._url, QIcon(self._icon))


class DeleteWebsiteDialog(ConfirmDeleteDialog):
    def __init__(self, website, parent=None):
        super().__init__("Remove website", f'Remove “{website.name}” from the website list?',
                         parent, section="WEBSITES")
