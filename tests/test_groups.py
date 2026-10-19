import sqlite3

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from worktool.app import MainWindow
from worktool.dialogs import GroupDialog
from worktool.store import Store


def assigned_tool(store, admin, title='Restricted finance portal'):
    return store.save_entry(admin.id, 'finance', 'link', title, 'Group access test',
                            'https://example.com/finance', [], restricted=True)


def test_groups_and_direct_grants_are_deduplicated_and_revoked_independently(store, admin, member):
    entry_id = assigned_tool(store, admin)
    with pytest.raises(PermissionError):
        store.authorized_entry(member.id, entry_id)
    first = store.save_group(admin.id, 'Project Alpha', '', [member.id, member.id], [entry_id, entry_id])
    second = store.save_group(admin.id, 'Project Beta', '', [], [entry_id])
    store.set_user_access(admin.id, member.id, [first, second, first], [entry_id, entry_id])
    assert [e.id for e in store.entries(member.id)].count(entry_id) == 1
    assert set(store.preview_access(admin.id, member.id)[entry_id]) == {
        'Direct assignment', 'Group: Project Alpha', 'Group: Project Beta'}
    store.set_user_access(admin.id, member.id, [second], [])
    assert store.authorized_entry(member.id, entry_id).id == entry_id
    store.delete_group(admin.id, second)
    with pytest.raises(PermissionError):
        store.authorized_entry(member.id, entry_id)
    assert 'finance' not in store.available_departments(member.id)


def test_assignment_does_not_grant_other_tools_in_that_department(store, admin, member):
    entry_id = assigned_tool(store, admin)
    store.set_user_access(admin.id, member.id, [], [entry_id])
    assert [e.id for e in store.entries(member.id, 'finance')] == [entry_id]
    assert store.available_departments(member.id) == ['general', 'it', 'finance']
    other = next(e for e in store.entries(admin.id, 'finance') if e.id != entry_id)
    with pytest.raises(PermissionError):
        store.authorized_entry(member.id, other.id)


def test_restricted_flag_can_remove_department_default_access(store, admin, member):
    entry = store.entries(member.id, 'it', 'link')[0]
    store.save_entry(admin.id, entry.department, entry.kind, entry.title, entry.description,
                     entry.target, entry.arguments, entry.id, restricted=True)
    with pytest.raises(PermissionError):
        store.authorized_entry(member.id, entry.id)
    group_id = store.save_group(admin.id, 'IT specialists', '', [member.id], [entry.id])
    assert store.authorized_entry(member.id, entry.id).id == entry.id
    store.save_group(admin.id, 'IT specialists', '', [], [entry.id], group_id)
    with pytest.raises(PermissionError):
        store.authorized_entry(member.id, entry.id)


def test_assignment_admin_authorization_and_atomic_writes(store, admin, member):
    entry_id = assigned_tool(store, admin)
    group_id = store.save_group(admin.id, 'Valid', '', [member.id], [entry_id])
    with pytest.raises(PermissionError):
        store.save_group(member.id, 'Escalation', '', [member.id], [entry_id])
    with pytest.raises(PermissionError):
        store.set_user_access(member.id, member.id, [group_id], [entry_id])
    with pytest.raises(PermissionError):
        store.delete_group(member.id, group_id)
    with pytest.raises(PermissionError):
        store.preview_access(member.id, admin.id)
    with pytest.raises(sqlite3.IntegrityError):
        store.set_user_access(admin.id, member.id, [999999], [entry_id])
    assert store.user_access(admin.id, member.id) == ({group_id}, set())
    with pytest.raises(sqlite3.IntegrityError):
        store.save_group(admin.id, 'Invalid replacement', '', [member.id], [999999], group_id)
    assert store.group_access(admin.id, group_id) == ({member.id}, {entry_id})
    assert store.groups(admin.id)[0]['name'] == 'Valid'


def test_grants_persist_and_deleted_catalog_entries_cascade(store, admin, member):
    entry_id = assigned_tool(store, admin)
    group_id = store.save_group(admin.id, 'Persistent', '', [member.id], [entry_id])
    store.set_user_access(admin.id, member.id, [group_id], [entry_id])
    reopened = Store(store.path)
    assert [e.id for e in reopened.entries(member.id)].count(entry_id) == 1
    reopened.close()
    store.delete_entry(admin.id, entry_id)
    assert store.user_access(admin.id, member.id) == ({group_id}, set())
    assert store.group_access(admin.id, group_id) == ({member.id}, set())


def test_real_tab_and_theme_clicks_remain_stable_and_pages_load_on_demand(app, store, admin):
    window = MainWindow(store)
    window.show()
    window.signed_in(admin)
    QTest.qWait(50)
    view = window.centralWidget()
    assert sum(len(page.cards) for page in view.pages) == 10
    bar = view.departments.tabBar()
    initial_rects = [bar.tabRect(i) for i in range(bar.count())]
    for mode, accent in [('dark', 'pink'), ('light', 'purple')]:
        QTest.mouseClick(view.appearance.buttons[mode], Qt.MouseButton.LeftButton)
        QTest.mouseClick(view.appearance.buttons[accent], Qt.MouseButton.LeftButton)
        QTest.qWait(50)
        assert (window.mode, window.accent) == (mode, accent)
        for index in range(bar.count()):
            QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=bar.tabRect(index).center())
            QTest.qWait(10)
            assert view.departments.currentIndex() == index
            assert [bar.tabRect(i) for i in range(bar.count())] == initial_rects
            if index < len(view.department_keys):
                tabs = view.departments.currentWidget()
                for subtab in (1, 0):
                    QTest.mouseClick(tabs.tabBar(), Qt.MouseButton.LeftButton, pos=tabs.tabBar().tabRect(subtab).center())
                    assert tabs.currentIndex() == subtab
    window.close()


def test_admin_group_and_user_access_workflow_with_no_duplicate_cards(app, store, admin, member):
    entry_id = assigned_tool(store, admin)
    dialog = GroupDialog(store, admin)
    dialog.name.setText('UI project group')
    dialog.member_checks[member.id].setChecked(True)
    dialog.tool_checks[entry_id].setChecked(True)
    dialog.save()
    assert dialog.result() == dialog.DialogCode.Accepted
    group_id = store.groups(admin.id)[0]['id']
    window = MainWindow(store)
    window.show()
    window.signed_in(admin)
    view = window.centralWidget()
    view.administration()
    app.processEvents()
    panel = view.admin_panel
    panel.tabs.setCurrentIndex(2)
    access = panel.access_panel
    access.user.setCurrentIndex(access.user.findData(member.id))
    app.processEvents()
    assert access.group_checks[group_id].isChecked()
    assert not access.tool_checks[entry_id].isChecked()
    assert [e.id for e in store.entries(member.id)].count(entry_id) == 1
    # Click the entire checkbox cell (including its far edge), not its tiny indicator.
    row = next(i for i, e in enumerate(access.entries) if e.id == entry_id)
    access.tools_table.scrollToItem(access.tools_table.item(row, 1))
    app.processEvents()
    control = access.tool_checks[entry_id]
    QTest.mouseClick(control, Qt.MouseButton.LeftButton, pos=QPoint(control.width() - 3, control.height() // 2))
    assert control.isChecked()
    assert [e.id for e in store.entries(member.id)].count(entry_id) == 1
    access.group_checks[group_id].click()
    assert store.authorized_entry(member.id, entry_id).id == entry_id
    control.click()
    with pytest.raises(PermissionError):
        store.authorized_entry(member.id, entry_id)
    window.close()
    dialog.close()


def test_group_changes_refresh_active_tabs_without_relogin(app, store, admin, member):
    entry_id = assigned_tool(store, admin)
    window = MainWindow(store)
    window.show()
    window.signed_in(member)
    group_id = store.save_group(admin.id, 'Live access', '', [member.id], [entry_id])
    window.last_policy_check = 0
    window.check_session()
    assert window.user.id == member.id
    assert 'finance' in window.centralWidget().department_keys
    store.delete_group(admin.id, group_id)
    window.last_policy_check = 0
    window.check_session()
    assert 'finance' not in window.centralWidget().department_keys
    assert window.user.id == member.id
    window.close()
