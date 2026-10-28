"""Files appear inline with folders; imports and async reads preserve context."""

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
from PySide6.QtTest import QTest

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.documentation.files import DocumentationError
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.documentation.navigation import FILE_ROLE
from tslibrary_ui.state import LibrarySession


class InlineFileChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.environment = patch.dict(os.environ)
        self.environment.start()
        os.environ.pop("TSLIBRARY_DOCUMENTS_PATH", None)
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.folder = self.root / "Guides/test"
        (self.folder / "lol/eafawf").mkdir(parents=True)
        (self.folder / "own.txt").write_text("parent attachment")
        (self.folder / "lol/eafawf/guide.pdf").write_bytes(b"child attachment")
        session = LibrarySession(documentation=DocumentationCatalog(str(self.root), "Guides", [
            DocumentationItem("test"), DocumentationItem("test/lol/eafawf")]))
        self.admin = AdminWindow(session=session)
        self.page = self.admin.documentation_page
        self.admin.set_page("Documentation")
        self.admin.resize(1000, 680)
        self.admin.show()
        self.wait_for_files()

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone(5000)
        self.app.processEvents()
        self.admin.close()
        self.admin.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.directory.cleanup()
        self.environment.stop()

    def wait_for_files(self):
        deadline = time.monotonic() + 8
        while (self.page.directory_loading or self.page.busy) and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.page.directory_loading)
        self.assertFalse(self.page.busy)

    def files(self):
        return {self.page.table.item(row, 0).data(FILE_ROLE): row for row in range(self.page.table.rowCount())
                if self.page.table.item(row, 0).data(FILE_ROLE) is not None}

    def test_parent_files_and_subfolders_share_one_view_and_open_directly(self):
        self.page.navigate_folder("test")
        self.wait_for_files()
        self.assertEqual({self.page.table.item(row, 0).text() for row in range(self.page.table.rowCount())}, {"lol", "own.txt"})
        self.assertFalse(hasattr(self.page, "folder_files_button"))
        self.assertIsNone(self.page.files_dialog)
        with patch("tslibrary_ui.documentation.page.QDesktopServices.openUrl", return_value=True) as launch:
            self.page._open_row(self.files()["test/own.txt"], 0)
        self.assertEqual(Path(launch.call_args.args[0].toLocalFile()).read_text(), "parent attachment")
        with patch("tslibrary_ui.documentation.page.QDesktopServices.openUrl", return_value=True) as launch:
            self.page.explorer_button.click()
        self.assertEqual(Path(launch.call_args.args[0].toLocalFile()), self.folder)
        self.page.navigate_folder("test/lol/eafawf")
        self.wait_for_files()
        self.assertEqual(set(self.files()), {"test/lol/eafawf/guide.pdf"})

    def test_add_files_copies_inline_and_duplicate_is_reported_without_overwriting(self):
        self.page.navigate_folder("test")
        self.wait_for_files()
        source = self.root / "new.txt"
        source.write_text("new file")
        self.page.import_files([source])
        self.assertTrue(self.page.busy)
        self.assertFalse(self.admin.sidebar.isEnabled())
        self.admin.close()
        self.assertTrue(self.admin.isVisible())
        self.wait_for_files()
        self.assertIn("test/new.txt", self.files())
        self.assertEqual((self.folder / "new.txt").read_text(), "new file")
        source.write_text("must not replace")
        self.page.import_files([source])
        self.wait_for_files()
        self.assertIn("already exists", self.page.file_message.text())
        self.assertEqual((self.folder / "new.txt").read_text(), "new file")
        self.assertTrue(self.admin.sidebar.isEnabled())

    def test_search_finds_real_files_recursively_and_root_import_is_supported(self):
        self.page.search.setText("guide.pdf")
        self.wait_for_files()
        self.assertEqual(set(self.files()), {"test/lol/eafawf/guide.pdf"})
        self.page.navigate_folder("")
        self.wait_for_files()
        source = self.root / "root.txt"
        source.write_text("root attachment")
        self.page.import_files([source])
        self.wait_for_files()
        self.assertIn("root.txt", self.files())

    def test_failed_refresh_keeps_visible_files_and_navigation_discards_old_results(self):
        self.page.navigate_folder("test")
        self.wait_for_files()
        with patch("tslibrary_ui.documentation.browser_files.DocumentationFiles.list_directory", side_effect=DocumentationError("Share unavailable")):
            self.page.reload_files(force=True)
            self.wait_for_files()
        self.assertIn("test/own.txt", self.files())
        self.assertIn("Share unavailable", self.page.file_message.text())
        self.page.reload_files(force=True)
        old = self.page._current_read
        self.page.navigate_folder("test/lol/eafawf")
        self.page._directory_read(old, [dict(path="test/stale.txt", folder=False, size=0, modified=0)], "")
        self.wait_for_files()
        self.assertNotIn("test/stale.txt", self.files())
        self.assertIn("test/lol/eafawf/guide.pdf", self.files())


if __name__ == "__main__":
    unittest.main()
