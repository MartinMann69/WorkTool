"""Workplace menus, local repairs, portable preferences, and launch workflows."""

from dataclasses import replace

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMenu, QMessageBox

from ..applications.targets import parse_launch_target
from ..shared.forms import action
from ..storage import StorageError
from ..transfers import export_backup, import_backup, recovery_path, export_catalog_csv
from .dialogs import LaunchSetsDialog, QuickLauncher
from .models import collection_entries, effective_application, entry_key, resolve_entry, workplace_entries


class WorkplaceTools:
    def _setup_tools(self, header):
        quick = action("Find tools · Ctrl+K", "workplaceSecondary")
        quick.clicked.connect(self.show_quick_launcher)
        header.insertWidget(header.count() - 1, quick)
        tools = action("Tools", "workplaceSecondary")
        self.tools_menu = QMenu(tools)
        tools.setMenu(self.tools_menu)
        header.insertWidget(header.count() - 1, tools)
        self.tools_menu.addAction("Workspace sets…", self.show_launch_sets)
        self.tools_menu.addAction("Rename group…", self.rename_group)
        self.tools_menu.addAction("Delete group…", self.delete_group)
        self.tools_menu.addSeparator()
        startup = self.tools_menu.addAction("Start directly in my workplace")
        self.startup_action = startup
        startup.setCheckable(True)
        startup.setChecked(self.config.start_in_workplace)
        startup.triggered.connect(lambda checked: self._set_startup(startup, checked))
        self.tools_menu.addSeparator()
        self.tools_menu.addAction("Export workplace backup…", self.export_workplace)
        self.tools_menu.addAction("Restore workplace backup…", self.restore_workplace)
        self.tools_menu.addAction("Export catalog CSV…", self.export_csv)
        self.quick_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.quick_shortcut.activated.connect(self.show_quick_launcher)

    def _set_startup(self, action, checked):
        if not self._commit(replace(self.config, start_in_workplace=checked)):
            action.setChecked(self.config.start_in_workplace)

    def set_view_mode(self, mode):
        if mode in ("cards", "list"):
            self._commit(replace(self.config, view_mode=mode))

    def all_workplace_entries(self):
        return (workplace_entries(self.session, self.config, "websites")
                + workplace_entries(self.session, self.config, "applications"))

    def show_entry_menu(self, entry, position):
        self.entry_menu = self.build_entry_menu(entry)
        self.entry_menu.popup(position)

    def build_entry_menu(self, entry):
        menu = QMenu(self)
        menu.addAction("Open", lambda: self.open_entry(entry))
        favorite = menu.addAction("Favorite")
        favorite.setCheckable(True)
        favorite.setChecked(entry_key(entry) in self.config.favorites)
        favorite.triggered.connect(lambda _: self.toggle_favorite(entry))
        groups = menu.addMenu("Groups")
        for name in sorted(self.config.groups, key=str.casefold):
            choice = groups.addAction(name)
            choice.setCheckable(True)
            choice.setChecked(entry_key(entry) in self.config.groups[name])
            choice.triggered.connect(lambda checked, group=name: self.assign_group(entry, group, checked))
        groups.addSeparator()
        groups.addAction("New group…", lambda: self.new_group(entry))
        if entry.kind == "applications":
            menu.addAction("Locate application on this PC…", lambda: self.locate_application(entry))
        if entry.source == "personal":
            menu.addAction("Edit…", lambda: self.edit_personal(entry))
        menu.addSeparator()
        menu.addAction("Remove personal entry…" if entry.source == "personal" else "Remove from workplace",
                       lambda: self.remove_entry(entry))
        return menu

    def toggle_favorite(self, entry):
        key = entry_key(entry)
        favorites = list(self.config.favorites)
        if key in favorites:
            favorites.remove(key)
        else:
            favorites.append(key)
        self._commit(replace(self.config, favorites=favorites))

    def assign_group(self, entry, name, selected=True):
        name = name.strip()
        if not name:
            return
        key = entry_key(entry)
        groups = {name: list(keys) for name, keys in self.config.groups.items()}
        keys = groups.setdefault(name, [])
        if selected and key not in keys:
            keys.append(key)
        elif not selected and key in keys:
            keys.remove(key)
        self._commit(replace(self.config, groups=groups))

    def new_group(self, entry):
        name, ok = QInputDialog.getText(self, "New group", "Group name:")
        if ok and name.strip():
            self.assign_group(entry, name.strip()[:80])

    def _choose_group(self, title):
        if not self.config.groups:
            QMessageBox.information(self, title, "Create a group from a tool's ⋯ menu first.")
            return None
        name, ok = QInputDialog.getItem(self, title, "Group:", sorted(self.config.groups), 0, False)
        return name if ok else None

    def rename_group(self):
        old = self._choose_group("Rename group")
        if old is None:
            return
        name, ok = QInputDialog.getText(self, "Rename group", "New name:", text=old)
        name = name.strip()[:80]
        if not ok or not name or name == old:
            return
        if name in self.config.groups:
            QMessageBox.information(self, "Group already exists", "Choose a different group name.")
            return
        groups = dict(self.config.groups)
        groups[name] = groups.pop(old)
        self._commit(replace(self.config, groups=groups))

    def delete_group(self):
        name = self._choose_group("Delete group")
        if name is not None and QMessageBox.question(self, "Delete group", f'Delete “{name}”? Its tools will stay in your workplace.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            groups = dict(self.config.groups)
            del groups[name]
            self._commit(replace(self.config, groups=groups))

    def locate_application(self, entry):
        record = resolve_entry(self.session, self.config, entry)
        if record is None or entry.kind != "applications":
            return
        path, _ = QFileDialog.getOpenFileName(self, f"Locate {entry.name}", "",
                                             "Applications and shortcuts (*.exe *.lnk)")
        if not path:
            return
        try:
            resolved, _ = parse_launch_target(path)
        except ValueError as error:
            QMessageBox.warning(self, "Could not use this application", str(error))
            return
        overrides = dict(self.config.application_overrides)
        overrides[entry_key(entry)] = str(resolved)
        if self._commit(replace(self.config, application_overrides=overrides)):
            self.statusBar().showMessage(f"Local path updated for {entry.name}. Shared entries are kept.", 4500)

    def show_quick_launcher(self):
        entries = {entry_key(entry): entry for entry in collection_entries(self.session, self.config)}
        entries.update((entry_key(entry), entry) for entry in self.all_workplace_entries())
        self.quick_launcher = QuickLauncher(list(entries.values()), self.open_entry, self)
        self.quick_launcher.open()

    def show_launch_sets(self):
        self.launch_sets_dialog = LaunchSetsDialog(self.all_workplace_entries(), self.config,
            lambda sets: self._commit(replace(self.config, launch_sets=sets)), self.launch_set, self)
        self.launch_sets_dialog.open()

    def launch_set(self, name):
        available = {entry_key(entry): entry for entry in self.all_workplace_entries()}
        keys = list(dict.fromkeys(self.config.launch_sets.get(name, [])))
        entries = [available[key] for key in keys if key in available]
        if not entries:
            QMessageBox.information(self, "No tools available", "This set has no tools currently in your workplace.")
            return
        missing = len(keys) - len(entries)
        description = f'Open {len(entries)} tools in “{name}”?'
        if missing:
            description += f"\n{missing} removed selection(s) will be skipped."
        if QMessageBox.question(self, "Open workspace set", description,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        # Each action uses the same explicit launcher and error handling as a card.
        for entry in entries:
            self.open_entry(entry)

    def export_workplace(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export workplace backup", "TSLibrary-workplace.json", "JSON (*.json)")
        if path:
            try:
                export_backup(path, self.config)
            except StorageError as error:
                QMessageBox.warning(self, "Could not export backup", str(error))

    def restore_workplace(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restore workplace backup", "", "JSON (*.json)")
        if not path:
            return
        try:
            config = import_backup(path)
            if QMessageBox.question(self, "Restore workplace", "Replace your workplace preferences and personal entries with this backup?\nA recovery backup of your current workplace will be saved beside it.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            export_backup(recovery_path(path), self.config)
            if self._commit(config):
                self.statusBar().showMessage("Workplace restored. Local application paths may need updating on this PC.", 6500)
        except StorageError as error:
            QMessageBox.warning(self, "Could not restore backup", str(error))

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export catalog CSV", "TSLibrary-catalog.csv", "CSV (*.csv)")
        if path:
            try:
                export_catalog_csv(path, self.session)
            except StorageError as error:
                QMessageBox.warning(self, "Could not export CSV", str(error))
