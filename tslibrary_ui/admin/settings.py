"""Admin team connection and documentation defaults, separate from inventories."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QVBoxLayout, QWidget,
)

from ..documentation.files import DocumentationError, DocumentationFiles
from ..documentation.models import DocumentationCatalog, folder_name
from ..shared.forms import action, caption


class SettingsPage(QWidget):
    create_requested = Signal(str)
    open_requested = Signal(str)
    refresh_requested = Signal()
    retry_requested = Signal()
    changed = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.repository = None
        self._loaded_documentation = None
        self.setObjectName("adminMain")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(38, 30, 38, 23)
        self.content_layout.setSpacing(12)
        self.content_layout.addWidget(caption("ADMINISTRATION  /  SETTINGS", "adminEyebrow"))
        self.heading = caption("Settings", "adminHeading")
        self.content_layout.addWidget(self.heading)
        self.content_layout.addWidget(caption("One shared catalog for your team. Your own workplace stays personal."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_layout.addWidget(scroll, 1)
        body = QWidget()
        body.setObjectName("settingsBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.setSpacing(18)

        connection = QFrame()
        connection.setObjectName("settingsSection")
        fields = QVBoxLayout(connection)
        fields.setContentsMargins(18, 16, 18, 16)
        fields.setSpacing(10)
        fields.addWidget(caption("Team configuration", "settingsHeading"))
        fields.addWidget(caption("Create a configuration in a shared network folder, then have the other admin open that same file.", "adminMuted"))
        self.connection_label = self._path_label()
        self.catalog_label = self._path_label()
        fields.addWidget(caption("Configuration file", "fieldLabel"))
        fields.addWidget(self.connection_label)
        fields.addWidget(caption("Catalog file", "fieldLabel"))
        fields.addWidget(self.catalog_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.create_button = action("Create configuration…", "adminPrimary")
        self.open_button = action("Open configuration…")
        self.refresh_button = action("Reload catalog")
        self.create_button.clicked.connect(self.choose_new_configuration)
        self.open_button.clicked.connect(self.choose_configuration)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        for button in (self.create_button, self.open_button, self.refresh_button):
            buttons.addWidget(button)
        buttons.addStretch()
        fields.addLayout(buttons)
        self.connection_message = caption("Local catalog. Create or open a team configuration to share it.", "adminMuted")
        fields.addWidget(self.connection_message)
        self.retry_button = action("Retry saving unsaved changes")
        self.retry_button.clicked.connect(self.retry_requested.emit)
        self.retry_button.hide()
        fields.addWidget(self.retry_button)
        layout.addWidget(connection)

        panel = QFrame()
        panel.setObjectName("documentationSettings")
        grid = QGridLayout(panel)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.addWidget(caption("Documentation", "settingsHeading"), 0, 0, 1, 3)
        grid.addWidget(caption("Shared location", "fieldLabel"), 1, 0)
        self.location_edit = QLineEdit()
        self.location_edit.setObjectName("dialogInput")
        self.location_edit.setAccessibleName("Shared documentation parent folder")
        self.location_edit.setPlaceholderText(r"\\server\team\documentation")
        grid.addWidget(self.location_edit, 1, 1)
        self.browse_button = action("Browse…")
        self.browse_button.clicked.connect(self.browse_location)
        grid.addWidget(self.browse_button, 1, 2)
        grid.addWidget(caption("Root folder name", "fieldLabel"), 2, 0)
        self.root_name_edit = QLineEdit()
        self.root_name_edit.setObjectName("dialogInput")
        self.root_name_edit.setAccessibleName("Documentation root folder name")
        self.root_name_edit.setMaxLength(120)
        grid.addWidget(self.root_name_edit, 2, 1)
        self.save_location_button = action("Save location", "adminPrimary")
        self.save_location_button.clicked.connect(self.save_location)
        grid.addWidget(self.save_location_button, 2, 2)
        self.settings_message = caption("These defaults are saved in the catalog and shared with the other admin. Changing the path does not move files; copy existing documentation to the new location first.", "adminMuted")
        grid.addWidget(self.settings_message, 3, 0, 1, 3)
        grid.setColumnStretch(1, 1)
        layout.addWidget(panel)
        layout.addStretch()
        self.bind_repository(None)
        self.refresh()

    @staticmethod
    def _path_label():
        label = caption("", "settingsPath")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setMinimumWidth(0)
        return label

    @property
    def dirty(self):
        return self._loaded_documentation != (self.location_edit.text(), self.root_name_edit.text())

    def bind_repository(self, repository):
        self.repository = repository
        enabled = repository is not None and hasattr(repository, "select_team")
        self.create_button.setEnabled(enabled)
        self.open_button.setEnabled(enabled)
        self.refresh_button.setEnabled(repository is not None)
        self.refresh()

    def refresh(self, *_):
        repo = self.repository
        profile = getattr(repo, "team_config_path", None)
        path = getattr(getattr(repo, "catalog_store", None), "path", None)
        self.connection_label.setText(str(profile) if profile else "No team configuration selected")
        self.catalog_label.setText(str(path) if path else "In-memory preview")
        # Do not replace a documentation draft when another tab refreshes.
        if self._loaded_documentation is None or not self.dirty:
            self.reload_settings()

    def reload_settings(self):
        docs = self.session.documentation
        self.location_edit.setText(docs.parent_path)
        self.root_name_edit.setText(docs.root_name)
        self._loaded_documentation = (docs.parent_path, docs.root_name)

    def set_status(self, message, *, unsaved=False):
        self.connection_message.setText(message)
        self.connection_message.setObjectName("formError" if unsaved else "adminMuted")
        self.connection_message.style().unpolish(self.connection_message)
        self.connection_message.style().polish(self.connection_message)
        self.retry_button.setVisible(unsaved)

    def choose_new_configuration(self):
        path, _ = QFileDialog.getSaveFileName(self, "Create team configuration in a shared folder", "TSLibrary-team.json", "TSLibrary team configuration (*.json)")
        if path:
            self.create_requested.emit(path)

    def choose_configuration(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open shared team configuration", "", "TSLibrary team configuration (*.json)")
        if path:
            self.open_requested.emit(path)

    def browse_location(self):
        path = QFileDialog.getExistingDirectory(self, "Choose shared documentation folder", self.location_edit.text())
        if path:
            self.location_edit.setText(path)

    def save_location(self):
        try:
            parent = self.location_edit.text().strip()
            root_name = folder_name(self.root_name_edit.text().strip())
            docs = self.session.documentation
            if self._loaded_documentation != (docs.parent_path, docs.root_name):
                raise DocumentationError("The documentation defaults changed since you began editing. Reload the catalog before saving these settings.")
            proposed = DocumentationCatalog(parent, root_name, docs.items)
            # Validate against the actual shared path, not a per-PC override.
            from os import environ
            if environ.get("TSLIBRARY_DOCUMENTS_PATH") and (parent, root_name) != (docs.parent_path, docs.root_name):
                raise DocumentationError("Remove TSLIBRARY_DOCUMENTS_PATH on this admin PC before changing shared storage.")
            files = DocumentationFiles(proposed)
            destination = files.root()
            if docs.items:
                if any(not files.item_path(item.name).is_dir() for item in docs.items):
                    raise DocumentationError("The new location must contain every existing documentation folder. Copy the files there before saving this path.")
            else:
                destination.mkdir(exist_ok=True)
            docs.parent_path, docs.root_name = parent, root_name
        except (OSError, ValueError, DocumentationError) as error:
            self.settings_message.setText(str(error))
            return
        self.location_edit.setText(parent)
        self.root_name_edit.setText(root_name)
        self._loaded_documentation = (parent, root_name)
        self.settings_message.setText("Documentation location updated. Existing files were kept in place.")
        self.changed.emit()
