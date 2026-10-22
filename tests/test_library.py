"""Browse, filter, and navigation behavior against a shared admin session."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tslibrary_ui import AdminWindow, LibraryWindow
from tslibrary_ui.app import create_app
from tslibrary_ui.applications.models import Application
from tslibrary_ui.licenses.models import LibraryItem, LicenseEntry
from tslibrary_ui.phone_apps.models import PhoneApp
from tslibrary_ui.websites.models import Website
from tslibrary_ui.library.models import catalog_entries, filter_entries
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.state import LibrarySession


class LibraryChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.session = LibrarySession(
            applications=[Application("Zebra Editor", r"C:\Tools\zebra.exe"),
                          Application("alpha Studio", r"C:\Tools\alpha.exe")],
            websites=[Website("Team portal", "https://portal.example.com/team")],
            phone_apps=[PhoneApp("Authenticator")],
            items=[LibraryItem("Design suite", "Creative tools", [
                LicenseEntry("Internal only", 4, "SECRET-LICENSE-KEY", used=2)])],
        )
        self.window = LibraryWindow(session=self.session)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def names(self):
        return [entry.name for entry in self.window.model.entries]

    def test_all_sources_and_sorts(self):
        self.assertEqual(self.names(), ["alpha Studio", "Authenticator", "Design suite", "Team portal", "Zebra Editor"])
        self.assertEqual({kind: label.text() for kind, label in self.window.type_counts.items()},
                         {"applications": "2", "websites": "1", "phone_apps": "1", "licenses": "1"})
        self.window.sort_select.setCurrentIndex(1)
        self.assertEqual(self.names(), ["Zebra Editor", "Team portal", "Design suite", "Authenticator", "alpha Studio"])
        self.window.sort_select.setCurrentIndex(2)
        self.assertEqual(self.names(), ["alpha Studio", "Zebra Editor", "Design suite", "Authenticator", "Team portal"])

    def test_search_combines_with_type_and_reset_preserves_sort(self):
        self.window.type_filter.setCurrentIndex(self.window.type_filter.findData("applications"))
        self.window.search.setText("  ALPHA   studio  ")
        self.assertEqual(self.names(), ["alpha Studio"])
        self.window.search.setText("portal.example")
        self.assertEqual(self.names(), [])
        self.assertIs(self.window.content_stack.currentWidget(), self.window.empty_state)
        self.window.type_filter.setCurrentIndex(0)
        self.assertEqual(self.names(), ["Team portal"])
        self.window.sort_select.setCurrentIndex(1)
        self.window.clear_button.click()
        self.assertEqual(len(self.names()), 5)
        self.assertEqual(self.names()[0], "Zebra Editor")
        self.assertFalse(self.window.clear_button.isEnabled())

    def test_changes_appear_on_return_without_mutating_admin_data(self):
        self.window.hide()
        first = self.session.applications[0]
        first.name = "Renamed application"
        self.session.websites.clear()
        self.session.phone_apps.append(PhoneApp("Team chat"))
        self.window.show()
        self.app.processEvents()
        self.assertIn("Renamed application", self.names())
        self.assertIn("Team chat", self.names())
        self.assertNotIn("Team portal", self.names())
        original = list(self.session.applications)
        self.window.search.setText("missing")
        self.window.sort_select.setCurrentIndex(1)
        self.assertEqual(self.session.applications, original)
        self.assertIs(self.session.applications[0], first)

    def test_license_keys_are_absent_from_projection_and_display(self):
        entries = catalog_entries(self.session)
        self.assertEqual(filter_entries(entries, "SECRET-LICENSE-KEY"), [])
        self.assertNotIn("SECRET-LICENSE-KEY", repr(entries))
        for row in range(self.window.model.rowCount()):
            index = self.window.model.index(row, 0)
            for role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole,
                         Qt.ItemDataRole.AccessibleDescriptionRole):
                self.assertNotIn("SECRET-LICENSE-KEY", str(index.data(role)))
        license_entry = next(entry for entry in entries if entry.kind == "licenses")
        self.assertIn("4 available", license_entry.detail)

    def test_empty_library_and_no_results_have_distinct_states(self):
        self.window.search.setText("no such resource")
        self.assertEqual(self.window.empty_heading.text(), "No matches this time.")
        self.window.session = LibrarySession()
        self.window.clear_filters()
        self.assertEqual(self.window.model.rowCount(), 0)
        self.assertEqual(self.window.empty_heading.text(), "A little room for your tools.")

    def test_responsive_grid_and_read_only_items(self):
        for width, height, columns in [(820, 650, 2), (1320, 850, 4),
                                       (1600, 1000, 5), (900, 700, 2)]:
            self.window.resize(width, height)
            for _ in range(3):
                self.app.processEvents()
            self.assertEqual((self.window.width(), self.window.height()), (width, height))
            self.assertEqual(self.window.grid.horizontalScrollBar().maximum(), 0)
            self.assertGreaterEqual(self.window.grid.gridSize().width(), 250)
            first_row = [self.window.grid.visualRect(self.window.model.index(row, 0)).top()
                         for row in range(self.window.model.rowCount())]
            self.assertEqual(first_row.count(first_row[0]), columns)
        index = self.window.model.index(0, 0)
        self.assertFalse(self.window.model.flags(index) & Qt.ItemFlag.ItemIsEditable)
        self.window.grid.setCurrentIndex(index)
        self.assertIn("alpha Studio", self.window.detail_label.text())
        QTest.keyClick(self.window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(self.window.search.hasFocus())
        QTest.keyClicks(self.window.search, "alpha")
        self.assertEqual(self.names(), ["alpha Studio"])

    def test_direct_library_navigation_and_admin_edits_survive(self):
        controller = PreviewController(session=self.session)
        try:
            controller.welcome.show()
            controller.show_library()
            self.app.processEvents()
            self.assertTrue(controller.library.isVisible())
            self.assertFalse(controller.welcome.isVisible())
            self.assertFalse(controller.admin.isVisible())
            self.assertIs(controller.library.session, controller.admin.session)
            controller.library.back_button.click()
            self.assertTrue(controller.welcome.isVisible())
            controller.welcome.sign_in_button.click()
            self.assertTrue(controller.admin.isVisible())
            # Exercise an actual admin dialog, then browse that same entry.
            controller.admin.set_page("Phone apps")
            controller.admin.phone_apps_page.add_phone_app()
            dialog = controller.admin.phone_apps_page.phone_app_dialog
            dialog.name_edit.setText("Added by administrator")
            dialog.save_button.click()
            self.app.processEvents()
            controller.admin.sidebar.back_button.click()
            controller.show_library()
            self.assertIn("Added by administrator", [entry.name for entry in controller.library.model.entries])
            self.assertFalse(controller.admin.isVisible())
        finally:
            for window in (controller.library, controller.admin, controller.welcome,
                           controller.main_window):
                window.close()
                window.deleteLater()
            controller.deleteLater()

    def test_admin_full_library_tab_combines_filters_and_refreshes_all_sources(self):
        admin = AdminWindow(session=self.session)
        try:
            admin.show()
            admin.sidebar.nav_buttons["Full library"].click()
            page = admin.full_library_page
            self.assertIs(admin.current_page, page)
            self.assertEqual(page.heading.text(), "Full library")
            self.assertEqual(page.model.rowCount(), 5)
            page.type_filter.setCurrentIndex(page.type_filter.findData("websites"))
            page.search.setText("portal")
            self.assertEqual([entry.name for entry in page.model.entries], ["Team portal"])
            page.clear_filters()
            admin.set_page("Phone apps")
            admin.phone_apps_page.add_phone_app()
            dialog = admin.phone_apps_page.phone_app_dialog
            dialog.name_edit.setText("New team app")
            dialog.save_button.click()
            self.app.processEvents()
            admin.set_page("Full library")
            self.assertEqual(page.model.rowCount(), 6)
            self.assertIn("New team app", [entry.name for entry in page.model.entries])
            admin.set_page("Websites")
            self.session.websites[0].name = "Renamed portal"
            self.session.applications.pop()
            admin.set_page("Full library")
            self.assertEqual(page.model.rowCount(), 5)
            self.assertIn("Renamed portal", [entry.name for entry in page.model.entries])
            self.assertNotIn("alpha Studio", [entry.name for entry in page.model.entries])
        finally:
            admin.close()
            admin.deleteLater()

    def test_admin_overview_sort_is_independent_of_inventory_sorts(self):
        admin = AdminWindow(session=self.session)
        try:
            admin.licenses_page.sort_select.setCurrentIndex(1)
            admin.set_page("Full library")
            page = admin.full_library_page
            self.assertEqual(page.sort_select.currentData(), "name_asc")
            page.sort_select.setCurrentIndex(page.sort_select.findData("type"))
            admin.set_page("Applications")
            self.assertEqual(admin.applications_page.sort_select.currentText(), "Name: A to Z")
            admin.applications_page.sort_select.setCurrentIndex(0)
            admin.set_page("Full library")
            self.assertEqual(page.sort_select.currentData(), "type")
            admin.set_page("Websites")
            self.assertEqual(admin.websites_page.sort_select.currentText(), "Recently added")
        finally:
            admin.close()
            admin.deleteLater()

    def test_admin_overview_fits_supported_window_sizes(self):
        admin = AdminWindow(session=self.session)
        try:
            admin.show()
            admin.set_page("Full library")
            page = admin.full_library_page
            for width, height in [(1000, 680), (1320, 850), (1600, 1000)]:
                with self.subTest(size=(width, height)):
                    admin.resize(width, height)
                    for _ in range(4):
                        self.app.processEvents()
                    self.assertEqual((admin.width(), admin.height()), (width, height))
                    self.assertEqual(page.grid.horizontalScrollBar().maximum(), 0)
                    self.assertGreater(page.grid.viewport().height(), 200)
                    self.assertGreaterEqual(page.search.width(), 100)
                    self.assertTrue(admin.sidebar.nav_buttons["Full library"].isChecked())
        finally:
            admin.close()
            admin.deleteLater()
