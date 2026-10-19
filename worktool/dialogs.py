"""Account and catalog administration dialogs."""
import json
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)
from .catalog import DEPARTMENTS


def label(text, name=None):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        item.setObjectName(name)
    return item


def button(text, callback, primary=False):
    item = QPushButton(text)
    if primary:
        item.setObjectName("primary")
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    item.clicked.connect(callback)
    return item


def password_field(placeholder=""):
    item = QLineEdit()
    item.setEchoMode(QLineEdit.EchoMode.Password)
    item.setPlaceholderText(placeholder)
    item.setMaxLength(128)
    return item


def failure(parent, exc):
    box = QMessageBox(parent)
    box.setWindowTitle("WorkTool")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(str(exc))
    box.exec()


def configure_tabs(tabs):
    """Stable tab hit targets with no native base line or changing font metrics."""
    tabs.setDocumentMode(False)
    tabs.tabBar().setDrawBase(False)
    tabs.tabBar().setExpanding(False)
    tabs.tabBar().setUsesScrollButtons(True)


class PasswordDialog(QDialog):
    def __init__(self, store, user, parent=None, required=False):
        super().__init__(parent)
        self.store, self.user = store, user
        self.setWindowTitle("Change password")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.addWidget(label("A fresh start", "title"))
        info = label("Set a new password to continue." if required else "Choose a unique password with 12–128 characters.", "subtitle")
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        self.old = password_field()
        self.new = password_field("At least 12 characters")
        self.confirm = password_field()
        form.addRow("Current password", self.old)
        form.addRow("New password", self.new)
        form.addRow("Confirm password", self.confirm)
        layout.addLayout(form)
        self.error = label("", "error")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        layout.addWidget(button("Update password", self.save, True))
        layout.addWidget(button("Sign out" if required else "Cancel", self.reject))
        self.confirm.returnPressed.connect(self.save)

    def save(self):
        try:
            if self.new.text() != self.confirm.text():
                raise ValueError("The new passwords do not match.")
            self.store.change_password(self.user.id, self.old.text(), self.new.text())
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class UserDialog(QDialog):
    def __init__(self, store, actor, row=None, parent=None):
        super().__init__(parent)
        self.store, self.actor, self.row = store, actor, row
        self.setWindowTitle("Edit account" if row else "Create account")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        self.username = QLineEdit(row["username"] if row else "")
        self.username.setMaxLength(64)
        self.name = QLineEdit(row["display_name"] if row else "")
        self.name.setMaxLength(80)
        self.password = password_field("Leave blank to keep password" if row else "Temporary password: 12+ characters")
        self.admin = QCheckBox("Administrator · access to every workspace")
        self.admin.setChecked(bool(row["admin"]) if row else False)
        self.active = QCheckBox("Account enabled")
        self.active.setChecked(bool(row["active"]) if row else True)
        form.addRow("Username", self.username)
        form.addRow("Display name", self.name)
        form.addRow("Temporary password", self.password)
        form.addRow("Role", self.admin)
        form.addRow("Status", self.active)
        layout.addLayout(form)
        layout.addWidget(label("WORKSPACE ACCESS", "eyebrow"))
        layout.addWidget(label("General is included for everyone.", "muted"))
        depts = json.loads(row["departments"]) if row else []
        self.checks = {}
        for key, (name, _, _) in DEPARTMENTS.items():
            if key != "general":
                check = QCheckBox(name.replace("&", "&&"))
                check.setChecked(key in depts)
                self.checks[key] = check
                layout.addWidget(check)
        layout.addWidget(label("New and reset passwords must be changed at the next sign-in.", "muted"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        try:
            if self.row is None and not self.active.isChecked():
                raise ValueError("Create an enabled account first; it can then be disabled.")
            self.store.save_user(self.actor.id, self.username.text(), self.name.text(), self.admin.isChecked(),
                                 [k for k, c in self.checks.items() if c.isChecked()],
                                 user_id=self.row["id"] if self.row else None,
                                 password=self.password.text(), active=self.active.isChecked())
        except sqlite3.IntegrityError:
            failure(self, "That username is already in use.")
            return
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            failure(self, exc)
            return
        self.accept()


class EntryDialog(QDialog):
    def __init__(self, store, actor, entry=None, parent=None):
        super().__init__(parent)
        self.store, self.actor, self.entry = store, actor, entry
        self.setWindowTitle("Edit tool" if entry else "Add tool")
        self.setMinimumWidth(660)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        self.department = QComboBox()
        for key, (name, _, _) in DEPARTMENTS.items():
            self.department.addItem(name, key)
        self.kind = QComboBox()
        self.kind.addItem("Application", "app")
        self.kind.addItem("Website", "link")
        self.title = QLineEdit()
        self.title.setMaxLength(70)
        self.description = QLineEdit()
        self.description.setMaxLength(180)
        self.target = QLineEdit()
        self.target.setMaxLength(2048)
        target_row = QHBoxLayout()
        target_row.addWidget(self.target)
        self.browse = button("Browse…", self.pick_file)
        target_row.addWidget(self.browse)
        self.arguments = QLineEdit("[]")
        self.arguments.setToolTip('JSON list, for example ["--profile", "work"]. Never a shell command.')
        form.addRow("Workspace", self.department)
        form.addRow("Type", self.kind)
        form.addRow("Title", self.title)
        form.addRow("Description", self.description)
        form.addRow("Path / URL", target_row)
        form.addRow("Arguments (JSON)", self.arguments)
        self.restricted = QCheckBox('Only assigned users / groups')
        self.restricted.setChecked(entry.restricted if entry else True)
        self.restricted.setToolTip('When unchecked, normal department access also grants this tool. General tools are then available to everyone.')
        form.addRow('Access', self.restricted)
        layout.addLayout(form)
        info = label("Use a local .exe path (environment variables are supported) or an https:// website. "
                     "Only configure software and arguments approved by your organization.", "muted")
        info.setWordWrap(True)
        layout.addWidget(info)
        if entry:
            self.department.setCurrentIndex(self.department.findData(entry.department))
            self.kind.setCurrentIndex(self.kind.findData(entry.kind))
            self.title.setText(entry.title)
            self.description.setText(entry.description)
            self.target.setText(entry.target)
            self.arguments.setText(json.dumps(entry.arguments))
        self.kind.currentIndexChanged.connect(self.kind_changed)
        self.kind_changed()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def kind_changed(self):
        app = self.kind.currentData() == "app"
        self.browse.setEnabled(app)
        self.arguments.setEnabled(app)
        self.target.setPlaceholderText(r"%ProgramFiles%\Vendor\Application.exe" if app else "https://your-company.example/")

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose application", "", "Windows applications (*.exe)")
        if path:
            self.target.setText(path)

    def save(self):
        try:
            arguments = json.loads(self.arguments.text()) if self.kind.currentData() == "app" else []
            self.store.save_entry(self.actor.id, self.department.currentData(), self.kind.currentData(),
                                  self.title.text(), self.description.text(), self.target.text(), arguments,
                                  self.entry.id if self.entry else None, restricted=self.restricted.isChecked())
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            failure(self, exc)
            return
        self.accept()


def table(headers):
    item = QTableWidget(0, len(headers))
    item.setHorizontalHeaderLabels(headers)
    item.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    item.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    item.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    item.verticalHeader().hide()
    item.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    item.horizontalHeader().setStretchLastSection(True)
    return item


def fill_table(widget, rows):
    widget.setRowCount(len(rows))
    for index, row in enumerate(rows):
        for column, value in enumerate(row):
            widget.setItem(index, column, QTableWidgetItem(str(value)))
    widget.resizeRowsToContents()


class AdminPanel(QWidget):
    changed = Signal()

    def __init__(self, store, actor, parent=None):
        super().__init__(parent)
        self.store, self.actor = store, actor
        self.loaded = False
        self.tabs = None

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded:
            self.build()

    def build(self):
        self.loaded = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        tabs = self.tabs = QTabWidget()
        configure_tabs(tabs)
        layout.addWidget(tabs)
        self.user_table = table(["Username", "Display name", "Role", "Status", "Departments"])
        self.entry_table = table(["Title", "Workspace", "Type", "Path / URL"])
        self.audit_table = table(["Time (UTC)", "Account", "Event", "Detail"])
        self.group_table = table(['Group', 'Description', 'Members', 'Tools'])
        for name, widget, actions in [
            ("Accounts", self.user_table, [("Create account", self.add_user), ("Edit selected", self.edit_user)]),
            ('Groups', self.group_table, [('Create group', self.add_group), ('Edit selected', self.edit_group), ('Delete selected', self.delete_group)]),
            ("Tool catalog", self.entry_table, [("Add tool", self.add_entry), ("Edit selected", self.edit_entry), ("Delete selected", self.delete_entry)]),
            ("Activity log", self.audit_table, [("Refresh", self.refresh)]),
        ]:
            page = QWidget()
            column = QVBoxLayout(page)
            row = QHBoxLayout()
            for text, callback in actions:
                row.addWidget(button(text, callback))
            row.addStretch()
            column.addLayout(row)
            column.addWidget(widget)
            tabs.addTab(page, name)
        self.access_panel = UserAccessPanel(self.store, self.actor)
        self.access_panel.changed.connect(self.changed.emit)
        tabs.insertTab(2, self.access_panel, 'User access')
        self.user_table.cellDoubleClicked.connect(lambda *_: self.edit_user())
        self.entry_table.cellDoubleClicked.connect(lambda *_: self.edit_entry())
        self.group_table.cellDoubleClicked.connect(lambda *_: self.edit_group())
        layout.addWidget(label("Activity shows the latest 500 events. Times are UTC. Changes are saved immediately.", "muted"))
        self.refresh()

    def refresh(self):
        if not self.loaded:
            return
        try:
            self.user_rows = self.store.users(self.actor.id)
            self.entry_rows = self.store.entries(self.actor.id)
            fill_table(self.user_table, [(r["username"], r["display_name"], "Admin" if r["admin"] else "Member",
                                        "Enabled" if r["active"] else "Disabled",
                                        "All" if r["admin"] else ", ".join(["General"] + [DEPARTMENTS[d][0] for d in json.loads(r["departments"])])) for r in self.user_rows])
            fill_table(self.entry_table, [(e.title, DEPARTMENTS[e.department][0], ('Application' if e.kind == 'app' else 'Website') + (' · assigned only' if e.restricted else ' · department'), e.target) for e in self.entry_rows])
            fill_table(self.audit_table, self.store.audit(self.actor.id))
            self.group_rows = self.store.groups(self.actor.id)
            fill_table(self.group_table, [(r['name'], r['description'], r['members'], r['tools']) for r in self.group_rows])
            self.access_panel.reload()
        except (PermissionError, sqlite3.Error) as exc:
            failure(self, exc)
            self.setEnabled(False)

    def saved(self):
        self.refresh()
        self.changed.emit()

    def add_user(self):
        UserDialog(self.store, self.actor, parent=self).exec()
        self.saved()

    def edit_user(self):
        selected = self.user_table.currentRow()
        if selected >= 0:
            UserDialog(self.store, self.actor, self.user_rows[selected], self).exec()
            self.saved()

    def add_entry(self):
        EntryDialog(self.store, self.actor, parent=self).exec()
        self.saved()

    def edit_entry(self):
        selected = self.entry_table.currentRow()
        if selected >= 0:
            EntryDialog(self.store, self.actor, self.entry_rows[selected], self).exec()
            self.saved()

    def delete_entry(self):
        selected = self.entry_table.currentRow()
        if selected < 0:
            return
        entry = self.entry_rows[selected]
        box = QMessageBox(self)
        box.setWindowTitle("Delete tool")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(f"Delete {entry.title} from the catalog? The application itself will stay installed.")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() == QMessageBox.StandardButton.Yes:
            try:
                self.store.delete_entry(self.actor.id, entry.id)
                self.saved()
            except (PermissionError, sqlite3.Error) as exc:
                failure(self, exc)

    def add_group(self):
        GroupDialog(self.store, self.actor, parent=self).exec()
        self.saved()

    def edit_group(self):
        index = self.group_table.currentRow()
        if index >= 0:
            GroupDialog(self.store, self.actor, self.group_rows[index], self).exec()
            self.saved()

    def delete_group(self):
        index = self.group_table.currentRow()
        if index < 0:
            return
        row = self.group_rows[index]
        if QMessageBox.question(self, 'Delete group', 'Delete this group and its grants? Other groups and direct assignments remain.',
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Yes:
            try:
                self.store.delete_group(self.actor.id, row['id'])
                self.saved()
            except (PermissionError, sqlite3.Error) as exc:
                failure(self, exc)


class CellCheckBox(QCheckBox):
    def hitButton(self, position):
        return self.rect().contains(position)


def check_rows(widget, rows, selected):
    """Checkbox text fills the cell, so clicking its label works as expected."""
    widget.setRowCount(len(rows))
    checks = {}
    for index, (identity, title, *values) in enumerate(rows):
        check = CellCheckBox(title.replace('&', '&&'))
        check.setToolTip(title)
        check.setChecked(identity in selected)
        widget.setCellWidget(index, 0, check)
        checks[identity] = check
        for column, value in enumerate(values, 1):
            widget.setItem(index, column, QTableWidgetItem(str(value)))
    widget.resizeRowsToContents()
    return checks


def checked_ids(checks):
    return {identity for identity, check in checks.items() if check.isChecked()}


class GroupDialog(QDialog):
    def __init__(self, store, actor, row=None, parent=None):
        super().__init__(parent)
        self.store, self.actor, self.row = store, actor, row
        self.setWindowTitle('Edit group' if row else 'Create group')
        self.resize(1050, 680)
        self.setMinimumSize(850, 520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(row['name'] if row else '')
        self.name.setMaxLength(80)
        self.description = QLineEdit(row['description'] if row else '')
        self.description.setMaxLength(180)
        form.addRow('Group name', self.name)
        form.addRow('Description', self.description)
        layout.addLayout(form)
        members, tools = store.group_access(actor.id, row['id']) if row else (set(), set())
        columns = QHBoxLayout()
        self.members = table(['Members'])
        self.tools = table(['Granted tool', 'Workspace', 'Type'])
        users = store.users(actor.id)
        entries = store.entries(actor.id)
        self.member_checks = check_rows(self.members, [(u['id'], u['username']) for u in users], members)
        self.tool_checks = check_rows(self.tools, [(e.id, e.title, DEPARTMENTS[e.department][0], e.kind) for e in entries], tools)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filter tools…')
        self.search.textChanged.connect(lambda text: self.filter_rows(text, entries))
        right = QVBoxLayout()
        right.addWidget(self.search)
        right.addWidget(self.tools)
        columns.addWidget(self.members, 1)
        columns.addLayout(right, 3)
        layout.addLayout(columns, 1)
        note = label('Members receive each selected catalog tool once, even through several groups or a direct assignment.', 'muted')
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(self.save)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

    def filter_rows(self, text, entries):
        for index, entry in enumerate(entries):
            self.tools.setRowHidden(index, text.casefold() not in f'{entry.title} {DEPARTMENTS[entry.department][0]}'.casefold())

    def save(self):
        try:
            self.store.save_group(self.actor.id, self.name.text(), self.description.text(),
                                  checked_ids(self.member_checks), checked_ids(self.tool_checks), self.row['id'] if self.row else None)
        except sqlite3.IntegrityError:
            failure(self, 'That group name is already used, or an assigned user/tool no longer exists. Reload and try again.')
            return
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            failure(self, exc)
            return
        self.accept()


class UserAccessPanel(QWidget):
    changed = Signal()

    def __init__(self, store, actor):
        super().__init__()
        self.store, self.actor = store, actor
        self.loading = False
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(label('Account'))
        self.user = QComboBox()
        self.user.setMinimumWidth(200)
        row.addWidget(self.user)
        row.addWidget(button('Reload', self.reload))
        row.addStretch()
        layout.addLayout(row)
        note = label('Choose groups and direct tool grants. Changes save immediately. Inherited tools are shown once; direct grants are optional.', 'muted')
        note.setWordWrap(True)
        layout.addWidget(note)
        columns = QHBoxLayout()
        self.groups_table = table(['Group membership'])
        self.tools_table = table(['Direct grant', 'Workspace', 'Type', 'Effective access'])
        columns.addWidget(self.groups_table, 1)
        right = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filter applications and links…')
        self.search.textChanged.connect(self.filter_tools)
        right.addWidget(self.search)
        right.addWidget(self.tools_table)
        columns.addLayout(right, 3)
        layout.addLayout(columns, 1)
        self.status = label('', 'muted')
        layout.addWidget(self.status)
        self.user.currentIndexChanged.connect(self.load_user)

    def reload(self):
        selected = self.user.currentData()
        self.user.blockSignals(True)
        self.user.clear()
        for row in self.store.users(self.actor.id):
            self.user.addItem(f"{row['username']} · {row['display_name']}", row['id'])
        index = self.user.findData(selected)
        self.user.setCurrentIndex(max(0, index))
        self.user.blockSignals(False)
        self.load_user()

    def load_user(self, *_):
        if self.user.currentData() is None:
            return
        self.loading = True
        try:
            group_ids, entry_ids = self.store.user_access(self.actor.id, self.user.currentData())
            self.entries = self.store.entries(self.actor.id)
            self.group_checks = check_rows(self.groups_table, [(g['id'], g['name']) for g in self.store.groups(self.actor.id)], group_ids)
            self.tool_checks = check_rows(self.tools_table, [(e.id, e.title, DEPARTMENTS[e.department][0], 'App' if e.kind == 'app' else 'Link', '') for e in self.entries], entry_ids)
            for check in [*self.group_checks.values(), *self.tool_checks.values()]:
                check.toggled.connect(self.save)
            self.update_sources()
            self.filter_tools()
        finally:
            self.loading = False

    def update_sources(self):
        sources = self.store.preview_access(self.actor.id, self.user.currentData())
        for index, entry in enumerate(self.entries):
            text = ', '.join(sources[entry.id]) or 'No access'
            item = QTableWidgetItem(text)
            item.setToolTip(text)
            self.tools_table.setItem(index, 3, item)
        self.tools_table.resizeRowsToContents()

    def filter_tools(self, *_):
        for index, entry in enumerate(getattr(self, 'entries', [])):
            self.tools_table.setRowHidden(index, self.search.text().casefold() not in f'{entry.title} {DEPARTMENTS[entry.department][0]}'.casefold())

    def save(self, *_):
        if self.loading:
            return
        try:
            self.store.set_user_access(self.actor.id, self.user.currentData(), checked_ids(self.group_checks), checked_ids(self.tool_checks))
            self.update_sources()
            self.status.setText('Saved. Effective access is deduplicated across departments, groups and direct grants.')
            self.changed.emit()
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            failure(self, exc)
            self.load_user()


class AdminDialog(QDialog):
    """Standalone wrapper used by the screenshot utility."""
    def __init__(self, store, actor, parent=None):
        super().__init__(parent)
        self.setWindowTitle('WorkTool · Administration')
        self.resize(1080, 690)
        layout = QVBoxLayout(self)
        self.panel = AdminPanel(store, actor, self)
        layout.addWidget(self.panel)
        layout.addWidget(button('Done', self.accept))
