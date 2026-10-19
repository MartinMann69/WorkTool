from collections import Counter
import time

import pytest

from worktool.catalog import validate_entry
from worktool.security import hash_password, verify_password
from worktool.store import Store


def test_salted_passwords_and_verification():
    a, b = hash_password("A-strong-password"), hash_password("A-strong-password")
    assert a != b
    assert verify_password("A-strong-password", a)
    assert not verify_password("wrong", a)
    assert not verify_password("wrong", "malformed")


def test_seed_counts_and_demo_access(tmp_path):
    store = Store(tmp_path / "demo.sqlite3")
    store.seed_demo()
    store.seed_demo()
    admin = store.authenticate("admin", "WorkTool!2026")
    assert len(store.users(admin.id)) == 7
    counts = Counter((e.department, e.kind) for e in store.entries(admin.id))
    assert len(counts) == 10
    assert set(counts.values()) == {10}
    expected = {"it.demo": {"general", "it"}, "finance.demo": {"general", "finance"},
                "people.demo": {"general", "people"}, "operations.demo": {"general", "operations"},
                "multi.demo": {"general", "it", "operations"}, "general.demo": {"general"}}
    for username, departments in expected.items():
        user = store.authenticate(username.upper(), "WorkTool!2026")
        assert {e.department for e in store.entries(user.id)} == departments
    store.close()


def test_hidden_departments_and_privileged_actions(store, admin, member):
    assert {e.department for e in store.entries(member.id)} == {"general", "it"}
    with pytest.raises(PermissionError):
        store.entries(member.id, "finance")
    finance = store.entries(admin.id, "finance")[0]
    with pytest.raises(PermissionError):
        store.authorized_entry(member.id, finance.id)
    with pytest.raises(PermissionError):
        store.users(member.id)
    with pytest.raises(PermissionError):
        store.save_user(member.id, "attacker", "Attacker", True, [], password="Temporary-pass-123")
    with pytest.raises(PermissionError):
        store.delete_entry(member.id, finance.id)


def test_lockout_persists_across_reopen(store):
    for _ in range(5):
        assert store.authenticate("admin", "wrong") is None
    assert store.authenticate("admin", "Admin-password-123") is None
    other = Store(store.path)
    assert other.authenticate("admin", "Admin-password-123") is None
    with other.db:
        other.db.execute("UPDATE users SET locked_until=?", (time.time() - 1,))
    assert other.authenticate("admin", "Admin-password-123")
    other.close()


def test_temporary_password_and_disable(store, admin):
    store.save_user(admin.id, "new.user", "New User", False, ["finance"], password="Temporary-pass-123")
    user = store.authenticate("new.user", "Temporary-pass-123")
    assert user.must_change
    with pytest.raises(PermissionError):
        store.entries(user.id)
    store.change_password(user.id, "Temporary-pass-123", "Changed-password-123")
    assert len(store.entries(user.id)) == 40
    store.save_user(admin.id, "new.user", "New User", False, ["finance"], user_id=user.id, active=False)
    assert store.authenticate("new.user", "Changed-password-123") is None
    with pytest.raises(PermissionError):
        store.entries(user.id)


def test_permission_changes_apply_immediately(store, admin, member):
    entry = store.entries(member.id, "it")[0]
    store.save_user(admin.id, member.username, member.display_name, False, [], user_id=member.id)
    with pytest.raises(PermissionError):
        store.authorized_entry(member.id, entry.id)
    store.save_user(admin.id, member.username, member.display_name, False, [], user_id=member.id, password="Reset-password-123")
    with pytest.raises(PermissionError):
        store.entries(member.id)


def test_admin_cannot_disable_or_demote_self(store, admin):
    with pytest.raises(ValueError):
        store.save_user(admin.id, "admin", "Admin", False, [], user_id=admin.id)
    with pytest.raises(ValueError):
        store.save_user(admin.id, "admin", "Admin", True, [], user_id=admin.id, active=False)


def test_catalog_changes_favorites_and_persistence(store, admin, member):
    store.save_entry(admin.id, "it", "link", "Test docs", "Documentation", "https://example.com/docs", [])
    entry = next(e for e in store.entries(member.id) if e.title == "Test docs")
    store.toggle_favorite(member.id, entry.id)
    assert entry.id in store.favorites(member.id)
    assert entry.id not in store.favorites(admin.id)
    other = Store(store.path)
    assert entry.id in other.favorites(member.id)
    other.close()
    store.save_entry(admin.id, "it", "link", "Renamed", "Documentation", "https://example.com/other", [], entry.id)
    assert store.authorized_entry(member.id, entry.id).title == "Renamed"
    store.delete_entry(admin.id, entry.id)
    assert entry.id not in store.favorites(member.id)


@pytest.mark.parametrize("target", ["javascript:alert(1)", "file:///C:/secret", "https://user:pass@example.com", "https://", "https://a b.com", "https://a.com:bad"])
def test_reject_unsafe_links(target):
    with pytest.raises(ValueError):
        validate_entry("general", "link", "Tool", "", target, [])


@pytest.mark.parametrize("target", ["evil.bat", "powershell -command hi", r"\\server\tool.exe", "tool.exe | calc.exe"])
def test_reject_scripts_network_apps_and_commands(target):
    with pytest.raises(ValueError):
        validate_entry("general", "app", "Tool", "", target, [])


def test_failed_validation_rolls_back_account_edit(store, admin, member):
    with pytest.raises(ValueError):
        store.save_user(admin.id, "changed", "Changed", False, [], user_id=member.id, password="short")
    assert store.current(member.id).username == "member"


def test_bootstrap_is_single_use(store):
    with pytest.raises(PermissionError):
        store.bootstrap("second", "Second", "Another-password-123")


def test_appearance_persistence_and_account_isolation(store, admin, member):
    assert store.appearance() == ("light", "purple")
    store.save_appearance("dark", "purple")
    store.save_appearance("dark", "pink", admin.id)
    assert store.appearance(member.id) == ("light", "purple")
    assert store.appearance() == ("dark", "purple")
    with pytest.raises(ValueError):
        store.save_appearance("invalid", "pink", admin.id)
    other = Store(store.path)
    assert other.appearance(admin.id) == ("dark", "pink")
    assert other.appearance(member.id) == ("light", "purple")
    assert other.appearance() == ("dark", "purple")
    other.close()


def test_existing_database_gains_appearance_without_losing_accounts(store, admin):
    with store.db:
        store.db.execute("DROP TABLE appearance")
    other = Store(store.path)
    assert other.authenticate("admin", "Admin-password-123").id == admin.id
    assert len(other.entries(admin.id)) == 100
    assert other.appearance(admin.id) == ("light", "purple")
    other.save_appearance("dark", "pink", admin.id)
    other.close()
