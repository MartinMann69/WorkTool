# TSLibrary

A PySide6 desktop app with a dark, Japanese-inspired welcome screen, a personal workplace, and an admin workspace for licenses, applications, phone apps, and websites.

Start with the [project structure guide](docs/PROJECT_STRUCTURE.md) to find the file for a change. The [feature reference](docs/FEATURES.md) describes the current workflows.

## Run

Requires Python 3.10 or newer.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

Open administration directly:

```powershell
.venv\Scripts\python main.py --admin
```

On Windows, only one TSLibrary process can run per PC, including launches from
different project copies or Windows sessions. Opening it again restores the
existing window and keeps its current page. Duplicate `--admin` / `--library`
launches also restore that window rather than changing its mode. If another
Windows session owns it, switch to that session. Closing the app releases the
instance; Windows also releases it after a crash. Tests and screenshots use
isolated windows without reserving the normal app instance.

The app starts maximized by default, including direct `--admin` and `--library` launches. Restoring down or resizing becomes your new preference: Welcome, Administration, Library, and the workplace share the same size, position, and maximized state when switching screens and after restarting. Editors and management windows initially follow their parent and then remember their own size/state by dialog type. Small confirmation messages and system file pickers keep their normal dialog sizes. These display preferences are stored locally in `%APPDATA%\TSLibrary\window-state.ini`, beside the user's workplace config (including when `TSLIBRARY_CONFIG_PATH` is overridden).

Choose **Open TSLibrary** without signing in. The user window has three tabs:

- **Websites**: selected Collection links and your own personal websites. Each card has an **Open website** button to open it in your browser. Double-click also works.
- **Applications**: selected Collection tools and your own personal apps. Each card has an **Open application** button to launch the executable or shortcut with its saved arguments. Double-click also works.
- **Collection**: all admin-managed applications and websites. Use **Add to workplace** or **Remove from workplace** inside each card. A check marks saved selections, and a live **Selected** list on the right shows all chosen Collection entries, including those hidden by search/type filters. Remove an entry directly with its **×** sidebar button. Keyboard users can focus a card and press **Space** to toggle it, or focus a sidebar entry and press **Delete** to remove it. Removing a selection keeps the admin entry. **Refresh collection** picks up changes made in another app instance.

Use **Add personal website/application** to add your own entries, and the **Edit** button inside a personal card to update it. The three-dot menu (or right-click / keyboard context menu) also provides personal-entry removal, favorites, group membership, and local app-path repair. Delete asks for confirmation before removing a personal entry. Websites and Applications have no bottom action bar or Remove buttons; manage Collection selections from Collection. Keyboard users can press **Space** or **Enter** to open a focused workplace card, or **F2** to edit a personal entry. Normal users have no accounts: each Windows user's selected IDs and personal entries are saved separately.

To browse the separate read-only overview of all four admin inventories directly, use:

```powershell
.venv\Scripts\python main.py --library
```

The library combines all four admin inventories. Search names and details, filter by resource type, and sort by name A–Z, Z–A, or type then name. Counts show the collection at a glance; selecting an item shows its details. This view has no edit, launch, or license-key controls.

Administration also includes a **Full library** sidebar tab with the same combined overview. Items added, renamed, or removed in the individual tabs appear when you return to it. Its sort choice is independent of the inventory tabs.

In an admin entry's add/edit form, use **Related entries → Choose entries…** to select applications, phone apps, websites, licensed items, or documentation. Connections are direct and work both ways. Contacts and Outlook can each link to the same phone documentation; the documentation lists both apps. Checking an entry selects just that entry. Saving replaces only the edited item's connections and preserves all other connections. **Use selection** stages the choices; saving the item applies them, while cancelling discards the draft. Linked rows show a **chain icon and direct connection count** in the **Links** column. Click to navigate to and highlight a single connected item, or choose the destination from a menu when there are several. Open, Explorer, and Manage licenses are separate actions. Renames preserve links; deleting an entry removes its own links. These controls are available only in Administration. Older releases may already have saved unwanted app-to-app links: uncheck those once in the connection editor. They stay removed even when both apps share documentation.

On macOS/Linux, use `.venv/bin/python` instead. Georgia, Segoe UI, and Yu Mincho are used when installed, with Qt font fallback.

Admin credentials are still not checked. Admin edits save automatically to the selected team catalog, or the existing local catalog until a team is configured. Each user's selections and personal entries save to `%APPDATA%\TSLibrary\workplace.json`. Files are created on the first change. Launching happens only through an explicit workplace Open action or double-click; adding/editing entries does not open them. Phone apps, license counts, owners, and renewal dates also save automatically. License key values stay in memory only and are excluded from JSON files and backups; after restarting, keyed entries show that the key needs to be re-entered. Sample entries are used only in screenshots.

The storage boundary is [storage.py](tslibrary_ui/storage.py). `ApplicationRepository` keeps two adapters separate: `LocalWorkplaceStore` for personal data and `CatalogStore` for admin-managed inventory. Without a team configuration, `JsonCatalogStore` keeps the existing local behavior. A selected team uses `SharedJsonCatalogStore` with a lock and stale-write protection; a server adapter can replace the catalog boundary later. Admin edits already save through this boundary, and workplace entry / **Refresh collection** reloads it. New catalog entries are available in Collection for users to select; they do not automatically enter personal workplaces. Version-1/2/3 catalogs upgrade automatically to catalog format 4 with an exact recovery backup; record IDs and relationships are preserved. Personal workplace files stay at version 1. See [storage and config](docs/STORAGE.md) for the file formats, shared-folder setup, conflict recovery, and future server/offline work.

## Set up two admins with one catalog

1. On the first admin PC, open **Administration → Settings → Create configuration…**. Save `Team.json` in a shared network folder, such as `\\server\Team\TSLibrary\Team.json`.
2. TSLibrary creates `Team.catalog.json` beside it, copying the current catalog with stable IDs. The original catalog is kept; personal entries and license key values are excluded.
3. Install this version on the other admin PC. In **Settings → Open configuration…**, select that same `Team.json` on the network share.
4. Set the documentation folder and root name in **Settings → Documentation**. Both admins receive those defaults through the shared catalog.

The chosen configuration path is remembered locally; copying the installer alone does not select a team. Keep both shared files together. A copied pair becomes an independent catalog rather than a live connection to the original. Use the same app version on both PCs and the same live network share, rather than separate cloud-synced copies.

Admin windows check for changes every 5 seconds in the background while no editor, documentation window, unsaved catalog change, or settings draft is open. **Reload catalog** checks immediately. Saves use a shared lock and reject stale sessions. If a save conflicts, keep the draft using **Data tools → Export catalog backup…**, reload in Settings, then reapply the change. **Retry saving** is useful for temporary access/permission failures; it does not override a conflict. Personal workplace choices remain local. Missing team files show an error rather than silently starting an empty catalog; startup offers Retry or another configuration.

## Applications on different PCs

Admin application entries now store a portable `target` reference in the shared JSON rather than a path tied to the first admin's Windows username. Shortcuts keep their `.lnk` identity and use the matching folder for the current user, including redirected Desktop and Start Menu folders. Each PC needs its own shortcut in that folder; TSLibrary does not copy the shortcut or replace it with the first PC's target.

Executables retain their filename, a portable location hint, and an installed-product identity when Windows provides it. The app checks that PC's installed location, the rebased hint, Windows App Paths registration, and explicit PATH folders. It does not scan drives or install programs. If detection fails or is ambiguous, use **Locate application on this PC…** from the card menu; this saves a local override. Arguments remain separate and unchanged, so argument values containing machine-specific paths may still need adjusting. A shared entry can be renamed even when it is not installed on the admin's PC. Personal application paths remain private in the workplace config.

## Everyday workplace tools

- **Find tools / Ctrl+K** searches apps and websites across the shared catalog and your workplace. Up/Down chooses a result; Enter opens it. No tools launch while searching.
- Use each workplace card's **three-dot menu** to pin a **Favorite**, create or join a group, edit/remove a personal entry, or **Locate application on this PC**. Favorites sort first. The group selector filters by Favorites or a custom group. Tools includes group rename/delete.
- Choose **Cards / List** for a compact list view. The preference applies to Websites, Applications, and Collection and is saved per user.
- Missing executable/shortcut paths show **Unavailable on this PC**. Locating a replacement saves a local override, preserves launch arguments, and keeps the shared catalog unchanged. The same override is used by cards, quick search, and workspace sets.
- **Tools → Workspace sets** creates, edits, deletes, and launches named groups of workplace tools. Opening a set asks for confirmation. Entries removed from the current workplace are skipped; selecting a set shows how many saved references are unavailable. Saving an edited set replaces its selections.
- **Tools → Start directly in my workplace** skips welcome next time. Back to welcome still provides admin access. `main.py --welcome` forces the welcome screen regardless of this preference.
- Admin tabs keep their individual search terms when switching pages. Search, filters, cards, and secondary labels use larger text.
- Licensed items now have an optional **owner / responsible team** and an optional **renewal date**. The license page highlights renewals due within 30 days or overdue; details and the full-library search include this metadata. These are in-app reminders, not background notifications.

## Shared documentation

In **Administration → Settings → Documentation**, choose an existing **Shared location**, enter a **Root folder name**, and click **Save location**. The root defaults to `TSLibrary Documentation`. These defaults live in the catalog, so every admin using the team configuration receives them. Changing the path keeps files in place; copy existing documentation to the destination first.

Documentation works as a file browser: open a folder and its actual files and subfolders appear together in the main list. Click **Open** or double-click a file to open it directly. Use **New folder**, **Add files…**, **Refresh**, **Up**, and clickable breadcrumbs in the same window. The separate “Files in this folder” button and file popup are no longer needed. Search finds folders and files recursively within the current location; Home searches the entire documentation root. Files show their type and size. The left tree includes documentation folders and folders discovered in the shared location.

Registered folders keep their existing IDs and relationships. New folder creates a named documentation folder; Add files copies originals into the current folder, including Home, while rejecting duplicate names. Existing files stay in place. Directory reads and copying run in the background; stale reads are discarded after navigation, failed refreshes keep the last displayed listing, and the app prevents leaving/closing administration during a copy. Use Refresh to see files added outside the app or by another admin.

Every documentation file/folder has a **chain icon** to edit its connections, also available as **⋯ → Connections…**. Select existing applications, licenses, or other library entries, then save the connections. From an app's or other entry's **Connect your library** window, use the separate **Documentation** tab to browse the same folder hierarchy and check either individual files or whole folders. Checking a folder links that folder itself; it does not check its contents. A documentation connection reveals and highlights the file or folder row. Use its Open button or double-click to open it. New documentation references remain drafts until the owning item is saved; cancelling does not create catalog records or copy files. Moves within TSLibrary preserve these references and their connections.

Use **Open in Explorer** to open the current directory in Windows File Explorer. In Administration, use an item's **⋯** menu or right-click a file/folder to choose **Move to…** or **Delete…**. The folder tree also supports these actions on right-click. Moves stay inside the documentation root, preserve registered folder IDs and connections, and reject existing destinations. **Delete** permanently removes the actual file or folder and its contents, including nested documentation records and their connections, after confirmation. If saving the catalog fails, the original location and records are restored before file cleanup begins. Cleanup runs in the background; if a locked file prevents completion, the message gives the retained temporary location.

The **folder icon in each Applications or Documentation row** also opens Explorer for that particular item. App rows resolve and select the executable or shortcut on this PC without running it; documentation file rows select the file, and folder rows open the folder.

Documentation is available in Administration. The user window contains **Websites**, **Applications**, and **Collection**. Renaming an item also renames its folder (and the paths of any child items). Changing the root name moves the existing root folder; existing destination folders are never merged. A move between drives may need to be done manually before changing deployment settings.

Use your network share's permissions to grant the team access. TSLibrary does not change sharing permissions. Every PC needs access to the same live team configuration/catalog and documentation folder. If PCs mount the shared parent at different paths, set `TSLIBRARY_DOCUMENTS_PATH` on each PC to its local shared-parent path; the configured root name is appended to it. On the administrator PC, unset this override before changing storage settings.

Catalog backups include documentation names and location settings, **not the attached files**. Back up the shared folder separately.

## Backup, restore, and export

**Tools** exports/restores the current user's workplace preferences and personal entries. Administration's **Data tools** exports/restores the shared catalog and exports a CSV inventory. Restore validates the whole backup before applying it, asks for confirmation, and writes a timestamped recovery backup beside the chosen file first. Backups preserve record IDs, favorites, groups, workspace sets, local paths, and preferences. Local paths may need repairing on a different PC.

Catalog backups and CSV exports include phone apps and license metadata/counts, but **never license key values**. Key storage and real admin authentication remain deferred. Team configurations add guarded shared saves; stale edits stay in memory and cannot overwrite another admin's work.

## Windows app and installer

The packaged build needs no Python installation:

- `dist/TSLibrary/TSLibrary.exe` runs the standalone app. Keep its `_internal` folder beside it.
- `dist/TSLibrary-Setup-<version>.exe` installs it for the current Windows user, adds a Start menu shortcut, optionally adds a desktop shortcut, and provides an uninstaller. Updating/uninstalling the program keeps catalog and workplace data outside the installation folder.
- Packaged catalog data defaults to `%LOCALAPPDATA%\TSLibrary\catalog.json`. `TSLIBRARY_CATALOG_PATH` still selects an explicit shared catalog; user preferences stay in `%APPDATA%\TSLibrary\workplace.json`. To move development data into an installed copy, export and restore a catalog backup.

Rebuild with Python dependencies from `requirements.txt` and `requirements-build.txt`, plus [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```powershell
.\scripts\build_windows.ps1 -InnoCompiler 'C:\Path\To\Inno Setup 6\ISCC.exe'
```

The build scripts create the icon from the project's own mark and bundle styles and installed dependency license files. `TSLibrary.exe --self-test` renders its windows with in-memory data without opening the real catalog or reserving the normal app instance. Set `QT_QPA_PLATFORM=offscreen` for an unattended check. The development installer is unsigned; production signing is a separate release step.

Release versions come from `tslibrary_ui/version.py`; the build passes that version to Inno Setup and creates a matching SHA-256 checksum. Install a newer setup over the existing installation under the same Windows user. Keep the installer `AppId` unchanged. App versions and saved-data versions are independent: this release uses catalog format 4 and personal workplace format 1. Version-1/2/3 catalogs are upgraded with a recovery backup; install this version on both admin PCs before reopening the shared catalog. A migration framework now validates conversions, creates an exact recovery backup before changing a saved-data format, and rejects newer unsupported files on both load and save. Future structural changes still require explicit migration functions and tests. See the [release and upgrade guide](docs/RELEASING.md).

## Find the right file

| Change | Start here |
| --- | --- |
| Welcome text, form, and buttons | [welcome/window.py](tslibrary_ui/welcome/window.py) |
| User tabs, selection actions, and personal entries | [main_window.py](tslibrary_ui/main_window.py), [workplace/](tslibrary_ui/workplace/) |
| JSON files or a future database backend | [storage.py](tslibrary_ui/storage.py) |
| Library overview, search, filters, and cards | [library/](tslibrary_ui/library/) |
| Admin tabs / sidebar | [admin/window.py](tslibrary_ui/admin/window.py), [admin/sidebar.py](tslibrary_ui/admin/sidebar.py) |
| License list and item actions | [licenses/page.py](tslibrary_ui/licenses/page.py) |
| License totals and usage rules | [licenses/models.py](tslibrary_ui/licenses/models.py) |
| Application list / file picker | [applications/page.py](tslibrary_ui/applications/page.py), [applications/dialogs.py](tslibrary_ui/applications/dialogs.py) |
| Phone app inventory (names only) | [phone_apps/page.py](tslibrary_ui/phone_apps/page.py), [phone_apps/dialogs.py](tslibrary_ui/phone_apps/dialogs.py) |
| Website list / URL validation | [websites/page.py](tslibrary_ui/websites/page.py), [websites/urls.py](tslibrary_ui/websites/urls.py) |
| Colors and QSS styling | [styles/](tslibrary_ui/styles/) |
| Logo, illustrations, and icons | [graphics/](tslibrary_ui/graphics/) |
| Cross-window navigation | [navigation.py](tslibrary_ui/navigation.py) |
| Session data | [state.py](tslibrary_ui/state.py) |

Each feature folder keeps its models, dialogs, and page together. Reusable controls and layouts live in `shared/`. See the [full guide](docs/PROJECT_STRUCTURE.md) for individual dialogs and extension examples.

## Verify and preview

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python scripts\preview.py
```

Tests are grouped by feature under `tests/`. Generated screenshots go into `previews/`; their sample data is not loaded into the runnable application.

## Reuse the windows

```python
from tslibrary_ui import AdminWindow, LibraryWindow, LoginWindow, MainWindow
from tslibrary_ui.app import create_app

app = create_app()
welcome = LoginWindow(show_preview_feedback=False)
welcome.open_requested.connect(your_open_handler)
welcome.sign_in_requested.connect(your_admin_handler)  # username, password
welcome.show()
app.exec()
```

`tslibrary_ui/navigation.py` shows the runnable preview's wiring. Keep the `styles/` folder with the Python package; its loader resolves paths independently of the working directory.

Pass the same `LibrarySession` to `AdminWindow(session=session)` and `LibraryWindow(session=session)` to share an inventory. The built-in controller already does this. `LibraryWindow.refresh()` reloads direct session edits; showing the window also refreshes it while preserving its search and sort choices.
