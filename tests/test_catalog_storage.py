"""Exercise a replaceable catalog through real admin/user windows, without a server."""

from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tslibrary_ui.app import create_app
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.storage import (
    ApplicationRepository, JsonCatalogStore, LocalWorkplaceStore, StorageError,
    catalog_data, create_repository, decode_catalog,
)
from tslibrary_ui.websites.models import Website
from tslibrary_ui.workplace.models import collection_entries


class MemoryCatalogStore:
    """Fake service with the same payload boundary a server adapter must use."""

    def __init__(self, session):
        self.payload = catalog_data(session)
        self.available = True

    def load_catalog(self):
        if not self.available:
            raise StorageError("Test catalog is offline.")
        return decode_catalog(self.payload)

    def save_catalog(self, session):
        if not self.available:
            raise StorageError("Test catalog is offline.")
        self.payload = catalog_data(session)


class CatalogStorageChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.controllers = []

    def tearDown(self):
        for controller in self.controllers:
            for window in (controller.main_window, controller.admin, controller.library, controller.welcome):
                window.close()
                window.deleteLater()
            controller.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def controller(self, repository):
        controller = PreviewController(repository=repository)
        self.controllers.append(controller)
        return controller

    def test_factory_keeps_existing_personal_file_when_catalog_backend_is_replaced(self):
        path = self.root / "user" / "workplace.json"
        local = LocalWorkplaceStore(path)
        config = WorkplaceConfig(personal_websites=[Website("Mine", "https://personal.example.com")],
                                 favorites=["websites:catalog:portal"], start_in_workplace=True)
        local.save_workplace(config)
        before = path.read_bytes()
        backend = MemoryCatalogStore(LibrarySession())
        with patch.dict(os.environ, {"TSLIBRARY_CONFIG_PATH": str(path)}):
            repo = create_repository(catalog_store=backend)
        self.assertIs(repo.catalog_store, backend)
        self.assertEqual(repo.load_workplace(), config)
        repo.save_catalog(LibrarySession(websites=[Website("Team", "https://team.example.com")]))
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn("personal.example.com", str(backend.payload))
        repo.save_workplace(replace(config, view_mode="list"))
        self.assertEqual(local.load_workplace().view_mode, "list")

    def test_default_personal_path_stays_per_user_even_with_a_custom_catalog(self):
        user_root = self.root / "AppData"
        with patch.dict(os.environ, {"APPDATA": str(user_root)}):
            with patch.dict(os.environ) as environment:
                environment.pop("TSLIBRARY_CONFIG_PATH", None)
                repo = create_repository(catalog_store=MemoryCatalogStore(LibrarySession()))
        self.assertEqual(repo.workplace_store.path, user_root / "TSLibrary" / "workplace.json")

    def test_json_placeholder_admin_updates_reach_collection_without_changing_personal_data(self):
        backend = JsonCatalogStore(self.root / "shared" / "catalog.json")
        portal = Website("Portal", "https://portal.example.com")
        backend.save_catalog(LibrarySession(websites=[portal]))
        personal = Website("Private", "https://private.example.com")
        user_store = LocalWorkplaceStore(self.root / "user" / "workplace.json")
        config = WorkplaceConfig(website_ids=[portal.id], personal_websites=[personal],
                                 favorites=[f"websites:catalog:{portal.id}"],
                                 groups={"Work": [f"websites:catalog:{portal.id}"]})
        user_store.save_workplace(config)
        admin = self.controller(ApplicationRepository(
            backend, LocalWorkplaceStore(self.root / "admin" / "workplace.json")))
        user_repo = ApplicationRepository(backend, user_store)
        user = self.controller(user_repo).main_window
        before = user_store.path.read_bytes()
        # Publish using the actual admin editor and its normal save signal.
        page = admin.admin.websites_page
        page.add_website()
        editor = page.website_dialog
        editor.name_edit.setText("New company site")
        editor.url_edit.setText("https://new.example.com")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(len(backend.load_catalog().websites), 2)
        user.collection_page.add_button.click()
        self.assertEqual(len(collection_entries(user.session, user.config)), 2)
        self.assertEqual({entry.id for entry in user.websites_page.model.entries}, {portal.id, personal.id})
        self.assertEqual(user_store.path.read_bytes(), before)
        self.assertFalse(admin.main_window.config.personal_websites)
        # A fresh application instance still reads exactly the same user data.
        restarted = self.controller(user_repo).main_window
        self.assertEqual(restarted.config, config)
        self.assertEqual(len(restarted.collection_page.model.entries), 2)

    def test_service_failure_preserves_collection_and_allows_personal_saves(self):
        portal = Website("Portal", "https://portal.example.com")
        backend = MemoryCatalogStore(LibrarySession(websites=[portal]))
        local = LocalWorkplaceStore(self.root / "user.json")
        controller = self.controller(ApplicationRepository(backend, local))
        window = controller.main_window
        backend.available = False
        with patch("tslibrary_ui.main_window.QMessageBox.warning") as warning:
            window.reload_catalog()
        warning.assert_called_once()
        self.assertEqual(window.session.websites[0].id, portal.id)
        page = window.websites_page
        page.add_button.click()
        editor = window.personal_dialog
        editor.name_edit.setText("Offline personal site")
        editor.url_edit.setText("https://offline.example.com")
        editor.save_button.click()
        self.assertEqual(local.load_workplace().personal_websites[0].name, "Offline personal site")
        before = local.path.read_bytes()
        controller.session.websites.append(Website("Unpublished", "https://unpublished.example.com"))
        with patch("tslibrary_ui.navigation.QMessageBox.warning") as warning:
            controller.admin.catalog_changed.emit()
        warning.assert_called_once()
        self.assertTrue(window.catalog_reload_blocked)
        self.assertEqual(local.path.read_bytes(), before)
        self.assertEqual(len(backend.payload["websites"]), 1)


if __name__ == "__main__":
    unittest.main()
