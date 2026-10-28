"""Shared profiles, independent admins, stale writers, and personal isolation."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QLockFile
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from tslibrary_ui.app import create_app
from tslibrary_ui.applications.models import Application
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.licenses.models import LibraryItem, LicenseEntry
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.storage import JsonFile, JsonRepository, StorageError, create_repository
from tslibrary_ui.team_config import CatalogConflict, SharedJsonCatalogStore, create_profile
from tslibrary_ui.websites.models import Website


class TeamConfigChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.controllers = []
        self.repo = JsonRepository(self.root / "old-catalog.json", self.root / "admin-a" / "workplace.json")
        self.session = LibrarySession(
            applications=[Application("Team editor", r"C:\Tools\Editor.exe", arguments="--team")],
            websites=[Website("Portal", "https://portal.example.com")],
            items=[LibraryItem("Seats", licenses=[LicenseEntry("Pool", 3, key="SESSION-SECRET")])])
        self.profile = self.root / "Team.json"

    def tearDown(self):
        for controller in self.controllers:
            controller._refresh_timer.stop()
            self.finish_refresh(controller)
            for window in (controller.main_window, controller.admin, controller.library, controller.welcome):
                window.close()
                window.deleteLater()
            controller.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def other_repo(self):
        return JsonRepository(self.root / "other-local.json", self.root / "admin-b" / "workplace.json")

    def controller(self, repo):
        controller = PreviewController(repository=repo)
        # These tests trigger each poll explicitly. A periodic poll can start a
        # second job during a slow full-suite event drain, making an idle-state
        # wait depend on unrelated rendering time rather than the read result.
        controller._refresh_timer.stop()
        self.controllers.append(controller)
        return controller

    def finish_refresh(self, controller):
        deadline = time.monotonic() + 8
        while controller._refresh_job is not None and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertIsNone(controller._refresh_job)

    def test_create_and_open_profile_preserve_ids_defaults_and_personal_files(self):
        self.repo.save_catalog(self.session)
        self.repo.save_workplace(WorkplaceConfig(personal_websites=[Website("Private", "https://private.example.com")]))
        old_catalog = self.repo.catalog_path.read_bytes()
        personal = self.repo.config_path.read_bytes()
        self.repo.create_team(self.profile, self.session)
        profile = json.loads(self.profile.read_text())
        self.assertEqual(profile["catalog"], "Team.catalog.json")
        shared = self.root / profile["catalog"]
        self.assertNotIn("SESSION-SECRET", shared.read_text())
        self.assertNotIn("private.example.com", shared.read_text())
        other = self.other_repo()
        loaded = other.select_team(self.profile)
        self.assertEqual(loaded.applications[0].id, self.session.applications[0].id)
        self.assertEqual(loaded.applications[0].arguments, "--team")
        self.assertEqual(loaded.items[0].licenses[0].key, "")
        self.assertEqual(self.repo.config_path.read_bytes(), personal)
        self.assertEqual(self.repo.catalog_path.read_bytes(), old_catalog)
        with patch.dict(os.environ, {"TSLIBRARY_CONFIG_PATH": str(other.config_path)}):
            restarted = create_repository()
        self.assertEqual(restarted.team_config_path, self.profile)
        self.assertEqual(restarted.load_catalog().applications[0].id, loaded.applications[0].id)
        self.assertFalse(other.config_path.exists())

    def test_missing_or_invalid_connection_never_replaces_current_repository(self):
        self.repo.create_team(self.profile, self.session)
        before = self.repo.connection_path.read_bytes()
        original = self.repo.catalog_store
        for data in ({"version": 1, "format": "tslibrary.team", "catalog": "missing.json"},
                     {"version": 99, "format": "tslibrary.team", "catalog": "Team.catalog.json"},
                     {"version": 1, "applications": []}):
            broken = self.root / "broken.json"
            JsonFile._write(broken, data)
            with self.assertRaises(StorageError):
                self.repo.select_team(broken)
            self.assertIs(self.repo.catalog_store, original)
            self.assertEqual(self.repo.connection_path.read_bytes(), before)
        (self.root / "Team.catalog.json").unlink()
        with self.assertRaises(StorageError):
            self.repo.load_catalog()
        self.assertFalse((self.root / "Team.catalog.json").exists())
        with patch.dict(os.environ, {"TSLIBRARY_CONFIG_PATH": str(self.repo.config_path)}), self.assertRaises(StorageError):
            create_repository()

    def test_existing_files_and_personal_paths_cannot_be_used_for_creation(self):
        self.repo.create_team(self.profile, self.session)
        before = self.profile.read_bytes()
        with self.assertRaises(StorageError):
            self.repo.create_team(self.profile, LibrarySession())
        self.assertEqual(self.profile.read_bytes(), before)
        with self.assertRaises(StorageError):
            self.repo.create_team(self.repo.config_path, self.session)
        self.assertFalse(self.repo.config_path.exists())

    def test_stale_admin_save_cannot_erase_another_admin_then_reload_allows_retry(self):
        first = self.repo.create_team(self.profile, self.session)
        other = self.other_repo()
        second = other.select_team(self.profile)
        first.websites.append(Website("Added by A", "https://a.example.com"))
        self.repo.save_catalog(first)
        published = self.repo.catalog_store.path.read_bytes()
        second.websites.append(Website("Added by B", "https://b.example.com"))
        with self.assertRaises(CatalogConflict):
            other.save_catalog(second)
        self.assertEqual(self.repo.catalog_store.path.read_bytes(), published)
        self.assertEqual(second.websites[-1].name, "Added by B")
        loaded = other.load_catalog()
        loaded.websites.append(second.websites[-1])
        other.save_catalog(loaded)
        loaded.websites[0].name = "Renamed portal"
        other.save_catalog(loaded)  # The store tracks its own successful writes.
        self.assertEqual(len(self.repo.load_catalog().websites), 3)
        self.assertEqual(self.repo.load_catalog().websites[0].name, "Renamed portal")

    def test_shared_lock_blocks_a_writer_without_touching_the_file(self):
        loaded = self.repo.create_team(self.profile, self.session)
        path = self.repo.catalog_store.path
        before = path.read_bytes()
        lock = QLockFile(str(path) + ".lock")
        self.assertTrue(lock.tryLock(0))
        try:
            loaded.websites.clear()
            with self.assertRaises(StorageError):
                self.repo.save_catalog(loaded)
            self.assertEqual(path.read_bytes(), before)
        finally:
            lock.unlock()
        self.repo.save_catalog(loaded)
        self.assertFalse(Path(str(path) + ".lock").exists())

    def test_config_pointer_change_requires_reopening_instead_of_writing_old_catalog(self):
        loaded = self.repo.create_team(self.profile, self.session)
        JsonFile._write(self.profile, dict(version=1, format="tslibrary.team", catalog="new.catalog.json"))
        with self.assertRaisesRegex(StorageError, "another catalog"):
            self.repo.save_catalog(loaded)

    def test_failed_write_keeps_catalog_revision_and_releases_the_lock_for_retry(self):
        loaded = self.repo.create_team(self.profile, self.session)
        path = self.repo.catalog_store.path
        original = path.read_bytes()
        loaded.websites[0].name = "Draft"
        with patch("tslibrary_ui.storage.os.replace", side_effect=PermissionError("fixture")):
            with self.assertRaises(StorageError):
                self.repo.save_catalog(loaded)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(Path(str(path) + ".lock").exists())
        self.repo.save_catalog(loaded)
        self.assertEqual(self.repo.load_catalog().websites[0].name, "Draft")

    def test_two_processes_cannot_both_publish_the_same_starting_revision(self):
        profile = create_profile(self.profile, LibrarySession(websites=[Website("Seed", "https://seed.example.com")]))
        path = profile.with_name("Team.catalog.json")
        code = '''
import sys
from pathlib import Path
from tslibrary_ui.team_config import SharedJsonCatalogStore
from tslibrary_ui.storage import StorageError
from tslibrary_ui.websites.models import Website
from tslibrary_ui.app import create_app
app = create_app()
store = SharedJsonCatalogStore(Path(sys.argv[1]))
session = store.load_catalog()
print("READY", flush=True)
sys.stdin.readline()
session.websites.append(Website(sys.argv[2], "https://" + sys.argv[2] + ".example.com"))
try:
    store.save_catalog(session)
    print("SAVED")
except StorageError:
    print("REJECTED")
'''
        processes = [subprocess.Popen([sys.executable, "-c", code, str(path), name],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for name in ("admin-a", "admin-b")]
        try:
            for process in processes:
                ready = process.stdout.readline().strip()
                if ready != "READY":
                    process.wait(timeout=10)
                    self.fail(f"Child did not start: {process.returncode}: {process.stderr.read()}")
            for process in processes:
                process.stdin.write("go\n")
                process.stdin.flush()
            results = []
            for process in processes:
                output, error = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 0, error)
                results.append(output.strip())
            self.assertCountEqual(results, ["SAVED", "REJECTED"])
            self.assertEqual(len(SharedJsonCatalogStore(path).load_catalog().websites), 2)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()

    def test_background_refresh_reaches_other_admin_and_does_not_replace_editor_or_draft(self):
        self.repo.create_team(self.profile, self.session)
        other = self.other_repo()
        other.select_team(self.profile)
        a, b = self.controller(self.repo), self.controller(other)
        b.show_admin()
        self.finish_refresh(b)
        a.session.websites.append(Website("New team site", "https://new.example.com"))
        a._save_catalog()
        b._poll_catalog()
        self.finish_refresh(b)
        self.assertEqual(b.session.websites[-1].name, "New team site")
        b.admin.websites_page.add_website()
        b.admin.websites_page.website_dialog.name_edit.setText("Unfinished draft")
        a.session.websites[0].name = "Changed again"
        a._save_catalog()
        b._poll_catalog()
        self.assertIsNone(b._refresh_job)
        self.assertEqual(b.admin.websites_page.website_dialog.name_edit.text(), "Unfinished draft")
        b.admin.websites_page.website_dialog.reject()
        b.admin.settings_page.location_edit.setText("Unsaved location")
        b._poll_catalog()
        self.assertEqual(b.session.websites[0].name, "Portal")
        b.admin.settings_page.reload_settings()
        b._poll_catalog()
        self.finish_refresh(b)
        self.assertEqual(b.session.websites[0].name, "Changed again")

    def test_controller_conflict_keeps_draft_and_explicit_reload_reveals_other_admin(self):
        self.repo.create_team(self.profile, self.session)
        other = self.other_repo()
        other.select_team(self.profile)
        a, b = self.controller(self.repo), self.controller(other)
        a.session.websites[0].name = "Admin A"
        a._save_catalog()
        b.session.websites[0].name = "Admin B"
        with patch("tslibrary_ui.navigation.QMessageBox.warning") as warning:
            b._save_catalog()
        warning.assert_called_once()
        self.assertTrue(b._catalog_unsaved)
        self.assertEqual(b.session.websites[0].name, "Admin B")
        with patch("tslibrary_ui.navigation.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            b.reload_admin_catalog()
        self.finish_refresh(b)
        self.assertFalse(b._catalog_unsaved)
        self.assertEqual(b.session.websites[0].name, "Admin A")

    def test_inflight_read_cannot_replace_an_editor_started_while_it_was_reading(self):
        self.repo.create_team(self.profile, self.session)
        other = self.other_repo()
        other.select_team(self.profile)
        controller = self.controller(other)
        updated = self.repo.load_catalog()
        updated.websites[0].name = "Remote update"
        self.repo.save_catalog(updated)
        controller._start_catalog_refresh(manual=False)
        controller.admin.websites_page.add_website()
        controller.admin.websites_page.website_dialog.name_edit.setText("Draft started during read")
        self.finish_refresh(controller)
        self.assertEqual(controller.session.websites[0].name, "Portal")
        self.assertEqual(controller.admin.websites_page.website_dialog.name_edit.text(), "Draft started during read")
        controller.admin.websites_page.website_dialog.reject()
        controller._start_catalog_refresh(manual=False)
        self.finish_refresh(controller)
        self.assertEqual(controller.session.websites[0].name, "Remote update")

    def test_stale_documentation_rename_does_not_change_any_shared_folder(self):
        parent = self.root / "documents"
        folder = parent / "Manuals" / "IT"
        folder.mkdir(parents=True)
        self.session.documentation = DocumentationCatalog(str(parent), "Manuals", [DocumentationItem("IT")])
        self.repo.create_team(self.profile, self.session)
        other = self.other_repo()
        other.select_team(self.profile)
        controller = self.controller(other)
        updated = self.repo.load_catalog()
        updated.websites[0].name = "Other admin saved"
        self.repo.save_catalog(updated)
        page = controller.admin.documentation_page
        page.add_item(controller.session.documentation.items[0])
        dialog = page.item_dialog
        dialog.name_edit.setText("Renamed")
        dialog.save_button.click()
        self.assertTrue(folder.is_dir())
        self.assertFalse(folder.with_name("Renamed").exists())
        self.assertEqual(controller.session.documentation.items[0].name, "IT")
        self.assertIn("Another admin", dialog.error.text())
        dialog.reject()
        controller.reload_admin_catalog()
        self.finish_refresh(controller)
        page.add_item(controller.session.documentation.items[0])
        dialog = page.item_dialog
        dialog.name_edit.setText("Renamed")
        dialog.save_button.click()
        self.assertFalse(folder.exists())
        self.assertTrue(folder.with_name("Renamed").is_dir())
        self.assertEqual(self.repo.load_catalog().documentation.items[0].name, "Renamed")
        self.assertEqual(page.selected_folder, "Renamed")

    def test_documentation_settings_share_defaults_without_moving_existing_files(self):
        shared = self.root / "documents"
        shared.mkdir()
        self.repo.create_team(self.profile, self.session)
        controller = self.controller(self.repo)
        settings = controller.admin.settings_page
        settings.location_edit.setText(str(shared))
        settings.root_name_edit.setText("Team manuals")
        settings.save_location()
        self.assertEqual(self.repo.load_catalog().documentation.root_name, "Team manuals")
        folder = shared / "Team manuals" / "IT"
        folder.mkdir()
        (folder / "guide.txt").write_text("keep this")
        controller.session.documentation.items.append(DocumentationItem("IT"))
        controller._save_catalog()
        settings.root_name_edit.setText("Different folder")
        settings.save_location()
        self.assertEqual(controller.session.documentation.root_name, "Team manuals")
        self.assertEqual((folder / "guide.txt").read_text(), "keep this")
        self.assertFalse((shared / "Different folder").exists())
        other = self.other_repo()
        loaded = other.select_team(self.profile)
        self.assertEqual(loaded.documentation.parent_path, str(shared))
        self.assertEqual(loaded.documentation.items[0].name, "IT")


if __name__ == "__main__":
    unittest.main()
