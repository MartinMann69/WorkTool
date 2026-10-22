# TSLibrary

A PySide6 desktop UI with a dark, Japanese-inspired welcome screen, an empty main workspace, a searchable read-only library, and an admin workspace for licenses, applications, phone apps, and websites.

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

Choose **Open TSLibrary** on the welcome screen to open an empty, dark main window without signing in. The main workspace has no collection or controls yet. To browse the collection directly, use:

```powershell
.venv\Scripts\python main.py --library
```

The library combines all four admin inventories. Search names and details, filter by resource type, and sort by name A–Z, Z–A, or type then name. Counts show the collection at a glance; selecting an item shows its details. This view has no edit, launch, or license-key controls.

Administration also includes a **Full library** sidebar tab with the same combined overview. Items added, renamed, or removed in the individual tabs appear when you return to it. Its sort choice is independent of the inventory tabs.

On macOS/Linux, use `.venv/bin/python` instead. Georgia, Segoe UI, and Yu Mincho are used when installed, with Qt font fallback.

This is a UI preview. Admin credentials are not checked, entries stay in memory, and closing the app loses the session. Application selection never launches files; website editing makes no network requests. Admin changes appear in the library when it is reopened during the same session. The application starts with an empty collection; sample entries are only used in screenshots.

## Find the right file

| Change | Start here |
| --- | --- |
| Welcome text, form, and buttons | [welcome/window.py](tslibrary_ui/welcome/window.py) |
| Empty main workspace | [main_window.py](tslibrary_ui/main_window.py) |
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
