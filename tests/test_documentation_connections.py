"""Real files/folders can be connected from either side without saving drafts."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool, Qt
from PySide6.QtTest import QTest

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.applications.models import Application
from tslibrary_ui.documentation.files import DocumentationFiles
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.documentation.navigation import FILE_ROLE, FOLDER_ROLE
from tslibrary_ui.licenses.models import LibraryItem
from tslibrary_ui.migrations import DataSchema, catalog_v1_to_v2
from tslibrary_ui.relationships import EntryRef, related_entries, replace_links
from tslibrary_ui.state import LibrarySession
from tslibrary_ui.storage import JsonRepository, StorageError, catalog_data, decode_catalog
from tslibrary_ui.team_config import SharedJsonCatalogStore


class DocumentationConnectionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.environment = patch.dict(os.environ)
        self.environment.start()
        os.environ.pop("TSLIBRARY_DOCUMENTS_PATH", None)
        self.temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary.name)
        self.root = self.parent / "Guides"
        (self.root / "Microsoft/Word").mkdir(parents=True)
        (self.root / "Microsoft/Word/Guide.pdf").write_bytes(b"guide")
        (self.root / "Microsoft/Excel").mkdir()
        self.session = LibrarySession(applications=[Application("Office", sys.executable, id="office")],
                                      items=[LibraryItem("Office license", "Software", id="license")],
                                      documentation=DocumentationCatalog(str(self.parent), "Guides"))
        self.admin = AdminWindow(session=self.session)
        self.admin.show()
        self.page = self.admin.documentation_page
        self.app_ref = EntryRef("application", "office")
        self.license_ref = EntryRef("license", "license")

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone(5000)
        self.app.processEvents()
        self.admin.close()
        self.admin.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.temporary.cleanup()
        self.environment.stop()

    def wait(self, predicate):
        deadline = time.monotonic() + 8
        while predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(predicate())

    def picker(self):
        self.admin.applications_page.add_application(self.session.applications[0])
        owner = self.admin.applications_page.application_dialog
        owner.related_editor.choose_entries()
        picker = owner.related_editor.picker
        picker.tabs.setCurrentIndex(1)
        docs = picker.documentation_picker
        self.wait(lambda: bool(docs.jobs))
        return owner, picker, docs

    def expand_word(self, docs):
        docs.nodes["microsoft"].setExpanded(True)
        self.wait(lambda: bool(docs.jobs))
        docs.nodes["microsoft/word"].setExpanded(True)
        self.wait(lambda: bool(docs.jobs))

    def test_app_picker_separates_documentation_and_stages_file_and_folder_until_save(self):
        owner, picker, docs = self.picker()
        self.assertEqual(picker.tabs.tabText(1), "Documentation")
        self.assertFalse(picker.type_filter.isVisible())
        self.assertTrue(all(picker.entries_list.item(index).data(Qt.ItemDataRole.UserRole).kind != "documentation"
                            for index in range(picker.entries_list.count())))
        self.expand_word(docs)
        docs.nodes["microsoft/word/guide.pdf"].setCheckState(0, Qt.CheckState.Checked)
        docs.nodes["microsoft/excel"].setCheckState(0, Qt.CheckState.Checked)
        picker.save_button.click()
        self.assertFalse(self.session.documentation.items)
        self.assertFalse(self.session.links)
        # Reopening keeps staged checks without publishing metadata.
        owner.related_editor.choose_entries()
        picker = owner.related_editor.picker
        self.assertEqual(len(picker.selected_refs()), 2)
        picker.reject()
        owner.save_button.click()
        by_name = {entry.name: entry for entry in self.session.documentation.items}
        self.assertEqual(by_name["Microsoft/Word/Guide.pdf"].kind, "file")
        self.assertEqual(by_name["Microsoft/Excel"].kind, "folder")
        self.assertEqual(set(related_entries(self.session, self.app_ref)), {EntryRef("documentation", entry.id) for entry in by_name.values()})
        self.assertTrue((self.root / "Microsoft/Word/Guide.pdf").is_file())
        self.assertEqual(decode_catalog(catalog_data(self.session)).documentation, self.session.documentation)

    def test_cancel_owner_or_picker_does_not_create_documentation_records(self):
        owner, picker, docs = self.picker()
        self.expand_word(docs)
        docs.nodes["microsoft/word/guide.pdf"].setCheckState(0, Qt.CheckState.Checked)
        picker.reject()
        self.assertFalse(owner.related_editor.selected_refs)
        self.assertFalse(self.session.documentation.items)
        owner.related_editor.choose_entries()
        picker = owner.related_editor.picker
        docs = picker.documentation_picker
        self.wait(lambda: bool(docs.jobs))
        self.expand_word(docs)
        docs.nodes["microsoft/word"].setCheckState(0, Qt.CheckState.Checked)
        picker.accept()
        owner.reject()
        self.assertFalse(self.session.documentation.items)
        self.assertFalse(self.session.links)

    def test_documentation_file_connections_can_add_apps_and_licenses_directly(self):
        self.admin.set_page("Documentation")
        self.page.navigate_folder("Microsoft/Word")
        self.wait(lambda: self.page.directory_loading)
        self.page.connect_path("Microsoft/Word/Guide.pdf")
        owner = self.page.item_dialog
        owner.related_editor.choose_entries()
        picker = owner.related_editor.picker
        self.assertIsNone(picker.tabs)  # Documentation's own editor keeps the regular entry list.
        picker.set_ref_checked(self.app_ref, True)
        picker.set_ref_checked(self.license_ref, True)
        picker.accept()
        self.assertFalse(self.session.documentation.items)
        owner.save_button.click()
        item = self.session.documentation.items[0]
        ref = EntryRef("documentation", item.id)
        self.assertEqual(item.kind, "file")
        self.assertEqual(set(related_entries(self.session, ref)), {self.app_ref, self.license_ref})
        with patch("tslibrary_ui.documentation.page.QDesktopServices.openUrl", return_value=True) as launch:
            self.assertTrue(self.admin.navigate_to_entry(ref))
        launch.assert_not_called()
        self.assertEqual(self.page.selected_folder, "Microsoft/Word")
        self.assertNotIn("Microsoft/Word/Guide.pdf", self.page.folder_tree.items_by_path)
        row = next(index for index in range(self.page.table.rowCount()) if self.page.table.item(index, 0).data(Qt.ItemDataRole.UserRole) == item.id)
        self.assertEqual(self.page.table.currentRow(), row)
        self.assertTrue(self.page.table.selectedItems())
        self.assertEqual(self.page.table.item(row, 0).data(FILE_ROLE), item.name)
        self.assertIsNone(self.page.table.item(row, 0).data(FOLDER_ROLE))

    def test_unregistered_folder_has_connection_action_and_preserves_id_on_move(self):
        self.page.connect_path("Microsoft/Word")
        owner = self.page.item_dialog
        owner.related_editor.choose_entries()
        picker = owner.related_editor.picker
        picker.set_ref_checked(self.app_ref, True)
        picker.accept()
        owner.save_button.click()
        item = self.session.documentation.items[0]
        ref = EntryRef("documentation", item.id)
        self.assertEqual(item.kind, "folder")
        self.assertTrue(self.page.move_path(item.name, "Microsoft/Excel"))
        self.assertEqual(item.name, "Microsoft/Excel/Word")
        self.assertEqual(related_entries(self.session, ref), [self.app_ref])

        self.page.add_item()
        new_folder = self.page.item_dialog
        new_folder.related_editor.choose_entries()
        self.assertIsNone(new_folder.related_editor.picker.tabs)
        new_folder.related_editor.picker.reject()
        new_folder.reject()

    def test_only_explicit_checks_remain_selected_across_tabs_and_search(self):
        item = DocumentationItem("Microsoft/Word/Guide.pdf", "guide", "file")
        self.session.documentation.items.append(item)
        doc_ref = EntryRef("documentation", item.id)
        replace_links(self.session, self.license_ref, {doc_ref})
        owner, picker, docs = self.picker()
        picker.tabs.setCurrentIndex(0)
        picker.set_ref_checked(self.license_ref, True)
        self.assertEqual(picker.selected_refs(), {self.license_ref})
        picker.set_ref_checked(doc_ref, True)
        self.assertEqual(picker.selected_refs(), {self.license_ref, doc_ref})
        picker.tabs.setCurrentIndex(1)
        picker.search.setText("does not exist")
        self.assertEqual(picker.selected_refs(), {self.license_ref, doc_ref})
        picker.search.clear()
        self.assertEqual(docs.nodes[item.name.casefold()].checkState(0), Qt.CheckState.Checked)
        docs.nodes[item.name.casefold()].setCheckState(0, Qt.CheckState.Unchecked)
        self.assertEqual(picker.selected_refs(), {self.license_ref})
        picker.accept()
        owner.save_button.click()
        self.assertEqual(related_entries(self.session, self.app_ref), [self.license_ref])
        self.assertEqual(related_entries(self.session, doc_ref), [self.license_ref])

    def test_file_move_delete_updates_connections_without_treating_file_as_folder(self):
        item = DocumentationItem("Microsoft/Word/Guide.pdf", "guide", "file")
        self.session.documentation.items.append(item)
        ref = EntryRef("documentation", item.id)
        replace_links(self.session, self.app_ref, {ref})
        self.assertTrue(self.page.move_path(item.name, "Microsoft/Excel"))
        self.assertEqual(item.name, "Microsoft/Excel/Guide.pdf")
        self.assertEqual(related_entries(self.session, ref), [self.app_ref])
        self.page.confirm_delete_path(item.name)
        self.page.remove_dialog.accept()
        self.wait(lambda: self.page.busy)
        self.assertFalse(related_entries(self.session, self.app_ref))
        self.assertFalse(self.session.documentation.items)

    def test_offline_picker_keeps_registered_documentation_and_reports_error(self):
        item = DocumentationItem("Microsoft/Word/Guide.pdf", "guide", "file")
        self.session.documentation.items.append(item)
        self.session.documentation.parent_path = str(self.parent / "offline")
        owner, picker, docs = self.picker()
        self.assertIn("unavailable", docs.status.text())
        docs.nodes[item.name.casefold()].setCheckState(0, Qt.CheckState.Checked)
        picker.accept()
        owner.save_button.click()
        self.assertEqual(related_entries(self.session, self.app_ref), [EntryRef("documentation", item.id)])

    def test_v2_upgrade_keeps_exact_backup_and_existing_folder_ids_and_links(self):
        data = catalog_data(self.session)
        data["version"] = 2
        data["documentation"]["items"] = [dict(id="old-folder", name="Microsoft/Word")]
        data["links"] = [dict(first=dict(kind="application", id="office"),
                              second=dict(kind="documentation", id="old-folder"))]
        for shared in (False, True):
            path = self.parent / ("shared.json" if shared else "local.json")
            raw = ("\ufeff" + json.dumps(data, ensure_ascii=False)).encode("utf-8")
            path.write_bytes(raw)
            store = SharedJsonCatalogStore(path) if shared else JsonRepository(path, self.parent / "personal.json")
            session = store.load_catalog()
            self.assertEqual(session.documentation.items[0], DocumentationItem("Microsoft/Word", "old-folder", "folder"))
            self.assertEqual(related_entries(session, self.app_ref), [EntryRef("documentation", "old-folder")])
            self.assertEqual(json.loads(path.read_text())["version"], 4)
            backups = list(self.parent.glob(path.name + ".before-migration-*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), raw)
            store.load_catalog()
            self.assertEqual(len(list(self.parent.glob(path.name + ".before-migration-*.bak"))), 1)
            with self.assertRaisesRegex(ValueError, "newer data version"):
                DataSchema("old catalog", 2, {1: catalog_v1_to_v2}).upgrade(json.loads(path.read_text()))

    def test_invalid_file_types_and_file_ancestors_are_rejected(self):
        data = catalog_data(self.session)
        for records in [[dict(id="bad", name="x", kind="unknown")],
                        [dict(id="file", name="x", kind="file"), dict(id="child", name="x/y", kind="folder")]]:
            data["documentation"]["items"] = records
            with self.assertRaises(ValueError):
                decode_catalog(data)

    def test_failed_documentation_connection_save_restores_records_and_groups(self):
        self.page.connect_path("Microsoft/Word/Guide.pdf")
        owner = self.page.item_dialog
        owner.related_editor.choose_entries()
        picker = owner.related_editor.picker
        picker.set_ref_checked(self.app_ref, True)
        picker.accept()
        def fail():
            raise StorageError("Read-only catalog")
        self.page.persist_change = fail
        owner.save_button.click()
        self.assertTrue(owner.isVisible())
        self.assertIn("Read-only", owner.error.text())
        self.assertFalse(self.session.documentation.items)
        self.assertFalse(self.session.links)
        self.assertTrue((self.root / "Microsoft/Word/Guide.pdf").exists())


if __name__ == "__main__":
    unittest.main()
