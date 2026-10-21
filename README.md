# TSLibrary

A PySide6 desktop UI with a dark, Japanese-inspired welcome screen and an admin workspace for licenses, applications, and websites.

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

On macOS/Linux, use `.venv/bin/python` instead. Georgia, Segoe UI, and Yu Mincho are used when installed, with Qt font fallback.

This is a UI preview. Admin credentials are not checked, entries stay in memory, and closing the app loses the session. Application selection never launches files; website editing makes no network requests. The regular-user window is still pending, so **Open TSLibrary** currently shows preview feedback.

## Find the right file

| Change | Start here |
| --- | --- |
| Welcome text, form, and buttons | [welcome/window.py](tslibrary_ui/welcome/window.py) |
| Admin tabs / sidebar | [admin/window.py](tslibrary_ui/admin/window.py), [admin/sidebar.py](tslibrary_ui/admin/sidebar.py) |
| License list and item actions | [licenses/page.py](tslibrary_ui/licenses/page.py) |
| License totals and usage rules | [licenses/models.py](tslibrary_ui/licenses/models.py) |
| Application list / file picker | [applications/page.py](tslibrary_ui/applications/page.py), [applications/dialogs.py](tslibrary_ui/applications/dialogs.py) |
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
from tslibrary_ui import AdminWindow, LoginWindow
from tslibrary_ui.app import create_app

app = create_app()
welcome = LoginWindow(show_preview_feedback=False)
welcome.open_requested.connect(your_open_handler)
welcome.sign_in_requested.connect(your_admin_handler)  # username, password
welcome.show()
app.exec()
```

`tslibrary_ui/navigation.py` shows the runnable preview's wiring. Keep the `styles/` folder with the Python package; its loader resolves paths independently of the working directory.
