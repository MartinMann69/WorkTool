"""JSON adapter contract, isolation, validation, and interrupted-write behavior."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tslibrary_ui.app import create_app
from tslibrary_ui.applications.models import Application
from tslibrary_ui.licenses.models import LibraryItem, LicenseEntry
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.storage import JsonRepository, StorageError, create_repository
from tslibrary_ui.websites.models import Website


class StorageChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.repo = JsonRepository(self.root / "shared" / "catalog.json", self.root / "user" / "config.json")

    def tearDown(self):
        self.directory.cleanup()

    def test_missing_files_start_empty_without_writing_anything(self):
        self.assertEqual(self.repo.load_catalog().applications, [])
        self.assertEqual(self.repo.load_workplace(), WorkplaceConfig())
        self.assertFalse(self.repo.catalog_path.exists())
        self.assertFalse(self.repo.config_path.exists())

    def test_catalog_round_trip_keeps_ids_unicode_and_raw_launch_arguments(self):
        arguments = r'--config "C:\Team files\設定.json" -launch -reg'
        session = LibrarySession(
            applications=[Application("Éditeur 日本語", r"C:\Program Files\Editor.exe", arguments=arguments)],
            websites=[Website("Team intranet", "https://intranet:8443/team?q=a%20b#home")],
            items=[LibraryItem("Private", licenses=[LicenseEntry("Seat", 1, key="SECRET-KEY")])])
        self.repo.save_catalog(session)
        loaded = self.repo.load_catalog()
        self.assertEqual(loaded.applications[0].id, session.applications[0].id)
        self.assertEqual(loaded.applications[0].arguments, arguments)
        self.assertEqual(loaded.applications[0].name, "Éditeur 日本語")
        self.assertEqual(loaded.websites[0].url, session.websites[0].url)
        raw = self.repo.catalog_path.read_text(encoding="utf-8")
        self.assertNotIn("SECRET-KEY", raw)
        self.assertNotIn('"icon"', raw)

    def test_two_user_configs_share_catalog_but_not_selections_or_personal_entries(self):
        shared = LibrarySession(websites=[Website("Portal", "https://portal.example.com")])
        self.repo.save_catalog(shared)
        other = JsonRepository(self.repo.catalog_path, self.root / "other-user" / "config.json")
        self.repo.save_workplace(WorkplaceConfig(
            website_ids=[shared.websites[0].id], personal_websites=[Website("Personal", "https://my.example.com")]))
        other.save_workplace(WorkplaceConfig(personal_applications=[Application("My tool", r"C:\Tool.exe")]))
        self.assertEqual(other.load_catalog().websites[0].id, shared.websites[0].id)
        self.assertEqual(other.load_workplace().website_ids, [])
        self.assertEqual(other.load_workplace().personal_websites, [])
        self.assertEqual(len(self.repo.load_workplace().personal_websites), 1)
        self.assertEqual(self.repo.load_workplace().personal_applications, [])
        config_data = json.loads(self.repo.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config_data["website_ids"], [shared.websites[0].id])
        self.assertNotIn("websites", config_data)

    def test_failed_atomic_replace_preserves_previous_file_and_cleans_temporary_file(self):
        self.repo.save_workplace(WorkplaceConfig(website_ids=["previous"]))
        before = self.repo.config_path.read_bytes()
        with patch("tslibrary_ui.storage.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(StorageError):
                self.repo.save_workplace(WorkplaceConfig(website_ids=["changed"]))
        self.assertEqual(self.repo.config_path.read_bytes(), before)
        self.assertEqual(list(self.repo.config_path.parent.glob("*.tmp")), [])

    def test_invalid_data_is_reported_without_modifying_file(self):
        self.repo.config_path.parent.mkdir(parents=True)
        for value in ["{broken", '{"version": 99}', '{"version": 1, "website_ids": "wrong"}',
                      '{"version": 1, "personal_websites": [{"id": "1", "name": "x", "url": "file:///x"}]}']:
            self.repo.config_path.write_text(value, encoding="utf-8")
            with self.assertRaises(StorageError):
                self.repo.load_workplace()
            self.assertEqual(self.repo.config_path.read_text(encoding="utf-8"), value)

    def test_duplicate_catalog_ids_are_rejected_and_preferences_are_deduplicated(self):
        self.repo.catalog_path.parent.mkdir(parents=True)
        record = dict(id="same", name="Site", url="https://example.com")
        self.repo.catalog_path.write_text(json.dumps(dict(version=1, websites=[record, record])), encoding="utf-8")
        with self.assertRaises(StorageError):
            self.repo.load_catalog()
        self.repo.save_workplace(WorkplaceConfig(website_ids=["a", "a", "b"]))
        self.assertEqual(self.repo.load_workplace().website_ids, ["a", "b"])

    def test_backend_factory_can_be_redirected_without_changing_the_ui(self):
        with patch.dict(os.environ, {"TSLIBRARY_CATALOG_PATH": str(self.repo.catalog_path),
                                     "TSLIBRARY_CONFIG_PATH": str(self.repo.config_path)}):
            repo = create_repository()
        self.assertEqual(repo.catalog_path, self.repo.catalog_path)
        self.assertEqual(repo.config_path, self.repo.config_path)
        with self.assertRaises(StorageError):
            JsonRepository(self.repo.catalog_path, self.repo.catalog_path)
