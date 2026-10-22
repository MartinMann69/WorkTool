"""Validate operating-system launch requests without opening any resource."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tslibrary_ui.app import create_app
from tslibrary_ui.applications.models import Application
from tslibrary_ui.websites.models import Website
from tslibrary_ui.workplace.launching import ResourceLauncher


class LaunchChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def test_browser_request_is_http_only_and_reports_failure(self):
        launcher = ResourceLauncher()
        with patch("tslibrary_ui.workplace.launching.QDesktopServices.openUrl", return_value=True) as opener:
            launcher.open_website(Website("Site", "example.com/path?q=test#anchor"))
            self.assertEqual(opener.call_args.args[0].toString(), "https://example.com/path?q=test#anchor")
            with self.assertRaises(ValueError):
                launcher.open_website(Website("Invalid", "file:///C:/Windows/test.exe"))
            self.assertEqual(opener.call_count, 1)
        with patch("tslibrary_ui.workplace.launching.QDesktopServices.openUrl", return_value=False):
            with self.assertRaises(OSError):
                launcher.open_website(Website("Site", "https://example.com"))

    @unittest.skipUnless(os.name == "nt", "Windows launching")
    def test_executable_and_shortcut_keep_raw_arguments_without_shell_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            for suffix in (".exe", ".lnk"):
                path = Path(directory) / ("Team tool" + suffix)
                path.write_bytes(b"test fixture, never launched")
                args = r'--profile "Team profile" -launch -reg'
                with patch("tslibrary_ui.workplace.launching.os.startfile") as opener:
                    ResourceLauncher().open_application(Application("Tool", str(path), arguments=args))
                    opener.assert_called_once_with(str(path.resolve()), "open", arguments=args)
        with patch("tslibrary_ui.workplace.launching.os.startfile") as opener:
            with self.assertRaises(ValueError):
                ResourceLauncher().open_application(Application("Missing", r"C:\NotPresent\missing.exe"))
            opener.assert_not_called()
