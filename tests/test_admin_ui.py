"""Checks for layout navigation; no backend or authentication is involved."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QPushButton

from tslibrary_ui.app import create_app
from tslibrary_ui import AdminWindow
from tslibrary_ui.shared.controls import TrashButton
from tslibrary_ui.licenses import LibraryItem, LicenseEntry
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.state import LibrarySession


class AdminUiChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def test_supplied_session_survives_recreating_the_admin_window(self):
        session = LibrarySession()
        first = AdminWindow(session=session)
        first.licenses_page.add_button.click()
        editor = first.licenses_page.item_dialog
        editor.name_edit.setText("Shared session item")
        editor.save_button.click()
        self.app.processEvents()
        first.licenses_page.license_window.close()
        first.close()
        first.deleteLater()
        self.app.processEvents()

        second = AdminWindow(session=session)
        self.assertEqual(len(session.items), 1)
        self.assertEqual(second.licenses_page.table.item(0, 0).text(), "Shared session item")
        second.close()
        second.deleteLater()

    def test_tab_switch_keeps_sort_and_category_but_clears_search(self):
        admin = AdminWindow(session=LibrarySession(items=[
            LibraryItem("Beta", "Tools"), LibraryItem("Alpha", "Tools"),
            LibraryItem("Other", "Reference"),
        ]))
        licenses = admin.licenses_page
        licenses.sort_select.setCurrentIndex(1)
        licenses.category_filter.setCurrentText("Tools")
        licenses.search.setText("Beta")
        admin.set_page("Websites")
        self.assertEqual(admin.websites_page.sort_select.currentIndex(), 1)
        admin.set_page("Licenses")
        self.assertEqual(licenses.search.text(), "")
        self.assertEqual(licenses.category_filter.currentText(), "Tools")
        self.assertEqual(licenses.table.rowCount(), 2)
        self.assertEqual(licenses.table.item(0, 0).text(), "Alpha")
        admin.close()
        admin.deleteLater()

    def test_admin_preview_opens_and_returns_to_welcome(self):
        controller = PreviewController()
        controller.welcome.show()
        self.app.processEvents()
        controller.welcome.password_field.edit.setText("preview-only")
        controller.welcome.sign_in_button.click()
        self.app.processEvents()
        self.assertTrue(controller.admin.isVisible())
        self.assertFalse(controller.welcome.isVisible())
        self.assertEqual(controller.welcome.password_field.edit.text(), "")
        controller.admin.sidebar.back_button.click()
        self.app.processEvents()
        self.assertTrue(controller.welcome.isVisible())
        self.assertFalse(controller.admin.isVisible())
        controller.welcome.close()
        controller.admin.close()
        controller.deleteLater()

    def test_navigation_switches_layouts(self):
        admin = AdminWindow()
        admin.show()
        self.app.processEvents()
        for page in ("Licenses", "Applications", "Websites"):
            admin.sidebar.nav_buttons[page].click()
            self.assertEqual(admin.current_page.heading.text(), page)
            self.assertTrue(admin.sidebar.nav_buttons[page].isChecked())
            self.assertTrue(admin.current_page.empty_state.isVisible())
            if page == "Applications":
                admin.current_page.add_button.click()
                self.assertTrue(admin.applications_page.application_dialog.isVisible())
                admin.applications_page.application_dialog.reject()
                self.app.processEvents()
            elif page == "Websites":
                admin.current_page.add_button.click()
                self.assertTrue(admin.websites_page.website_dialog.isVisible())
                admin.websites_page.website_dialog.reject()
                self.app.processEvents()
        admin.close()
        admin.deleteLater()

    def test_application_and_website_tabs_keep_licenses_separate(self):
        admin = AdminWindow()
        admin.licenses_page.items.append(LibraryItem("Design suite", licenses=[LicenseEntry("Pool", 4)]))
        admin.show()
        admin.current_page.refresh()
        self.app.processEvents()
        for page in ("Applications", "Websites"):
            admin.sidebar.nav_buttons[page].click()
            self.assertEqual(admin.current_page.content_stack.currentWidget(), admin.current_page.empty_state)
            self.assertFalse(admin.current_page.category_filter.isVisible())
            self.assertEqual(admin.current_page.search.placeholderText(), f"Search {page.lower()}")
            self.assertNotIn("license", admin.current_page.subtitle.text().lower())
        admin.sidebar.nav_buttons["Licenses"].click()
        self.assertEqual(admin.current_page.content_stack.currentWidget(), admin.licenses_page.table)
        self.assertEqual(admin.licenses_page.table.item(0, 0).text(), "Design suite")
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "4")
        admin.close()
        admin.deleteLater()

    def test_item_license_subwindow_tracks_remaining_counts(self):
        admin = AdminWindow()
        admin.show()
        self.app.processEvents()
        admin.current_page.add_button.click()
        dialog = admin.licenses_page.item_dialog
        dialog.name_edit.setText("Design suite")
        dialog.category_edit.setText("Creative tools")
        dialog.save_button.click()
        self.app.processEvents()
        self.assertEqual(len(admin.licenses_page.items), 1)
        manager = admin.licenses_page.license_window
        self.assertTrue(manager.isVisible())
        for label, remaining, key in [("Shared pool", 10, ""), ("Studio", 3, "DEMO-KEY")]:
            manager.add_button.click()
            editor = manager.entry_dialog
            editor.label_edit.setText(label)
            editor.available_spin.setValue(remaining)
            editor.mode_select.setCurrentIndex(1 if key else 0)
            editor.key_edit.setText(key)
            editor.save_button.click()
            self.app.processEvents()
        self.assertEqual(admin.licenses_page.items[0].available, 13)
        self.assertEqual(manager.table.rowCount(), 2)
        self.assertIn("13 available", manager.summary_label.text())
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "13")
        manager.table.cellWidget(0, 5).findChild(QPushButton).click()
        editor = manager.entry_dialog
        editor.available_spin.setValue(0)
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(admin.licenses_page.items[0].available, 3)
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "3")
        manager.accept()
        admin.close()
        admin.deleteLater()

    def test_item_search_sort_and_subwindow_keep_item_identity(self):
        admin = AdminWindow()
        admin.licenses_page.items.extend([LibraryItem("Alpha", "Tools", [LicenseEntry("Pool", 7)]),
                            LibraryItem("Beta", "Reference")])
        admin.current_page.category_filter.addItems(["Tools", "Reference"])
        admin.show()
        admin.current_page.refresh()
        self.app.processEvents()
        self.assertEqual(admin.licenses_page.table.item(0, 0).text(), "Beta")
        admin.current_page.sort_select.setCurrentIndex(1)
        self.assertEqual(admin.licenses_page.table.item(0, 0).text(), "Alpha")
        admin.current_page.category_filter.setCurrentText("Reference")
        self.assertEqual(admin.licenses_page.table.rowCount(), 1)
        admin.licenses_page.table.cellWidget(0, 4).findChild(QPushButton).click()
        self.assertEqual(admin.licenses_page.license_window.item.name, "Beta")
        admin.licenses_page.license_window.accept()
        admin.current_page.category_filter.setCurrentText("All categories")
        admin.current_page.search.setText("missing")
        self.assertEqual(admin.licenses_page.table.rowCount(), 0)
        self.assertEqual(admin.current_page.empty_heading.text(), "No matching items.")
        admin.current_page.search.clear()
        self.assertEqual(admin.licenses_page.table.rowCount(), 2)
        admin.close()
        admin.deleteLater()

    def test_editing_item_updates_name_category_and_preserves_licenses(self):
        entry = LicenseEntry("Standard", 7, "DEMO-KEY", used=3)
        item = LibraryItem("Old name", "Old category", [entry])
        original_id = item.id
        original_licenses = item.licenses
        admin = AdminWindow()
        admin.licenses_page.items.append(item)
        admin.licenses_page.refresh_categories()
        admin.current_page.category_filter.setCurrentText("Old category")
        admin.show()
        admin.licenses_page.open_licenses(item)
        manager = admin.licenses_page.license_window
        manager.edit_item_button.click()
        editor = manager.details_dialog
        self.assertEqual(editor.name_edit.text(), "Old name")
        self.assertEqual(editor.category_edit.text(), "Old category")
        editor.name_edit.setText("Renamed item")
        editor.category_edit.setText("New category")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((item.name, item.category), ("Renamed item", "New category"))
        self.assertEqual(item.id, original_id)
        self.assertIs(item.licenses, original_licenses)
        self.assertIs(item.licenses[0], entry)
        self.assertEqual((entry.available, entry.used, entry.key), (7, 3, "DEMO-KEY"))
        self.assertEqual(manager.item_title.text(), "Renamed item")
        self.assertEqual(manager.category_label.text(), "New category")
        self.assertIn("Renamed item", manager.windowTitle())
        self.assertEqual(admin.current_page.category_filter.findText("Old category"), -1)
        self.assertGreater(admin.current_page.category_filter.findText("New category"), 0)
        self.assertEqual(admin.licenses_page.table.item(0, 0).text(), "Renamed item")
        self.assertEqual(admin.licenses_page.table.item(0, 1).text(), "New category")
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "7")
        self.assertEqual(admin.licenses_page.table.item(0, 3).text(), "3")
        manager.close()
        admin.close()
        admin.deleteLater()

    def test_admin_layout_fits_small_and_large_windows(self):
        admin = AdminWindow()
        admin.show()
        for width, height in [(1320, 850), (1000, 680), (1600, 1000)]:
            with self.subTest(size=(width, height)):
                admin.resize(width, height)
                self.app.processEvents()
                self.assertEqual((admin.width(), admin.height()), (width, height))
                self.assertGreaterEqual(admin.current_page.empty_state.height(), 300)
                self.assertGreaterEqual(admin.current_page.search.width(), 120)
                self.assertGreaterEqual(admin.current_page.empty_heading.width(),
                                        admin.current_page.empty_heading.minimumSizeHint().width())
        admin.close()
        admin.deleteLater()

    def test_cancel_delete_keeps_item_and_licenses(self):
        item = LibraryItem("Design suite", licenses=[LicenseEntry("Pool", 3, "DEMO-KEY", used=2)])
        admin = AdminWindow()
        admin.licenses_page.items.append(item)
        admin.show()
        admin.current_page.refresh()
        admin.licenses_page.table.cellWidget(0, 4).findChild(TrashButton).click()
        confirm = admin.licenses_page.delete_dialog
        self.assertIn("Design suite", confirm.description.text())
        self.assertIn("1 license entry", confirm.description.text())
        confirm.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(admin.licenses_page.items, [item])
        self.assertEqual((item.available, item.used), (3, 2))
        self.assertEqual(item.licenses[0].key, "DEMO-KEY")
        self.assertTrue(admin.isVisible())
        admin.close()
        admin.deleteLater()

    def test_confirm_delete_removes_only_target_id_and_refreshes_counts(self):
        removed = LibraryItem("Same name", "Unlimited category", [
            LicenseEntry("Unlimited", 0, "DEMO-KEY", unlimited=True)])
        retained = LibraryItem("Same name", "Retained category", [LicenseEntry("Pool", 4, used=1)])
        admin = AdminWindow()
        admin.licenses_page.items.extend([removed, retained])
        admin.licenses_page.refresh_categories()
        admin.current_page.category_filter.setCurrentText("Unlimited category")
        admin.show()
        admin.current_page.refresh()
        admin.licenses_page.table.cellWidget(0, 4).findChild(TrashButton).click()
        finished = QSignalSpy(admin.licenses_page.delete_dialog.finished)
        admin.licenses_page.delete_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual([item.id for item in admin.licenses_page.items], [retained.id])
        self.assertEqual(finished.count(), 1)
        self.assertEqual(admin.current_page.category_filter.findText("Unlimited category"), -1)
        self.assertEqual(admin.licenses_page.table.rowCount(), 1)
        self.assertEqual(admin.licenses_page.table.item(0, 1).text(), "Retained category")
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "4")
        self.assertEqual(admin.licenses_page.table.item(0, 3).text(), "1")
        self.assertNotIn("∞", admin.current_page.count_label.text())
        admin.close()
        admin.deleteLater()

    def test_delete_last_item_restores_empty_state(self):
        item = LibraryItem("Last item")
        admin = AdminWindow()
        admin.licenses_page.items.append(item)
        admin.show()
        admin.current_page.refresh()
        admin.licenses_page.table.cellWidget(0, 4).findChild(TrashButton).click()
        admin.licenses_page.delete_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(admin.licenses_page.items, [])
        self.assertEqual(admin.licenses_page.table.rowCount(), 0)
        self.assertEqual(admin.current_page.content_stack.currentWidget(), admin.current_page.empty_state)
        self.assertTrue(admin.current_page.empty_button.isVisible())
        self.assertIn("0 available", admin.current_page.count_label.text())
        admin.close()
        admin.deleteLater()
