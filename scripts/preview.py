"""Render the real Qt screen at desktop and compact sizes."""

import os
from pathlib import Path
from datetime import date, timedelta
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication

from tslibrary_ui.app import create_app
from tslibrary_ui import AdminWindow, LibraryWindow, LoginWindow, MainWindow
from tslibrary_ui.applications.models import Application
from tslibrary_ui.phone_apps.models import PhoneApp
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.websites.models import Website
from tslibrary_ui.licenses import (
    DeleteItemDialog, DeleteLicenseDialog, LibraryItem, LicenseEntry, LicenseEntryDialog,
    LicenseWindow,
)
from tslibrary_ui.workplace.models import entry_key, workplace_entries


def save_preview(app, window, destination):
    window.show()
    for _ in range(4):
        QCoreApplication.sendPostedEvents()
        app.processEvents()
    if not window.grab().save(str(destination)):
        raise RuntimeError(f"Could not save {destination}")
    print(destination)


def save_library_previews(app, output):
    # These examples belong only to screenshots; the runnable app starts empty.
    session = LibrarySession(
        applications=[Application("Adobe Acrobat", r"C:\Tools\Acrobat\Acrobat.exe"),
                      Application("Visual Studio Code", r"C:\Tools\VSCode\Code.exe")],
        websites=[Website("Team knowledge base", "https://docs.example.com"),
                  Website("Team portal", "https://portal.example.com")],
        phone_apps=[PhoneApp("Microsoft Authenticator"), PhoneApp("Microsoft Teams")],
        items=[LibraryItem("Creative Cloud", "Design & creative", [LicenseEntry("Team pool", 8, used=2)]),
               LibraryItem("Microsoft 365", "Productivity", [LicenseEntry("Company plan", 20, used=12)])],
    )
    library = LibraryWindow(session=session)
    save_preview(app, library, output / "library.png")
    library.resize(820, 650)
    save_preview(app, library, output / "library-small.png")
    library.resize(1320, 850)
    library.type_filter.setCurrentIndex(library.type_filter.findData("websites"))
    save_preview(app, library, output / "library-websites.png")
    library.close()
    empty = LibraryWindow()
    save_preview(app, empty, output / "library-empty.png")
    empty.close()
    admin = AdminWindow(session=session)
    admin.set_page("Full library")
    save_preview(app, admin, output / "admin-full-library.png")
    admin.resize(1000, 680)
    save_preview(app, admin, output / "admin-full-library-small.png")
    admin.close()


def save_workplace_previews(app, output):
    # Sample data is kept in memory, never written to the runnable catalog/config.
    session = LibrarySession(
        applications=[Application("Adobe Acrobat", r"C:\Tools\Acrobat.exe"),
                      Application("Visual Studio Code", r"C:\Tools\Code.exe"),
                      Application("Figma", r"C:\Tools\Figma.exe")],
        websites=[Website("Team portal", "https://portal.example.com"),
                  Website("Knowledge base", "https://docs.example.com"),
                  Website("Project board", "https://projects.example.com")])
    config = WorkplaceConfig(application_ids=[session.applications[1].id],
                             website_ids=[session.websites[0].id, session.websites[1].id],
                             personal_websites=[Website("My notes", "https://notes.example.com")])
    window = MainWindow(session=session, config=config)
    for index, name in [(0, "workplace-websites"), (1, "workplace-applications"),
                        (2, "workplace-collection")]:
        window.tabs.setCurrentIndex(index)
        page = window.tabs.currentWidget()
        page.grid.setCurrentIndex(page.model.index(0, 0))
        save_preview(app, window, output / f"{name}.png")
    window.tabs.setCurrentIndex(0)
    entry = workplace_entries(session, window.config, "websites")[0]
    window.toggle_favorite(entry)
    window.assign_group(entry, "Office")
    window.set_view_mode("list")
    save_preview(app, window, output / "workplace-list.png")
    window.show_quick_launcher()
    save_preview(app, window.quick_launcher, output / "quick-launcher.png")
    window.quick_launcher.close()
    window.config.launch_sets = {"Morning": [entry_key(entry)]}
    window.show_launch_sets()
    window.launch_sets_dialog.names.setCurrentRow(0)
    save_preview(app, window.launch_sets_dialog, output / "workspace-sets.png")
    window.launch_sets_dialog.close()
    window.set_view_mode("cards")
    window.tabs.setCurrentIndex(2)
    window.resize(820, 650)
    save_preview(app, window, output / "workplace-small.png")
    window.close()


def main():
    app = create_app()
    output = ROOT / "previews"
    output.mkdir(exist_ok=True)
    main_window = MainWindow()
    save_preview(app, main_window, output / "main.png")
    main_window.close()
    save_workplace_previews(app, output)
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
    for page in ("Applications", "Phone apps", "Websites"):
        admin.set_page(page)
        save_preview(app, admin, output / f"admin-{page.lower().replace(' ', '-')}.png")
    admin.set_page("Phone apps")
    admin.resize(1320, 850)
    admin.phone_apps_page.add_phone_app()
    phone_editor = admin.phone_apps_page.phone_app_dialog
    phone_editor.name_edit.setText("Microsoft Teams")
    save_preview(app, phone_editor, output / "phone-app-entry.png")
    phone_editor.save_button.click()
    for name in ("Microsoft Authenticator", "Adobe Scan"):
        admin.phone_apps_page.add_phone_app()
        admin.phone_apps_page.phone_app_dialog.name_edit.setText(name)
        admin.phone_apps_page.phone_app_dialog.save_button.click()
        app.processEvents()
    save_preview(app, admin, output / "admin-phone-app-list.png")
    admin.resize(1000, 680)
    save_preview(app, admin, output / "admin-phone-app-list-small.png")
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
    sample.owner = "Design team"
    sample.renewal_date = (date.today() + timedelta(days=21)).isoformat()
    admin.licenses_page.items.extend([sample, LibraryItem("Project toolkit", "Utilities", [
        LicenseEntry("Team pool", 6)])])
    admin.current_page.category_filter.addItems(["Creative tools", "Utilities"])
    admin.resize(1320, 850)
    admin.current_page.refresh()
    save_preview(app, admin, output / "admin-items.png")
    manager = LicenseWindow(sample, admin)
    save_preview(app, manager, output / "licenses.png")
    manager.edit_item()
    save_preview(app, manager.details_dialog, output / "license-details.png")
    manager.details_dialog.close()
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
    save_library_previews(app, output)


if __name__ == "__main__":
    main()
