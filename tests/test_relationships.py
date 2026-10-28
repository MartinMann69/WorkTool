"""Catalog links persist safely and navigate only inside Administration."""

import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QFrame, QMessageBox, QToolButton, QWidget

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.admin.relationships import RelatedEntriesEditor
from tslibrary_ui.applications.models import Application
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.licenses.models import LibraryItem, LicenseEntry
from tslibrary_ui.main_window import MainWindow
from tslibrary_ui.phone_apps.models import PhoneApp
from tslibrary_ui.relationships import (
    EntryRef, catalog_entries, link_between, related_entries, replace_links,
)
from tslibrary_ui.state import LibrarySession
from tslibrary_ui.storage import catalog_data, decode_catalog
from tslibrary_ui.transfers import export_backup, import_backup
from tslibrary_ui.websites.models import Website


class RelationshipChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.session = LibrarySession(
            applications=[Application("Studio", sys.executable, id="same"),
                          Application("Other app", sys.executable, id="other")],
            websites=[Website("Studio website", "https://example.com", id="same")],
            items=[LibraryItem("Studio license", "Creative", [LicenseEntry("Seat", 3, "SECRET")], id="seat"),
                   LibraryItem("Other license", "Other", id="other")],
            phone_apps=[PhoneApp("Studio mobile", "phone")],
            documentation=DocumentationCatalog(items=[DocumentationItem("Studio guide", "guide")]),
        )
        self.source = EntryRef("application", "same")
        self.website = EntryRef("website", "same")
        self.license = EntryRef("license", "seat")
        self.guide = EntryRef("documentation", "guide")
        self.admin = None

    def tearDown(self):
        if self.admin is not None:
            for dialog in self.admin.findChildren(QWidget):
                if dialog.isWindow():
                    dialog.close()
            self.admin.close()
            self.admin.deleteLater()
        self.app.processEvents()

    def window(self):
        self.admin = AdminWindow(session=self.session)
        self.admin.show()
        self.app.processEvents()
        return self.admin

    def test_optional_bidirectional_links_survive_rename_and_roundtrip(self):
        replace_links(self.session, self.source, {self.website, self.license, self.guide})
        self.session.applications[0].name = "Renamed"
        payload = catalog_data(self.session)
        self.assertNotIn("SECRET", str(payload))
        loaded = decode_catalog(payload)
        self.assertEqual(set(related_entries(loaded, self.source)), {self.website, self.license, self.guide})
        self.assertEqual(set(related_entries(loaded, self.website)), {self.source, self.license, self.guide})
        replace_links(loaded, self.website, [])
        self.assertEqual(set(related_entries(loaded, self.source)), {self.license, self.guide})
        self.assertEqual(related_entries(loaded, EntryRef("phone_app", "phone")), [])

    def test_legacy_invalid_duplicate_and_deleted_references(self):
        payload = catalog_data(self.session)
        payload.pop("links")
        self.assertEqual(decode_catalog(payload).links, [])
        replace_links(self.session, self.source, {self.website})
        payload = catalog_data(self.session)
        link = payload["links"][0]
        payload["links"].append(dict(first=link["second"], second=link["first"]))
        self.assertEqual(len(decode_catalog(payload).links), 1)
        for invalid in (None, {}, [None], [dict(first=link["first"], second=link["first"])],
                        [dict(first=dict(kind="unknown", id="same"), second=link["second"])],
                        [dict(first=dict(kind="application", id=""), second=link["second"])]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                decode_catalog(dict(payload, links=invalid))
        payload["websites"] = []
        self.assertEqual(decode_catalog(payload).links, [])

    def test_backups_keep_links_without_key_values(self):
        replace_links(self.session, self.source, {self.website, self.guide})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.json"
            export_backup(path, self.session, catalog=True)
            self.assertNotIn("SECRET", path.read_text(encoding="utf-8"))
            loaded = import_backup(path, catalog=True)
            self.assertEqual(set(related_entries(loaded, self.source)), {self.website, self.guide})

    def open_editor(self, ref):
        admin = self.admin or self.window()
        entry = catalog_entries(self.session)[ref]
        page = admin.relationship_pages[ref.kind]
        if ref.kind == "application":
            page.add_application(entry)
            return page.application_dialog
        if ref.kind == "website":
            page.add_website(entry)
            return page.website_dialog
        if ref.kind == "phone_app":
            page.add_phone_app(entry)
            return page.phone_app_dialog
        if ref.kind == "license":
            page.open_licenses(entry)
            page.license_window.edit_item()
            return page.license_window.details_dialog
        page.add_item(entry)
        return page.item_dialog

    def choose_links(self, dialog, refs):
        field = dialog.related_editor
        field.choose_button.click()
        picker = field.picker
        for index in range(picker.entries_list.count()):
            row = picker.entries_list.item(index)
            if row.data(Qt.ItemDataRole.UserRole) in refs:
                row.setCheckState(Qt.CheckState.Checked)
        # A newly selected member includes its existing group. Uncheck excluded
        # members afterwards, as an admin would when deliberately splitting it.
        for index in range(picker.entries_list.count()):
            row = picker.entries_list.item(index)
            if row.data(Qt.ItemDataRole.UserRole) not in refs:
                row.setCheckState(Qt.CheckState.Unchecked)
        if picker.documentation_picker is not None:
            for ref in refs:
                if ref.kind == "documentation":
                    picker.set_ref_checked(ref, True)
            for ref in picker.selected_refs() - refs:
                picker.set_ref_checked(ref, False)
        return picker

    def assert_group(self, session, refs):
        refs = set(refs)
        for ref in refs:
            with self.subTest(member=ref):
                self.assertEqual(set(related_entries(session, ref)), refs - {ref})

    def legacy_anki_group(self):
        refs = {self.source, self.website, self.license, self.guide, EntryRef("phone_app", "phone")}
        self.session.links[:] = [link_between(self.source, target) for target in refs - {self.source}]
        return refs

    def test_existing_anki_star_links_become_a_group_in_every_admin_tab(self):
        refs = self.legacy_anki_group()
        self.window()
        self.assert_group(self.session, refs)
        for ref in refs:
            button = self.row_button(ref)
            self.assertEqual(button.text(), "4")
            self.assertEqual(set(button.target_refs), refs - {ref})
        dialog = self.open_editor(self.website)
        self.assertEqual(dialog.related_editor.selected_refs, refs - {self.website})

    def test_legacy_catalog_backup_roundtrip_preserves_whole_group(self):
        refs = self.legacy_anki_group()
        payload = catalog_data(self.session)
        payload["links"] = [dict(first=dict(kind=link.first.kind, id=link.first.id),
                                 second=dict(kind=link.second.kind, id=link.second.id))
                            for link in self.session.links]
        loaded = decode_catalog(payload)
        self.assertEqual(len(loaded.links), 10)
        self.assert_group(loaded, refs)
        self.assert_group(decode_catalog(catalog_data(loaded)), refs)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "group.json"
            export_backup(path, loaded, catalog=True)
            self.assert_group(import_backup(path, catalog=True), refs)

    def test_deleting_original_application_keeps_other_group_members_connected(self):
        refs = self.legacy_anki_group()
        admin = self.window()
        admin.applications_page._remove_application(self.source.id)
        self.assert_group(self.session, refs - {self.source})
        self.assertEqual(len(self.session.links), 6)
        for ref in refs - {self.source}:
            self.assertEqual(self.row_button(ref).text(), "3")

    def test_unchecking_member_splits_group_without_indirect_reconnection(self):
        refs = self.legacy_anki_group()
        self.window()
        dialog = self.open_editor(self.source)
        phone = EntryRef("phone_app", "phone")
        self.choose_links(dialog, refs - {self.source, phone}).save_button.click()
        self.assert_group(self.session, refs)  # Still a draft until item Save.
        dialog.save_button.click()
        self.assert_group(self.session, refs - {phone})
        self.assertEqual(related_entries(self.session, phone), [])
        self.assertIsNone(self.row_button(phone))
        dialog = self.open_editor(self.website)
        self.choose_links(dialog, set()).save_button.click()
        dialog.save_button.click()
        self.assertEqual(related_entries(self.session, self.website), [])
        self.assert_group(self.session, refs - {phone, self.website})

    def test_selecting_member_of_another_group_includes_its_hidden_members(self):
        phone = EntryRef("phone_app", "phone")
        replace_links(self.session, self.source, {self.website})
        replace_links(self.session, phone, {self.guide})
        unrelated = {EntryRef("application", "other"), EntryRef("license", "other")}
        replace_links(self.session, EntryRef("application", "other"), unrelated)
        self.window()
        dialog = self.open_editor(self.website)
        dialog.related_editor.choose_entries()
        picker = dialog.related_editor.picker
        picker.type_filter.setCurrentIndex(picker.type_filter.findData("phone_app"))
        for index in range(picker.entries_list.count()):
            row = picker.entries_list.item(index)
            if row.data(Qt.ItemDataRole.UserRole) == phone:
                row.setCheckState(Qt.CheckState.Checked)
        self.assertEqual(picker.selected_refs(), {self.source, phone, self.guide})
        picker.save_button.click()
        dialog.save_button.click()
        self.assert_group(self.session, {self.source, self.website, phone, self.guide})
        self.assert_group(self.session, unrelated)

    def test_moving_selected_members_preserves_the_groups_left_behind(self):
        phone = EntryRef("phone_app", "phone")
        replace_links(self.session, self.source, {self.website})
        replace_links(self.session, phone, {self.license, self.guide})
        replace_links(self.session, self.source, {self.website, phone})
        self.assert_group(self.session, {self.source, self.website, phone})
        self.assert_group(self.session, {self.license, self.guide})
        self.assert_group(decode_catalog(catalog_data(self.session)), {self.source, self.website, phone})

    def row_button(self, ref):
        page = self.admin.relationship_pages[ref.kind]
        for row in range(page.table.rowCount()):
            if page.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == ref.id:
                host = page.table.cellWidget(row, page.links_column)
                return host.findChild(QToolButton) if host else None
        return None

    def test_picker_stages_choices_until_item_save_and_cancel_discards_them(self):
        admin = self.window()
        saved = QSignalSpy(admin.catalog_changed)
        dialog = self.open_editor(self.website)
        picker = self.choose_links(dialog, {self.source, self.license})
        self.assertEqual(picker.entries_list.count(), len(catalog_entries(self.session)) - 2)
        self.assertEqual(picker.tabs.tabText(1), "Documentation")
        picker.search.setText("Studio guide")
        self.assertEqual(picker.selected_refs(), {self.source, self.license})
        picker.cancel_button.click()
        self.assertEqual(dialog.related_editor.selected_refs, set())
        picker = self.choose_links(dialog, {self.source, self.license})
        picker.save_button.click()
        self.assertEqual(dialog.related_editor.selected_refs, {self.source, self.license})
        self.assertEqual(self.session.links, [])
        self.assertEqual(saved.count(), 0)
        dialog.cancel_button.click()
        self.assertEqual(self.session.links, [])
        dialog = self.open_editor(self.website)
        self.assertEqual(dialog.related_editor.selected_refs, set())
        self.choose_links(dialog, {self.source}).save_button.click()
        dialog.save_button.click()
        self.assertEqual(related_entries(self.session, self.website), [self.source])
        self.assertEqual(saved.count(), 1)
        dialog = self.open_editor(self.website)
        self.choose_links(dialog, set()).save_button.click()
        dialog.save_button.click()
        self.assertEqual(self.session.links, [])
        self.assertIsNone(self.row_button(self.website))
        self.assertEqual(saved.count(), 2)

    def test_link_buttons_navigate_to_exact_record_and_back(self):
        replace_links(self.session, self.source, {self.website})
        admin = self.window()
        admin.websites_page.search.setText("hidden")
        self.assertTrue(admin.navigate_to_entry(self.source))
        button = self.row_button(self.source)
        self.assertEqual(button.source, self.source)
        self.assertFalse(button.icon().isNull())
        button.click()
        self.assertIs(admin.current_page, admin.websites_page)
        self.assertEqual(admin.websites_page.search.text(), "")
        self.row_button(self.website).click()
        self.assertIs(admin.current_page, admin.applications_page)
        self.assertIsNone(admin.findChild(QFrame, "relatedEntriesPanel"))

    def test_multiple_links_offer_typed_destinations_and_open_details(self):
        replace_links(self.session, self.source, {self.website, self.license, self.guide})
        admin = self.window()
        admin.navigate_to_entry(self.source)
        button = self.row_button(self.source)
        self.assertEqual(button.text(), "3")
        self.assertEqual(len(button.menu().actions()), 3)
        self.assertTrue(all(not item.icon().isNull() for item in button.menu().actions()))
        page = admin.licenses_page
        page.search.setText("Other")
        page.category_filter.setCurrentText("Other")
        license_action = button.menu().actions()[button.target_refs.index(self.license)]
        license_action.trigger()
        self.assertIs(page.license_window.item, self.session.items[0])
        page.license_window.close()
        admin.navigate_to_entry(self.source)
        button = self.row_button(self.source)
        with patch.object(admin.documentation_page, "open_item") as open_item:
            button.menu().actions()[button.target_refs.index(self.guide)].trigger()
            open_item.assert_called_once_with(self.session.documentation.items[0])

    def test_sort_rename_filter_and_delete_keep_buttons_on_their_record(self):
        replace_links(self.session, self.source, {self.website})
        admin = self.window()
        admin.navigate_to_entry(self.source)
        page = admin.applications_page
        page.sort_select.setCurrentIndex(1)
        self.assertEqual(self.row_button(self.source).source, self.source)
        self.assertIsNone(self.row_button(EntryRef("application", "other")))
        self.session.applications[0].name = "AAA renamed"
        page.refresh()
        page.changed.emit()
        self.assertIn("AAA renamed", self.row_button(self.website).toolTip())
        page.search.setText("Other app")
        self.assertIsNone(self.row_button(self.source))
        self.assertTrue(page.table.isColumnHidden(page.links_column))
        page.search.clear()
        admin.navigate_to_entry(self.source)
        page._remove_application(self.source.id)
        self.assertEqual(self.session.links, [])
        self.assertIsNone(self.row_button(self.website))
        self.assertFalse(admin.navigate_to_entry(self.source))

    def test_new_phone_entry_can_link_before_it_has_an_id(self):
        admin = self.window()
        page = admin.phone_apps_page
        page.add_phone_app()
        dialog = page.phone_app_dialog
        dialog.name_edit.setText("New mobile app")
        self.choose_links(dialog, {self.website, self.guide}).save_button.click()
        self.assertEqual(self.session.links, [])
        dialog.save_button.click()
        created = self.session.phone_apps[-1]
        ref = EntryRef("phone_app", created.id)
        self.assertEqual(set(related_entries(self.session, ref)), {self.website, self.guide})
        self.assertEqual(self.row_button(ref).source, ref)

    def test_link_editor_is_available_for_every_admin_type(self):
        with tempfile.TemporaryDirectory() as directory:
            self.session.documentation.parent_path = directory
            (Path(directory) / self.session.documentation.root_name / "Studio guide").mkdir(parents=True)
            admin = self.window()
            for ref in (self.source, self.website, self.license, self.guide, EntryRef("phone_app", "phone")):
                with self.subTest(kind=ref.kind):
                    dialog = self.open_editor(ref)
                    self.assertIsInstance(dialog.related_editor, RelatedEntriesEditor)
                    target = self.source if ref != self.source else self.website
                    self.choose_links(dialog, {target}).save_button.click()
                    dialog.save_button.click()
                    self.assertEqual(related_entries(self.session, ref), [target])
                    # Reset so each editor is tested independently.
                    replace_links(self.session, ref, set())
                    if ref.kind == "license":
                        admin.licenses_page.license_window.close()
                    if ref.kind == "documentation":
                        self.assertIsNone(admin.documentation_page.files_dialog)

    def test_documentation_failure_does_not_commit_draft_links(self):
        from tslibrary_ui.documentation.files import DocumentationError, DocumentationFiles
        admin = self.window()
        dialog = self.open_editor(self.guide)
        self.choose_links(dialog, {self.source}).save_button.click()
        with patch.object(DocumentationFiles, "rename_item", side_effect=DocumentationError("Unavailable folder")):
            dialog.save_button.click()
        self.assertEqual(self.session.links, [])
        self.assertTrue(dialog.isVisible())
        with patch.object(DocumentationFiles, "rename_item"), patch.object(admin.documentation_page, "open_item"):
            dialog.save_button.click()
        self.assertEqual(related_entries(self.session, self.guide), [self.source])

    def test_public_windows_and_personal_editors_have_no_link_controls(self):
        from tslibrary_ui.websites.dialogs import WebsiteDialog
        replace_links(self.session, self.source, {self.website})
        public = MainWindow(session=self.session)
        personal_editor = WebsiteDialog(public)
        self.assertEqual(public.findChildren(RelatedEntriesEditor), [])
        self.assertEqual(public.findChildren(QToolButton, "relatedLinksButton"), [])
        self.assertFalse(hasattr(personal_editor, "related_editor"))
        personal_editor.close()
        public.close()
        public.deleteLater()

    def test_compact_admin_and_item_editors_fit(self):
        admin = self.window()
        admin.resize(1000, 680)
        admin.set_page("Documentation")
        page = admin.documentation_page
        self.app.processEvents()
        self.assertEqual((admin.width(), admin.height()), (1000, 680))
        self.assertFalse(hasattr(page, "location_edit"))
        admin.set_page("Settings")
        settings = admin.settings_page
        self.app.processEvents()
        self.assertLess(settings.location_edit.geometry().bottom(), settings.root_name_edit.geometry().top())
        self.assertLess(settings.root_name_edit.geometry().bottom(), settings.settings_message.geometry().top())
        admin.set_page("Documentation")
        self.assertGreaterEqual(page.table.viewport().height(), page.table.rowHeight(0))
        for ref in (self.source, self.website, self.license, self.guide):
            dialog = self.open_editor(ref)
            self.app.processEvents()
            self.assertLessEqual(dialog.height(), 680)
            self.assertTrue(dialog.related_editor.choose_button.isVisible())
            dialog.reject()
            if ref.kind == "license":
                admin.licenses_page.license_window.close()

    def test_refresh_hides_replaced_row_buttons_immediately(self):
        admin = self.window()
        admin.navigate_to_entry(self.source)
        page = admin.applications_page
        previous = page.table.cellWidget(0, 2)
        page.refresh()
        self.assertTrue(previous.isHidden())

    def test_admin_restore_replaces_links_and_closes_the_old_editor(self):
        replace_links(self.session, self.source, {self.website, self.guide})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            export_backup(path, self.session, catalog=True)
            replace_links(self.session, self.source, {self.license})
            admin = self.window()
            dialog = self.open_editor(self.website)
            picker = self.choose_links(dialog, {self.license})
            with patch("tslibrary_ui.admin.transfers.QFileDialog.getOpenFileName", return_value=(str(path), "")), patch("tslibrary_ui.admin.transfers.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                admin.restore_catalog()
            self.assertFalse(dialog.isVisible())
            self.assertFalse(picker.isVisible())
            self.assertEqual(set(related_entries(self.session, self.source)), {self.website, self.guide})
            self.assertTrue(admin.navigate_to_entry(self.website))
            recovery = list(Path(directory).glob("*.before-restore-*.json"))
            self.assertEqual(len(recovery), 1)
            self.assertEqual(related_entries(import_backup(recovery[0], catalog=True), self.source), [self.license])


if __name__ == "__main__":
    unittest.main()
