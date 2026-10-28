"""Name documentation folders and browse or attach their shared files."""

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLineEdit, QListWidget, QVBoxLayout,
)

from ..shared.forms import action, caption
from ..shared.controls import FilterCombo
from .files import DocumentationError, DocumentationFiles
from .models import item_name


class DocumentationConnectionsDialog(QDialog):
    def __init__(self, path, kind, parent=None):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        self.setWindowTitle("TSLibrary — Documentation connections")
        self.setMinimumWidth(480)
        self.resize(620, 360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)
        layout.addWidget(caption("DOCUMENTATION  /  CONNECTIONS", "adminEyebrow"))
        layout.addWidget(caption("Connect this " + kind, "dialogHeading"))
        self.name_edit = QLineEdit(path)
        self.name_edit.setObjectName("dialogInput")
        self.name_edit.setReadOnly(True)
        self.name_edit.setAccessibleName("Documentation path")
        layout.addWidget(self.name_edit)
        self.error = caption("", "formError")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = action("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save_button = action("Save connections", "adminPrimary")
        self.save_button.clicked.connect(self.accept)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)


class DocumentationItemDialog(QDialog):
    def __init__(self, parent=None, *, item=None, folder="", folders=()):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        self.setWindowTitle("TSLibrary — " + ("Edit folder" if item else "New folder"))
        self.setMinimumWidth(460)
        self.resize(560, 320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)
        layout.addWidget(caption("DOCUMENTATION  /  ITEM DETAILS", "adminEyebrow"))
        layout.addWidget(caption("Edit folder" if item else "New folder", "dialogHeading"))
        layout.addWidget(caption("Create a folder for your documents, then use Add files to put documents inside it."))
        layout.addWidget(caption("Parent folder (optional)", "fieldLabel"))
        self.folder_edit = FilterCombo()
        self.folder_edit.setEditable(True)
        self.folder_edit.setAccessibleName("Documentation parent folder")
        self.folder_edit.addItems([""] + sorted(folders, key=str.casefold))
        self.folder_edit.setMinimumHeight(42)
        self.folder_edit.setCurrentText(item.name.rpartition("/")[0] if item else folder)
        self.folder_edit.lineEdit().setPlaceholderText("e.g. Microsoft/Word")
        layout.addWidget(self.folder_edit)
        label = caption("Folder name", "fieldLabel")
        layout.addWidget(label)
        self.name_edit = QLineEdit(item.name.rpartition("/")[2] if item else "")
        self.name_edit.setObjectName("dialogInput")
        self.name_edit.setAccessibleName("Documentation item name")
        self.name_edit.setPlaceholderText("e.g. Word")
        self.name_edit.setMaxLength(220)
        label.setBuddy(self.name_edit)
        layout.addWidget(self.name_edit)
        self.error = caption("", "formError")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = action("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save_button = action("Save changes" if item else "Add item", "adminPrimary")
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.name_edit.returnPressed.connect(self._save)

    def _save(self):
        try:
            name = self.name_edit.text().strip()
            folder = self.folder_edit.currentText().strip().strip("/")
            self.name = item_name(name if "/" in name or "\\" in name or not folder else folder + "/" + name)
        except ValueError as error:
            self.error.setText(str(error))
            return
        self.accept()


class ImportSignals(QObject):
    succeeded = Signal(list)
    failed = Signal(str)
    finished = Signal()


class ImportFiles(QRunnable):
    def __init__(self, files, name, sources):
        super().__init__()
        self.files, self.name, self.sources = files, name, sources
        self.signals = ImportSignals()

    def run(self):
        try:
            result = self.files.add_files(self.name, self.sources)
        except (OSError, ValueError, DocumentationError) as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


class DocumentationFilesDialog(QDialog):
    files_changed = Signal()

    def __init__(self, catalog, item, parent=None, *, editable=False):
        super().__init__(parent)
        self.files = DocumentationFiles(catalog)
        self.item = item
        self.editable = editable
        self.busy = False
        self.setObjectName("inventoryDialog")
        self.setWindowTitle(f"TSLibrary — {item.name}")
        self.resize(760, 560)
        self.setMinimumSize(530, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(13)
        layout.addWidget(caption("DOCUMENTATION  /  SHARED FILES", "adminEyebrow"))
        layout.addWidget(caption(item.name, "dialogHeading"))
        self.path_label = caption("", "adminMuted")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.path_label)
        self.file_list = QListWidget()
        self.file_list.setObjectName("documentationFiles")
        self.file_list.setAccessibleName("Documentation files")
        self.file_list.itemDoubleClicked.connect(lambda _: self.open_file())
        layout.addWidget(self.file_list, 1)
        self.message = caption("", "formError")
        layout.addWidget(self.message)
        buttons = QHBoxLayout()
        self.add_button = action("Add files…", "adminPrimary")
        self.add_button.setVisible(editable)
        self.add_button.clicked.connect(self.choose_files)
        buttons.addWidget(self.add_button)
        self.refresh_button = action("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        buttons.addWidget(self.refresh_button)
        self.open_button = action("Open file")
        self.open_button.clicked.connect(self.open_file)
        buttons.addWidget(self.open_button)
        buttons.addStretch()
        close = action("Close")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        self.file_list.clear()
        try:
            self.path_label.setText(str(self.files.item_path(self.item.name)))
            # Registered sub-documents own their attachments. Do not show their
            # files again as attachments of a parent that also has its own files.
            prefix = self.item.name + "/"
            child_roots = [entry.name[len(prefix):].casefold() + "/"
                           for entry in self.files.catalog.items if entry.name.casefold().startswith(prefix.casefold())]
            self.file_list.addItems([relative for relative in self.files.list_files(self.item.name)
                                     if not any(relative.casefold().startswith(child) for child in child_roots)])
        except (OSError, ValueError, DocumentationError) as error:
            self.message.setText(str(error))
            self.open_button.setEnabled(False)
            return
        self.message.setText("No files yet. Add files to share them." if self.editable and not self.file_list.count()
                             else "No files have been added yet." if not self.file_list.count() else "")
        self.open_button.setEnabled(bool(self.file_list.count()))
        if self.file_list.count():
            self.file_list.setCurrentRow(0)

    def choose_files(self):
        if not self.editable or self.busy:
            return
        sources, _ = QFileDialog.getOpenFileNames(self, "Add documentation files", "", "All files (*)")
        if sources:
            self.import_files(sources)

    def import_files(self, sources):
        if not self.editable or self.busy:
            return
        self.busy = True
        self.add_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.message.setText("Copying files to the shared folder…")
        self.task = ImportFiles(self.files, self.item.name, sources)
        self.task.signals.succeeded.connect(self._imported)
        self.task.signals.failed.connect(self.message.setText)
        self.task.signals.finished.connect(self._finished)
        QThreadPool.globalInstance().start(self.task)

    def _imported(self, names):
        self.refresh()
        self.message.setText(f"Added {len(names)} {'file' if len(names) == 1 else 'files'}. Your sync service handles sharing.")
        self.files_changed.emit()

    def _finished(self):
        self.busy = False
        self.add_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.open_button.setEnabled(bool(self.file_list.count()))

    def open_file(self):
        selected = self.file_list.currentItem()
        if selected is None or self.busy:
            return
        try:
            path = self.files.file_path(self.item.name, selected.text())
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise DocumentationError("No application could open this file.")
        except (OSError, ValueError, DocumentationError) as error:
            self.message.setText(str(error))

    def reject(self):
        if not self.busy:
            super().reject()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        else:
            super().closeEvent(event)
