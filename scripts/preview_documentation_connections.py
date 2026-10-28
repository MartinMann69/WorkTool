"""Render documentation links against disposable example folders and files."""

import os
from pathlib import Path
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtTest import QTest

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.applications.models import Application
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.licenses.models import LibraryItem
from tslibrary_ui.relationships import EntryRef
from tslibrary_ui.state import LibrarySession


def wait_for(predicate):
    deadline = time.monotonic() + 8
    while predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    if predicate():
        raise RuntimeError("Preview file read did not finish")


def save(app, widget, filename):
    widget.show()
    app.processEvents()
    path = ROOT / "previews" / filename
    if not widget.grab().save(str(path)):
        raise RuntimeError(f"Could not render {path}")
    print(path)


if __name__ == "__main__":
    app = create_app()
    with tempfile.TemporaryDirectory(dir=ROOT / ".test-temp") as directory:
        root = Path(directory) / "Team Guides"
        (root / "Microsoft/Word").mkdir(parents=True)
        (root / "Microsoft/Excel").mkdir()
        (root / "Microsoft/Word/Getting started.pdf").write_bytes(b"Disposable preview file")
        (root / "Microsoft/Word/Keyboard shortcuts.pdf").write_bytes(b"Disposable preview file")
        session = LibrarySession(applications=[Application("Microsoft Word", sys.executable, id="word")],
                                 items=[LibraryItem("Microsoft 365", "Office", id="office")],
                                 documentation=DocumentationCatalog(directory, "Team Guides"))
        admin = AdminWindow(session=session)
        admin.resize(1000, 680)
        admin.show()
        admin.applications_page.add_application(session.applications[0])
        owner = admin.applications_page.application_dialog
        owner.related_editor.choose_entries()
        picker = owner.related_editor.picker
        picker.tabs.setCurrentIndex(1)
        docs = picker.documentation_picker
        wait_for(lambda: bool(docs.jobs))
        docs.nodes["microsoft"].setExpanded(True)
        wait_for(lambda: bool(docs.jobs))
        docs.nodes["microsoft/word"].setExpanded(True)
        wait_for(lambda: bool(docs.jobs))
        docs.nodes["microsoft/word/getting started.pdf"].setCheckState(0, Qt.CheckState.Checked)
        docs.nodes["microsoft/excel"].setCheckState(0, Qt.CheckState.Checked)
        save(app, picker, "relationships-documentation-picker.png")
        picker.accept()
        owner.save_button.click()
        admin.set_page("Documentation")
        page = admin.documentation_page
        page.navigate_folder("Microsoft/Word")
        wait_for(lambda: page.directory_loading)
        page.connect_path("Microsoft/Word/Getting started.pdf")
        owner = page.item_dialog
        owner.related_editor.choose_entries()
        picker = owner.related_editor.picker
        picker.set_ref_checked(EntryRef("license", "office"), True)
        save(app, picker, "documentation-file-connections.png")
        picker.accept()
        owner.save_button.click()
        wait_for(lambda: page.directory_loading)
        save(app, admin, "documentation-file-linked.png")
        QThreadPool.globalInstance().waitForDone(5000)
        admin.close()
