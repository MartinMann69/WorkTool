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

Choose **Open TSLibrary** without signing in. The user window has three tabs:

- **Websites**: selected Collection links and your own personal websites. Each card has an **Open website** button to open it in your browser. Double-click also works.
- **Applications**: selected Collection tools and your own personal apps. Each card has an **Open application** button to launch the executable or shortcut with its saved arguments. Double-click also works.
- **Collection**: all admin-managed applications and websites. Use **Add to workplace** or **Remove from workplace** inside each card. A check marks saved selections, and a live **Selected** list on the right shows all chosen Collection entries, including those hidden by search/type filters. Remove an entry directly with its **×** sidebar button. Keyboard users can focus a card and press **Space** to toggle it, or focus a sidebar entry and press **Delete** to remove it. Removing a selection keeps the admin entry. **Refresh collection** picks up changes made in another app instance.

Use **Add personal website/application** to add your own entries, and the **Edit** button inside a personal card to update it. Websites and Applications have no bottom action bar or Remove buttons; manage Collection selections from Collection. Keyboard users can press **Space** or **Enter** to open a focused workplace card, or **F2** to edit a personal entry. Normal users have no accounts: each Windows user's selected IDs and personal entries are saved separately.

To browse the separate read-only overview of all four admin inventories directly, use:

```powershell
.venv\Scripts\python main.py --library
```

The library combines all four admin inventories. Search names and details, filter by resource type, and sort by name A–Z, Z–A, or type then name. Counts show the collection at a glance; selecting an item shows its details. This view has no edit, launch, or license-key controls.

Administration also includes a **Full library** sidebar tab with the same combined overview. Items added, renamed, or removed in the individual tabs appear when you return to it. Its sort choice is independent of the inventory tabs.

On macOS/Linux, use `.venv/bin/python` instead. Georgia, Segoe UI, and Yu Mincho are used when installed, with Qt font fallback.

Admin credentials are still not checked. App/website edits save automatically to the shared `data/catalog.json`. Each user's selections and personal entries save to `%APPDATA%\TSLibrary\workplace.json`. Files are created on the first change. Launching happens only through an explicit workplace Open action or double-click; adding/editing entries does not open them. The phone-app and license inventories remain session-only, and license keys are not written to these JSON files. Sample entries are used only in screenshots.

The storage boundary is [storage.py](tslibrary_ui/storage.py). Replace its implementation and factory to use a database; windows and feature pages do not read or write JSON themselves. See [storage and config](docs/STORAGE.md) for the four-method contract, schemas, and deployment paths.

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
