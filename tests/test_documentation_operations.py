"""Destructive documentation operations preserve data, IDs and shared metadata."""

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
from PySide6.QtTest import QTest

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.documentation.files import DocumentationError, DocumentationFiles
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.documentation.page import DocumentationPage
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.relationships import CatalogLink, EntryRef
from tslibrary_ui.state import LibrarySession
from tslibrary_ui.storage import JsonRepository, StorageError


class DocumentationOperationChecks(unittest.TestCase):
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
        (self.root / "Source/Child").mkdir(parents=True)
        (self.root / "Target").mkdir()
        (self.root / "Source/note.txt").write_text("keep me")
        (self.root / "Source/Child/guide.pdf").write_bytes(b"nested")
        self.source = DocumentationItem("Source")
        self.child = DocumentationItem("Source/Child")
        self.target = DocumentationItem("Target")
        self.session = LibrarySession(documentation=DocumentationCatalog(str(self.parent), "Guides", [self.source, self.child, self.target]))
        self.session.links.append(CatalogLink(EntryRef("documentation", self.child.id), EntryRef("documentation", self.target.id)))
        self.admin = AdminWindow(session=self.session)
        self.page = self.admin.documentation_page
        self.windows = [self.admin]
        self.files = DocumentationFiles(self.session.documentation)

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone(5000)
        self.app.processEvents()
        for window in self.windows:
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.temporary.cleanup()
        self.environment.stop()

    def wait(self):
        for _ in range(800):
            if not self.page.busy and not self.page.directory_loading:
                return
            QTest.qWait(10)
        self.fail("File operation did not finish")

    def test_move_file_and_folder_keeps_descendant_ids_connections_and_selection(self):
        self.assertTrue(self.page.move_path("Source/note.txt", "Target"))
        self.assertEqual((self.root / "Target/note.txt").read_text(), "keep me")
        self.page.navigate_folder("Source/Child")
        links = list(self.session.links)
        identifier = self.child.id
        self.assertTrue(self.page.move_path("Source", "Target"))
        self.assertEqual(self.source.name, "Target/Source")
        self.assertEqual(self.child.name, "Target/Source/Child")
        self.assertEqual(self.child.id, identifier)
        self.assertEqual(self.session.links, links)
        self.assertEqual(self.page.selected_folder, "Target/Source/Child")
        self.assertEqual((self.root / "Target/Source/Child/guide.pdf").read_bytes(), b"nested")
        self.assertNotIn("Source", self.page.folder_tree.items_by_path)

    def test_invalid_moves_never_replace_or_merge_files_or_folders(self):
        (self.root / "Target/note.txt").write_text("existing")
        for source, target in [("Source", "Source/Child"), ("Source", "Source"),
                               ("Source", ""), ("Source/note.txt", "Target"),
                               ("Source/note.txt", "../outside"), ("", "Target")]:
            with self.subTest(source=source, target=target):
                self.assertFalse(self.page.move_path(source, target))
        self.assertEqual((self.root / "Source/note.txt").read_text(), "keep me")
        self.assertEqual((self.root / "Target/note.txt").read_text(), "existing")
        self.assertEqual(self.source.name, "Source")

    def test_delete_requires_confirmation_then_removes_contents_records_and_links(self):
        self.page.confirm_delete_path("Source")
        self.page.remove_dialog.reject()
        self.assertTrue((self.root / "Source/note.txt").exists())
        self.assertEqual(len(self.session.documentation.items), 3)
        self.page.confirm_delete_path("Source")
        self.assertIn("all files and subfolders", self.page.remove_dialog.description.text())
        self.page.remove_dialog.accept()
        self.wait()
        self.assertFalse((self.root / "Source").exists())
        self.assertEqual(self.session.documentation.items, [self.target])
        self.assertFalse(self.session.links)
        self.assertFalse(list(self.root.glob(".tslibrary-*")))

    def test_delete_file_does_not_remove_its_parent_or_siblings(self):
        self.page.confirm_delete_path("Source/note.txt")
        self.page.remove_dialog.accept()
        self.wait()
        self.assertFalse((self.root / "Source/note.txt").exists())
        self.assertTrue((self.root / "Source/Child/guide.pdf").exists())
        self.assertEqual(len(self.session.documentation.items), 3)

    def test_failed_catalog_save_rolls_back_moves_and_staged_deletions(self):
        def fail():
            raise StorageError("Share is read only")
        self.page.persist_change = fail
        links = list(self.session.links)
        for destination in ("Target", None):
            self.assertFalse(self.page._change_path("Source", destination=destination))
            self.assertTrue((self.root / "Source/Child/guide.pdf").exists())
            self.assertFalse((self.root / "Target/Source").exists())
            self.assertEqual(self.source.name, "Source")
            self.assertEqual(self.child.name, "Source/Child")
            self.assertEqual(self.session.links, links)
            self.assertEqual(len(self.session.documentation.items), 3)
            self.assertIn("Share is read only", self.page.file_message.text())
            self.assertFalse(list(self.root.glob(".tslibrary-*")))

    def test_stale_catalog_guard_prevents_touching_shared_files(self):
        @contextmanager
        def stale():
            raise StorageError("Another admin changed the catalog")
            yield
        self.page.write_guard = stale
        self.assertFalse(self.page.move_path("Source", "Target"))
        self.assertFalse(self.page._change_path("Source"))
        self.assertTrue((self.root / "Source/Child/guide.pdf").exists())

    def test_committed_delete_cleanup_failure_reports_recovery_location(self):
        with patch("tslibrary_ui.documentation.browser_files.DocumentationFiles.finish_delete", side_effect=OSError("locked file")):
            self.assertTrue(self.page._change_path("Source"))
            self.wait()
        staged = list(self.root.glob(".tslibrary-*.deleted"))
        self.assertEqual(len(staged), 1)
        self.assertEqual((staged[0] / "note.txt").read_text(), "keep me")
        self.assertIn(str(staged[0]), self.page.file_message.text())
        self.assertIn("locked file", self.page.file_message.text())

    def test_read_only_page_cannot_move_or_delete(self):
        page = DocumentationPage(self.session, editable=False)
        self.windows.append(page)
        self.assertFalse(page.move_path("Source", "Target"))
        page.confirm_delete_path("Source")
        self.assertFalse(hasattr(page, "remove_dialog"))
        self.assertTrue((self.root / "Source/note.txt").exists())

    def test_controller_saves_moves_and_deletes_to_catalog(self):
        repository = JsonRepository(self.parent / "catalog.json", self.parent / "personal.json")
        repository.save_catalog(self.session)
        controller = PreviewController(repository=repository)
        self.windows.extend([controller.admin, controller.main_window, controller.library, controller.welcome])
        self.page = controller.admin.documentation_page
        self.assertTrue(self.page.move_path("Source", "Target"))
        loaded = repository.load_catalog()
        self.assertEqual(next(entry.name for entry in loaded.documentation.items if entry.id == self.child.id), "Target/Source/Child")
        self.assertTrue(self.page._change_path("Target/Source"))
        self.wait()
        loaded = repository.load_catalog()
        self.assertEqual(loaded.documentation.items, [self.target])
        self.assertFalse(loaded.links)


if __name__ == "__main__":
    unittest.main()
