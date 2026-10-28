"""Render documentation UI using disposable sample files, never real user data."""

import os
from pathlib import Path
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication, QThreadPool
from PySide6.QtTest import QTest

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.documentation.files import DocumentationFiles
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.state import LibrarySession


def save(app, window, path):
    window.show()
    page = getattr(window, "documentation_page", None)
    deadline = time.monotonic() + 8
    while page is not None and page.directory_loading and time.monotonic() < deadline:
        QTest.qWait(10)
    for _ in range(4):
        QCoreApplication.sendPostedEvents()
        app.processEvents()
    if not window.grab().save(str(path)):
        raise RuntimeError(f"Could not render {path}")
    print(path)


def save_documentation_previews(app, output):
    temporary_root = ROOT / ".test-temp"
    temporary_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
        root = Path(directory)
        session = LibrarySession(documentation=DocumentationCatalog(str(root), "TSLibrary Guides"))
        files = DocumentationFiles(session.documentation)
        for name in ("IT/Getting started", "Engineering/Workflows", "Team handbook",
                     "Microsoft/Word/docuWord", "Microsoft/Excel/docuExcel"):
            files.create_item(name)
            session.documentation.items.append(DocumentationItem(name))
        for name in ("01 - First steps.md", "02 - Account setup.txt", "Troubleshooting.txt"):
            source = root / name
            source.write_text("Sample documentation for UI previews only.", encoding="utf-8")
            files.add_files("IT/Getting started", [source])
        admin = AdminWindow(session=session)
        admin.set_page("Documentation")
        admin.documentation_page.storage_status.setText("SHARED CATALOG · SAVED")
        save(app, admin, output / "documentation-admin.png")
        admin.resize(1000, 680)
        save(app, admin, output / "documentation-admin-small.png")
        page = admin.documentation_page
        page.folder_tree.select_path("Microsoft/Word")
        save(app, admin, output / "documentation-folders.png")
        page.folder_tree.select_path("")
        page.open_item(session.documentation.items[0])
        save(app, admin, output / "documentation-files.png")
        admin.set_page("Settings")
        settings = admin.settings_page
        # Display-only example paths. No real network share is accessed.
        settings.connection_label.setText(r"\\office-server\Team\TSLibrary\Team.json")
        settings.catalog_label.setText(r"\\office-server\Team\TSLibrary\Team.catalog.json")
        settings.location_edit.setText(r"\\office-server\Team\Documentation")
        settings.set_status("Connected. Shared changes are checked every 5 seconds while no editor is open.")
        for button in (settings.create_button, settings.open_button, settings.refresh_button):
            button.setEnabled(True)
        admin.resize(1320, 850)
        save(app, admin, output / "admin-settings.png")
        admin.resize(1000, 680)
        save(app, admin, output / "admin-settings-small.png")
        admin.close()


def save_nested_browser_previews(app, output):
    """Reproduce the parent-record/child-record layout from the UI report."""
    from tslibrary_ui.applications.models import Application
    from tslibrary_ui.phone_apps.models import PhoneApp
    from tslibrary_ui.licenses.models import LibraryItem
    from tslibrary_ui.websites.models import Website
    from tslibrary_ui.relationships import EntryRef, replace_links
    with tempfile.TemporaryDirectory(dir=ROOT / ".test-temp") as directory:
        parent = DocumentationItem("test")
        session = LibrarySession(
            documentation=DocumentationCatalog(directory, "Team Guides", [parent, DocumentationItem("test/lol/eafawf")]),
            applications=[Application("Example app", "C:/Tools/Example.exe")],
            phone_apps=[PhoneApp("Example phone app")],
            items=[LibraryItem("Example license")],
            websites=[Website("Example website", "https://example.com")])
        replace_links(session, EntryRef("documentation", parent.id), {
            EntryRef("application", session.applications[0].id), EntryRef("website", session.websites[0].id),
            EntryRef("phone_app", session.phone_apps[0].id), EntryRef("license", session.items[0].id)})
        files = DocumentationFiles(session.documentation)
        files.item_path("test", create=True)
        files.item_path("test/lol/eafawf", create=True)
        for filename in ("Getting started.pdf", "Team notes.txt"):
            source = Path(directory) / filename
            source.write_text("Disposable preview attachment", encoding="utf-8")
            files.add_files("test", [source])
        source = Path(directory) / "Word guide.docx"
        source.write_text("Disposable preview attachment", encoding="utf-8")
        files.add_files("test/lol/eafawf", [source])
        admin = AdminWindow(session=session)
        admin.set_page("Documentation")
        admin.resize(1000, 680)
        save(app, admin, output / "documentation-browser-root.png")
        admin.documentation_page.navigate_folder("test")
        save(app, admin, output / "documentation-browser-folder.png")
        admin.documentation_page.navigate_folder("test/lol")
        save(app, admin, output / "documentation-browser-child.png")
        admin.close()
        QThreadPool.globalInstance().waitForDone(5000)



if __name__ == "__main__":
    app = create_app()
    output = ROOT / "previews"
    output.mkdir(exist_ok=True)
    save_documentation_previews(app, output)
    save_nested_browser_previews(app, output)
