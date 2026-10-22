"""User workplace and its actions; persistence is delegated to a repository."""

from dataclasses import replace

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QMainWindow, QMessageBox, QTabWidget, QVBoxLayout, QWidget,
)

from .applications.dialogs import ApplicationDialog
from .graphics.brand import BrandMark
from .graphics.icons import admin_icon
from .shared.confirmation import ConfirmDeleteDialog
from .shared.forms import action, caption
from .state import LibrarySession, WorkplaceConfig
from .storage import StorageError
from .styles import load_stylesheets
from .websites.dialogs import WebsiteDialog
from .workplace.launching import ResourceLauncher
from .workplace.models import resolve_entry, workplace_entries
from .workplace.page import WorkplacePage


class MainWindow(QMainWindow):
    back_requested = Signal()

    def __init__(self, parent=None, *, session=None, config=None, repository=None, launcher=None):
        super().__init__(parent)
        self.session = (session if session is not None else repository.load_catalog()
                        if repository is not None else LibrarySession())
        self.config = (config if config is not None else repository.load_workplace()
                       if repository is not None else WorkplaceConfig())
        self.repository = repository
        self.catalog_reload_blocked = False
        self.launcher = launcher if launcher is not None else ResourceLauncher()
        self.setObjectName("mainWindow")
        self.setWindowTitle("TSLibrary — Your workplace")
        self.setWindowIcon(admin_icon("library", "#c9b18c"))
        self.setMinimumSize(820, 650)
        self.resize(1320, 850)
        self.setStyleSheet(load_stylesheets("base", "admin", "library", "main"))
        content = QWidget()
        content.setObjectName("mainContent")
        self.setCentralWidget(content)
        root = QVBoxLayout(content)
        self.content_layout = root
        self._compact_layout = None
        root.setContentsMargins(34, 25, 34, 13)
        root.setSpacing(18)
        header = QHBoxLayout()
        header.addWidget(BrandMark())
        header.addStretch()
        header.addWidget(caption("A WORKPLACE OF YOUR OWN", "workplaceEyebrow", wrap=False))
        header.addSpacing(18)
        back = action("Back to welcome", "workplaceSecondary")
        back.setIcon(admin_icon("back"))
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("workplaceTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.pages = {}
        for kind, name, symbol in [("websites", "Websites", "websites"),
                                   ("applications", "Applications", "applications"),
                                   ("collection", "Collection", "library")]:
            page = WorkplacePage(kind, self.session, self.config)
            self.pages[kind] = page
            self.tabs.addTab(page, admin_icon(symbol), name)
            page.add_personal_requested.connect(self.add_personal)
            page.browse_requested.connect(self.browse_collection)
            page.toggle_requested.connect(self.toggle_catalog_entry)
            page.edit_requested.connect(self.edit_personal)
            page.remove_requested.connect(self.remove_entry)
            page.open_requested.connect(self.open_entry)
            page.refresh_requested.connect(self.reload_catalog)
        self.websites_page = self.pages["websites"]
        self.applications_page = self.pages["applications"]
        self.collection_page = self.pages["collection"]
        root.addWidget(self.tabs, 1)
        footer = QHBoxLayout()
        self.summary_label = caption("", "workplaceMuted", wrap=False)
        footer.addWidget(self.summary_label)
        footer.addStretch()
        footer.addWidget(caption("Your selections. Your space.", "workplaceMuted", wrap=False))
        root.addLayout(footer)
        self.tabs.currentChanged.connect(self.refresh)
        self.statusBar().setSizeGripEnabled(False)
        self.refresh()

    def refresh(self, *_):
        for page in self.pages.values():
            page.config = self.config
            page.refresh()
        sites = len(workplace_entries(self.session, self.config, "websites"))
        apps = len(workplace_entries(self.session, self.config, "applications"))
        self.summary_label.setText(f"{sites} {'website' if sites == 1 else 'websites'} · "
                                   f"{apps} {'application' if apps == 1 else 'applications'} in your workplace")

    def browse_collection(self):
        self.tabs.setCurrentWidget(self.collection_page)

    def reload_catalog(self):
        if self.catalog_reload_blocked:
            QMessageBox.warning(self, "Admin changes have not been saved",
                                "Return to Administration and save an entry again before refreshing the Collection.")
            return
        if self.repository is not None:
            try:
                loaded = self.repository.load_catalog()
            except StorageError as error:
                QMessageBox.warning(self, "Could not refresh Collection", str(error))
                return
            self.session.applications[:] = loaded.applications
            self.session.websites[:] = loaded.websites
        self.refresh()

    def _commit(self, config):
        try:
            if self.repository is not None:
                self.repository.save_workplace(config)
        except StorageError as error:
            QMessageBox.warning(self, "Could not save your workplace", str(error))
            return False
        self.config = config
        self.refresh()
        return True

    def toggle_catalog_entry(self, entry):
        if entry.source != "catalog" or resolve_entry(self.session, self.config, entry) is None:
            self.refresh()
            return
        field = "website_ids" if entry.kind == "websites" else "application_ids"
        ids = list(getattr(self.config, field))
        added = entry.id not in ids
        if added:
            ids.append(entry.id)
        else:
            ids.remove(entry.id)
        if self._commit(replace(self.config, **{field: ids})):
            self.statusBar().showMessage(f"{'Added' if added else 'Removed'} “{entry.name}” "
                                         f"{'to' if added else 'from'} your workplace.", 4500)

    def add_personal(self, kind):
        self._personal_dialog(kind)

    def edit_personal(self, entry):
        if entry.source == "personal":
            self._personal_dialog(entry.kind, entry)

    def _personal_dialog(self, kind, entry=None):
        original = resolve_entry(self.session, self.config, entry) if entry else None
        if entry and original is None:
            self.refresh()
            return
        dialog = (WebsiteDialog(self, website=original) if kind == "websites"
                  else ApplicationDialog(self, application=original))
        noun = "website" if kind == "websites" else "application"
        dialog.setWindowTitle(f"TSLibrary — {'Edit' if original else 'Add'} personal {noun}")
        # Keep values available for retry if a save fails after validation.
        self.personal_dialog = dialog
        dialog.accepted.connect(lambda: self._save_personal(dialog, kind, entry))
        dialog.rejected.connect(dialog.deleteLater)
        dialog.open()

    def _save_personal(self, dialog, kind, entry):
        record = dialog.website() if kind == "websites" else dialog.application()
        field = "personal_websites" if kind == "websites" else "personal_applications"
        records = list(getattr(self.config, field))
        if entry:
            record.id = entry.id
            records = [record if item.id == entry.id else item for item in records]
        else:
            records.append(record)
        if self._commit(replace(self.config, **{field: records})):
            self.statusBar().showMessage(f"Saved “{record.name}” to your workplace.", 4500)
            dialog.deleteLater()
        else:
            QTimer.singleShot(0, dialog.open)

    def remove_entry(self, entry):
        if entry.source == "catalog":
            field = "website_ids" if entry.kind == "websites" else "application_ids"
            if entry.id in getattr(self.config, field):
                self.toggle_catalog_entry(entry)
            return
        dialog = ConfirmDeleteDialog("Remove personal entry",
            f'Remove “{entry.name}” from your workplace? The file or website itself is kept.',
            self, section="YOUR WORKPLACE")
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.accepted.connect(lambda: self._remove_personal(entry))
        self.remove_dialog = dialog
        dialog.open()

    def _remove_personal(self, entry):
        field = "personal_websites" if entry.kind == "websites" else "personal_applications"
        records = [item for item in getattr(self.config, field) if item.id != entry.id]
        self._commit(replace(self.config, **{field: records}))

    def open_entry(self, entry):
        record = resolve_entry(self.session, self.config, entry)
        if record is None:
            self.refresh()
            return
        try:
            if entry.kind == "websites":
                self.launcher.open_website(record)
            else:
                self.launcher.open_application(record)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, f"Could not open {entry.name}", str(error))
            return
        self.statusBar().showMessage(f"Opening “{entry.name}”…", 4500)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "pages"):
            return
        compact = self.height() < 750 or self.width() < 1000
        if compact == self._compact_layout:
            return
        self._compact_layout = compact
        self.content_layout.setContentsMargins(24 if compact else 34, 14 if compact else 25,
                                               24 if compact else 34, 10 if compact else 13)
        self.content_layout.setSpacing(10 if compact else 18)
        for page in self.pages.values():
            page.content_layout.setContentsMargins(0, 12 if compact else 27, 0, 0)
            page.heading.setStyleSheet("font-size: 32px;" if compact else "")
