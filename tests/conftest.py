import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Keep pytest temporary data within the workspace in restricted environments.
os.environ["TMP"] = str(Path(__file__).resolve().parents[1] / ".tmp")
os.environ["TEMP"] = os.environ["TMP"]
Path(os.environ["TMP"]).mkdir(exist_ok=True)

import pytest
from PySide6.QtWidgets import QApplication

from worktool.store import Store


@pytest.fixture(scope="session")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def store(tmp_path):
    instance = Store(tmp_path / "test.sqlite3")
    instance.bootstrap("admin", "Test Administrator", "Admin-password-123")
    yield instance
    instance.close()


@pytest.fixture
def admin(store):
    return store.authenticate("admin", "Admin-password-123")


@pytest.fixture
def member(store, admin):
    store.save_user(admin.id, "member", "Test Member", False, ["it"], password="Temporary-pass-123")
    user = store.authenticate("member", "Temporary-pass-123")
    store.change_password(user.id, "Temporary-pass-123", "Member-password-123")
    return store.current(user.id)
