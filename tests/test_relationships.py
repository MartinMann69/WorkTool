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
        self.assertEqual(set(related_entries(loaded, self.website)), {self.source})
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

    def star_links(self):
        refs = {self.source, self.website, self.license, self.guide, EntryRef("phone_app", "phone")}
        self.session.links[:] = [link_between(self.source, target) for target in refs - {self.source}]
        return refs

    def test_existing_star_links_stay_direct_in_every_admin_tab(self):
        refs = self.star_links()
        self.window()
        for ref in refs:
            button = self.row_button(ref)
            expected = refs - {self.source} if ref == self.source else {self.source}
            self.assertEqual(button.text(), str(len(expected)))
            self.assertEqual(set(button.target_refs), expected)
        dialog = self.open_editor(self.website)
        self.assertEqual(dialog.related_editor.selected_refs, {self.source})

    def test_legacy_catalog_backup_roundtrip_preserves_only_saved_edges(self):
        refs = self.star_links()
        payload = catalog_data(self.session)
        payload["links"] = [dict(first=dict(kind=link.first.kind, id=link.first.id),
                                 second=dict(kind=link.second.kind, id=link.second.id))
                            for link in self.session.links]
        loaded = decode_catalog(payload)
        self.assertEqual(len(loaded.links), 4)
        self.assertEqual(loaded.links, sorted(self.session.links))
        self.assertEqual(decode_catalog(catalog_data(loaded)).links, loaded.links)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "group.json"
            export_backup(path, loaded, catalog=True)
            self.assertEqual(import_backup(path, catalog=True).links, loaded.links)

    def test_deleting_application_removes_its_edges_and_keeps_independent_edges(self):
        refs = self.star_links()
        self.session.links.append(link_between(self.website, self.guide))
        admin = self.window()
        admin.applications_page._remove_application(self.source.id)
        self.assertEqual(self.session.links, [link_between(self.website, self.guide)])
        for ref in refs - {self.source}:
            if ref in (self.website, self.guide):
                self.assertEqual(self.row_button(ref).text(), "1")
            else:
                self.assertIsNone(self.row_button(ref))

    def test_unchecking_removes_only_this_items_connection(self):
        refs = self.star_links()
        self.window()
        dialog = self.open_editor(self.source)
        phone = EntryRef("phone_app", "phone")
        self.choose_links(dialog, refs - {self.source, phone}).save_button.click()
        self.assertEqual(set(related_entries(self.session, self.source)), refs - {self.source})
        dialog.save_button.click()
        self.assertEqual(set(related_entries(self.session, self.source)), refs - {self.source, phone})
        self.assertEqual(related_entries(self.session, phone), [])
        self.assertIsNone(self.row_button(phone))
        dialog = self.open_editor(self.website)
        self.choose_links(dialog, set()).save_button.click()
        dialog.save_button.click()
        self.assertEqual(related_entries(self.session, self.website), [])
        self.assertEqual(set(related_entries(self.session, self.source)), {self.license, self.guide})

    def test_selecting_an_entry_does_not_select_its_hidden_connections(self):
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
        self.assertEqual(picker.selected_refs(), {self.source, phone})
        picker.save_button.click()
        dialog.save_button.click()
        self.assertEqual(set(related_entries(self.session, self.website)), {self.source, phone})
        self.assertEqual(set(related_entries(self.session, phone)), {self.website, self.guide})
        self.assertEqual(set(related_entries(self.session, self.guide)), {phone})
        self.assertEqual(set(related_entries(self.session, EntryRef("application", "other"))), {EntryRef("license", "other")})

    def test_editing_one_item_does_not_steal_another_items_connections(self):
        phone = EntryRef("phone_app", "phone")
        replace_links(self.session, self.source, {self.website})
        replace_links(self.session, phone, {self.license, self.guide})
        replace_links(self.session, self.source, {self.website, phone})
        for session in (self.session, decode_catalog(catalog_data(self.session))):
            self.assertEqual(set(related_entries(session, self.source)), {self.website, phone})
            self.assertEqual(set(related_entries(session, phone)), {self.source, self.license, self.guide})
            self.assertEqual(set(related_entries(session, self.license)), {phone})
            self.assertEqual(set(related_entries(session, self.guide)), {phone})

    def test_contacts_and_outlook_can_share_phone_documentation_without_app_link(self):
        self.session.phone_apps.extend([PhoneApp("Outlook", "outlook"), PhoneApp("Contacts", "contacts")])
        self.session.documentation.items[0].name = "Phones"
        outlook, contacts = EntryRef("phone_app", "outlook"), EntryRef("phone_app", "contacts")
        replace_links(self.session, outlook, {self.guide})
        self.window()
        dialog = self.open_editor(contacts)
        dialog.related_editor.choose_entries()
        picker = dialog.related_editor.picker
        picker.tabs.setCurrentIndex(1)
        picker.documentation_picker.nodes["phones"].setCheckState(0, Qt.CheckState.Checked)
        self.assertEqual(picker.selected_refs(), {self.guide})
        picker.save_button.click()
        dialog.save_button.click()
        for session in (self.session, decode_catalog(catalog_data(self.session))):
            self.assertEqual(related_entries(session, contacts), [self.guide])
            self.assertEqual(related_entries(session, outlook), [self.guide])
            self.assertEqual(set(related_entries(session, self.guide)), {contacts, outlook})
        self.assertEqual(self.row_button(contacts).text(), "1")
        self.assertEqual(self.row_button(outlook).text(), "1")

    def test_removing_old_inferred_app_link_does_not_regenerate_it(self):
        phone = EntryRef("phone_app", "phone")
        self.session.links[:] = [link_between(self.source, self.guide), link_between(phone, self.guide),
                                 link_between(self.source, phone)]
        admin = self.window()
        dialog = self.open_editor(phone)
        self.choose_links(dialog, {self.guide}).save_button.click()
        dialog.save_button.click()
        admin._catalog_edited()
        for session in (self.session, decode_catalog(catalog_data(self.session))):
            self.assertEqual(related_entries(session, phone), [self.guide])
            self.assertEqual(related_entries(session, self.source), [self.guide])
            self.assertEqual(set(related_entries(session, self.guide)), {self.source, phone})

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

    def test_multiple_links_navigate_and_select_without_opening_details(self):
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
        with patch.object(page, "open_licenses") as open_licenses:
            license_action.trigger()
            open_licenses.assert_not_called()
        self.assertIs(admin.current_page, page)
        self.assertEqual(page.table.item(page.table.currentRow(), 0).data(Qt.ItemDataRole.UserRole), self.license.id)
        self.assertTrue(page.table.selectedItems())
        admin.navigate_to_entry(self.source)
        button = self.row_button(self.source)
        with patch.object(admin.documentation_page, "open_item") as open_item:
            button.menu().actions()[button.target_refs.index(self.guide)].trigger()
            open_item.assert_not_called()
        page = admin.documentation_page
        self.assertIs(admin.current_page, page)
        self.assertEqual(page.table.item(page.table.currentRow(), 0).data(Qt.ItemDataRole.UserRole), self.guide.id)

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
