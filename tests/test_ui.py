import time
import json
import sys
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QPalette

from worktool.app import LoginView, MainWindow, WorkspaceView
from worktool.launcher import launch
from worktool.theme import STYLE


def test_login_search_favorites_and_logout(app, store, admin):
    app.setStyleSheet(STYLE)
    window = MainWindow(store)
    window.show()
    app.processEvents()
    login = window.centralWidget()
    assert isinstance(login, LoginView)
    login.username.setText("admin")
    login.password.setText("Admin-password-123")
    QTest.mouseClick(login.submit, Qt.MouseButton.LeftButton)
    app.processEvents()
    workspace = window.centralWidget()
    assert isinstance(workspace, WorkspaceView)
    assert workspace.departments.count() == 6
    assert len(workspace.pages[0].cards) == 10
    workspace.search.setText("Calculator")
    assert len(workspace.pages[0].cards) == 1
    entry_id = workspace.pages[0].cards[0].entry.id
    workspace.favorite(entry_id)
    workspace.search.clear()
    workspace.favorite_filter.setChecked(True)
    workspace.filter_tools()
    assert len(workspace.pages[0].cards) == 1
    window.logout()
    app.processEvents()
    assert isinstance(window.centralWidget(), LoginView)
    assert window.user is None
    window.close()


def test_member_tabs_and_inactivity_lock(app, store, member):
    window = MainWindow(store, idle_minutes=1)
    window.signed_in(member)
    assert window.centralWidget().department_keys == ["general", "it"]
    window.last_activity = time.monotonic() - 61
    window.check_session()
    assert window.user is None
    assert isinstance(window.centralWidget(), LoginView)
    window.close()


def test_live_account_policy_check(app, store, admin, member):
    window = MainWindow(store)
    window.signed_in(member)
    store.save_user(admin.id, member.username, member.display_name, False, [], user_id=member.id)
    window.last_policy_check = 0
    window.check_session()
    assert window.user is None
    window.close()


def test_launcher_requests_browser_without_opening_real_site(app, store, admin):
    entry = store.entries(admin.id, "general", "link")[0]
    with patch("worktool.launcher.QDesktopServices.openUrl", return_value=True) as opener:
        assert launch(store, admin.id, entry.id) == entry.title
        assert opener.call_args.args[0].toString() == entry.target


def test_launcher_preserves_argument_boundaries(app, store, admin):
    store.save_entry(admin.id, "general", "app", "Example", "", "example.exe", ["a b", "literal&value"])
    entry = next(e for e in store.entries(admin.id) if e.title == "Example")
    with patch("worktool.launcher.resolve_executable", return_value="C:/Example/example.exe"), patch("worktool.launcher.QProcess.startDetached", return_value=(True, 123)) as start:
        launch(store, admin.id, entry.id)
        start.assert_called_once_with("C:/Example/example.exe", ["a b", "literal&value"])


def test_real_detached_process_launch(app, store, admin, tmp_path):
    marker = tmp_path / "launched.json"
    code = f"import json,sys; from pathlib import Path; Path({str(marker)!r}).write_text(json.dumps(sys.argv[1:]))"
    arguments = ["-c", code, "value with spaces", "literal&symbol"]
    store.save_entry(admin.id, "general", "app", "Process integration", "", sys.executable, arguments)
    entry = next(e for e in store.entries(admin.id) if e.title == "Process integration")
    launch(store, admin.id, entry.id)
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        QTest.qWait(50)
    assert json.loads(marker.read_text()) == ["value with spaces", "literal&symbol"]


def test_live_appearance_preserves_workspace_and_restores_per_user(app, store, admin, member):
    window = MainWindow(store)
    window.signed_in(admin)
    workspace = window.centralWidget()
    workspace.departments.setCurrentIndex(1)
    workspace.search.setText("Calculator")
    for mode, accent in (("light", "pink"), ("dark", "pink"), ("dark", "purple"), ("light", "purple")):
        QTest.mouseClick(workspace.appearance.buttons[mode], Qt.MouseButton.LeftButton)
        QTest.mouseClick(workspace.appearance.buttons[accent], Qt.MouseButton.LeftButton)
        app.processEvents()
        assert window.centralWidget() is workspace
        assert workspace.departments.currentIndex() == 1
        assert workspace.search.text() == "Calculator"
        assert (app.palette().color(QPalette.ColorRole.Window).lightness() < 128) == (mode == "dark")
    workspace.appearance.buttons['dark'].click()
    workspace.appearance.buttons['pink'].click()
    app.processEvents()
    window.check_session()
    assert window.user.id == admin.id
    window.logout()
    assert (window.mode, window.accent) == ("light", "purple")
    window.signed_in(member)
    assert (window.mode, window.accent) == ("light", "purple")
    window.close()
    restarted = MainWindow(store)
    restarted.signed_in(admin)
    assert (restarted.mode, restarted.accent) == ("dark", "pink")
    assert restarted.centralWidget().appearance.buttons['dark'].isChecked()
    restarted.close()
