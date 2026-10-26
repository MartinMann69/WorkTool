"""Render documentation UI using disposable sample files, never real user data."""

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.documentation.files import DocumentationFiles
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.state import LibrarySession


def save(app, window, path):
    window.show()
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
        for name in ("IT/Getting started", "Engineering/Workflows", "Team handbook"):
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
        page.open_item(session.documentation.items[0])
        save(app, page.files_dialog, output / "documentation-files.png")
        page.files_dialog.reject()
        admin.close()


if __name__ == "__main__":
    app = create_app()
    output = ROOT / "previews"
    output.mkdir(exist_ok=True)
    save_documentation_previews(app, output)
