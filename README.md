# TSLibrary

A Japanese-inspired PySide6 login screen for TSLibrary. A charcoal theme with warm ivory type, brass accents, and original shoji, bamboo, and lantern artwork drawn with Qt. No image assets, downloads, browser views, authentication, or credential storage.

## Run

Requires Python 3.10 or newer.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

On macOS/Linux, use `.venv/bin/python` instead. The layout uses installed Georgia and Segoe UI fonts with Qt font fallback; Yu Mincho is used for Japanese text.

## Included

- Original architectural artwork inspired by dark timber, shoji screens, and warm lantern light.
- Scalable bookshelf mark, artwork, and icons drawn with QPainter; no external images.
- Focus and hover states, password visibility toggle, remember checkbox, and keyboard navigation.
- Gentle entrance animation; pass `animate=False` to disable it.
- Compact single-panel layout below 900px, with scrolling for short windows.
- UI-only sign-in and recovery actions. Clicking shows a brief preview notice; no action authenticates or navigates.
- New users are added by an administrator; the login screen has no self-registration option.

## Use in your project

```python
from tslibrary_ui import LoginWindow

window = LoginWindow(show_preview_feedback=False)
# Optional: connect intent signals to your own code later.
window.sign_in_requested.connect(your_handler)  # username, password, remember
window.recovery_requested.connect(your_recovery_handler)
window.show()
```

Create a `QApplication` first (see `main.py`). Keep `tslibrary_ui/theme.qss` and `tslibrary_ui/check.svg` with the Python modules. Colors and styling live in `theme.qss`; the original Qt artwork lives in `artwork.py`.

## Verify and preview

```powershell
.venv\Scripts\python -m unittest discover -s checks -v
.venv\Scripts\python scripts\preview.py
```

The preview script renders the actual Qt UI offscreen to `previews/desktop.png`, `previews/compact.png`, `previews/wide.png`, and `previews/tall.png`.
