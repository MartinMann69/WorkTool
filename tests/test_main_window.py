"""Normal entry opens an empty workspace rather than the inventory collection."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QWidget

from tslibrary_ui.app import create_app
from tslibrary_ui.applications.models import Application
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.state import LibrarySession


class MainWindowChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.controller = PreviewController(session=LibrarySession(
            applications=[Application("Existing application", r"C:\Tools\app.exe")],
        ))

    def tearDown(self):
        controller = self.controller
        for window in (controller.main_window, controller.library,
                       controller.admin, controller.welcome):
            window.close()
            window.deleteLater()
        controller.deleteLater()
        self.app.processEvents()

    def test_open_button_shows_empty_main_window_even_with_catalog_entries(self):
        controller = self.controller
        controller.welcome.show()
        controller.welcome.open_button.click()
        self.app.processEvents()
        self.assertTrue(controller.main_window.isVisible())
        self.assertFalse(controller.library.isVisible())
        self.assertFalse(controller.admin.isVisible())
        self.assertFalse(controller.welcome.isVisible())
        self.assertEqual(controller.main_window.windowTitle(), "TSLibrary")
        self.assertEqual(controller.main_window.centralWidget().findChildren(QWidget), [])
        self.assertEqual(len(controller.session.applications), 1)

    def test_navigation_hides_the_empty_workspace_when_another_window_opens(self):
        controller = self.controller
        for destination in (controller.show_welcome, controller.show_admin,
                            controller.show_library):
            controller.show_main()
            self.assertTrue(controller.main_window.isVisible())
            destination()
            self.app.processEvents()
            self.assertFalse(controller.main_window.isVisible())
