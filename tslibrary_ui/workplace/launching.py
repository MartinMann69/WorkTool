"""Explicit workplace actions only; never called during editing or loading."""

import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from ..applications.targets import parse_launch_target
from ..websites.urls import normalize_website_url


class ResourceLauncher:
    def open_website(self, website):
        url = QUrl(normalize_website_url(website.url))
        if not QDesktopServices.openUrl(url):
            raise OSError("Your default browser could not open this website.")

    def open_application(self, application):
        path, arguments = parse_launch_target(application.launch_target)
        if os.name != "nt":
            raise OSError("Desktop application launching requires Windows.")
        # ShellExecute opens .lnk files intact and preserves their own settings.
        # No command interpreter or shell command string is involved.
        os.startfile(str(path), "open", arguments=arguments)
