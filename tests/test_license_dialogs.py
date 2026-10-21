"""Validate license input and editing without persistence or external services."""

import os
import unittest
from math import isinf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QDialog, QLineEdit

from tslibrary_ui.app import create_app
from tslibrary_ui import AdminWindow
from tslibrary_ui.shared.controls import TrashButton
from tslibrary_ui.licenses import (
    ItemDialog, LicenseEntry, LicenseEntryDialog, LibraryItem, LicenseWindow,
)


class LicenseDialogChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def test_empty_names_and_missing_key_are_rejected(self):
        item = ItemDialog()
        item._save()
        self.assertEqual(item.result(), QDialog.DialogCode.Rejected)
        self.assertTrue(item.error.text())
        editor = LicenseEntryDialog()
        editor.label_edit.setText("Standard")
        editor.mode_select.setCurrentIndex(1)
        editor._save()
        self.assertEqual(editor.result(), QDialog.DialogCode.Rejected)
        self.assertTrue(editor.error.text())
        editor.key_edit.setText("DEMO-KEY")
        editor._save()
        self.assertEqual(editor.result(), QDialog.DialogCode.Accepted)
        item.deleteLater()
        editor.deleteLater()

    def test_count_mode_keeps_available_and_used_when_key_is_removed(self):
        editor = LicenseEntryDialog(entry=LicenseEntry("Pool", 5, "DEMO-KEY", used=3))
        editor.mode_select.setCurrentIndex(0)
        editor.available_spin.setValue(0)
        editor._save()
        self.assertEqual(editor.entry(), LicenseEntry("Pool", 0, used=3))
        self.assertEqual(editor.total_label.text(), "Total licenses: 3")
        editor.available_spin.setValue(-5)
        self.assertEqual(editor.available_spin.value(), 0)
        editor.deleteLater()

    def test_cancel_leaves_original_entry_unchanged_and_keys_start_masked(self):
        entry = LicenseEntry("Studio", 4, "DEMO-SECRET", used=2)
        item = LibraryItem("Design suite", licenses=[entry])
        admin = AdminWindow()
        manager = LicenseWindow(item, admin)
        key_view = manager.table.cellWidget(0, 4).findChild(QLineEdit)
        self.assertEqual(key_view.echoMode(), QLineEdit.EchoMode.Password)
        manager._open_editor(0)
        editor = manager.entry_dialog
        editor.available_spin.setValue(2)
        editor.used_spin.setValue(7)
        editor.key_edit.setText("changed")
        editor.reject()
        self.assertEqual(entry.available, 4)
        self.assertEqual(entry.used, 2)
        self.assertEqual(entry.key, "DEMO-SECRET")
        manager.close()
        admin.close()
        admin.deleteLater()

    def test_quick_usage_updates_preserve_total_and_refresh_item_counts(self):
        item = LibraryItem("Design suite", licenses=[LicenseEntry("Pool", 2, used=1),
                                                      LicenseEntry("Keyed", 1, "DEMO-KEY")])
        admin = AdminWindow()
        admin.licenses_page.items.append(item)
        admin.show()
        admin.current_page.refresh()
        admin.licenses_page.open_licenses(item)
        manager = admin.licenses_page.license_window
        self.app.processEvents()
        spy = QSignalSpy(manager.changed)
        release, count_label, use = manager.usage_controls[0]
        use.click()
        use.click()
        self.assertEqual((item.licenses[0].available, item.licenses[0].used), (0, 3))
        self.assertEqual(count_label.text(), "3")
        self.assertFalse(use.isEnabled())
        self.assertEqual(item.total, 4)
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "1")
        self.assertEqual(admin.licenses_page.table.item(0, 3).text(), "3")
        for _ in range(3):
            release.click()
        self.assertFalse(release.isEnabled())
        self.assertEqual((item.available, item.used, item.total), (4, 0, 4))
        self.assertEqual(spy.count(), 5)
        # Count buttons stay alive for repeated clicks instead of rebuilding rows.
        self.assertIs(use, manager.usage_controls[0][2])
        self.assertEqual(manager.summary_label.text(), "4 available · 0 used · 4 total")
        self.assertEqual(item.licenses[1].available, 1)
        manager.close()
        admin.close()
        admin.deleteLater()

    def test_quick_updates_on_keyed_entry_cannot_use_or_return_below_zero(self):
        item = LibraryItem("Keyed item", licenses=[LicenseEntry("Seat", 1, "DEMO-KEY")])
        admin = AdminWindow()
        manager = LicenseWindow(item, admin)
        manager._change_usage(0, -1)
        self.assertEqual((item.available, item.used), (1, 0))
        manager._change_usage(0, 1)
        manager._change_usage(0, 1)
        self.assertEqual((item.available, item.used), (0, 1))
        manager._change_usage(0, -1)
        self.assertEqual((item.available, item.used, item.total), (1, 0, 1))
        self.assertEqual(item.licenses[0].key, "DEMO-KEY")
        manager.close()
        admin.close()
        admin.deleteLater()

    def test_cancel_item_edit_keeps_original_details_and_blank_name_is_rejected(self):
        item = LibraryItem("Design suite", "Creative tools")
        admin = AdminWindow()
        manager = LicenseWindow(item, admin)
        manager.edit_item_button.click()
        editor = manager.details_dialog
        editor.name_edit.setText("   ")
        editor.save_button.click()
        self.assertTrue(editor.error.text())
        self.assertEqual(item.name, "Design suite")
        editor.name_edit.setText("Changed name")
        editor.category_edit.setText("Changed category")
        editor.reject()
        self.assertEqual((item.name, item.category), ("Design suite", "Creative tools"))
        manager.close()
        admin.close()
        admin.deleteLater()

    def test_unlimited_key_can_be_added_and_switched_back_to_counted(self):
        editor = LicenseEntryDialog()
        editor.label_edit.setText("Company key")
        editor.mode_select.setCurrentIndex(1)
        editor.available_spin.setValue(5)
        editor.used_spin.setValue(2)
        editor.unlimited_checkbox.setChecked(True)
        self.assertFalse(editor.available_spin.isEnabled())
        self.assertFalse(editor.used_spin.isEnabled())
        self.assertTrue(editor.count_fields.isHidden())
        self.assertFalse(editor.unlimited_fields.isHidden())
        editor._save()
        self.assertTrue(editor.error.text())
        self.assertEqual(editor.result(), QDialog.DialogCode.Rejected)
        editor.key_edit.setText("DEMO-UNLIMITED")
        editor._save()
        entry = editor.entry()
        self.assertTrue(entry.unlimited)
        self.assertEqual((entry.available_text, entry.used_text), ("∞", "—"))
        reopened = LicenseEntryDialog(entry=entry)
        self.assertTrue(reopened.unlimited_checkbox.isChecked())
        reopened.unlimited_checkbox.setChecked(False)
        self.assertTrue(reopened.available_spin.isEnabled())
        self.assertEqual((reopened.entry().available, reopened.entry().used), (5, 2))
        self.assertFalse(reopened.entry().unlimited)
        self.assertEqual(reopened.entry().key, "DEMO-UNLIMITED")
        reopened.unlimited_checkbox.setChecked(True)
        reopened.mode_select.setCurrentIndex(0)
        self.assertFalse(reopened.unlimited_checkbox.isChecked())
        self.assertFalse(reopened.entry().unlimited)
        self.assertEqual(reopened.entry().key, "")
        reopened.deleteLater()
        editor.deleteLater()

    def test_unlimited_row_and_item_show_infinity_and_dash_without_usage_controls(self):
        item = LibraryItem("Unlimited item", licenses=[
            LicenseEntry("Company key", 5, "DEMO-KEY", used=2, unlimited=True)])
        admin = AdminWindow()
        admin.licenses_page.items.append(item)
        admin.show()
        admin.current_page.refresh()
        admin.licenses_page.open_licenses(item)
        manager = admin.licenses_page.license_window
        self.app.processEvents()
        self.assertTrue(isinf(item.available))
        self.assertTrue(isinf(item.total))
        self.assertIsNone(item.used)
        self.assertEqual(manager.table.item(0, 2).text(), "∞")
        release, used_label, use = manager.usage_controls[0]
        self.assertEqual(used_label.text(), "—")
        self.assertFalse(release.isEnabled())
        self.assertFalse(use.isEnabled())
        self.assertFalse(release.isVisible())
        self.assertEqual(manager.summary_label.text(), "∞ available · — used · ∞ total")
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "∞")
        self.assertEqual(admin.licenses_page.table.item(0, 3).text(), "—")
        spy = QSignalSpy(manager.changed)
        manager._change_usage(0, 1)
        manager._change_usage(0, -1)
        self.assertEqual(spy.count(), 0)
        self.assertEqual((item.licenses[0].available, item.licenses[0].used), (5, 2))
        manager._open_editor(0)
        editor = manager.entry_dialog
        editor.unlimited_checkbox.setChecked(False)
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((item.available, item.used, item.total), (5, 2, 7))
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "5")
        self.assertEqual(admin.licenses_page.table.item(0, 3).text(), "2")
        manager.close()
        admin.close()
        admin.deleteLater()

    def test_mixed_license_summary_excludes_unlimited_usage(self):
        item = LibraryItem("Mixed", licenses=[LicenseEntry("Pool", 3, used=2),
            LicenseEntry("Unlimited", 5, "DEMO-KEY", used=7, unlimited=True)])
        admin = AdminWindow()
        admin.licenses_page.items.append(item)
        admin.show()
        admin.current_page.refresh()
        manager = LicenseWindow(item, admin)
        self.assertEqual(item.used, 2)
        self.assertEqual(item.used_text, "2 tracked")
        self.assertEqual(manager.summary_label.text(), "∞ available · 2 tracked used · ∞ total")
        self.assertEqual(admin.licenses_page.table.item(0, 3).text(), "2 tracked")
        self.assertIn("2 tracked used", admin.current_page.count_label.text())
        manager._change_usage(0, 1)
        self.assertEqual((item.licenses[0].available, item.licenses[0].used), (2, 3))
        self.assertIn("3 tracked used", manager.summary_label.text())
        manager.close()
        admin.close()
        admin.deleteLater()

    def test_cancel_license_deletion_preserves_key_and_counts(self):
        entry = LicenseEntry("Studio key", 5, "DEMO-SECRET", used=2)
        item = LibraryItem("Design suite", licenses=[entry])
        admin = AdminWindow()
        admin.licenses_page.items.append(item)
        admin.show()
        admin.licenses_page.open_licenses(item)
        manager = admin.licenses_page.license_window
        manager.table.cellWidget(0, 5).findChild(TrashButton).click()
        confirm = manager.delete_entry_dialog
        self.assertIn("Studio key", confirm.description.text())
        self.assertNotIn("DEMO-SECRET", confirm.description.text())
        confirm.cancel_button.click()
        self.app.processEvents()
        self.assertIs(item.licenses[0], entry)
        self.assertEqual((entry.available, entry.used, entry.key), (5, 2, "DEMO-SECRET"))
        self.assertTrue(manager.isVisible())
        manager.close()
        admin.close()
        admin.deleteLater()

    def test_delete_specific_license_keys_refreshes_totals_and_keeps_item(self):
        finite = LicenseEntry("Pool", 4, used=2)
        first = LicenseEntry("Same label", 0, "DEMO-KEY", unlimited=True)
        second = LicenseEntry("Same label", 0, "DEMO-KEY", unlimited=True)
        item = LibraryItem("Design suite", licenses=[finite, first, second])
        admin = AdminWindow()
        admin.licenses_page.items.append(item)
        admin.show()
        admin.licenses_page.open_licenses(item)
        manager = admin.licenses_page.license_window
        spy = QSignalSpy(manager.changed)
        # Equal labels/keys must still delete the specific row that was chosen.
        manager.table.cellWidget(2, 5).findChild(TrashButton).click()
        manager.delete_entry_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(len(item.licenses), 2)
        self.assertIs(item.licenses[1], first)
        self.assertEqual(manager.table.rowCount(), 2)
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "∞")
        manager.table.cellWidget(1, 5).findChild(TrashButton).click()
        manager.delete_entry_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(manager.summary_label.text(), "4 available · 2 used · 6 total")
        self.assertEqual(admin.licenses_page.table.item(0, 2).text(), "4")
        self.assertEqual(admin.licenses_page.table.item(0, 3).text(), "2")
        manager.usage_controls[0][2].click()
        self.assertEqual((finite.available, finite.used), (3, 3))
        manager.table.cellWidget(0, 5).findChild(TrashButton).click()
        manager.delete_entry_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(item.licenses, [])
        self.assertEqual(admin.licenses_page.items, [item])
        self.assertEqual(manager.table.rowCount(), 0)
        self.assertTrue(manager.empty_label.isVisible())
        self.assertEqual(manager.summary_label.text(), "0 available · 0 used · 0 total")
        self.assertEqual(spy.count(), 4)
        manager.close()
        admin.close()
        admin.deleteLater()
