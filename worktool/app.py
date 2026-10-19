"""Desktop views, session lifecycle and startup."""
import argparse
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sqlite3
import sys
import time

from PySide6.QtCore import QEvent, QLockFile, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)
from . import __version__
from .catalog import DEPARTMENTS, resolve_executable
from .dialogs import AdminPanel, PasswordDialog, button, failure, label, password_field, configure_tabs
from .launcher import launch
from .store import Store
from .theme import STYLE, DEFAULT_APPEARANCE, apply_theme, theme_colors


def app_icon(accent="purple"):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(theme_colors(accent=accent)["primary"]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 64, 64, 15, 15)
    painter.setBrush(QColor("white"))
    for x, y in ((16, 16), (35, 16), (16, 35), (35, 35)):
        painter.drawRoundedRect(x, y, 13, 13, 3, 3)
    painter.end()
    return QIcon(pixmap)


class AppearanceControls(QWidget):
    changed = Signal(str, str)

    def __init__(self, appearance=DEFAULT_APPEARANCE):
        super().__init__()
        self.setObjectName("appearanceControls")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.buttons = {}
        self.groups = []
        for options in ((('light', 'Light'), ('dark', 'Dark')), (('purple', 'Purple'), ('pink', 'Pink'))):
            group = QButtonGroup(self)
            group.setExclusive(True)
            self.groups.append(group)
            for value, text in options:
                control = QPushButton(text)
                control.setObjectName('appearanceChoice')
                control.setCheckable(True)
                control.setCursor(Qt.CursorShape.PointingHandCursor)
                control.setAccessibleName(f'{text} theme' if value in {'purple', 'pink'} else f'{text} mode')
                control.setFixedSize(62, 36)
                group.addButton(control)
                row.addWidget(control)
                self.buttons[value] = control
            group.buttonClicked.connect(self.selection_changed)
            row.addSpacing(4)
        self.set_selection(*appearance)

    def set_selection(self, mode, accent):
        self.buttons[mode].setChecked(True)
        self.buttons[accent].setChecked(True)

    def selection_changed(self, *_):
        self.changed.emit('dark' if self.buttons['dark'].isChecked() else 'light',
                          'pink' if self.buttons['pink'].isChecked() else 'purple')


class LoginView(QWidget):
    authenticated = Signal(object)

    def __init__(self, store, demo=False, message="", appearance=DEFAULT_APPEARANCE):
        super().__init__()
        self.store, self.demo = store, demo
        self.setup = not store.has_users()
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        left = QFrame()
        left.setObjectName("sidebar")
        left.setMinimumWidth(350)
        left.setMaximumWidth(490)
        side = QVBoxLayout(left)
        side.setContentsMargins(54, 45, 54, 40)
        side.addWidget(label("▦  WorkTool", "brand"))
        side.addWidget(label("YOUR WORKSPACE, CONNECTED", "brandSmall"))
        side.addStretch(2)
        heading = label("Less searching.\nMore doing.")
        heading.setStyleSheet("color: white; font-size: 38px; font-weight: 700;")
        side.addWidget(heading)
        side.addSpacing(16)
        body = label("One home for your applications, links and everyday tools. Built around the way your team works.")
        body.setWordWrap(True)
        body.setStyleSheet("color: #9caec8; font-size: 15px;")
        side.addWidget(body)
        side.addSpacing(35)
        for text in ("01   Your tools, organized", "02   The right workspace for you", "03   One focused place to start"):
            point = label(text)
            point.setStyleSheet("color: #bdcbe0; padding: 10px 0;")
            side.addWidget(point)
        side.addStretch(3)
        side.addWidget(label(f"WORKTOOL  /  DESKTOP {__version__}", "brandSmall"))
        outer.addWidget(left, 2)
        right = QWidget()
        column = QVBoxLayout(right)
        column.setContentsMargins(48, 32, 48, 32)
        self.appearance = AppearanceControls(appearance)
        column.addWidget(self.appearance, alignment=Qt.AlignmentFlag.AlignRight)
        column.addStretch()
        form = QWidget()
        form.setFixedWidth(440)
        fields = QVBoxLayout(form)
        fields.setSpacing(13)
        fields.addWidget(label("LET'S GET TO WORK", "eyebrow"))
        fields.addWidget(label("Create your workspace" if self.setup else "Welcome back.", "title"))
        subtitle = label("Set up the first administrator account." if self.setup else "Sign in to find everything you need for your day.", "subtitle")
        subtitle.setWordWrap(True)
        fields.addWidget(subtitle)
        fields.addSpacing(14)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Your full name")
        self.name.setMaxLength(80)
        if self.setup:
            fields.addWidget(label("Display name"))
            fields.addWidget(self.name)
        self.username = QLineEdit()
        self.username.setMaxLength(64)
        self.username.setPlaceholderText("e.g. admin" if demo else "Enter your username")
        fields.addWidget(label("Username"))
        fields.addWidget(self.username)
        self.password = password_field("12–128 characters" if self.setup else "Enter your password")
        fields.addWidget(label("Password"))
        fields.addWidget(self.password)
        self.confirm = password_field("Repeat your password")
        if self.setup:
            fields.addWidget(label("Confirm password"))
            fields.addWidget(self.confirm)
        self.show_password = QCheckBox("Show password")
        self.show_password.toggled.connect(self.toggle_password)
        fields.addWidget(self.show_password)
        self.error = label(message, "error")
        self.error.setWordWrap(True)
        fields.addWidget(self.error)
        self.submit = button("Create administrator  →" if self.setup else "Sign in  →", self.sign_in, True)
        self.submit.setMinimumHeight(44)
        fields.addWidget(self.submit)
        self.username.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self.sign_in)
        self.confirm.returnPressed.connect(self.sign_in)
        if demo:
            note = label("DEMO WORKSPACE\nTry admin or it.demo\nPassword: WorkTool!2026", "notice")
            note.setWordWrap(True)
            fields.addSpacing(10)
            fields.addWidget(note)
        else:
            note = label("Need access? Contact your WorkTool administrator.\nYour session locks after a period of inactivity.", "muted")
            note.setWordWrap(True)
            fields.addWidget(note)
        column.addWidget(form, alignment=Qt.AlignmentFlag.AlignHCenter)
        column.addStretch()
        outer.addWidget(right, 3)
        self.username.setFocus()

    def toggle_password(self, shown):
        for field in (self.password, self.confirm):
            field.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)

    def sign_in(self):
        self.submit.setEnabled(False)
        try:
            if self.setup:
                if self.password.text() != self.confirm.text():
                    raise ValueError("The passwords do not match.")
                self.store.bootstrap(self.username.text(), self.name.text(), self.password.text())
                self.setup = False
            user = self.store.authenticate(self.username.text(), self.password.text())
            if not user:
                self.error.setText("Sign-in failed. Check your credentials or contact your administrator. After five failed attempts, wait five minutes.")
                self.password.clear()
                self.password.setFocus()
                return
            self.password.clear()
            self.confirm.clear()
            self.authenticated.emit(user)
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            self.error.setText(str(exc))
        finally:
            self.submit.setEnabled(True)


class ToolCard(QFrame):
    def __init__(self, entry, favorite, on_launch, on_favorite):
        super().__init__()
        self.entry = entry
        self.setObjectName("card")
        self.setMinimumWidth(240)
        self.setFixedHeight(205)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(19, 17, 19, 15)
        layout.setSpacing(8)
        top = QHBoxLayout()
        icon = label(entry.title[:2].upper(), "toolIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(42, 42)
        top.addWidget(icon)
        top.addStretch()
        star = button("★" if favorite else "☆", lambda: on_favorite(entry.id))
        star.setObjectName("star")
        star.setCheckable(True)
        star.setChecked(favorite)
        star.setFixedSize(28, 30)
        star.setToolTip("Remove favorite" if favorite else "Add to favorites")
        star.setAccessibleName(f"Favorite {entry.title}")
        top.addWidget(star)
        layout.addLayout(top)
        title = label(entry.title, "cardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        description = label(entry.description, "muted")
        description.setWordWrap(True)
        layout.addWidget(description, 1)
        bottom = QHBoxLayout()
        available = entry.kind == "link" or bool(resolve_executable(entry.target))
        status = label("WEBSITE" if entry.kind == "link" else ("DESKTOP APP" if available else "SETUP NEEDED"), "eyebrow")
        status.setStyleSheet("font-size: 9px; letter-spacing: 1px;")
        bottom.addWidget(status)
        bottom.addStretch()
        launch_button = button("Open ↗" if entry.kind == "link" else "Launch →", lambda: on_launch(entry.id))
        launch_button.setAccessibleName(f"Open {entry.title}")
        launch_button.setToolTip(entry.target)
        launch_button.setMinimumWidth(86)
        bottom.addWidget(launch_button)
        layout.addLayout(bottom)


class CatalogPage(QWidget):
    access_error = Signal(str)
    def __init__(self, store, user, department, kind, launch_callback, favorite_callback):
        super().__init__()
        self.store, self.user, self.department, self.kind = store, user, department, kind
        self.launch_callback, self.favorite_callback = launch_callback, favorite_callback
        self.query, self.only_favorites, self.last_columns = "", False, 0
        self.cards = []
        self.reflow_timer = QTimer(self)
        self.reflow_timer.setSingleShot(True)
        self.reflow_timer.timeout.connect(self.reflow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 15, 0, 0)
        self.count = label("", "muted")
        layout.addWidget(self.count)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.viewport().installEventFilter(self)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(0, 5, 10, 10)
        self.grid.setSpacing(17)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)
        self.empty = label("", "subtitle")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        self.dirty = True

    def invalidate(self):
        self.dirty = True
        if self.isVisible():
            self.reload()

    def showEvent(self, event):
        super().showEvent(event)
        if self.dirty:
            self.reload()

    def reload(self):
        try:
            entries = self.store.entries(self.user.id, self.department, self.kind)
            favorites = self.store.favorites(self.user.id)
        except (PermissionError, sqlite3.Error) as exc:
            self.access_error.emit(str(exc))
            return
        self.dirty = False
        for card in self.cards:
            self.grid.removeWidget(card)
            card.deleteLater()
        self.cards.clear()
        for entry in entries:
            searchable = f"{entry.title} {entry.description}".casefold()
            if self.query.casefold() not in searchable or (self.only_favorites and entry.id not in favorites):
                continue
            self.cards.append(ToolCard(entry, entry.id in favorites, self.launch_callback, self.favorite_callback))
        self.count.setText(f"{len(self.cards)} {'applications' if self.kind == 'app' else 'links'}  ·  {DEPARTMENTS[self.department][0]} workspace")
        self.empty.setText("No tools match your search. Try another name or turn off Favorites." if not self.cards else "")
        self.empty.setVisible(not self.cards)
        self.scroll.setVisible(bool(self.cards))
        self.reflow(force=True)

    def reflow(self, force=False):
        columns = max(1, min(4, self.scroll.viewport().width() // 265))
        if columns == self.last_columns and not force:
            return
        self.last_columns = columns
        for index in range(4):
            self.grid.setColumnStretch(index, 1 if index < columns else 0)
        for card in self.cards:
            self.grid.removeWidget(card)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self.reflow_timer.start(0)
        return super().eventFilter(watched, event)


class WorkspaceView(QWidget):
    sign_out = Signal(str)

    def __init__(self, store, user, demo=False, appearance=DEFAULT_APPEARANCE):
        super().__init__()
        self.store, self.user = store, user
        self.pages = []
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(23, 28, 23, 24)
        side.setSpacing(10)
        side.addWidget(label("▦  WorkTool", "brand"))
        side.addWidget(label("WORK, WITHIN REACH", "brandSmall"))
        side.addSpacing(35)
        side.addWidget(label("WORKSPACE", "sideTitle"))
        workspace_button = button("▦   My workspace", lambda: self.departments.setCurrentIndex(0))
        workspace_button.setCheckable(True)
        workspace_button.setChecked(True)
        side.addWidget(workspace_button)
        side.addWidget(button("↻   Refresh tools", self.refresh))
        if user.admin:
            side.addSpacing(18)
            side.addWidget(label("MANAGEMENT", "sideTitle"))
            side.addWidget(button("⚙   Administration", self.administration))
        side.addStretch()
        if demo:
            demo_label = label("DEMO ENVIRONMENT\nSample tools & accounts")
            demo_label.setStyleSheet("color: #d4b778; font-size: 11px; padding: 12px 0;")
            side.addWidget(demo_label)
        avatar_row = QHBoxLayout()
        initials = "".join(p[0] for p in user.display_name.split()[:2]).upper()
        avatar = label(initials, "avatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(40, 40)
        avatar_row.addWidget(avatar)
        person = QVBoxLayout()
        name = label(user.display_name)
        name.setWordWrap(True)
        name.setStyleSheet("color: white; font-weight: 600;")
        person.addWidget(name)
        person.addWidget(label("Administrator" if user.admin else "Team member", "muted"))
        avatar_row.addLayout(person)
        side.addLayout(avatar_row)
        side.addWidget(button("Change password", self.change_password))
        side.addWidget(button("Sign out  →", lambda: self.sign_out.emit("You have been signed out.")))
        root.addWidget(sidebar)
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(34, 27, 28, 18)
        content.setSpacing(16)
        top = QHBoxLayout()
        top.addWidget(label("YOUR DAILY STARTING POINT", "eyebrow"))
        top.addStretch()
        top.addWidget(label(datetime.now().strftime("%A, %d %B %Y"), "muted"))
        top.addSpacing(12)
        self.appearance = AppearanceControls(appearance)
        top.addWidget(self.appearance)
        content.addLayout(top)
        title_row = QHBoxLayout()
        greeting = QVBoxLayout()
        self.heading = label(f"Welcome, {user.display_name.split()[0]}.", "title")
        greeting.addWidget(self.heading)
        greeting.addWidget(label("Your team. Your tools. One place to get started.", "subtitle"))
        title_row.addLayout(greeting)
        title_row.addStretch()
        title_row.addWidget(label("ALL ACCESS" if user.admin else "TEAM WORKSPACE", "badge"))
        content.addLayout(title_row)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tools in this workspace…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search tools")
        self.search.setMinimumHeight(43)
        toolbar.addWidget(self.search, 1)
        self.favorite_filter = button("☆  Favorites", self.filter_tools)
        self.favorite_filter.setObjectName("filter")
        self.favorite_filter.setCheckable(True)
        self.favorite_filter.setMinimumHeight(43)
        toolbar.addWidget(self.favorite_filter)
        content.addLayout(toolbar)
        self.departments = QTabWidget()
        configure_tabs(self.departments)
        self.departments.setAccessibleName("Department workspaces")
        self.department_keys = []
        self.admin_panel = AdminPanel(store, user) if user.admin else None
        if self.admin_panel:
            self.admin_panel.changed.connect(self.refresh)
        self.rebuild_departments()
        content.addWidget(self.departments, 1)
        footer = QHBoxLayout()
        self.hint = label("Tip: use the star to keep frequently used tools close.", "muted")
        footer.addWidget(self.hint, 1)
        footer.addWidget(label(f"WorkTool {__version__}", "muted"))
        content.addLayout(footer)
        root.addWidget(body, 1)
        self.search.textChanged.connect(self.filter_tools)

    def filter_tools(self, *_):
        try:
            for page in self.pages:
                page.query = self.search.text().strip()
                page.only_favorites = self.favorite_filter.isChecked()
                page.invalidate()
        except (PermissionError, sqlite3.Error) as exc:
            self.sign_out.emit(str(exc))

    def refresh(self):
        try:
            current = self.store.current(self.user.id)
            if current != self.user:
                self.sign_out.emit("Your account settings changed. Please sign in again.")
                return
            self.rebuild_departments()
            self.filter_tools()
            self.hint.setText("Your tool catalog is up to date.")
        except (PermissionError, sqlite3.Error) as exc:
            self.sign_out.emit(str(exc))

    def open_tool(self, entry_id):
        try:
            title = launch(self.store, self.user.id, entry_id)
            self.hint.setText(f"Open request sent: {title}")
        except (ValueError, PermissionError, OSError, sqlite3.Error) as exc:
            failure(self, exc)

    def favorite(self, entry_id):
        try:
            self.store.toggle_favorite(self.user.id, entry_id)
            self.filter_tools()
        except (PermissionError, sqlite3.Error) as exc:
            failure(self, exc)

    def administration(self):
        try:
            self.store.current(self.user.id, admin=True)
            self.departments.setCurrentWidget(self.admin_panel)
            self.admin_panel.refresh()
        except (PermissionError, sqlite3.Error) as exc:
            self.sign_out.emit(str(exc))

    def change_password(self):
        PasswordDialog(self.store, self.user, self).exec()
        self.refresh()

    def rebuild_departments(self):
        keys = self.store.available_departments(self.user.id)
        if keys == self.department_keys:
            return
        old_index = self.departments.currentIndex()
        old_key = self.department_keys[old_index] if 0 <= old_index < len(self.department_keys) else 'general'
        old_widget = self.departments.currentWidget()
        old_subtab = old_widget.currentIndex() if isinstance(old_widget, QTabWidget) else 0
        while self.departments.count():
            widget = self.departments.widget(0)
            self.departments.removeTab(0)
            if widget is not self.admin_panel:
                widget.deleteLater()
        self.pages.clear()
        self.department_keys = keys
        for key in keys:
            name = DEPARTMENTS[key][0]
            tabs = QTabWidget()
            configure_tabs(tabs)
            tabs.setAccessibleName(f'{name} tools')
            for kind, title in (('app', 'Applications'), ('link', 'Links')):
                page = CatalogPage(self.store, self.user, key, kind, self.open_tool, self.favorite)
                page.access_error.connect(self.sign_out.emit)
                page.query = self.search.text().strip()
                page.only_favorites = self.favorite_filter.isChecked()
                self.pages.append(page)
                tabs.addTab(page, title)
            self.departments.addTab(tabs, name.replace('&', '&&'))
        if self.admin_panel:
            self.departments.addTab(self.admin_panel, 'Admin')
        selected = keys.index(old_key) if old_key in keys else 0
        self.departments.setCurrentIndex(selected)
        self.departments.widget(selected).setCurrentIndex(old_subtab)


class MainWindow(QMainWindow):
    def __init__(self, store, demo=False, idle_minutes=15):
        super().__init__()
        self.store, self.demo, self.user = store, demo, None
        self.idle_seconds = idle_minutes * 60
        self.last_activity = time.monotonic()
        self.last_policy_check = 0
        self.setWindowTitle("WorkTool · Your workspace")
        self.mode, self.accent = DEFAULT_APPEARANCE
        self.pending_appearance = None
        self.appearance_timer = QTimer(self)
        self.appearance_timer.setSingleShot(True)
        self.appearance_timer.timeout.connect(self.commit_appearance)
        self.access_revision = store.access_revision()
        self.resize(1280, 880)
        self.setMinimumSize(1000, 720)
        self.show_login()
        QApplication.instance().installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_session)
        self.timer.start(1000)

    def replace_view(self, view):
        old = self.takeCentralWidget()
        if old:
            old.deleteLater()
        self.setCentralWidget(view)

    def show_login(self, message=""):
        self.appearance_timer.stop()
        self.pending_appearance = None
        self.user = None
        self.set_appearance(*self.store.appearance())
        view = LoginView(self.store, self.demo, message, (self.mode, self.accent))
        view.appearance.changed.connect(self.change_appearance)
        view.authenticated.connect(self.signed_in)
        self.replace_view(view)

    def signed_in(self, user):
        self.set_appearance(*self.store.appearance(user.id))
        if user.must_change:
            dialog = PasswordDialog(self.store, user, self, required=True)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.show_login("Sign in to continue and change your temporary password.")
                return
        self.user = self.store.current(user.id)
        self.access_revision = self.store.access_revision()
        self.last_activity = time.monotonic()
        self.last_policy_check = self.last_activity
        view = WorkspaceView(self.store, self.user, self.demo, (self.mode, self.accent))
        view.appearance.changed.connect(self.change_appearance)
        view.sign_out.connect(self.logout)
        self.replace_view(view)

    def set_appearance(self, mode, accent):
        apply_theme(QApplication.instance(), mode, accent)
        self.mode, self.accent = mode, accent
        icon = app_icon(accent)
        self.setWindowIcon(icon)
        QApplication.instance().setWindowIcon(icon)

    def change_appearance(self, mode, accent):
        self.pending_appearance = (mode, accent)
        # Finish handling the click before repolishing widgets. Coalesce rapid choices.
        self.appearance_timer.start(0)

    def commit_appearance(self):
        if self.pending_appearance is None:
            return
        mode, accent = self.pending_appearance
        self.pending_appearance = None
        try:
            self.store.save_appearance(mode, accent, self.user.id if self.user else None)
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            # Keep controls and the applied colors consistent if persistence fails.
            controls = self.centralWidget().appearance
            controls.set_selection(self.mode, self.accent)
            failure(self, exc)
            return
        self.set_appearance(mode, accent)

    def logout(self, message="You have been signed out."):
        user, self.user = self.user, None
        # Reject any nested modal dialogs before removing the authenticated view.
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
        if user:
            try:
                self.store.record_event(user.id, "session_ended")
            except (PermissionError, sqlite3.Error):
                logging.getLogger(__name__).info("Unable to record session end")
        self.show_login(message)

    def eventFilter(self, watched, event):
        if self.user and event.type() in {QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.Wheel, QEvent.Type.MouseMove}:
            # Do not revive an already-expired session when the PC resumes from sleep.
            if time.monotonic() - self.last_activity >= self.idle_seconds:
                self.logout("Your session expired after inactivity. Sign in to continue.")
                return True
            self.last_activity = time.monotonic()
        return super().eventFilter(watched, event)

    def check_session(self):
        if not self.user:
            return
        now = time.monotonic()
        if now - self.last_activity >= self.idle_seconds:
            self.logout("Your session expired after inactivity. Sign in to continue.")
        elif now - self.last_policy_check >= 30:
            self.last_policy_check = now
            try:
                if self.store.current(self.user.id) != self.user:
                    self.logout("Your account settings changed. Please sign in again.")
                elif self.access_revision != self.store.access_revision():
                    self.access_revision = self.store.access_revision()
                    self.centralWidget().refresh()
            except (PermissionError, sqlite3.Error):
                self.logout("Your account settings changed. Please sign in again.")

    def closeEvent(self, event):
        self.timer.stop()
        QApplication.instance().removeEventFilter(self)
        if self.user:
            try:
                self.store.record_event(self.user.id, "application_closed")
            except (PermissionError, sqlite3.Error):
                pass
        super().closeEvent(event)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="WorkTool desktop launcher (Windows 10/11)")
    parser.add_argument("--demo", action="store_true", help="Use isolated demo storage and create seven test accounts on first run")
    parser.add_argument("--data-dir", type=Path, help="Override the local data folder; do not use a network share")
    parser.add_argument("--idle-minutes", type=int, default=15, choices=range(1, 121), metavar="1..120")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    app = QApplication([sys.argv[0]])
    app.setApplicationName("WorkTool")
    app.setOrganizationName("WorkTool")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setWindowIcon(app_icon())
    data_dir = args.data_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / ("WorkTool-Demo" if args.demo else "WorkTool")
    store, lock = None, None
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(data_dir / "worktool.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(100):
            failure(None, "WorkTool is already running with this data folder. Close that window before opening another instance.")
            return 1
        logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(data_dir / "worktool.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")], format="%(asctime)s %(levelname)s %(message)s")
        store = Store(data_dir / "worktool.sqlite3")
        # An explicit custom data folder is permanently tagged, preventing accidental
        # seeding of known demo accounts into a previously normal installation.
        mode = "demo" if args.demo else "standard"
        saved = store.db.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()
        if saved and saved[0] != mode:
            raise ValueError("This data folder belongs to a different mode. Choose a separate --data-dir for demo and standard use.")
        with store.db:
            store.db.execute("INSERT OR IGNORE INTO metadata VALUES ('mode', ?)", (mode,))
        if args.demo:
            store.seed_demo()
        window = MainWindow(store, args.demo, args.idle_minutes)

        def handle_exception(exc_type, value, traceback):
            logging.error("Unhandled application error", exc_info=(exc_type, value, traceback))
            failure(window, f"An unexpected error occurred. Restart WorkTool if the problem continues.\n\nDiagnostic log: {data_dir / 'worktool.log'}")

        sys.excepthook = handle_exception
        window.show()
        return app.exec()
    except (OSError, sqlite3.Error, ValueError) as exc:
        failure(None, f"WorkTool could not start.\n\n{exc}")
        return 1
    finally:
        if store:
            store.close()
        if lock:
            lock.unlock()
