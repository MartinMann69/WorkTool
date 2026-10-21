"""Add/edit an application or shortcut and confirm list-entry removal."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QStyle, QVBoxLayout,
)

from ..shared.forms import action, caption
from ..shared.confirmation import ConfirmDeleteDialog
from .targets import parse_launch_target, format_launch_target
from .icons import executable_icon
from .models import Application


class ApplicationDialog(QDialog):
    def __init__(self, parent=None, *, application=None):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        self.setWindowTitle("TSLibrary — Edit application" if application else "TSLibrary — Add application")
        self.setMinimumWidth(560)
        self.resize(620, 465)
        self._suggested_name = ""
        self._selected_path = None
        self._selected_icon = QIcon()
        self._selected_arguments = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(10)
        layout.addWidget(caption("APPLICATIONS  /  APPLICATION DETAILS" if application else
                                 "APPLICATIONS  /  NEW APPLICATION", "adminEyebrow"))
        layout.addWidget(caption("Edit application" if application else "Add application", "dialogHeading"))
        preview = QHBoxLayout()
        preview.setSpacing(16)
        self.icon_preview = QLabel()
        self.icon_preview.setObjectName("applicationIcon")
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_preview.setAccessibleName("Application icon preview")
        preview.addWidget(self.icon_preview)
        self.icon_description = caption("Choose an .exe or .lnk shortcut. Its icon is picked up automatically.")
        preview.addWidget(self.icon_description, 1)
        layout.addLayout(preview)
        layout.addSpacing(8)
        path_label = caption("Launch target", "fieldLabel")
        layout.addWidget(path_label)
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(application.launch_target if application else "")
        self.path_edit.setObjectName("dialogInput")
        self.path_edit.setAccessibleName("Launch target")
        self.path_edit.setPlaceholderText(r'"C:\Program Files\App\app.exe" -launch -reg')
        self.path_edit.setClearButtonEnabled(True)
        path_label.setBuddy(self.path_edit)
        path_row.addWidget(self.path_edit, 1)
        self.browse_button = action("Browse…")
        self.browse_button.clicked.connect(self.browse)
        path_row.addWidget(self.browse_button)
        layout.addLayout(path_row)
        layout.addWidget(caption('Optional arguments go after the path. Put paths with spaces in quotes.',
                                 "adminMuted"))
        layout.addWidget(caption("Application name", "fieldLabel"))
        self.name_edit = QLineEdit(application.name if application else "")
        self.name_edit.setObjectName("dialogInput")
        self.name_edit.setAccessibleName("Application name")
        self.name_edit.setPlaceholderText("Filled from the selected file; you can change it")
        self.name_edit.setMaxLength(150)
        layout.addWidget(self.name_edit)
        self.error = caption("", "formError")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = action("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        self.save_button = action("Save changes" if application else "Add application", "adminPrimary")
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(180)
        self.preview_timer.timeout.connect(self._update_preview)
        self.path_edit.textChanged.connect(lambda _: self.preview_timer.start())
        self.path_edit.returnPressed.connect(self._path_entered)
        self.name_edit.returnPressed.connect(self._save)
        self._update_preview()
        self.path_edit.setFocus()

    def browse(self):
        try:
            current_path, arguments = parse_launch_target(self.path_edit.text())
            start = str(current_path)
        except ValueError:
            start, arguments = str(Path.home()), ""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Choose an application or shortcut", start,
            "Applications and shortcuts (*.exe *.lnk);;Executables (*.exe);;Windows shortcuts (*.lnk)",
            options=QFileDialog.Option.DontResolveSymlinks)
        if filename:
            self.path_edit.setText(format_launch_target(filename, arguments))
            self.preview_timer.stop()
            self._update_preview()
            self.name_edit.setFocus()

    def _path_entered(self):
        self.preview_timer.stop()
        self._update_preview()
        self.name_edit.setFocus()

    def _update_preview(self):
        try:
            path, arguments = parse_launch_target(self.path_edit.text())
        except ValueError:
            self._selected_path = None
            self._selected_icon = QIcon()
            self._selected_arguments = ""
            fallback = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            self.icon_preview.setPixmap(fallback.pixmap(QSize(36, 36)))
            self.icon_description.setText("Choose an .exe or .lnk shortcut. Its icon is picked up automatically.")
            return
        # Extract once per path change, not on every unrelated name edit.
        if path != self._selected_path:
            self._selected_path = path
            self._selected_icon = executable_icon(path)
        self._selected_arguments = arguments
        if not self.name_edit.text().strip() or self.name_edit.text() == self._suggested_name:
            self.name_edit.setText(path.stem)
        self._suggested_name = path.stem
        self.icon_preview.setPixmap(self._selected_icon.pixmap(QSize(40, 40)))
        self.icon_description.setText(f"Icon from {path.name}")

    def _save(self):
        self.preview_timer.stop()
        try:
            parse_launch_target(self.path_edit.text())
        except ValueError as error:
            self.error.setText(str(error))
            self.path_edit.setFocus()
            return
        self._update_preview()
        self.error.clear()
        self.accept()

    def application(self):
        return Application(self.name_edit.text().strip() or self._selected_path.stem,
                           str(self._selected_path), QIcon(self._selected_icon),
                           arguments=self._selected_arguments)


class DeleteApplicationDialog(ConfirmDeleteDialog):
    def __init__(self, application, parent=None):
        super().__init__("Remove application", f'Remove “{application.name}” from the application list? '
                         "The application or shortcut file on disk will be kept.", parent, section="APPLICATIONS")
