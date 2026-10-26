"""Saved-data upgrade safety: real legacy data plus simulated future formats."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tslibrary_ui.app import create_app
from tslibrary_ui.migrations import DataSchema
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.storage import JsonFile, JsonRepository, StorageError
from tslibrary_ui.transfers import import_backup


# Snapshot of the shipping v1 workplace shape, deliberately independent of its
# current serializer. IDs, launch arguments and local preferences must survive.
LEGACY_WORKPLACE = {
    "version": 1,
    "application_ids": ["editor"], "website_ids": ["portal"],
    "personal_applications": [{"id": "local-app", "name": "Editor 日本語",
                               "executable": "C:\\Tools\\editor.exe", "arguments": '--profile "My work"'}],
    "personal_websites": [{"id": "my-site", "name": "My site", "url": "https://personal.example.com"}],
    "favorites": ["websites:catalog:portal"],
    "groups": {"Office": ["websites:catalog:portal"]},
    "launch_sets": {"Morning": ["applications:personal:local-app"]},
    "application_overrides": {"applications:catalog:editor": "D:\\Tools\\editor.exe"},
    "view_mode": "list", "start_in_workplace": True,
}


def to_v2(data):
    """Simulate a future format moving personal entries into a nested object."""
    data["personal"] = {
        "websites": data.pop("personal_websites"),
        "applications": data.pop("personal_applications"),
    }
    data["version"] = 2
    return data


def to_v3(data):
    """Simulate another release renaming the selection field."""
    data["selected_websites"] = data.pop("website_ids")
    data["version"] = 3
    return data


FUTURE_SCHEMA = DataSchema("test workplace", 3, {1: to_v2, 2: to_v3})


def decode_future(data):
    # A future application's decoder must validate the migrated shape too.
    if not isinstance(data.get("personal"), dict) or not isinstance(data.get("selected_websites"), list):
        raise ValueError("Invalid migrated workplace.")
    return data


class MigrationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.path = self.root / "workplace.json"
        self.original = ("\ufeff" + json.dumps(LEGACY_WORKPLACE, ensure_ascii=False)).encode("utf-8")
        self.path.write_bytes(self.original)

    def tearDown(self):
        self.directory.cleanup()

    def backups(self):
        return list(self.root.glob("*.before-migration-*.bak"))

    def test_current_release_loads_legacy_data_without_rewriting_it(self):
        repo = JsonRepository(self.root / "catalog.json", self.path)
        config = repo.load_workplace()
        self.assertEqual(config.personal_applications[0].arguments, '--profile "My work"')
        self.assertEqual(config.personal_websites[0].id, "my-site")
        self.assertEqual(config.website_ids, ["portal"])
        self.assertEqual(config.favorites, ["websites:catalog:portal"])
        self.assertEqual(config.groups, LEGACY_WORKPLACE["groups"])
        self.assertEqual(config.launch_sets, LEGACY_WORKPLACE["launch_sets"])
        self.assertEqual(config.application_overrides, LEGACY_WORKPLACE["application_overrides"])
        self.assertTrue(config.start_in_workplace)
        self.assertEqual(config.view_mode, "list")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.backups(), [])

    def test_skipping_releases_runs_every_step_and_keeps_one_exact_original_backup(self):
        loaded = JsonFile._read(self.path, decode_future, schema=FUTURE_SCHEMA)
        self.assertEqual(loaded["version"], 3)
        self.assertEqual(loaded["selected_websites"], ["portal"])
        self.assertEqual(loaded["personal"]["websites"][0]["id"], "my-site")
        self.assertEqual(loaded["personal"]["applications"][0]["arguments"], '--profile "My work"')
        for field in ("favorites", "groups", "launch_sets", "application_overrides"):
            self.assertEqual(loaded[field], LEGACY_WORKPLACE[field])
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), loaded)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.backups()[0].read_bytes(), self.original)
        self.assertEqual(JsonFile._read(self.path, decode_future, schema=FUTURE_SCHEMA), loaded)
        self.assertEqual(len(self.backups()), 1)
        self.assertIn("personal_websites", LEGACY_WORKPLACE)

    def test_failed_migration_or_validation_keeps_source_untouched(self):
        def broken_step(data):
            data.clear()
            raise RuntimeError("Conversion failed")

        schemas = [DataSchema("broken", 2, {1: broken_step}), DataSchema("missing step", 2, {}),
                   DataSchema("wrong step", 2, {1: lambda data: {"version": 3}}),
                   DataSchema("invalid result", 3, {1: lambda data: {"version": 2},
                                                          2: lambda data: {"version": 3}})]
        for schema in schemas:
            with self.subTest(schema=schema.name), self.assertRaises(StorageError):
                JsonFile._read(self.path, decode_future, schema=schema)
            self.assertEqual(self.path.read_bytes(), self.original)
            self.assertEqual(self.backups(), [])

    def test_backup_failure_prevents_migration(self):
        original_open = Path.open

        def protected_open(path, *args, **kwargs):
            if path.suffix == ".bak":
                raise PermissionError("Backup is not writable")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", protected_open), self.assertRaises(StorageError):
            JsonFile._read(self.path, decode_future, schema=FUTURE_SCHEMA)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_interrupted_migration_write_keeps_original_and_recovery_backup(self):
        with patch("tslibrary_ui.storage.os.replace", side_effect=PermissionError("File is locked")):
            with self.assertRaises(StorageError):
                JsonFile._read(self.path, decode_future, schema=FUTURE_SCHEMA)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.backups()[0].read_bytes(), self.original)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_partial_backup_is_removed_when_flush_fails(self):
        with patch("tslibrary_ui.storage.os.fsync", side_effect=OSError("Disk is full")):
            with self.assertRaises(StorageError):
                JsonFile._read(self.path, decode_future, schema=FUTURE_SCHEMA)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.backups(), [])

    def test_newer_data_cannot_be_loaded_or_overwritten_by_older_app(self):
        repo = JsonRepository(self.root / "catalog.json", self.path)
        for path, loader, saver, value in [
            (self.path, repo.load_workplace, repo.save_workplace, WorkplaceConfig()),
            (repo.catalog_path, repo.load_catalog, repo.save_catalog, LibrarySession()),
        ]:
            raw = b'{"version":99,"important_future_field":"keep me"}'
            path.write_bytes(raw)
            with self.assertRaisesRegex(StorageError, "newer data version"):
                loader()
            with self.assertRaisesRegex(StorageError, "newer data version"):
                saver(value)
            self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(self.backups(), [])

    def test_read_only_backup_import_migrates_payload_without_modifying_backup(self):
        def add_default(data):
            data["version"] = 2
            data["view_mode"] = "list"
            return data

        path = self.root / "backup.json"
        raw = json.dumps({"version": 1, "format": "tslibrary.workplace",
                          "workplace": {"version": 1, "website_ids": ["portal"]}}).encode("utf-8")
        path.write_bytes(raw)
        with patch("tslibrary_ui.storage.WORKPLACE_SCHEMA", DataSchema("workplace", 2, {1: add_default})):
            restored = import_backup(path)
        self.assertEqual(restored.website_ids, ["portal"])
        self.assertEqual(restored.view_mode, "list")
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(self.backups(), [])

    def test_non_integer_schema_version_is_rejected(self):
        for version in (True, 1.0, "1", 0, None):
            self.path.write_text(json.dumps({"version": version}), encoding="utf-8")
            with self.subTest(version=version), self.assertRaises(StorageError):
                JsonFile._read(self.path, lambda data: data, schema=FUTURE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
