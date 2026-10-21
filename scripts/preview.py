"""Render the real Qt screen at desktop and compact sizes."""

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication

from tslibrary_ui.app import create_app
from tslibrary_ui import AdminWindow, LoginWindow
from tslibrary_ui.licenses import (
    DeleteItemDialog, DeleteLicenseDialog, LibraryItem, LicenseEntry, LicenseEntryDialog,
    LicenseWindow,
)


def save_preview(app, window, destination):
    window.show()
    for _ in range(4):
        QCoreApplication.sendPostedEvents()
        app.processEvents()
    if not window.grab().save(str(destination)):
        raise RuntimeError(f"Could not save {destination}")
    print(destination)


def main():
    app = create_app()
    output = ROOT / "previews"
    output.mkdir(exist_ok=True)
    window = LoginWindow(animate=False)
    for name, width, height in [("desktop", 1180, 820), ("compact", 480, 820),
                                ("wide", 1543, 790), ("tall", 1000, 1100)]:
        window.resize(width, height)
        window.show()
        for _ in range(4):
            QCoreApplication.sendPostedEvents()
            app.processEvents()
        destination = output / f"{name}.png"
        if not window.grab().save(str(destination)):
            raise RuntimeError(f"Could not save {destination}")
        print(destination)
    window.close()
    admin = AdminWindow()
    for name, width, height in [("admin", 1320, 850), ("admin-small", 1000, 680)]:
        admin.resize(width, height)
        admin.show()
        for _ in range(4):
            QCoreApplication.sendPostedEvents()
            app.processEvents()
        destination = output / f"{name}.png"
        if not admin.grab().save(str(destination)):
            raise RuntimeError(f"Could not save {destination}")
        print(destination)
    for page in ("Applications", "Websites"):
        admin.set_page(page)
        save_preview(app, admin, output / f"admin-{page.lower()}.png")
    admin.set_page("Applications")
    admin.resize(1320, 850)
    admin.applications_page.add_application()
    application_editor = admin.applications_page.application_dialog
    notepad = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32" / "notepad.exe"
    application_editor.path_edit.setText(str(notepad if notepad.is_file() else Path(sys.executable)))
    application_editor._update_preview()
    save_preview(app, application_editor, output / "application-entry.png")
    application_editor.save_button.click()
    save_preview(app, admin, output / "admin-application-list.png")
    admin.resize(1000, 680)
    save_preview(app, admin, output / "admin-application-list-small.png")
    admin.set_page("Websites")
    admin.resize(1320, 850)
    admin.websites_page.add_website()
    website_editor = admin.websites_page.website_dialog
    website_editor.url_edit.setText("https://portal.example.com")
    website_editor._update_preview()
    website_editor.name_edit.setText("Team portal")
    save_preview(app, website_editor, output / "website-entry.png")
    website_editor.save_button.click()
    for url, name in [("https://docs.example.com/start", "Documentation"),
                      ("https://status.example.com", "Service status")]:
        admin.websites_page.add_website()
        admin.websites_page.website_dialog.url_edit.setText(url)
        admin.websites_page.website_dialog.name_edit.setText(name)
        admin.websites_page.website_dialog.save_button.click()
        app.processEvents()
    save_preview(app, admin, output / "admin-website-list.png")
    admin.resize(1000, 680)
    save_preview(app, admin, output / "admin-website-list-small.png")
    admin.set_page("Licenses")
    # Sample data is only used for screenshots; the runnable app starts empty.
    sample = LibraryItem("Design suite", "Creative tools", [
        LicenseEntry("Shared licenses", 12, used=3), LicenseEntry("Studio key", 1, "DEMO-KEY-0000", used=1)])
    admin.licenses_page.items.extend([sample, LibraryItem("Project toolkit", "Utilities", [
        LicenseEntry("Team pool", 6)])])
    admin.current_page.category_filter.addItems(["Creative tools", "Utilities"])
    admin.resize(1320, 850)
    admin.current_page.refresh()
    save_preview(app, admin, output / "admin-items.png")
    manager = LicenseWindow(sample, admin)
    save_preview(app, manager, output / "licenses.png")
    editor = LicenseEntryDialog(manager, sample.licenses[1])
    save_preview(app, editor, output / "license-entry.png")
    editor.close()
    sample.licenses.append(LicenseEntry("Company-wide key", 0, "DEMO-UNLIMITED", unlimited=True))
    manager.refresh()
    save_preview(app, manager, output / "licenses-unlimited.png")
    unlimited_editor = LicenseEntryDialog(manager, sample.licenses[-1])
    save_preview(app, unlimited_editor, output / "license-unlimited-entry.png")
    unlimited_editor.close()
    delete_dialog = DeleteItemDialog(sample, manager)
    save_preview(app, delete_dialog, output / "delete-item.png")
    delete_dialog.close()
    delete_key_dialog = DeleteLicenseDialog(sample.licenses[-1], manager)
    save_preview(app, delete_key_dialog, output / "delete-license.png")
    delete_key_dialog.close()
    manager.close()
    admin.close()


if __name__ == "__main__":
    main()
