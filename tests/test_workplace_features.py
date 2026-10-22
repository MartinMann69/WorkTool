"""End-to-end checks for personal workflows, portable backups, and local repair."""

from dataclasses import replace
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QMessageBox

from tslibrary_ui.app import create_app, main
from tslibrary_ui.applications.models import Application
from tslibrary_ui.licenses.item_dialog import ItemDialog
from tslibrary_ui.licenses.models import LibraryItem, LicenseEntry
from tslibrary_ui.main_window import MainWindow
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.phone_apps.models import PhoneApp
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.storage import JsonRepository, StorageError
from tslibrary_ui.transfers import export_backup, import_backup, export_catalog_csv
from tslibrary_ui.websites.models import Website
from tslibrary_ui.workplace.models import entry_key, workplace_entries


class FakeLauncher:
    def __init__(self):
        self.records = []

    def open_application(self, record):
        self.records.append(record)

    def open_website(self, record):
        self.records.append(record)


class WorkplaceFeatureChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.target = self.root / "Team tool.exe"
        self.target.write_bytes(b"not executable; never launched")
        self.session = LibrarySession(
            applications=[Application("Team editor", str(self.target), arguments='--profile "Team profile"')],
            websites=[Website("Zebra portal", "https://example.com")],
            phone_apps=[PhoneApp("Authenticator")],
            items=[LibraryItem("Editor licenses", licenses=[LicenseEntry("Team", 4, "PRIVATE-TEST-KEY", 2)],
                               owner="Design team", renewal_date="2027-01-30")])
        self.personal = Website("My notes", "https://notes.example.com")
        self.config = WorkplaceConfig(
            application_ids=[self.session.applications[0].id],
            website_ids=[self.session.websites[0].id], personal_websites=[self.personal])
        self.repo = JsonRepository(self.root / "catalog.json", self.root / "user.json")
        self.repo.save_catalog(self.session)
        self.repo.save_workplace(self.config)
        self.launcher = FakeLauncher()
        self.window = MainWindow(session=self.session, config=self.config, repository=self.repo, launcher=self.launcher)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        for child in self.window.findChildren(QDialog):
            child.close()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def entry(self, kind="websites", *, personal=False):
        return next(entry for entry in workplace_entries(self.session, self.window.config, kind)
                    if entry.source == ("personal" if personal else "catalog"))

    def test_personal_remove_menu_cancel_and_confirm_keep_shared_catalog(self):
        entry = self.entry(personal=True)
        self.window.toggle_favorite(entry)
        self.window.assign_group(entry, "Notes")
        before = self.repo.catalog_path.read_bytes()
        menu = self.window.build_entry_menu(entry)
        remove = next(action for action in menu.actions() if action.text() == "Remove personal entry…")
        remove.trigger()
        self.window.remove_dialog.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(len(self.window.config.personal_websites), 1)
        remove.trigger()
        self.window.remove_dialog.delete_button.click()
        self.app.processEvents()
        config = self.repo.load_workplace()
        self.assertEqual(config.personal_websites, [])
        self.assertNotIn(entry_key(entry), config.favorites)
        self.assertEqual(config.groups["Notes"], [])
        self.assertEqual(self.repo.catalog_path.read_bytes(), before)

    def test_favorites_and_groups_survive_reload_and_filter_both_views(self):
        entry = self.entry()
        self.window.toggle_favorite(entry)
        self.window.assign_group(entry, "Office")
        page = self.window.websites_page
        self.assertEqual(page.model.entries[0].id, entry.id)
        page.group_filter.setCurrentIndex(page.group_filter.findData("group:Office"))
        self.assertEqual([item.id for item in page.model.entries], [entry.id])
        page.view_select.setCurrentIndex(1)
        self.app.processEvents()
        self.assertTrue(page.grid.dense)
        self.assertEqual(page.grid.row_height, 80)
        self.assertFalse(page.grid.grab().isNull())
        saved = self.repo.load_workplace()
        self.assertEqual(saved.view_mode, "list")
        self.assertEqual(saved.groups["Office"], [entry_key(entry)])
        self.assertEqual(saved.favorites, [entry_key(entry)])

    def test_failed_favorite_save_keeps_current_preferences(self):
        entry = self.entry()
        with patch.object(self.repo, "save_workplace", side_effect=StorageError("fixture")), \
             patch("tslibrary_ui.main_window.QMessageBox.warning"):
            self.window.toggle_favorite(entry)
        self.assertEqual(self.window.config.favorites, [])
        self.assertEqual(self.repo.load_workplace().favorites, [])

    def test_visible_card_menu_and_dense_collection_toggle(self):
        page = self.window.websites_page
        index = page.model.index(0, 0)
        page.grid.setCurrentIndex(index)
        entry = index.data(Qt.ItemDataRole.UserRole)
        point = page.grid.itemDelegate().menu_rect(page.grid.visualRect(index), entry).center().toPoint()
        QTest.mouseClick(page.grid.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.app.processEvents()
        self.assertTrue(self.window.entry_menu.isVisible())
        self.window.entry_menu.hide()
        self.window.set_view_mode("list")
        collection = self.window.collection_page
        self.window.tabs.setCurrentWidget(collection)
        self.app.processEvents()
        self.assertTrue(collection.grid.dense)
        index = collection.model.index(0, 0)
        entry = index.data(Qt.ItemDataRole.UserRole)
        point = collection.grid.itemDelegate().action_rect(collection.grid.visualRect(index)).center().toPoint()
        selected_before = entry.added
        QTest.mouseClick(collection.grid.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.app.processEvents()
        updated = next(item for item in collection.model.entries if item.id == entry.id)
        self.assertNotEqual(updated.added, selected_before)

    def test_missing_shared_app_can_be_repaired_for_this_pc_without_editing_catalog(self):
        app = self.session.applications[0]
        app.executable = str(self.root / "missing.exe")
        self.repo.save_catalog(self.session)
        self.window.refresh()
        entry = self.entry("applications")
        self.assertFalse(entry.available)
        before = self.repo.catalog_path.read_bytes()
        with patch("tslibrary_ui.workplace.tools.QFileDialog.getOpenFileName", return_value=(str(self.target), "")):
            self.window.locate_application(entry)
        self.assertEqual(self.repo.catalog_path.read_bytes(), before)
        self.window.open_entry(entry)
        self.assertEqual(self.launcher.records[-1].executable, str(self.target.resolve()))
        self.assertEqual(self.launcher.records[-1].arguments, '--profile "Team profile"')
        loaded = workplace_entries(self.session, self.repo.load_workplace(), "applications")[0]
        self.assertTrue(loaded.available)

    def test_quick_launcher_filters_and_opens_one_selected_entry(self):
        self.window.show_quick_launcher()
        dialog = self.window.quick_launcher
        dialog.search.setText("my notes")
        self.assertEqual(dialog.results.count(), 1)
        QTest.keyClick(dialog.search, Qt.Key.Key_Return)
        self.assertEqual([record.id for record in self.launcher.records], [self.personal.id])

    def test_launch_set_save_cancel_and_explicit_launch(self):
        self.window.show_launch_sets()
        dialog = self.window.launch_sets_dialog
        dialog.name_edit.setText("Morning")
        for i in range(dialog.tools.count()):
            dialog.tools.item(i).setCheckState(Qt.CheckState.Checked)
        dialog.save_set()
        self.assertEqual(len(self.repo.load_workplace().launch_sets["Morning"]), 3)
        with patch("tslibrary_ui.workplace.tools.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.window.launch_set("Morning")
        self.assertEqual(self.launcher.records, [])
        with patch("tslibrary_ui.workplace.tools.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.window.launch_set("Morning")
        self.assertEqual(len(self.launcher.records), 3)

    def test_backups_preserve_preferences_counts_and_phone_apps_but_never_key_values(self):
        entry = self.entry()
        self.window.toggle_favorite(entry)
        self.window.assign_group(entry, "Office")
        workplace = self.root / "workplace-backup.json"
        catalog = self.root / "catalog-backup.json"
        export_backup(workplace, self.window.config)
        export_backup(catalog, self.session, catalog=True)
        self.assertEqual(import_backup(workplace), self.repo.load_workplace())
        restored = import_backup(catalog, catalog=True)
        self.assertEqual(restored.phone_apps[0].name, "Authenticator")
        self.assertEqual(restored.items[0].owner, "Design team")
        self.assertEqual(restored.items[0].renewal_date, "2027-01-30")
        self.assertEqual(restored.items[0].licenses[0].used, 2)
        self.assertEqual(restored.items[0].licenses[0].key, "")
        self.assertTrue(restored.items[0].licenses[0].tracks_key)
        self.assertNotIn("PRIVATE-TEST-KEY", catalog.read_text(encoding="utf-8"))
        self.assertNotIn("PRIVATE-TEST-KEY", self.repo.catalog_path.read_text(encoding="utf-8"))

    def test_restore_creates_recovery_backup_and_keeps_existing_data_on_invalid_input(self):
        path = self.root / "restore.json"
        export_backup(path, WorkplaceConfig(start_in_workplace=True, view_mode="list"))
        with patch("tslibrary_ui.workplace.tools.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
             patch("tslibrary_ui.workplace.tools.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.window.restore_workplace()
        self.assertTrue(self.repo.load_workplace().start_in_workplace)
        recovery = list(self.root.glob("restore.before-restore-*.json"))
        self.assertEqual(len(recovery), 1)
        self.assertEqual(import_backup(recovery[0]).personal_websites[0].id, self.personal.id)
        before = self.repo.config_path.read_bytes()
        path.write_text('{"version":1,"format":"tslibrary.workplace","workplace":{"version":1,"view_mode":"wrong"}}')
        with patch("tslibrary_ui.workplace.tools.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
             patch("tslibrary_ui.workplace.tools.QMessageBox.warning"):
            self.window.restore_workplace()
        self.assertEqual(self.repo.config_path.read_bytes(), before)

    def test_csv_export_has_renewal_metadata_excludes_keys_and_quotes_formulas(self):
        self.session.websites[0].name = "=FORMULA()"
        path = self.root / "catalog.csv"
        export_catalog_csv(path, self.session)
        text = path.read_text(encoding="utf-8-sig")
        self.assertIn("'=FORMULA()", text)
        self.assertIn("Design team", text)
        self.assertIn("2027-01-30", text)
        self.assertNotIn("PRIVATE-TEST-KEY", text)

    def test_renewal_details_validate_and_keep_counts_when_edited(self):
        item = self.session.items[0]
        dialog = ItemDialog(self.window, item=item)
        dialog.renewal_edit.setText("2027-99-40")
        dialog.save_button.click()
        self.assertIn("YYYY-MM-DD", dialog.error.text())
        dialog.renewal_edit.setText("2027-02-01")
        dialog.owner_edit.setText("Support")
        updated = dialog.item()
        self.assertEqual(updated.owner, "Support")
        self.assertEqual(updated.renewal_date, "2027-02-01")
        self.assertEqual(item.licenses[0].used, 2)
        self.assertEqual(item.renewal_status(date(2027, 1, 31)), "Overdue by 1 day")
        dialog.close()

    def test_new_inventory_changes_persist_through_the_controller(self):
        controller = PreviewController(repository=self.repo)
        try:
            controller.admin.phone_apps_page.add_phone_app()
            editor = controller.admin.phone_apps_page.phone_app_dialog
            editor.name_edit.setText("Teams")
            editor.save_button.click()
            self.assertEqual(len(self.repo.load_catalog().phone_apps), 2)
            item = controller.session.items[0]
            controller.admin.licenses_page.open_licenses(item)
            manager = controller.admin.licenses_page.license_window
            manager._change_usage(0, 1)
            self.assertEqual(self.repo.load_catalog().items[0].licenses[0].used, 3)
        finally:
            for window in (controller.main_window, controller.admin, controller.library, controller.welcome):
                window.close()
                window.deleteLater()
            controller.deleteLater()
            self.app.processEvents()

    def test_startup_preference_opens_workplace_and_welcome_flag_overrides_it(self):
        for args, expected in [(["main.py"], "show_main"), (["main.py", "--welcome"], None)]:
            app = MagicMock()
            app.exec.return_value = 0
            controller = MagicMock()
            controller.main_window.config.start_in_workplace = True
            with patch("tslibrary_ui.app.create_app", return_value=app), \
                 patch("tslibrary_ui.app.SingleInstance") as guard, \
                 patch("tslibrary_ui.app.create_repository"), \
                 patch("tslibrary_ui.app.PreviewController", return_value=controller), \
                 patch("sys.argv", args):
                guard.return_value.start.return_value = True
                self.assertEqual(main(), 0)
            if expected:
                controller.show_main.assert_called_once()
            else:
                controller.welcome.show.assert_called_once()
                controller.show_main.assert_not_called()

    def test_legacy_config_defaults_and_invalid_new_preferences_are_handled(self):
        self.repo.config_path.write_text('{"version":1}', encoding="utf-8")
        self.assertEqual(self.repo.load_workplace(), WorkplaceConfig())
        for extra in [{"favorites": "bad"}, {"groups": {"Office": 1}}, {"start_in_workplace": "yes"},
                      {"application_overrides": {"id": 42}}, {"launch_sets": {"Set": [42]}}]:
            self.repo.config_path.write_text(json.dumps(dict(version=1, **extra)), encoding="utf-8")
            with self.assertRaises(StorageError):
                self.repo.load_workplace()


if __name__ == "__main__":
    unittest.main()
