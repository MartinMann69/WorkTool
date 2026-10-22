"""Workplace interactions and restart behavior, using temporary per-user files."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from tslibrary_ui.app import create_app
from tslibrary_ui.applications.models import Application
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.storage import JsonRepository, StorageError
from tslibrary_ui.websites.models import Website
from tslibrary_ui.workplace.models import collection_entries, workplace_entries
from tslibrary_ui.workplace.collection import CollectionDelegate
from tslibrary_ui.workplace.selection import SelectionDelegate
from tslibrary_ui.workplace.cards import WorkplaceDelegate


class FakeLauncher:
    def __init__(self):
        self.opened = []

    def open_website(self, record):
        self.opened.append(("website", record.id, record.url))

    def open_application(self, record):
        self.opened.append(("application", record.id, record.launch_target))


class WorkplaceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.repo = JsonRepository(self.root / "catalog.json", self.root / "user.json")
        self.session = LibrarySession(
            applications=[Application("Team editor", r"C:\Team\editor.exe", arguments='--profile "Team profile"')],
            websites=[Website("Team portal", "https://portal.example.com")])
        self.repo.save_catalog(self.session)
        self.controller = PreviewController(repository=self.repo)
        self.window = self.controller.main_window
        self.launcher = FakeLauncher()
        self.window.launcher = self.launcher
        self.controller.show_main()
        self.app.processEvents()

    def tearDown(self):
        self.close_controller(self.controller)
        self.app.processEvents()
        self.directory.cleanup()

    def close_controller(self, controller):
        for window in (controller.main_window, controller.library, controller.admin, controller.welcome):
            window.close()
            window.deleteLater()
        controller.deleteLater()

    def select(self, page, entry_id):
        self.window.tabs.setCurrentWidget(page)
        for row, entry in enumerate(page.model.entries):
            if entry.id == entry_id:
                page.grid.setCurrentIndex(page.model.index(row, 0))
                self.app.processEvents()
                return entry
        self.fail(f"Entry {entry_id} not shown")

    def toggle_card(self, page, entry_id):
        self.select(page, entry_id)
        index = page.grid.currentIndex()
        page.grid.scrollTo(index)
        self.app.processEvents()
        point = CollectionDelegate.action_rect(page.grid.visualRect(index)).center().toPoint()
        QTest.mouseClick(page.grid.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.app.processEvents()

    def click_workplace_action(self, page, entry_id, action="open"):
        entry = self.select(page, entry_id)
        index = page.grid.currentIndex()
        page.grid.scrollTo(index)
        self.app.processEvents()
        rect = page.grid.visualRect(index)
        bounds = (WorkplaceDelegate.open_rect(rect, entry) if action == "open"
                  else WorkplaceDelegate.edit_rect(rect, entry))
        QTest.mouseClick(page.grid.viewport(), Qt.MouseButton.LeftButton, pos=bounds.center().toPoint())
        self.app.processEvents()

    def remove_from_sidebar(self, entry_id):
        sidebar = self.window.collection_page.selection_sidebar
        for row, entry in enumerate(sidebar.model.entries):
            if entry.id == entry_id:
                index = sidebar.model.index(row, 0)
                sidebar.list.scrollTo(index)
                self.app.processEvents()
                point = SelectionDelegate.remove_rect(sidebar.list.visualRect(index)).center().toPoint()
                QTest.mouseClick(sidebar.list.viewport(), Qt.MouseButton.LeftButton, pos=point)
                self.app.processEvents()
                return
        self.fail(f"Entry {entry_id} not in sidebar")

    def test_select_unselect_and_restart_keep_personal_workplace_separate_from_catalog(self):
        page = self.window.collection_page
        for record in (self.session.applications[0], self.session.websites[0]):
            self.toggle_card(page, record.id)
        self.assertEqual(self.window.applications_page.model.rowCount(), 1)
        self.assertEqual(self.window.websites_page.model.rowCount(), 1)
        self.assertEqual(self.launcher.opened, [])
        config = self.repo.load_workplace()
        self.assertEqual(config.application_ids, [self.session.applications[0].id])
        self.assertEqual(config.website_ids, [self.session.websites[0].id])
        self.close_controller(self.controller)
        self.app.processEvents()
        self.controller = PreviewController(repository=self.repo)
        self.window = self.controller.main_window
        self.controller.show_main()
        self.assertEqual(self.window.websites_page.model.entries[0].name, "Team portal")
        page = self.window.collection_page
        self.select(page, self.session.websites[0].id)
        self.assertEqual(page.grid.currentIndex().data(Qt.ItemDataRole.CheckStateRole), Qt.CheckState.Checked)
        self.assertEqual(page.selection_sidebar.model.rowCount(), 2)
        self.toggle_card(page, self.session.websites[0].id)
        self.assertEqual(self.window.websites_page.model.rowCount(), 0)
        self.assertEqual(page.selection_sidebar.model.rowCount(), 1)
        self.assertEqual(len(self.repo.load_catalog().websites), 1)

    def test_admin_add_edit_delete_are_saved_and_existing_selections_follow_stable_id(self):
        site_id = self.session.websites[0].id
        self.window.toggle_catalog_entry(next(entry for entry in collection_entries(
            self.window.session, self.window.config) if entry.id == site_id))
        admin = self.controller.admin
        page = admin.websites_page
        page.add_website(admin.session.websites[0])
        editor = page.website_dialog
        editor.url_edit.setText("https://new.example.com/home")
        editor.name_edit.setText("Updated portal")
        editor.save_button.click()
        self.app.processEvents()
        saved = self.repo.load_catalog().websites[0]
        self.assertEqual((saved.id, saved.name), (site_id, "Updated portal"))
        entry = self.window.websites_page.model.entries[0]
        self.assertEqual((entry.id, entry.name), (site_id, "Updated portal"))
        self.assertEqual(self.window.collection_page.selection_sidebar.model.entries[0].name, "Updated portal")
        self.window.open_entry(entry)
        self.assertEqual(self.launcher.opened[-1], ("website", site_id, "https://new.example.com/home"))
        page.add_website()
        editor = page.website_dialog
        editor.url_edit.setText("https://second.example.com")
        editor.name_edit.setText("Second site")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(len(self.repo.load_catalog().websites), 2)
        page.confirm_remove_website(admin.session.websites[0])
        page.remove_website_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(self.window.websites_page.model.rowCount(), 0)
        self.assertEqual(self.window.collection_page.selection_sidebar.model.rowCount(), 0)
        self.assertEqual(len(self.repo.load_catalog().websites), 1)

    def test_personal_website_inline_edit_and_cancel_only_change_user_file(self):
        catalog_before = self.repo.catalog_path.read_bytes()
        self.window.websites_page.add_button.click()
        dialog = self.window.personal_dialog
        dialog.url_edit.setText("https://notes.example.com")
        dialog.name_edit.setText("My notes")
        dialog.save_button.click()
        self.app.processEvents()
        record = self.window.config.personal_websites[0]
        entry = self.select(self.window.websites_page, record.id)
        self.click_workplace_action(self.window.websites_page, record.id, "edit")
        dialog = self.window.personal_dialog
        dialog.name_edit.setText("Renamed notes")
        dialog.url_edit.setText("https://notes.example.com/new")
        dialog.save_button.click()
        self.app.processEvents()
        self.assertEqual(self.repo.load_workplace().personal_websites[0].id, record.id)
        self.assertEqual(self.repo.load_workplace().personal_websites[0].name, "Renamed notes")
        self.window.edit_personal(entry)
        self.window.personal_dialog.name_edit.setText("Cancelled")
        self.window.personal_dialog.reject()
        self.assertEqual(self.window.config.personal_websites[0].name, "Renamed notes")
        self.assertEqual(len(self.window.config.personal_websites), 1)
        self.assertFalse(hasattr(self.window.websites_page, "remove_button"))
        self.assertEqual(self.repo.catalog_path.read_bytes(), catalog_before)

    def test_personal_application_preserves_arguments_and_opening_is_explicit(self):
        target = self.root / "Personal tool.exe"
        target.write_bytes(b"not an executable; tests never launch it")
        self.window.add_personal("applications")
        dialog = self.window.personal_dialog
        dialog.path_edit.setText(f'"{target}" --profile "My profile"')
        dialog.name_edit.setText("Personal tool")
        dialog.save_button.click()
        self.app.processEvents()
        saved = self.repo.load_workplace().personal_applications[0]
        self.assertEqual(saved.arguments, '--profile "My profile"')
        self.assertEqual(self.launcher.opened, [])
        page = self.window.applications_page
        self.click_workplace_action(page, saved.id)
        self.assertEqual(self.launcher.opened, [("application", saved.id, saved.launch_target)])
        self.assertTrue(target.exists())
        self.assertEqual(self.repo.load_workplace().personal_applications[0].id, saved.id)
        self.assertFalse(hasattr(page, "remove_button"))

    def test_catalog_entries_cannot_be_edited_as_personal_and_failed_saves_do_not_change_selection(self):
        entry = collection_entries(self.window.session, self.window.config)[0]
        self.window.edit_personal(entry)
        self.assertFalse(hasattr(self.window, "personal_dialog"))
        with patch.object(self.repo, "save_workplace", side_effect=StorageError("read only")), \
                patch("tslibrary_ui.main_window.QMessageBox.warning") as warning:
            self.toggle_card(self.window.collection_page, entry.id)
        self.assertEqual(self.window.config.website_ids, [])
        self.assertEqual(self.window.config.application_ids, [])
        self.assertEqual(self.window.collection_page.grid.currentIndex().data(Qt.ItemDataRole.CheckStateRole),
                         Qt.CheckState.Unchecked)
        self.assertEqual(self.window.collection_page.selection_sidebar.model.rowCount(), 0)
        warning.assert_called_once()
        self.assertFalse(self.repo.config_path.exists())

    def test_refresh_picks_up_external_admin_edits_without_losing_personal_choices(self):
        self.window.toggle_catalog_entry(collection_entries(self.window.session, self.window.config)[0])
        loaded = self.repo.load_catalog()
        loaded.websites[0].name = "Changed by another admin process"
        self.repo.save_catalog(loaded)
        self.window.collection_page.add_button.click()
        self.assertEqual(self.window.websites_page.model.entries[0].name, loaded.websites[0].name)
        self.assertEqual(self.window.config.website_ids, [loaded.websites[0].id])
        self.repo.catalog_path.write_text("broken", encoding="utf-8")
        with patch("tslibrary_ui.main_window.QMessageBox.warning"):
            self.window.reload_catalog()
        self.assertEqual(self.window.websites_page.model.entries[0].name, loaded.websites[0].name)

    def test_search_type_filter_and_layout_fit_all_three_tabs(self):
        page = self.window.collection_page
        self.window.tabs.setCurrentWidget(page)
        page.type_filter.setCurrentIndex(page.type_filter.findData("applications"))
        page.search.setText("team")
        self.assertEqual([entry.kind for entry in page.model.entries], ["applications"])
        page.search.setText("no matching entry")
        self.assertIs(page.stack.currentWidget(), page.empty_state)
        self.assertEqual(page.model.rowCount(), 0)
        page.search.clear()
        for width, height in [(820, 650), (1320, 850), (1600, 1000), (900, 700)]:
            self.window.resize(width, height)
            for index in range(3):
                self.window.tabs.setCurrentIndex(index)
                for _ in range(3):
                    self.app.processEvents()
                active = self.window.tabs.currentWidget()
                self.assertEqual((self.window.width(), self.window.height()), (width, height))
                self.assertEqual(active.grid.horizontalScrollBar().maximum(), 0)
                self.assertGreaterEqual(active.stack.height(), 184)

    def test_failed_admin_save_cannot_be_overwritten_by_collection_reload(self):
        controller = self.controller
        site = controller.session.websites[0]
        with patch.object(self.repo, "save_catalog", side_effect=StorageError("read only")), \
                patch("tslibrary_ui.navigation.QMessageBox.warning"):
            site.name = "Unsaved admin edit"
            controller.admin.catalog_changed.emit()
        self.assertTrue(self.window.catalog_reload_blocked)
        with patch("tslibrary_ui.main_window.QMessageBox.warning"):
            self.window.reload_catalog()
        self.assertEqual(controller.session.websites[0].name, "Unsaved admin edit")
        controller.admin.catalog_changed.emit()
        self.assertFalse(self.window.catalog_reload_blocked)
        self.assertEqual(self.repo.load_catalog().websites[0].name, "Unsaved admin edit")

    def test_launch_error_is_reported_without_editing_saved_preferences(self):
        self.window.toggle_catalog_entry(collection_entries(self.window.session, self.window.config)[0])
        entry = self.window.websites_page.model.entries[0]
        before = self.repo.config_path.read_bytes()
        with patch.object(self.launcher, "open_website", side_effect=OSError("No browser")), \
                patch("tslibrary_ui.main_window.QMessageBox.warning") as warning:
            self.window.open_entry(entry)
        warning.assert_called_once()
        self.assertEqual(self.repo.config_path.read_bytes(), before)

    def test_card_button_toggles_but_card_body_and_right_click_do_not(self):
        page = self.window.collection_page
        entry = self.select(page, self.session.websites[0].id)
        rect = page.grid.visualRect(page.grid.currentIndex())
        QTest.mouseClick(page.grid.viewport(), Qt.MouseButton.LeftButton,
                         pos=rect.center())
        self.assertEqual(self.window.config.website_ids, [])
        point = CollectionDelegate.action_rect(rect).center().toPoint()
        QTest.mouseClick(page.grid.viewport(), Qt.MouseButton.RightButton, pos=point)
        self.assertEqual(self.window.config.website_ids, [])
        self.toggle_card(page, entry.id)
        self.assertEqual(self.repo.load_workplace().website_ids, [entry.id])
        self.assertEqual(page.selection_sidebar.count_label.text(), "1")
        self.toggle_card(page, entry.id)
        self.assertEqual(self.repo.load_workplace().website_ids, [])
        self.assertTrue(page.selection_sidebar.empty_label.isVisible())
        self.assertFalse(hasattr(page, "action_bar"))

    def test_space_key_toggles_card_and_sidebar_stays_complete_during_filters(self):
        page = self.window.collection_page
        for record in (self.session.applications[0], self.session.websites[0]):
            self.select(page, record.id)
            QTest.keyClick(page.grid, Qt.Key.Key_Space)
            self.app.processEvents()
        self.assertEqual(page.selection_sidebar.model.rowCount(), 2)
        self.assertEqual(len(self.repo.load_workplace().application_ids), 1)
        self.assertEqual(len(self.repo.load_workplace().website_ids), 1)
        page.search.setText("nothing matches this")
        page.type_filter.setCurrentIndex(page.type_filter.findData("applications"))
        self.assertEqual(page.model.rowCount(), 0)
        self.assertEqual({entry.name for entry in page.selection_sidebar.model.entries},
                         {"Team editor", "Team portal"})

    def test_toggling_scrolled_card_keeps_its_position_and_sidebar_can_scroll(self):
        self.controller.session.websites.extend(Website(f"Site {i:02}", f"https://site{i}.example.com")
                                                for i in range(30))
        self.repo.save_catalog(self.controller.session)
        page = self.window.collection_page
        self.window.resize(820, 650)
        self.window.refresh()
        self.select(page, self.controller.session.websites[-1].id)
        page.grid.scrollTo(page.grid.currentIndex())
        self.app.processEvents()
        before = page.grid.verticalScrollBar().value()
        self.assertGreater(before, 0)
        point = CollectionDelegate.action_rect(page.grid.visualRect(page.grid.currentIndex())).center().toPoint()
        QTest.mouseClick(page.grid.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.app.processEvents()
        self.assertEqual(page.grid.verticalScrollBar().value(), before)
        config = self.window.config
        config.website_ids = [site.id for site in self.controller.session.websites]
        self.window.refresh()
        self.app.processEvents()
        self.assertEqual(page.selection_sidebar.model.rowCount(), 31)
        self.assertGreater(page.selection_sidebar.list.verticalScrollBar().maximum(), 0)
        self.assertEqual(page.selection_sidebar.list.horizontalScrollBar().maximum(), 0)

    def test_sidebar_remove_works_for_filtered_out_entry_and_persists_only_that_removal(self):
        page = self.window.collection_page
        app_id, site_id = self.session.applications[0].id, self.session.websites[0].id
        for record_id in (app_id, site_id):
            self.toggle_card(page, record_id)
        catalog_before = self.repo.catalog_path.read_bytes()
        page.type_filter.setCurrentIndex(page.type_filter.findData("applications"))
        self.assertEqual([entry.id for entry in page.model.entries], [app_id])
        self.remove_from_sidebar(site_id)
        config = self.repo.load_workplace()
        self.assertEqual(config.website_ids, [])
        self.assertEqual(config.application_ids, [app_id])
        self.assertEqual([entry.id for entry in page.selection_sidebar.model.entries], [app_id])
        self.assertEqual(self.window.websites_page.model.rowCount(), 0)
        self.assertEqual(self.repo.catalog_path.read_bytes(), catalog_before)
        page.type_filter.setCurrentIndex(0)
        self.select(page, site_id)
        self.assertEqual(page.grid.currentIndex().data(Qt.ItemDataRole.CheckStateRole), Qt.CheckState.Unchecked)
        # A second removal request for an old row must never add it back.
        self.window.remove_entry(next(entry for entry in collection_entries(self.window.session, self.window.config)
                                      if entry.id == site_id))
        self.assertEqual(self.window.config.website_ids, [])

    def test_sidebar_delete_key_moves_to_next_entry_and_last_removal_shows_empty_state(self):
        page = self.window.collection_page
        for record in (self.session.applications[0], self.session.websites[0]):
            self.toggle_card(page, record.id)
        sidebar = page.selection_sidebar
        sidebar.list.setCurrentIndex(sidebar.model.index(0, 0))
        QTest.keyClick(sidebar.list, Qt.Key.Key_Delete)
        self.app.processEvents()
        self.assertEqual(sidebar.model.rowCount(), 1)
        self.assertTrue(sidebar.list.currentIndex().isValid())
        QTest.keyClick(sidebar.list, Qt.Key.Key_Delete)
        self.app.processEvents()
        self.assertEqual(sidebar.count_label.text(), "0")
        self.assertTrue(sidebar.empty_label.isVisible())
        self.assertFalse(sidebar.list.isVisible())
        self.assertEqual(self.repo.load_workplace().website_ids, [])
        self.assertEqual(self.repo.load_workplace().application_ids, [])
        self.assertEqual(page.model.rowCount(), 2)

    def test_sidebar_failed_save_keeps_item_selected_in_card_and_list(self):
        page = self.window.collection_page
        site_id = self.session.websites[0].id
        self.toggle_card(page, site_id)
        before = self.repo.config_path.read_bytes()
        with patch.object(self.repo, "save_workplace", side_effect=StorageError("read only")), \
                patch("tslibrary_ui.main_window.QMessageBox.warning") as warning:
            self.remove_from_sidebar(site_id)
        warning.assert_called_once()
        self.assertEqual(self.repo.config_path.read_bytes(), before)
        self.assertEqual(page.selection_sidebar.count_label.text(), "1")
        self.select(page, site_id)
        self.assertEqual(page.grid.currentIndex().data(Qt.ItemDataRole.CheckStateRole), Qt.CheckState.Checked)

    def test_inline_open_in_both_tabs_uses_current_target_and_has_no_bottom_or_remove_controls(self):
        collection = self.window.collection_page
        for record in (self.session.applications[0], self.session.websites[0]):
            self.toggle_card(collection, record.id)
        before = self.repo.config_path.read_bytes()
        for kind, record in [("websites", self.session.websites[0]),
                             ("applications", self.session.applications[0])]:
            page = self.window.pages[kind]
            self.assertFalse(hasattr(page, "action_bar"))
            self.assertFalse(hasattr(page, "remove_button"))
            self.assertFalse(hasattr(page, "primary_button"))
            self.assertFalse(any("remove" in button.text().casefold() for button in page.findChildren(QPushButton)))
            self.select(page, record.id)
            index = page.grid.currentIndex()
            body = page.grid.visualRect(index).center()
            previous_opens = len(self.launcher.opened)
            QTest.mouseClick(page.grid.viewport(), Qt.MouseButton.LeftButton, pos=body)
            self.assertEqual(len(self.launcher.opened), previous_opens)
            self.click_workplace_action(page, record.id)
            expected = record.url if kind == "websites" else record.launch_target
            self.assertEqual(self.launcher.opened[-1],
                             ("website" if kind == "websites" else "application", record.id, expected))
            self.assertEqual(len(self.launcher.opened), previous_opens + 1)
        self.assertEqual(self.repo.config_path.read_bytes(), before)

    def test_workplace_keyboard_opens_card_and_delete_does_not_remove_it(self):
        for record in (self.session.applications[0], self.session.websites[0]):
            self.toggle_card(self.window.collection_page, record.id)
        for kind, record in [("websites", self.session.websites[0]),
                             ("applications", self.session.applications[0])]:
            page = self.window.pages[kind]
            self.select(page, record.id)
            QTest.keyClick(page.grid, Qt.Key.Key_Delete)
            self.assertEqual(page.model.rowCount(), 1)
            previous = len(self.launcher.opened)
            QTest.keyClick(page.grid, Qt.Key.Key_Space)
            self.assertEqual(len(self.launcher.opened), previous + 1)
            QTest.keyClick(page.grid, Qt.Key.Key_Return)
            self.assertEqual(len(self.launcher.opened), previous + 2)
            self.assertEqual(page.model.rowCount(), 1)
