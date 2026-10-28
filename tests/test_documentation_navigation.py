"""Nested documentation browsing, exact links, and text/button fit."""

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QPushButton
from PySide6.QtTest import QTest
from PySide6.QtCore import QThreadPool

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.licenses.models import LibraryItem
from tslibrary_ui.relationships import EntryRef
from tslibrary_ui.state import LibrarySession
from tslibrary_ui.documentation.navigation import FILE_ROLE


class DocumentationNavigationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.word = DocumentationItem("Microsoft/Word/docuWord")
        self.excel = DocumentationItem("Microsoft/Excel/docuExcel")
        self.session = LibrarySession(documentation=DocumentationCatalog(items=[self.word, self.excel,
                                      DocumentationItem("Adobe/Acrobat/Guide")]))
        self.admin = AdminWindow(session=self.session)
        self.admin.resize(1000, 680)
        self.admin.set_page("Documentation")
        self.admin.show()
        self.app.processEvents()

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone(5000)
        self.app.processEvents()
        self.admin.close()
        self.admin.deleteLater()
        self.app.processEvents()

    def test_folder_navigation_shows_document_names_and_scoped_recursive_search(self):
        page = self.admin.documentation_page
        self.assertEqual(page.table.rowCount(), 2)
        self.assertEqual({page.table.item(row, 0).text() for row in range(2)}, {"Adobe", "Microsoft"})
        page.folder_tree.select_path("Microsoft/Word")
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 0).text(), "docuWord")
        self.assertEqual(page.folder_caption.accessibleName(), "Documentation / Microsoft / Word")
        page.folder_tree.select_path("Microsoft")
        page.search.setText("docu")
        self.assertEqual(page.table.rowCount(), 2)
        page.folder_tree.select_path("")
        page.search.setText("Adobe/Acrobat")
        self.assertIn("Guide", {page.table.item(row, 0).text() for row in range(page.table.rowCount())})

    def test_new_documentation_inherits_selected_folder(self):
        page = self.admin.documentation_page
        page.folder_tree.select_path("Microsoft/Word")
        page.add_item()
        self.assertEqual(page.item_dialog.folder_edit.currentText(), "Microsoft/Word")
        page.item_dialog.name_edit.setText("Keyboard shortcuts")
        page.item_dialog._save()
        self.assertEqual(page.item_dialog.name, "Microsoft/Word/Keyboard shortcuts")
        # The unconfigured preview cannot create a folder; its editor stays open.
        self.assertTrue(page.item_dialog.error.text())
        page.item_dialog.reject()

    def test_related_entry_navigation_reveals_exact_document_in_another_folder(self):
        page = self.admin.documentation_page
        page.folder_tree.select_path("Adobe/Acrobat")
        page.search.setText("nothing")
        with patch.object(page, "open_item") as open_item:
            self.assertTrue(self.admin.navigate_to_entry(EntryRef("documentation", self.word.id)))
            open_item.assert_called_once_with(self.word)
        self.assertEqual(page.selected_folder, "Microsoft/Word")
        self.assertEqual(page.search.text(), "")
        self.assertEqual(page.table.item(page.table.currentRow(), 0).text(), "docuWord")

    def test_refresh_preserves_folder_expansion_and_case_insensitive_groups(self):
        page = self.admin.documentation_page
        page.folder_tree.select_path("Microsoft/Word")
        self.session.documentation.items.append(DocumentationItem("microsoft/Word/Another guide"))
        page.refresh()
        self.assertEqual(page.table.rowCount(), 2)
        roots = [path for path in page.folder_tree.items_by_path if path.casefold() == "microsoft"]
        self.assertEqual(len(roots), 1)
        self.assertTrue(page.folder_tree.items_by_path[roots[0]].isExpanded())

    def test_manage_licenses_and_document_actions_fit_at_compact_size(self):
        self.admin.session.items.append(LibraryItem("Word"))
        self.admin.set_page("Licenses")
        self.app.processEvents()
        button = next(button for button in self.admin.licenses_page.table.findChildren(QPushButton) if button.text() == "Manage licenses")
        self.assertGreaterEqual(button.width(), button.fontMetrics().horizontalAdvance(button.text()) + 16)
        self.admin.set_page("Documentation")
        self.app.processEvents()
        page = self.admin.documentation_page
        page.folder_tree.select_path("Microsoft/Word")
        self.app.processEvents()
        files = next(button for button in page.table.findChildren(QPushButton) if button.text() == "Open folder")
        self.assertGreaterEqual(files.width(), files.fontMetrics().horizontalAdvance(files.text()) + 16)
        self.assertEqual(page.table.horizontalScrollBar().maximum(), 0)

    def test_screenshot_parent_record_appears_once_as_a_folder(self):
        parent = DocumentationItem("test")
        child = DocumentationItem("test/lol/eafawf")
        self.session.documentation.items[:] = [parent, child]
        page = self.admin.documentation_page
        page.refresh()
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 0).text(), "test")
        page._open_row(0, 0)
        self.assertEqual(page.selected_folder, "test")
        self.assertEqual(page.table.item(0, 0).text(), "lol")
        self.assertFalse(hasattr(page, "folder_files_button"))
        self.assertIsNone(page.files_dialog)
        page._open_row(0, 0)
        self.assertEqual(page.table.item(0, 0).text(), "eafawf")
        page.up_button.click()
        self.assertEqual(page.selected_folder, "test")
        page.navigate_folder("")
        page.search.setText("eafawf")
        self.assertEqual(page.table.rowCount(), 1)
        self.assertIn("Search results", page.folder_caption.accessibleName())

    def test_folder_with_catalog_id_retains_relationships_and_breadcrumb_is_escaped(self):
        parent = DocumentationItem("Research & Notes")
        self.session.documentation.items[:] = [parent, DocumentationItem("Research & Notes/Guide")]
        from tslibrary_ui.relationships import replace_links
        from tslibrary_ui.websites.models import Website
        website = Website("Portal", "https://example.com")
        self.session.websites.append(website)
        replace_links(self.session, EntryRef("documentation", parent.id), {EntryRef("website", website.id)})
        page = self.admin.documentation_page
        page.refresh()
        self.assertIsNotNone(page.table.cellWidget(0, page.links_column))
        self.assertTrue(self.admin.navigate_to_entry(EntryRef("documentation", parent.id)))
        self.assertEqual(page.selected_folder, parent.name)
        self.assertIn("Research &amp; Notes", page.folder_caption.text())
        self.assertNotIn("Research & Notes", page.folder_caption.text())

    def test_parent_attachments_do_not_repeat_files_owned_by_sub_documents(self):
        from tslibrary_ui.documentation.dialogs import DocumentationFilesDialog
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ):
            os.environ.pop("TSLIBRARY_DOCUMENTS_PATH", None)
            parent = DocumentationItem("Straße")
            child = DocumentationItem("Straße/Child")
            catalog = DocumentationCatalog(directory, "Guides", [parent, child])
            folder = Path(directory) / "Guides/Straße"
            (folder / "Child").mkdir(parents=True)
            (folder / "own.txt").write_text("parent attachment")
            (folder / "Child/child.txt").write_text("child attachment")
            dialog = DocumentationFilesDialog(catalog, parent)
            self.assertEqual([dialog.file_list.item(i).text() for i in range(dialog.file_list.count())], ["own.txt"])
            dialog.reject()
            dialog.deleteLater()
            dialog = DocumentationFilesDialog(catalog, child)
            self.assertEqual(dialog.file_list.item(0).text(), "child.txt")
            dialog.reject()
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
