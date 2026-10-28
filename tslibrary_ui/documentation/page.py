"""Documentation inventory and file access; defaults live in admin Settings."""

from contextlib import nullcontext
from html import escape
import os
from pathlib import Path
from urllib.parse import quote, unquote

from PySide6.QtCore import Qt, Signal, QSignalBlocker, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMenu, QWidget

from ..graphics.icons import admin_icon
from ..shared.catalog_page import CatalogPage
from ..shared.confirmation import ConfirmDeleteDialog
from ..shared.forms import action, caption
from ..shared.tables import button_cell, cell, preserve_selection
from ..storage import StorageError
from ..relationships import valid_links
from .dialogs import DocumentationConnectionsDialog, DocumentationItemDialog, ImportFiles
from .browser_files import ReadDirectory, DeleteStaged
from .files import DocumentationError, DocumentationFiles
from .models import DocumentationItem, DocumentationCatalog
from .navigation import DocumentationFolders, DocumentationNameDelegate, DocumentationStatus, PARENT_ROLE, FOLDER_ROLE, FILE_ROLE, browse_rows


class DocumentationPage(CatalogPage):
    changed = Signal()
    refresh_requested = Signal()
    filesystem_changed = Signal()
    title = "Documentation"
    description = "Browse your shared folders and open files directly."
    empty_title = "A place for your team's knowledge."
    empty_description_text = "Choose a shared location in Settings, then add your first documentation item."
    add_text = "New folder"
    empty_action = "Create your first folder"
    search_text = "Search documentation"
    headers = ("NAME", "")

    def __init__(self, session, parent=None, *, editable=True):
        self.session, self.editable = session, editable
        self.files_dialog = None
        self.busy = False
        self.directory_loading = False
        self._directory_jobs = {}
        self._current_read = None
        self._listing_key = None
        self._disk_entries = []
        self._known_folders = set()
        self._directory_error = ""
        self._import_message = ""
        self._root_key = None
        self.write_guard = nullcontext
        self.persist_change = lambda: None
        self.selected_folder = ""
        super().__init__(parent)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 252 if editable else 148)
        self.table.setItemDelegateForColumn(0, DocumentationNameDelegate(self.table))
        self.table.cellDoubleClicked.connect(self._open_row)
        if editable:
            self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.table.customContextMenuRequested.connect(self._row_context_menu)
            self.folder_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.folder_tree.customContextMenuRequested.connect(self._folder_context_menu)
        self.add_requested.connect(self.add_item)
        if not editable:
            self.breadcrumb.setText("YOUR WORKPLACE  /  DOCUMENTATION")
            for badge in self.findChildren(QLabel):
                if badge.objectName() == "adminBadge":
                    badge.setText("READ ONLY")
            self.add_button.setText("Refresh")
            self.add_button.setIcon(admin_icon("documentation"))
            self.add_requested.disconnect(self.add_item)
            self.add_requested.connect(self.refresh_requested.emit)
            self.empty_button.hide()
            self.empty_description_text = "Shared documentation will appear here when your administrator adds it."
            self.storage_status.setText("SHARED DOCUMENTATION")
        self.refresh()

    def _build_content(self):
        super()._build_content()
        index = self.content_layout.indexOf(self.content_stack)
        self.content_layout.removeWidget(self.content_stack)
        browser = QWidget()
        layout = QHBoxLayout(browser)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.folder_tree = DocumentationFolders()
        layout.addWidget(self.folder_tree, 1)
        layout.addWidget(self.content_stack, 4)
        self.content_layout.insertWidget(index, browser, 1)
        self.folder_tree.currentItemChanged.connect(self._folder_changed)
        bar = QWidget()
        self.folder_bar = QHBoxLayout(bar)
        self.folder_bar.setContentsMargins(0, 0, 0, 0)
        self.folder_bar.setSpacing(12)
        self.up_button = action("Up")
        self.up_button.setFixedHeight(34)
        self.up_button.setIcon(admin_icon("back"))
        self.up_button.clicked.connect(lambda: self.navigate_folder(self.selected_folder.rpartition("/")[0]))
        self.folder_bar.addWidget(self.up_button)
        self.folder_caption = caption("Documentation", "adminMuted")
        self.folder_caption.setTextFormat(Qt.TextFormat.RichText)
        self.folder_caption.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        self.folder_caption.linkActivated.connect(lambda href: self.navigate_folder(unquote(href.removeprefix("folder:"))))
        self.folder_bar.addWidget(self.folder_caption, 1)
        self.explorer_button = action("Open in Explorer")
        self.explorer_button.setFixedHeight(34)
        self.explorer_button.setIcon(admin_icon("folder"))
        self.explorer_button.setToolTip("Open the current documentation folder in Windows File Explorer")
        self.explorer_button.clicked.connect(self.open_in_explorer)
        self.folder_bar.addWidget(self.explorer_button)
        self.add_files_button = action("Add files…", "adminPrimary")
        self.add_files_button.setFixedHeight(34)
        self.add_files_button.clicked.connect(self.choose_files)
        self.add_files_button.setVisible(self.editable)
        self.folder_bar.addWidget(self.add_files_button)
        self.refresh_files_button = action("Refresh")
        self.refresh_files_button.setFixedHeight(34)
        self.refresh_files_button.clicked.connect(lambda: self.reload_files(force=True))
        self.folder_bar.addWidget(self.refresh_files_button)
        self.content_layout.insertWidget(index, bar)
        self.content_layout.insertSpacing(index + 1, 10)

    def _build_footer(self):
        super()._build_footer()
        bottom = self.content_layout.itemAt(self.content_layout.count() - 1).layout()
        bottom.takeAt(1)  # Replace the footer's stretch with the status label.
        bottom.insertSpacing(1, 16)
        self.file_message = DocumentationStatus()
        self.file_message.setFixedHeight(self.count_label.sizeHint().height())
        bottom.insertWidget(2, self.file_message, 1)

    def _folder_changed(self, current, _previous):
        if current is not None:
            if self.busy:
                with QSignalBlocker(self.folder_tree):
                    self.folder_tree.select_path(self.selected_folder)
                return
            current.setExpanded(True)
            with QSignalBlocker(self.search):
                self.search.clear()
            self.selected_folder = current.data(0, Qt.ItemDataRole.UserRole)
            self._import_message = ""
            self.refresh()
            self.reload_files()

    def navigate_folder(self, path):
        if self.busy:
            return
        self._known_folders.add(path)
        self.folder_tree.rebuild(self.catalog.items, self.selected_folder, self._known_folders)
        before = self.folder_tree.currentItem()
        self.folder_tree.select_path(path)
        if self.folder_tree.currentItem() is before:
            self._folder_changed(before, None)

    def _update_breadcrumb(self):
        parts = self.selected_folder.split("/") if self.selected_folder else []
        links = ['<a href="folder:" style="color:#d9c39f">Documentation</a>']
        for index, part in enumerate(parts):
            path = "/".join(parts[:index + 1])
            links.append(f'<a href="folder:{quote(path, safe="")}" style="color:#d9c39f">{escape(part)}</a>')
        prefix = "Search results in " if self.search.text().strip() else ""
        self.folder_caption.setText(prefix + " &nbsp;/&nbsp; ".join(links))
        self.folder_caption.setAccessibleName(prefix + "Documentation" + (" / " + self.selected_folder.replace("/", " / ") if parts else ""))
        self.up_button.setEnabled(bool(parts) and not self.busy)

    def reveal_entry(self, identifier):
        item = next((item for item in self.catalog.items if item.id == identifier), None)
        if item is not None:
            self.folder_tree.select_path(item.name.rpartition("/")[0])

    @property
    def catalog(self):
        return self.session.documentation

    def _busy(self):
        return self.busy

    def _directory_key(self):
        return (self.catalog.parent_path, self.catalog.root_name, os.environ.get("TSLIBRARY_DOCUMENTS_PATH", ""),
                self.selected_folder, bool(self.search.text().strip()))

    def showEvent(self, event):
        super().showEvent(event)
        self.reload_files(force=True)

    def reload_files(self, *, force=False):
        if self.busy:
            return
        key = self._directory_key()
        if not force and key == self._listing_key:
            return
        if key != self._listing_key:
            self._disk_entries = []
        self._listing_key = key
        self._directory_error = ""
        self.directory_loading = True
        snapshot = DocumentationCatalog(self.catalog.parent_path, self.catalog.root_name, list(self.catalog.items))
        job = ReadDirectory(snapshot, self.selected_folder, key[-1])
        self._current_read = job
        self._directory_jobs[id(job)] = job
        job.signals.finished.connect(self._directory_read)
        QThreadPool.globalInstance().start(job)
        self._update_file_message()

    def _directory_read(self, job, entries, error):
        self._directory_jobs.pop(id(job), None)
        if job is not self._current_read or self._listing_key != self._directory_key():
            return
        self._current_read = None
        self.directory_loading = False
        self._directory_error = error
        if not error:
            self._disk_entries = entries
            self._known_folders.update(entry["path"] for entry in entries if entry["folder"])
        self.refresh()

    def _update_file_message(self):
        text = self._import_message if self.busy else self._directory_error or ("Loading files…" if self.directory_loading else self._import_message)
        self.file_message.setText(text)
        self.file_message.setToolTip(text)
        self.explorer_button.setEnabled(not self.busy)
        self.add_files_button.setEnabled(not self.busy and not self.directory_loading and not self._directory_error)
        self.refresh_files_button.setEnabled(not self.busy and not self.directory_loading)

    def choose_files(self):
        if not self.editable or self.busy:
            return
        sources, _ = QFileDialog.getOpenFileNames(self, "Add files to this folder", "", "All files (*)")
        if sources:
            self.import_files(sources)

    def import_files(self, sources):
        if not self.editable or self.busy or not sources:
            return
        self._import_message = f"Copying {len(sources)} file{'s' if len(sources) != 1 else ''}…"
        self._set_busy(True)
        snapshot = DocumentationCatalog(self.catalog.parent_path, self.catalog.root_name, list(self.catalog.items))
        self.task = ImportFiles(DocumentationFiles(snapshot), self.selected_folder, sources)
        self.task.signals.succeeded.connect(self._files_imported)
        self.task.signals.failed.connect(self._files_failed)
        self.task.signals.finished.connect(self._files_finished)
        QThreadPool.globalInstance().start(self.task)
        self._update_file_message()

    def _files_imported(self, names):
        self._import_message = f"Added {len(names)} file{'s' if len(names) != 1 else ''}."

    def _files_failed(self, error):
        self._import_message = error

    def _files_finished(self):
        self._set_busy(False)
        self.refresh()
        self.reload_files(force=True)

    def _set_busy(self, busy):
        self.busy = busy
        for widget in (self.folder_tree, self.search, self.table, self.add_button, self.sort_select):
            widget.setEnabled(not busy)
        self.up_button.setEnabled(not busy and bool(self.selected_folder))
        sidebar = getattr(self.window(), "sidebar", None)
        if sidebar is not None:
            sidebar.setEnabled(not busy)
        self._update_file_message()

    def _item_menu(self, path, parent):
        menu = QMenu(parent)
        menu.addAction(admin_icon("links"), "Connections…", lambda: self.connect_path(path))
        item = next((entry for entry in self.catalog.items if entry.name.casefold() == path.casefold()), None)
        if item is not None and item.kind == "folder":
            menu.addAction(admin_icon("edit"), "Edit folder…", lambda: self.add_item(item))
        menu.addSeparator()
        menu.addAction("Move to…", lambda: self.choose_move(path))
        menu.addSeparator()
        menu.addAction("Delete…", lambda: self.confirm_delete_path(path))
        return menu

    def connect_path(self, path):
        if not self.editable or self.busy:
            return
        item = next((entry for entry in self.catalog.items if entry.name.casefold() == path.casefold()), None)
        try:
            if item is None:
                target = DocumentationFiles(self.catalog).managed_path(path)
                item = DocumentationItem(path, kind="folder" if target.is_dir() else "file")
        except (OSError, ValueError, DocumentationError) as error:
            self._import_message = str(error)
            self._update_file_message()
            return
        dialog = DocumentationConnectionsDialog(item.name, item.kind, self)
        self.item_dialog = dialog
        self.editing.emit(dialog, item)
        dialog.accepted.connect(lambda: self._save_connections(dialog, item))
        dialog.open()

    def _save_connections(self, dialog, item):
        old_items, old_links = list(self.catalog.items), list(self.session.links)
        try:
            with self.write_guard():
                try:
                    if not any(entry.id == item.id for entry in self.catalog.items):
                        self.catalog.items.append(item)
                    self.entry_saved.emit(dialog, item)
                    self.persist_change()
                except (OSError, ValueError, DocumentationError, StorageError):
                    self.catalog.items[:] = old_items
                    self.session.links[:] = old_links
                    raise
        except (OSError, ValueError, DocumentationError, StorageError) as error:
            dialog.error.setText(str(error))
            dialog.show()
            return
        self.filesystem_changed.emit()
        self.refresh()

    def _row_context_menu(self, position):
        if self.busy:
            return
        row = self.table.rowAt(position.y())
        if row < 0:
            return
        self.table.selectRow(row)
        item = self.table.item(row, 0)
        path = item.data(FILE_ROLE) or item.data(FOLDER_ROLE)
        if path:
            menu = self._item_menu(path, self.table)
            menu.exec(self.table.viewport().mapToGlobal(position))
            menu.deleteLater()

    def _folder_context_menu(self, position):
        item = self.folder_tree.itemAt(position)
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not self.busy and path:
            menu = self._item_menu(path, self.folder_tree)
            menu.exec(self.folder_tree.viewport().mapToGlobal(position))
            menu.deleteLater()

    def choose_move(self, path):
        if not self.editable or self.busy:
            return
        try:
            files = DocumentationFiles(self.catalog)
            source = files.managed_path(path)
            root = files.root().resolve()
            selected = QFileDialog.getExistingDirectory(self, f"Move {source.name} — choose destination folder", str(root))
            if not selected:
                return
            destination = Path(selected).relative_to(root).as_posix()
            self.move_path(path, "" if destination == "." else destination)
        except (OSError, ValueError, DocumentationError) as error:
            self._import_message = f"Choose a destination inside the documentation folder. {error}"
            self._update_file_message()

    def move_path(self, path, destination):
        return self._change_path(path, destination=destination)

    def confirm_delete_path(self, path):
        if not self.editable or self.busy:
            return
        try:
            target = DocumentationFiles(self.catalog).managed_path(path)
        except (OSError, ValueError, DocumentationError) as error:
            self._import_message = str(error)
            self._update_file_message()
            return
        title = "Delete folder" if target.is_dir() else "Delete file"
        description = (f'Permanently delete “{path}”' + (" and all files and subfolders inside it?\nNested documentation entries and their library connections will also be removed." if target.is_dir() else "?")
                       + "\nThis affects the shared folder for everyone and cannot be undone.")
        dialog = ConfirmDeleteDialog(title, description, self, section="DOCUMENTATION")
        self.remove_dialog = dialog
        dialog.accepted.connect(lambda: self._change_path(path))
        dialog.open()

    def _change_path(self, path, *, destination=None):
        if not self.editable or self.busy:
            return False
        old_items = list(self.catalog.items)
        old_names = [(entry, entry.name) for entry in old_items]
        old_links = list(self.session.links)
        moved = None
        self._import_message = "Moving item…" if destination is not None else "Deleting item…"
        self._set_busy(True)
        try:
            with self.write_guard():
                try:
                    files = DocumentationFiles(self.catalog)
                    moved = files.move(path, destination) if destination is not None else files.stage_delete(path)
                    self.session.links[:] = valid_links(self.session)
                    self.persist_change()
                except (OSError, ValueError, DocumentationError, StorageError):
                    self.catalog.items[:] = old_items
                    for entry, name in old_names:
                        entry.name = name
                    self.session.links[:] = old_links
                    if moved is not None:
                        source, target = moved
                        try:
                            if source.exists():
                                raise OSError("The original location is occupied.")
                            target.rename(source)
                        except OSError as error:
                            raise DocumentationError(f"The catalog was not saved. Restore the item from {target} to {source}. {error}") from error
                    raise
        except (OSError, ValueError, DocumentationError, StorageError) as error:
            self._import_message = str(error)
            self._set_busy(False)
            self.refresh()
            return False
        # Reads started before a move/delete must never repopulate old paths.
        self._current_read = None
        self.directory_loading = False
        self._listing_key = None
        self._disk_entries = []
        prefix = path.casefold() + "/"
        self._known_folders = {folder for folder in self._known_folders
                               if folder.casefold() != path.casefold() and not folder.casefold().startswith(prefix)}
        if self.selected_folder.casefold() == path.casefold() or self.selected_folder.casefold().startswith(prefix):
            self.selected_folder = (moved[1].relative_to(files.root()).as_posix() + self.selected_folder[len(path):]
                                    if destination is not None else path.rpartition("/")[0])
            self._known_folders.add(self.selected_folder)
        self.filesystem_changed.emit()
        if destination is None:
            self._import_message = "Deleting files…"
            self.task = DeleteStaged(moved[1])
            self.task.signals.finished.connect(self._delete_finished)
            QThreadPool.globalInstance().start(self.task)
            self._update_file_message()
        else:
            self._import_message = "Item moved."
            self._files_finished()
        return True

    def _delete_finished(self, error):
        self._import_message = error or "Item deleted."
        self._files_finished()

    def open_in_explorer(self):
        if self.busy:
            return
        try:
            target = DocumentationFiles(self.catalog).directory_path(self.selected_folder)
            if not target.is_dir():
                raise DocumentationError("This folder is unavailable. Connect the shared location and try again.")
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
                raise DocumentationError("Windows File Explorer could not open this folder.")
        except (OSError, ValueError, DocumentationError) as error:
            self._import_message = str(error)
            self._update_file_message()

    def open_file(self, path):
        if self.busy:
            return
        try:
            target = DocumentationFiles(self.catalog).file_path("", path)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
                raise DocumentationError("No application could open this file.")
        except (OSError, ValueError, DocumentationError) as error:
            self._import_message = str(error)
            self._update_file_message()

    def add_item(self, item=None):
        if not self.editable or self._busy():
            return
        folders = {"/".join(entry.name.split("/")[:index]) for entry in self.catalog.items
                   for index in range(1, len(entry.name.split("/")))}
        dialog = DocumentationItemDialog(self, item=item, folder=self.selected_folder, folders=folders)
        self.item_dialog = dialog
        self.editing.emit(dialog, item)
        dialog.accepted.connect(lambda: self._save_item(dialog, item))
        dialog.open()

    def _save_item(self, dialog, item):
        try:
            with self.write_guard():
                files = DocumentationFiles(self.catalog)
                if item is None:
                    files.create_item(dialog.name)
                    item = DocumentationItem(dialog.name)
                    self.catalog.items.append(item)
                else:
                    files.rename_item(item, dialog.name)
                self.entry_saved.emit(dialog, item)
                self.refresh()
                self.changed.emit()
        except (OSError, ValueError, DocumentationError, StorageError) as error:
            dialog.error.setText(str(error))
            dialog.show()
            return
        self.reveal_entry(item.id)
        self.open_item(item)

    def open_item(self, item):
        if item.kind == "file":
            self.navigate_folder(item.name.rpartition("/")[0])
            self.open_file(item.name)
        else:
            self.navigate_folder(item.name)

    def open_files(self, item):
        self.open_item(item)

    def _open_row(self, row, column):
        path = self.table.item(row, 0).data(FILE_ROLE)
        if path is not None:
            self.open_file(path)
            return
        folder = self.table.item(row, 0).data(FOLDER_ROLE)
        if folder is not None:
            self.navigate_folder(folder)
            return
        identifier = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        item = next((item for item in self.catalog.items if item.id == identifier), None)
        if item is not None:
            self.open_item(item)

    def confirm_remove(self, item):
        if not self.editable or self._busy():
            return
        dialog = ConfirmDeleteDialog("Remove documentation item", f'Remove “{item.name}” from TSLibrary?\nThe folder and its files are kept in the shared location.', self, section="DOCUMENTATION")
        self.remove_dialog = dialog
        dialog.accepted.connect(lambda: self._remove(item))
        dialog.open()

    def _remove(self, item):
        self.catalog.items[:] = [entry for entry in self.catalog.items if entry.id != item.id]
        self.refresh()
        self.changed.emit()

    @preserve_selection
    def refresh(self, *_):
        if not hasattr(self, "table"):
            return
        query = self.search.text().strip().casefold()
        root_key = self._directory_key()[:3]
        if root_key != self._root_key:
            self._root_key = root_key
            self._known_folders.clear()
        self.selected_folder = self.folder_tree.rebuild(self.catalog.items, self.selected_folder, self._known_folders)
        self._update_breadcrumb()
        disk = self._disk_entries if self._listing_key == self._directory_key() else []
        rows = browse_rows(self.catalog.items, self.selected_folder, query, bool(self.sort_select.currentIndex()), disk)
        # Cell widgets are deleted later by Qt. Hide them immediately so a
        # second refresh or resize cannot briefly paint old row actions.
        for row in range(self.table.rowCount()):
            previous = self.table.cellWidget(row, 1)
            if previous is not None:
                previous.hide()
        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for row, result in enumerate(rows):
            item = result.entry
            parent, _, title = result.path.rpartition("/")
            name = cell(title)
            detail = "Documentation folder" if item is not None else "Folder"
            if result.file:
                size = f"{result.size / 1024 / 1024:.1f} MB" if result.size >= 1024 * 1024 else f"{max(1, round(result.size / 1024))} KB" if result.size else "0 bytes"
                extension = title.rpartition(".")[2].upper() if "." in title else ""
                detail = f"{extension + ' file' if extension else 'File'} · {size}"
            if query:
                detail += " · " + (parent or "Top level")
            name.setData(PARENT_ROLE, detail)
            name.setData(Qt.ItemDataRole.UserRole, item.id if item else ("file" if result.file else "folder", result.path.casefold()))
            name.setData(FOLDER_ROLE, result.path if result.folder else None)
            name.setData(FILE_ROLE, result.path if result.file else None)
            name.setToolTip(f"{self.catalog.root_name}/{result.path}")
            name.setIcon(admin_icon("folder", "#c9b18c") if result.folder else admin_icon("documentation"))
            self.table.setItem(row, 0, name)
            files = action("Open folder" if result.folder else "Open")
            if result.folder:
                files.setMaximumWidth(120)
                files.clicked.connect(lambda checked=False, path=result.path: self.navigate_folder(path))
            else:
                files.clicked.connect(lambda checked=False, path=result.path: self.open_file(path))
            buttons = [files]
            if self.editable:
                connect = action("")
                connect.setIcon(admin_icon("links"))
                connect.setFixedWidth(34)
                connect.setToolTip(f"Edit connections: {result.path}")
                connect.setAccessibleName(f"Edit connections: {result.path}")
                connect.clicked.connect(lambda checked=False, path=result.path: self.connect_path(path))
                buttons.append(connect)
                more = action("")
                more.setIcon(admin_icon("more", "#d9c39f"))
                more.setProperty("iconOnly", True)
                more.setFixedWidth(42)
                more.setToolTip(f"Move or delete: {result.path}")
                more.setAccessibleName(f"Actions for {result.path}")
                more.setMenu(self._item_menu(result.path, more))
                buttons.append(more)
            self.table.setCellWidget(row, 1, button_cell(*buttons))
        self.content_stack.setCurrentWidget(self.table if rows else self.empty_state)
        self.empty_heading.setText("Loading files…" if self.directory_loading else "No search results." if query else "This folder is empty." if self.selected_folder else self.empty_title)
        self.empty_description.setText("Search includes this folder and its subfolders." if query else "Use Add files to place documents here, or create a subfolder." if self.selected_folder else self.empty_description_text)
        self.empty_button.setText("Create subfolder" if self.selected_folder else self.empty_action)
        self.empty_button.setVisible(self.editable and not query)
        folders = sum(result.folder for result in rows)
        documents = len(rows) - folders
        self.count_label.setText(f"{len(rows)} search result{'s' if len(rows) != 1 else ''}" if query else
                                 f"{folders} folder{'s' if folders != 1 else ''} · {documents} file{'s' if documents != 1 else ''}")
        self._update_file_message()
        if self.isVisible() and not self.busy:
            self.reload_files()

    def reload_settings(self):
        self.refresh()
