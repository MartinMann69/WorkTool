"""Reveal a local file or folder without executing the selected file."""

import os
from pathlib import Path
import subprocess

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from ..graphics.icons import admin_icon
from .forms import action


def show_in_explorer(path):
    target = Path(path).resolve(strict=True)
    if not target.is_dir() and not target.is_file():
        raise OSError("This file or folder is unavailable on this PC.")
    if target.is_file() and os.name == "nt":
        explorer = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "explorer.exe"
        # Explorer's /select switch needs a comma followed by a quoted path.
        # A Windows file path cannot contain quotes; no command shell is used.
        subprocess.Popen(f'"{explorer}" /select,"{target}"', shell=False)
        return
    folder = target if target.is_dir() else target.parent
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
        raise OSError("File Explorer could not open this folder.")


def explorer_button(name, callback):
    button = action("")
    button.setIcon(admin_icon("folder", "#c9b18c"))
    button.setFixedWidth(34)
    button.setProperty("iconOnly", True)
    button.setToolTip(f"Open in Explorer: {name}")
    button.setAccessibleName(f"Open in Explorer: {name}")
    button.clicked.connect(callback)
    return button
