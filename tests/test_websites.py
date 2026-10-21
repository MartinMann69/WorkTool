"""Website entry editing and list behavior, without accessing the network."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QDialog, QPushButton

from tslibrary_ui.app import create_app
from tslibrary_ui import AdminWindow
from tslibrary_ui.applications import Application
from tslibrary_ui.shared.controls import TrashButton
from tslibrary_ui.licenses import LibraryItem
from tslibrary_ui.websites import normalize_website_url


class WebsiteChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.admin = AdminWindow()
        self.admin.set_page("Websites")
        self.admin.show()
        self.app.processEvents()

    def tearDown(self):
        for dialog in self.admin.findChildren(QDialog):
            dialog.close()
        self.admin.close()
        self.admin.deleteLater()
        self.app.processEvents()

    def add(self, url, name=None):
        self.admin.current_page.add_button.click()
        editor = self.admin.websites_page.website_dialog
        editor.url_edit.setText(url)
        if name is not None:
            editor.name_edit.setText(name)
        editor.save_button.click()
        self.app.processEvents()
        return self.admin.websites_page.websites[-1]

    def test_empty_action_adds_website_with_suggested_name_and_icon(self):
        self.admin.current_page.empty_button.click()
        editor = self.admin.websites_page.website_dialog
        self.app.processEvents()
        editor.url_edit.setText("  www.example.com/docs?q=one%20two#start  ")
        QTest.keyClick(editor.url_edit, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertTrue(editor.name_edit.hasFocus())
        self.assertEqual(editor.name_edit.text(), "example.com")
        self.assertFalse(editor.icon_preview.pixmap().isNull())
        with patch("PySide6.QtGui.QDesktopServices.openUrl") as browser:
            QTest.keyClick(editor.name_edit, Qt.Key.Key_Return)
            self.app.processEvents()
        browser.assert_not_called()
        entry = self.admin.websites_page.websites[0]
        self.assertEqual((entry.name, entry.url),
                         ("example.com", "https://www.example.com/docs?q=one%20two#start"))
        self.assertFalse(entry.icon.isNull())
        self.assertIs(self.admin.current_page.content_stack.currentWidget(), self.admin.websites_page.table)
        self.assertEqual(self.admin.websites_page.table.item(0, 1).text(), entry.url)
        self.assertEqual(self.admin.websites_page.table.item(0, 0).icon().cacheKey(), entry.icon.cacheKey())
        self.assertEqual(self.admin.current_page.count_label.text(), "Showing 1 of 1 website")

    def test_url_suggestions_follow_address_but_keep_custom_names(self):
        self.admin.websites_page.add_website()
        editor = self.admin.websites_page.website_dialog
        editor.url_edit.setText("alpha.example.com")
        editor._update_preview()
        self.assertEqual(editor.name_edit.text(), "alpha.example.com")
        editor.url_edit.setText("beta.example.com")
        editor._update_preview()
        self.assertEqual(editor.name_edit.text(), "beta.example.com")
        editor.name_edit.setText("Team portal")
        editor.url_edit.setText("https://portal.example.com/dashboard")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(self.admin.websites_page.websites[0].name, "Team portal")

    def test_invalid_urls_are_rejected_and_cancel_does_not_save(self):
        self.admin.current_page.add_button.click()
        editor = self.admin.websites_page.website_dialog
        for url in ("", "not a website", "https://", "http:///path", "https://.example.com",
                    "https://example.com:99999", "https://example.com:port", "mailto:test@example.com",
                    "file:///C:/Windows/notepad.exe", "javascript:alert(1)", "ftp://example.com",
                    "https://admin:secret@example.com", "https://example.com/a\nb", r"C:\website.url"):
            with self.subTest(url=url):
                editor.url_edit.setText(url)
                editor.save_button.click()
                self.assertEqual(editor.result(), QDialog.DialogCode.Rejected)
                self.assertTrue(editor.error.text())
                self.assertEqual(self.admin.websites_page.websites, [])
        editor.url_edit.setText("https://example.com")
        editor.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(self.admin.websites_page.websites, [])

    def test_internal_addresses_unicode_and_encoded_url_parts(self):
        for raw, expected in [
            ("example.com/path?q=a%26b#section", "https://example.com/path?q=a%26b#section"),
            ("HTTP://localhost:8080/tools", "http://localhost:8080/tools"),
            ("intranet:8443/tools", "https://intranet:8443/tools"),
            ("//portal.example.com", "https://portal.example.com"),
            ("https://[::1]:8080/", "https://[::1]:8080/"),
            ("https://例え.テスト/資料", "https://xn--r8jz45g.xn--zckzah/%E8%B3%87%E6%96%99"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_website_url(raw), expected)

    def test_edit_and_cancel_keep_identity_and_other_tabs_independent(self):
        item = LibraryItem("Licensed tool")
        app_entry = Application("Desktop tool", "C:/Tools/tool.exe")
        self.admin.licenses_page.items.append(item)
        self.admin.applications_page.applications.append(app_entry)
        entry = self.add("https://old.example.com", "Original")
        original_id = entry.id
        self.admin.websites_page.table.cellWidget(0, 2).findChild(QPushButton).click()
        editor = self.admin.websites_page.website_dialog
        editor.url_edit.setText("https://ignored.example.com")
        editor.name_edit.setText("Ignored")
        editor.cancel_button.click()
        self.app.processEvents()
        self.assertEqual((entry.name, entry.url), ("Original", "https://old.example.com"))
        self.admin.websites_page.table.cellDoubleClicked.emit(0, 0)
        editor = self.admin.websites_page.website_dialog
        editor.url_edit.setText("http://intranet:8080/library")
        editor.name_edit.setText("Updated")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((entry.id, entry.name, entry.url),
                         (original_id, "Updated", "http://intranet:8080/library"))
        self.admin.set_page("Licenses")
        self.assertEqual(self.admin.licenses_page.table.item(0, 0).text(), item.name)
        self.admin.set_page("Applications")
        self.assertEqual(self.admin.applications_page.table.item(0, 0).text(), app_entry.name)
        self.admin.set_page("Websites")
        self.assertEqual(self.admin.websites_page.table.item(0, 0).text(), "Updated")
        self.assertEqual(self.admin.websites_page.websites, [entry])

    def test_search_sort_and_actions_use_the_filtered_website_id(self):
        first = self.add("https://alpha.example.com", "Alpha")
        second = self.add("https://beta.example.com", "Beta")
        self.assertEqual(self.admin.websites_page.table.item(0, 0).text(), "Beta")
        self.admin.current_page.sort_select.setCurrentIndex(1)
        self.assertEqual(self.admin.websites_page.table.item(0, 0).text(), "Alpha")
        self.admin.current_page.search.setText("BETA.EXAMPLE")
        self.assertEqual(self.admin.websites_page.table.rowCount(), 1)
        self.admin.websites_page._edit_website_row(0, 1)
        editor = self.admin.websites_page.website_dialog
        editor.name_edit.setText("Renamed")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((first.name, second.name), ("Alpha", "Renamed"))
        self.admin.current_page.search.setText("no match")
        self.assertIs(self.admin.current_page.content_stack.currentWidget(), self.admin.current_page.empty_state)
        self.assertEqual(self.admin.current_page.empty_heading.text(), "No matching websites.")
        self.assertFalse(self.admin.current_page.empty_button.isVisible())
        self.assertEqual(self.admin.current_page.count_label.text(), "Showing 0 of 2 websites")
        self.admin.current_page.search.clear()
        self.assertEqual(self.admin.websites_page.table.rowCount(), 2)

    def test_remove_confirmation_targets_one_entry_and_restores_empty_state(self):
        first = self.add("https://first.example.com", "Same name")
        second = self.add("https://second.example.com", "Same name")
        self.admin.current_page.search.setText("second.example")
        self.admin.websites_page.table.cellWidget(0, 2).findChild(TrashButton).click()
        self.admin.websites_page.remove_website_dialog.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(self.admin.websites_page.websites, [first, second])
        self.admin.websites_page.table.cellWidget(0, 2).findChild(TrashButton).click()
        finished = QSignalSpy(self.admin.websites_page.remove_website_dialog.finished)
        self.admin.websites_page.remove_website_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(finished.count(), 1)
        self.assertEqual(self.admin.websites_page.websites, [first])
        self.assertIs(self.admin.current_page.content_stack.currentWidget(), self.admin.current_page.empty_state)
        self.admin.current_page.search.clear()
        self.admin.websites_page.confirm_remove_website(first)
        self.admin.websites_page.remove_website_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(self.admin.websites_page.websites, [])
        self.assertIs(self.admin.current_page.content_stack.currentWidget(), self.admin.current_page.empty_state)
        self.assertTrue(self.admin.current_page.empty_button.isVisible())
        self.assertEqual(self.admin.current_page.count_label.text(), "Showing 0 of 0 websites")


if __name__ == "__main__":
    unittest.main()
