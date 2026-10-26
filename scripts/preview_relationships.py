"""Render admin relationships with disposable in-memory sample entries."""

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslibrary_ui.app import create_app
from tslibrary_ui.admin.window import AdminWindow
from tslibrary_ui.applications.models import Application
from tslibrary_ui.documentation.models import DocumentationCatalog, DocumentationItem
from tslibrary_ui.licenses.models import LibraryItem, LicenseEntry
from tslibrary_ui.phone_apps.models import PhoneApp
from tslibrary_ui.relationships import EntryRef, replace_links
from tslibrary_ui.state import LibrarySession
from tslibrary_ui.websites.models import Website


def save(app, widget, path):
    widget.show()
    for _ in range(3):
        app.processEvents()
    if not widget.grab().save(str(path)):
        raise RuntimeError(f"Could not render {path}")
    print(path)


if __name__ == "__main__":
    app = create_app()
    output = ROOT / "previews"
    output.mkdir(exist_ok=True)
    session = LibrarySession(
        applications=[Application("Affinity Designer", "C:/Tools/Affinity/Designer.exe", id="designer"),
                      Application("Visual Studio Code", "C:/Tools/VSCode/Code.exe")],
        websites=[Website("Affinity account", "https://affinity.serif.com", id="affinity")],
        items=[LibraryItem("Affinity suite", "Design", [LicenseEntry("Team seats", 8, used=2)], id="seats")],
        phone_apps=[PhoneApp("Affinity for iPad", "ipad")],
        documentation=DocumentationCatalog(items=[DocumentationItem("Design/Getting started", "guide")]),
    )
    source = EntryRef("application", "designer")
    replace_links(session, source, {EntryRef("website", "affinity"), EntryRef("license", "seats"),
                                   EntryRef("documentation", "guide"), EntryRef("phone_app", "ipad")})
    admin = AdminWindow(session=session)
    admin.navigate_to_entry(source)
    save(app, admin, output / "relationships-admin.png")
    admin.resize(1000, 680)
    save(app, admin, output / "relationships-admin-small.png")
    admin.applications_page.add_application(session.applications[0])
    editor = admin.applications_page.application_dialog
    save(app, editor, output / "relationships-editor.png")
    editor.related_editor.choose_entries()
    save(app, editor.related_editor.picker, output / "relationships-picker.png")
    editor.related_editor.picker.reject()
    editor.reject()
    admin.set_page("Documentation")
    admin.documentation_page.table.setCurrentCell(0, 0)
    save(app, admin, output / "relationships-documentation-small.png")
    admin.close()
