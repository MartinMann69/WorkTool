"""Name-only inventory workflows and isolation from desktop applications."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton

from tslibrary_ui import AdminWindow
from tslibrary_ui.app import create_app
from tslibrary_ui.applications import Application
from tslibrary_ui.shared.controls import TrashButton
from tslibrary_ui.state import LibrarySession


class PhoneAppChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.admin = AdminWindow()
        self.admin.sidebar.nav_buttons["Phone apps"].click()
        self.admin.show()
        self.app.processEvents()
        self.page = self.admin.phone_apps_page

    def tearDown(self):
        for dialog in self.admin.findChildren(QDialog):
            dialog.close()
        self.admin.close()
        self.admin.deleteLater()
        self.app.processEvents()

    def add(self, name):
        self.page.add_button.click()
        editor = self.page.phone_app_dialog
        editor.name_edit.setText(name)
        editor.save_button.click()
        self.app.processEvents()
        return self.page.phone_apps[-1]

    def test_add_requires_only_a_name_and_no_path(self):
        self.page.empty_button.click()
        editor = self.page.phone_app_dialog
        self.assertEqual(editor.findChildren(QLineEdit), [editor.name_edit])
        editor.name_edit.setText("  Teams ツール  ")
        QTest.keyClick(editor.name_edit, Qt.Key.Key_Return)
        self.app.processEvents()
        entry = self.admin.session.phone_apps[0]
        self.assertEqual(entry.name, "Teams ツール")
        self.assertEqual(self.page.table.item(0, 0).text(), entry.name)
        self.assertFalse(self.page.table.item(0, 0).icon().isNull())
        self.assertEqual(self.page.table.columnCount(), 2)
        self.assertEqual(self.page.count_label.text(), "Showing 1 of 1 phone app")

    def test_blank_names_and_cancel_keep_inventory(self):
        self.page.add_button.click()
        editor = self.page.phone_app_dialog
        for name in ("", "   "):
            editor.name_edit.setText(name)
            editor.save_button.click()
            self.assertEqual(editor.result(), QDialog.DialogCode.Rejected)
            self.assertTrue(editor.error.text())
            self.assertEqual(self.page.phone_apps, [])
        editor.name_edit.setText("Cancelled app")
        editor.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(self.page.phone_apps, [])
        entry = self.add("Keep this name")
        self.page.add_phone_app(entry)
        editor = self.page.phone_app_dialog
        editor.name_edit.setText("Unsaved edit")
        editor.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(entry.name, "Keep this name")

    def test_search_sort_and_edit_target_the_visible_entry(self):
        alpha = self.add("Alpha")
        beta = self.add("Beta")
        original_id = beta.id
        self.assertEqual(self.page.table.item(0, 0).text(), "Beta")
        self.page.sort_select.setCurrentIndex(1)
        self.assertEqual(self.page.table.item(0, 0).text(), "Alpha")
        self.page.search.setText("BETA")
        self.assertEqual(self.page.table.rowCount(), 1)
        self.page.table.cellDoubleClicked.emit(0, 0)
        editor = self.page.phone_app_dialog
        self.assertEqual(editor.name_edit.text(), "Beta")
        editor.name_edit.setText("Renamed app")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((beta.id, beta.name), (original_id, "Renamed app"))
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(self.page.table.rowCount(), 0)
        self.assertEqual(self.page.empty_heading.text(), "No matching phone apps.")
        self.assertFalse(self.page.empty_button.isVisible())
        self.page.search.clear()
        self.assertEqual(self.page.table.rowCount(), 2)

    def test_cancel_and_confirm_delete_preserve_other_entries(self):
        retained = self.add("Same name")
        removed = self.add("Same name")
        shared_list = self.admin.session.phone_apps
        self.page.table.cellWidget(0, 1).findChild(TrashButton).click()
        self.page.remove_phone_app_dialog.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(shared_list, [retained, removed])
        self.page.table.cellWidget(0, 1).findChild(TrashButton).click()
        self.page.remove_phone_app_dialog.delete_button.click()
        self.app.processEvents()
        self.assertIs(self.admin.session.phone_apps, shared_list)
        self.assertEqual(shared_list, [retained])
        self.page.table.cellWidget(0, 1).findChild(TrashButton).click()
        self.page.remove_phone_app_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(shared_list, [])
        self.assertIs(self.page.content_stack.currentWidget(), self.page.empty_state)
        self.assertTrue(self.page.empty_button.isVisible())

    def test_session_keeps_phone_apps_separate_across_windows(self):
        entry = self.add("Phone inventory")
        desktop = Application("Desktop app", "example.exe")
        self.admin.session.applications.append(desktop)
        self.page.sort_select.setCurrentIndex(1)
        self.page.search.setText("missing")
        self.admin.set_page("Applications")
        self.assertEqual(self.admin.applications_page.table.item(0, 0).text(), "Desktop app")
        self.admin.set_page("Phone apps")
        self.assertEqual(self.page.search.text(), "missing")
        self.assertEqual(self.page.sort_select.currentIndex(), 1)
        second = AdminWindow(session=self.admin.session)
        try:
            second.set_page("Phone apps")
            self.assertEqual(second.phone_apps_page.phone_apps, [entry])
            self.assertEqual(second.session.applications, [desktop])
            self.assertEqual(second.session.websites, [])
            self.assertEqual(second.session.items, [])
            self.assertEqual(LibrarySession().phone_apps, [])
        finally:
            second.close()
            second.deleteLater()

    def test_empty_and_populated_layout_fit_supported_sizes(self):
        for populated in (False, True):
            if populated:
                self.add("A long phone app name " * 6)
            for size in [(1000, 680), (1320, 850), (1600, 1000)]:
                with self.subTest(populated=populated, size=size):
                    self.admin.resize(*size)
                    self.app.processEvents()
                    self.assertEqual((self.admin.width(), self.admin.height()), size)
                    self.assertFalse(self.page.category_filter.isVisible())
                    if populated:
                        self.assertEqual(self.page.table.horizontalScrollBar().maximum(), 0)
                        self.assertTrue(self.page.table.cellWidget(0, 1).findChild(QPushButton).isVisible())


if __name__ == "__main__":
    unittest.main()
