"""Shared folder lifecycle, safe imports, persistence, and real admin/user flows."""

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool
from PySide6.QtTest import QSignalSpy, QTest

from tslibrary_ui.app import create_app
from tslibrary_ui.documentation.files import DocumentationError, DocumentationFiles
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem, item_name
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.storage import JsonRepository, StorageError, catalog_data, decode_catalog
from tslibrary_ui.transfers import export_backup, import_backup


class DocumentationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.environment = patch.dict(os.environ)
        self.environment.start()
        os.environ.pop("TSLIBRARY_DOCUMENTS_PATH", None)
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.shared = self.root / "shared"
        self.shared.mkdir()
        self.catalog = DocumentationCatalog(str(self.shared), "Team manuals")
        self.files = DocumentationFiles(self.catalog)
        self.windows = []

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone(5000)
        self.app.processEvents()
        for window in self.windows:
            window.close()
            window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()
        self.environment.stop()

    def source(self, name="Getting started.pdf", content=b"test guide"):
        source = self.root / name
        source.write_bytes(content)
        return source

    def create_item(self, name="IT/Setup"):
        self.files.create_item(name)
        item = DocumentationItem(name)
        self.catalog.items.append(item)
        return item

    def controller(self, repository):
        controller = PreviewController(repository=repository)
        self.windows.extend([controller.admin, controller.main_window,
                             controller.library, controller.welcome])
        return controller

    def test_names_create_nested_folders_and_copy_original_files(self):
        self.create_item()
        source = self.source()
        self.files.add_files("IT/Setup", [source])
        expected = self.shared / "Team manuals" / "IT" / "Setup" / source.name
        self.assertEqual(expected.read_bytes(), source.read_bytes())
        self.assertTrue(source.exists())
        self.assertEqual(self.files.list_files("IT/Setup"), [source.name])
        self.assertEqual(self.files.file_path("IT/Setup", source.name), expected)

    def test_invalid_names_and_traversal_are_rejected(self):
        for name in ["", "..", "../Outside", "/Absolute", "C:/Escape", "CON", "a//b", "a/../b", "Folder.", "Folder /x"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.files.create_item(name)
        self.assertFalse((self.root / "Outside").exists())
        self.assertEqual(item_name(r"IT\Setup"), "IT/Setup")

    def test_duplicate_import_is_non_destructive_and_batch_is_preflighted(self):
        self.create_item()
        source = self.source()
        self.files.add_files("IT/Setup", [source])
        extra = self.source("Extra.txt", b"new")
        source.write_bytes(b"replacement")
        with self.assertRaises(DocumentationError):
            self.files.add_files("IT/Setup", [extra, source])
        folder = self.files.item_path("IT/Setup")
        self.assertFalse((folder / extra.name).exists())
        self.assertEqual((folder / source.name).read_bytes(), b"test guide")
        self.assertEqual(source.read_bytes(), b"replacement")

    def test_partial_copy_failure_cleans_only_new_files(self):
        self.create_item()
        source = self.source()
        original = self.files.item_path("IT/Setup") / "Keep.txt"
        original.write_text("keep", encoding="utf-8")
        with patch("tslibrary_ui.documentation.files.shutil.copyfileobj", side_effect=OSError("Disconnected")):
            with self.assertRaises(OSError):
                self.files.add_files("IT/Setup", [source])
        self.assertEqual(list(self.files.item_path("IT/Setup").iterdir()), [original])

    def test_concurrent_upload_is_not_overwritten_and_partial_file_is_hidden(self):
        self.create_item()
        source = self.source()
        destination = self.files.item_path("IT/Setup") / source.name

        def competing_upload(origin, target, **kwargs):
            target.write(origin.read())
            self.assertEqual(self.files.list_files("IT/Setup"), [])
            destination.write_bytes(b"another upload")

        with patch("tslibrary_ui.documentation.files.shutil.copyfileobj", side_effect=competing_upload):
            with self.assertRaises(OSError):
                self.files.add_files("IT/Setup", [source])
        self.assertEqual(destination.read_bytes(), b"another upload")
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_unavailable_location_does_not_create_a_fake_share(self):
        missing = self.root / "offline-share"
        self.catalog.parent_path = str(missing)
        with self.assertRaises(DocumentationError):
            self.files.create_item("IT")
        self.assertFalse(missing.exists())

    def test_root_rename_and_item_rename_keep_files_and_child_ids(self):
        parent = self.create_item("IT")
        child = self.create_item("it/Setup")
        source = self.source()
        self.files.add_files(child.name, [source])
        self.files.configure(str(self.shared), "Company guides")
        self.assertFalse((self.shared / "Team manuals").exists())
        self.files.rename_item(parent, "Engineering")
        self.assertEqual(child.name, "Engineering/Setup")
        self.assertEqual(self.files.file_path(child.name, source.name).read_bytes(), source.read_bytes())
        self.assertEqual(self.catalog.items[1].id, child.id)

    def test_existing_destination_is_not_merged_or_overwritten(self):
        item = self.create_item()
        self.create_item("HR")
        with self.assertRaises(DocumentationError):
            self.files.rename_item(item, "HR")
        (self.shared / "Other root").mkdir()
        with self.assertRaises(DocumentationError):
            self.files.configure(str(self.shared), "Other root")
        self.assertEqual(self.catalog.root_name, "Team manuals")
        self.assertTrue(self.files.item_path(item.name).is_dir())

    def test_catalog_and_backup_round_trip_without_personal_data_or_file_contents(self):
        item = self.create_item()
        self.files.add_files(item.name, [self.source(content=b"PRIVATE-FILE-CONTENTS")])
        session = LibrarySession(documentation=self.catalog)
        repo = JsonRepository(self.root / "catalog.json", self.root / "personal.json")
        repo.save_workplace(WorkplaceConfig(start_in_workplace=True))
        before = repo.config_path.read_bytes()
        repo.save_catalog(session)
        loaded = repo.load_catalog()
        self.assertEqual(loaded.documentation, self.catalog)
        self.assertEqual(repo.config_path.read_bytes(), before)
        backup = self.root / "backup.json"
        export_backup(backup, session, catalog=True)
        self.assertEqual(import_backup(backup, catalog=True).documentation, self.catalog)
        self.assertNotIn("PRIVATE-FILE-CONTENTS", backup.read_text(encoding="utf-8"))
        self.assertEqual(decode_catalog({"version": 1}).documentation, DocumentationCatalog())

    def test_bad_documentation_metadata_fails_validation(self):
        repo = JsonRepository(self.root / "catalog.json", self.root / "personal.json")
        from tslibrary_ui.storage import JsonFile
        for docs in [[], {"root_name": "../outside"}, {"items": [{"id": "1", "name": "bad/../path"}]},
                     {"items": [{"id": "1", "name": "A"}, {"id": "2", "name": "a"}]}]:
            JsonFile._write(repo.catalog_path, dict(version=1, documentation=docs))
            with self.assertRaises(StorageError):
                repo.load_catalog()

    def test_local_mount_override_keeps_catalog_portable(self):
        self.create_item()
        self.catalog.parent_path = r"Z:\OtherUsersMount"
        with patch.dict(os.environ, {"TSLIBRARY_DOCUMENTS_PATH": str(self.shared)}):
            self.assertTrue(self.files.item_path("IT/Setup").is_dir())

    def test_admin_documents_persist_without_a_user_documentation_tab(self):
        repo = JsonRepository(self.root / "catalog.json", self.root / "admin.json")
        admin = self.controller(repo)
        admin.admin.set_page("Documentation")
        page = admin.admin.documentation_page
        settings = admin.admin.settings_page
        settings.location_edit.setText(str(self.shared))
        settings.root_name_edit.setText("Company documentation")
        settings.save_location_button.click()
        page.add_button.click()
        editor = page.item_dialog
        editor.name_edit.setText("IT/Setup")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(page.selected_folder, "IT/Setup")
        self.assertIsNone(page.files_dialog)
        page.import_files([self.source()])
        deadline = time.monotonic() + 8
        while (page.busy or page.directory_loading) and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(page.busy)
        self.assertFalse(page.directory_loading)
        self.assertEqual(page.table.rowCount(), 1)
        user_repo = JsonRepository(repo.catalog_path, self.root / "user.json")
        user = self.controller(user_repo).main_window
        self.assertEqual([user.tabs.tabText(i) for i in range(user.tabs.count())],
                         ["Websites", "Applications", "Collection"])
        self.assertEqual(user.session.documentation.items[0].name, "IT/Setup")
        with patch("tslibrary_ui.documentation.page.QDesktopServices.openUrl", return_value=True) as launch:
            page._open_row(0, 0)
        self.assertEqual(Path(launch.call_args.args[0].toLocalFile()).read_bytes(), b"test guide")
        self.assertFalse(user_repo.config_path.exists())
        # Removing the published item keeps actual shared documents intact.
        folder = DocumentationFiles(admin.session.documentation).item_path("IT/Setup")
        page._remove(admin.session.documentation.items[0])
        user.reload_catalog()
        self.assertEqual(user.session.documentation.items, [])
        self.assertTrue((folder / "Getting started.pdf").exists())

    def test_failed_creation_does_not_publish_a_catalog_item(self):
        repo = JsonRepository(self.root / "catalog.json", self.root / "admin.json")
        controller = self.controller(repo)
        page = controller.admin.documentation_page
        page.add_item()
        page.item_dialog.name_edit.setText("Setup")
        page.item_dialog.save_button.click()
        self.assertFalse(controller.session.documentation.items)
        self.assertFalse(repo.catalog_path.exists())
        self.assertTrue(page.item_dialog.error.text())
        page.item_dialog.reject()


if __name__ == "__main__":
    unittest.main()
