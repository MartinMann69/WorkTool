# Project structure

The code is organized by feature. Start in the folder named after the part of the app you want to change. `shared/` contains UI used by multiple features.

## Folder map

```text
main.py                         Small executable entry point
requirements.txt                Runtime dependency
tslibrary_ui/
    __init__.py                 Public AdminWindow, LibraryWindow, LoginWindow, MainWindow imports
    app.py                      QApplication, fonts, palette, startup arguments
    single_instance.py          Exclusive Windows instance and local window activation
    navigation.py               Welcome/main/admin/library transitions and shared session
    window_state.py             Shared main-window placement and local dialog size/state preferences
    main_window.py              User tabs, selection/personal-entry actions, and repository calls
    transfers.py                Validated catalog/workplace backups and CSV exports
    state.py                    Catalog session and per-user WorkplaceConfig dataclasses
    relationships.py            Typed, bidirectional catalog links and JSON validation
    storage.py                  Separate catalog/local workplace adapters and JSON codecs
    team_config.py              Portable team connections, shared locks, and stale-write protection
    catalog_refresh.py          Background reads of shared catalog bytes
    migrations.py               Saved-data versions and sequential format conversions
    version.py                  App release version used by Qt and the Windows build
    workplace/
        page.py                 Shared layout for Websites, Applications, and Collection
        cards.py                Inline workplace Open/Edit controls and mouse/keyboard actions
        collection.py           Inline card toggle, check-state model, and mouse/keyboard input
        selection.py            Live sidebar of selected Collection entries
        models.py               User selections, local paths, and personal/catalog projections
        tools.py                Card menus, favorites/groups, repair, and data actions
        dialogs.py              Quick launcher and workspace-set editor
        launching.py            Explicit browser and Windows executable/shortcut launching
    library/
        window.py               Standalone library window
        page.py                 Shared admin/public overview, totals, search and sorting
        models.py               Public inventory projections and filtering/sorting
        cards.py                Responsive Qt item-view cards
    admin/
        window.py               Admin shell: creates pages and switches tabs
        relationships.py        Draft links in item editors, picker, and row navigation buttons
        sidebar.py              Navigation, branding, and back button
        settings.py             Team configuration selection and documentation defaults
    welcome/
        window.py               Welcome layout, copy, signals, and animation
        widgets.py              InputField, password toggle, primary button
    licenses/
        models.py               LibraryItem, LicenseEntry, totals, usage rules
        page.py                 Item table, search, category filter, item actions
        item_dialog.py          Item details and item deletion confirmation
        entry_dialog.py         License entry editor and deletion confirmation
        window.py               Per-item license manager and license table
    applications/
        models.py               Application data and launch-target display
        page.py                 Table, search, add/edit/remove actions
        dialogs.py              Application editor and removal confirmation
        targets.py              File-path validation and argument parsing
        portable.py             Portable reference validation and user-folder rebasing
        resolver.py             Current-PC shortcuts, installed-app registration, and path lookup
        icons.py                Windows executable/shortcut icon lookup
    phone_apps/
        models.py               Name-only phone app inventory entries
        page.py                 Table, search, add/edit/remove actions
        dialogs.py              Name editor and removal confirmation
    documentation/
        models.py               Shared root settings, named items, and path validation
        files.py                Folder lifecycle, guarded moves/deletion, exclusive copies, browsing
        page.py                 Documentation folder navigation, inventory, and file browsing
        navigation.py           Folder/file projections, navigator, and name rendering
        browser_files.py        Background directory reads and committed deletion cleanup
        picker.py               Lazy file/folder tree and staged documentation link targets
        dialogs.py              Item names, file listing, and background file import
    websites/
        models.py               Website data
        page.py                 Table, search, add/edit/remove actions
        dialogs.py              Website editor and removal confirmation
        urls.py                 URL validation and suggested names
        icons.py                Locally drawn globe icon
    shared/
        catalog_page.py         Common admin header, toolbar, empty state, table
        controls.py             Trash button, filter combo, spinbox, checkbox
        forms.py                Label and button factories
        explorer.py             Shared Explorer row button and file/folder reveal action
        tables.py               Table configuration and cell helpers
        confirmation.py         Common confirmation-dialog layout
    graphics/
        brand.py                Bookshelf logo and TSLibrary wordmark
        shoji.py                Large welcome illustration and resize painting
        shelf.py                Sidebar and empty-state illustration
        icons.py                General welcome/admin icons
        typography.py           Painter font helpers
    styles/
        __init__.py             Package-relative QSS loader
        base.qss                Welcome and common theme rules
        admin.qss               Admin pages, tables, and dialogs
        library.qss             Read-only library, summary tiles, and filters
        main.qss                Workplace tabs, cards, search, and action styling
tests/                          Feature-based automated checks
scripts/preview.py              Screenshots with sample data
previews/                       Generated screenshots, not application source
docs/FEATURES.md                Detailed behavior and preview limitations
```

`__init__.py` files expose convenient imports or mark packages. Implementation belongs in the named modules.

`.venv/` contains installed dependencies, `__pycache__/` contains generated Python caches, and `.idea/` contains IDE settings. These are not places to change application behavior.

## Where to make common changes

| If you want to… | Edit |
| --- | --- |
| Change welcome copy or rearrange its fields | `welcome/window.py` |
| Change user workplace tabs or actions | `main_window.py`, `workplace/page.py` |
| Change local persistence or connect a catalog server | `storage.py` adapters and `create_catalog_store()`; see `docs/STORAGE.md` |
| Change password visibility or field focus behavior | `welcome/widgets.py` |
| Change what happens between welcome and admin | `navigation.py` |
| Change startup, fonts, or the application palette | `app.py` |
| Change the combined library layout, search, filtering or sorting | `library/page.py`, `library/models.py` |
| Change library card drawing or responsive columns | `library/cards.py` |
| Rename, reorder, or add admin tabs | `admin/window.py`; sidebar buttons follow its page mapping |
| Change sidebar spacing or its back button | `admin/sidebar.py` |
| Change the common admin search/header/empty-state layout | `shared/catalog_page.py` |
| Change one tab's labels, filtering, sorting, columns, or row actions | That feature's `page.py` |
| Change item-name/category fields | `licenses/item_dialog.py` |
| Change license-label/key/count/unlimited fields | `licenses/entry_dialog.py` |
| Change license rows or key visibility | `licenses/window.py` |
| Change total calculations or available/used transfer rules | `licenses/models.py` |
| Change executable/shortcut paths or argument handling | `applications/targets.py` |
| Change the application picker or icon preview | `applications/dialogs.py`, `applications/icons.py` |
| Change accepted URLs or suggested website names | `websites/urls.py` |
| Change phone app names or inventory actions | `phone_apps/dialogs.py`, `phone_apps/page.py` |
| Change dialog-wide confirmation behavior | `shared/confirmation.py` |
| Change colors, borders, or hover styles | `styles/base.qss` or `styles/admin.qss` |
| Change illustrations, branding, or general icons | The matching file in `graphics/` |
| Change application/website data fields | That feature's `models.py` |
| Find session items, applications, phone apps, or websites | `state.py` |

## Responsibilities and data flow

`main.py` starts `app.py`, which creates Qt, the repository, and the `PreviewController` in `navigation.py`. That controller owns the welcome, user workplace, admin, and library windows, and supplies a single shared `LibrarySession`. **Open TSLibrary** opens Websites/Applications/Collection. Admin app/website changes signal the controller to save the catalog; workplace changes save through the same repository to the user's separate config. The admin preview opens without checking credentials; normal access requires no sign-in.

`AdminWindow` composes a sidebar, a read-only Full library overview, and four feature pages. Each inventory page owns its dialogs, rows, filtering, and refresh behavior. `CatalogPage` supplies their shared editing layout; changing one feature's behavior belongs in its own `page.py`. The Full library tab embeds `LibraryPage`, shared with the standalone `LibraryWindow`.

`LibrarySession` holds four in-memory lists. Pages receive those same lists, so edits update the session without copying it. Dataclasses describe entries. Parsing and validation stay in `applications/targets.py` and `websites/urls.py`; license calculations and usage transfers stay in `licenses/models.py`.

`LibraryWindow` builds read-only display entries from all four lists whenever shown or refreshed. These projections include names, types, public details, and icons; license keys are excluded. Sorting and filtering affect only the display model and never reorder or edit session data. The Qt item view draws responsive cards without creating a widget for each entry.

`storage.py` composes `ApplicationRepository` from a catalog adapter and a local workplace adapter. `JsonCatalogStore` is a placeholder for a future server; replace `create_catalog_store()` without changing `LocalWorkplaceStore` or user data. All file paths, JSON serialization, atomic writes, and reconstruction of persisted records stay there. There is no authentication service yet. Keep future storage/authentication operations out of painting and layout construction. See [STORAGE.md](STORAGE.md).

## Access a feature from code

```python
from tslibrary_ui import AdminWindow
from tslibrary_ui.licenses.models import LibraryItem
from tslibrary_ui.state import LibrarySession

session = LibrarySession(items=[LibraryItem("Design suite", "Creative tools")])
admin = AdminWindow(session=session)
admin.set_page("Licenses")

admin.session.items
admin.licenses_page.open_licenses(session.items[0])
admin.applications_page.add_application()
admin.websites_page.add_website()
```

Create a QApplication first. After changing a list directly, call the matching page's `refresh()`; item-category changes also need `licenses_page.refresh_categories()`. Normal dialog actions do this automatically. A supplied session can be reused across windows, but is still lost when the process exits.

## Add another admin feature

1. Create a feature folder with `models.py`, `page.py`, and any needed dialogs/validation modules.
2. Subclass `shared.catalog_page.CatalogPage` for the common catalog layout. Define its copy/headers, connect `add_requested`, configure its table, and implement `refresh()`.
3. Add its list to `LibrarySession`, create the page in `admin/window.py`, and register it in `self.pages`. Add its navigation icon to `graphics/icons.py`.
4. Put feature behavior in that page/dialog/model rather than adding edit logic to `AdminWindow`.
5. Add checks in `tests/test_<feature>.py`, run the suite, and add screenshots in `scripts/preview.py` if useful.

## Updated locations

The public `from tslibrary_ui import AdminWindow, LoginWindow` imports are unchanged. Old flat implementation files have been removed to avoid duplicate sources.

| Previous location | Current location |
| --- | --- |
| `main.create_app` | `tslibrary_ui.app.create_app` |
| `tslibrary_ui.login.LoginWindow` | `tslibrary_ui.welcome.LoginWindow` |
| `tslibrary_ui.preview.PreviewController` | `tslibrary_ui.navigation.PreviewController` |
| `tslibrary_ui.controls` | `tslibrary_ui.shared.controls` |
| `tslibrary_ui.artwork` | `tslibrary_ui.graphics` modules |
| `admin.items`, `admin.applications`, `admin.websites` | `admin.session.items`, `.applications`, `.websites` |
| Admin-wide list/dialog methods | `admin.licenses_page`, `.applications_page`, `.websites_page` |
| `admin.nav_buttons`, `admin.back_button` | `admin.sidebar.nav_buttons`, `.back_button` |
| `checks/` | `tests/` |

Models and dialogs remain available from feature packages, such as `from tslibrary_ui.licenses import LicenseEntry, LicenseEntryDialog`.

`packaging/` and `scripts/build_windows.ps1` produce the standalone Windows app and Inno Setup installer. Runtime preferences remain outside the installation folder.
