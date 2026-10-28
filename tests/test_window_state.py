"""Window placement follows navigation and persists without touching catalog data."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QObject, QRect, QSettings, Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from tslibrary_ui.app import create_app
from tslibrary_ui.navigation import PreviewController
from tslibrary_ui.shared.confirmation import ConfirmDeleteDialog
from tslibrary_ui.window_state import WindowStateManager, create_window_settings


class ContentDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        self.resize(520, 350)


class WindowStateChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "window-state.ini"
        self.managers = []
        self.windows = []
        self.owners = []

    def tearDown(self):
        for manager in self.managers:
            manager.flush()
            self.app.removeEventFilter(manager)
        for window in reversed(self.windows):
            window.close()
            window.deleteLater()
        for owner in self.owners:
            owner.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def create_windows(self, *, persistent=False):
        owner = QObject()
        self.owners.append(owner)
        windows = [QWidget(), QWidget()]
        self.windows.extend(windows)
        for window in windows:
            window.resize(620, 460)
        settings = QSettings(str(self.path), QSettings.Format.IniFormat) if persistent else None
        manager = WindowStateManager(windows, settings=settings, parent=owner)
        self.managers.append(manager)
        return manager, windows

    def show(self, window):
        window.show()
        self.app.processEvents()

    def detach(self, manager, windows):
        for window in windows:
            window.close()
        manager.flush()
        self.app.removeEventFilter(manager)

    def test_any_main_screen_starts_maximized_without_saved_preferences(self):
        for first in (0, 1):
            manager, windows = self.create_windows()
            self.show(windows[first])
            self.assertTrue(windows[first].isMaximized())
            self.show(windows[1 - first])
            self.assertTrue(windows[1 - first].isMaximized())
            self.detach(manager, windows)
        self.assertFalse(self.path.exists())

    def test_main_screens_share_exact_resized_rectangle_and_maximized_state(self):
        _, (first, second) = self.create_windows()
        self.show(first)
        first.showNormal()
        first.setGeometry(QRect(35, 45, 640, 470))
        self.app.processEvents()
        self.show(second)
        first.hide()
        self.assertFalse(second.isMaximized())
        self.assertEqual(second.geometry(), QRect(35, 45, 640, 470))
        second.showMaximized()
        self.app.processEvents()
        self.show(first)
        second.hide()
        self.assertTrue(first.isMaximized())
        first.showNormal()
        self.app.processEvents()
        self.assertEqual(first.geometry(), QRect(35, 45, 640, 470))

    def test_real_controller_keeps_size_across_all_four_main_windows(self):
        controller = PreviewController()
        self.owners.append(controller)
        self.managers.append(controller.window_state)
        windows = [controller.welcome, controller.admin, controller.library, controller.main_window]
        self.windows.extend(windows)
        controller.show_welcome()
        self.app.processEvents()
        self.assertTrue(controller.welcome.isMaximized())
        controller.welcome.showNormal()
        controller.welcome.setGeometry(QRect(25, 35, 1120, 720))
        self.app.processEvents()
        for destination, window in ((controller.show_admin, controller.admin),
                                    (controller.show_library, controller.library),
                                    (controller.show_main, controller.main_window),
                                    (controller.show_welcome, controller.welcome)):
            destination()
            self.app.processEvents()
            self.assertFalse(window.isMaximized())
            self.assertEqual(window.geometry(), QRect(25, 35, 1120, 720))
        controller.welcome.showMaximized()
        for destination, window in ((controller.show_main, controller.main_window),
                                    (controller.show_admin, controller.admin),
                                    (controller.show_library, controller.library)):
            destination()
            self.app.processEvents()
            self.assertTrue(window.isMaximized())

    def test_resized_placement_survives_a_new_manager_and_settings_instance(self):
        manager, windows = self.create_windows(persistent=True)
        first = windows[0]
        self.show(first)
        first.showNormal()
        first.setGeometry(QRect(40, 50, 630, 450))
        self.app.processEvents()
        self.detach(manager, windows)
        _, replacement = self.create_windows(persistent=True)
        self.show(replacement[1])
        self.assertFalse(replacement[1].isMaximized())
        self.assertEqual(replacement[1].geometry(), QRect(40, 50, 630, 450))

    def test_maximized_placement_keeps_restore_down_size_after_restart(self):
        manager, windows = self.create_windows(persistent=True)
        first = windows[0]
        self.show(first)
        first.showNormal()
        first.setGeometry(QRect(40, 50, 630, 450))
        self.app.processEvents()
        first.showMaximized()
        self.app.processEvents()
        self.assertEqual(first.normalGeometry().size().width(), 630)
        self.detach(manager, windows)
        _, replacement = self.create_windows(persistent=True)
        self.show(replacement[0])
        self.assertTrue(replacement[0].isMaximized())
        replacement[0].showNormal()
        self.app.processEvents()
        self.assertEqual(replacement[0].size().width(), 630)
        self.assertEqual(replacement[0].size().height(), 450)

    def test_minimizing_immediately_after_resize_does_not_lose_the_choice(self):
        for maximized in (False, True):
            with self.subTest(maximized=maximized):
                manager, windows = self.create_windows(persistent=True)
                first = windows[0]
                self.show(first)
                first.showNormal()
                first.setGeometry(QRect(40, 50, 630, 450))
                if maximized:
                    first.showMaximized()
                first.showMinimized()
                self.app.processEvents()
                self.detach(manager, windows)
                _, replacement = self.create_windows(persistent=True)
                self.show(replacement[0])
                self.assertFalse(replacement[0].isMinimized())
                self.assertEqual(replacement[0].isMaximized(), maximized)
                if not maximized:
                    self.assertEqual(replacement[0].size().width(), 630)
                self.detach(self.managers[-1], replacement)

    def test_dialog_inherits_parent_then_remembers_its_own_resized_state(self):
        _, windows = self.create_windows()
        self.show(windows[0])
        dialog = ContentDialog(windows[0])
        self.windows.append(dialog)
        dialog.open()
        self.app.processEvents()
        self.assertTrue(dialog.isMaximized())
        self.assertTrue(dialog.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint)
        dialog.showNormal()
        dialog.setGeometry(QRect(45, 55, 590, 430))
        self.app.processEvents()
        dialog.reject()
        again = ContentDialog(windows[0])
        self.windows.append(again)
        again.open()
        self.app.processEvents()
        self.assertFalse(again.isMaximized())
        self.assertEqual(again.geometry(), QRect(45, 55, 590, 430))
        self.assertTrue(windows[0].isMaximized())

    def test_dialog_placement_is_persisted_by_type_across_restart(self):
        manager, windows = self.create_windows(persistent=True)
        self.show(windows[0])
        dialog = ContentDialog(windows[0])
        self.windows.append(dialog)
        dialog.open()
        dialog.showNormal()
        dialog.setGeometry(QRect(45, 55, 590, 430))
        dialog.accept()
        self.detach(manager, windows)
        _, replacement = self.create_windows(persistent=True)
        self.show(replacement[0])
        again = ContentDialog(replacement[0])
        self.windows.append(again)
        again.open()
        self.app.processEvents()
        self.assertFalse(again.isMaximized())
        self.assertEqual(again.size().width(), 590)
        self.assertTrue(replacement[0].isMaximized())

    def test_confirmation_and_system_messages_keep_normal_dialog_sizes(self):
        _, windows = self.create_windows()
        self.show(windows[0])
        for dialog in (ConfirmDeleteDialog("Remove item", "Keep this compact.", windows[0]),
                       QMessageBox(windows[0])):
            self.windows.append(dialog)
            dialog.open()
            self.app.processEvents()
            self.assertFalse(dialog.isMaximized())
            dialog.reject()

    def test_closing_hidden_screen_does_not_overwrite_the_active_screen(self):
        manager, (first, second) = self.create_windows(persistent=True)
        self.show(first)
        self.show(second)
        first.hide()
        second.showNormal()
        second.setGeometry(QRect(40, 50, 630, 450))
        self.app.processEvents()
        first.close()
        manager.flush()
        self.assertFalse(manager.settings.value("main/maximized", type=bool))
        self.assertEqual(manager._placements["main"].normal_rect, second.geometry())

    def test_invalid_geometry_falls_back_without_blocking_startup(self):
        settings = QSettings(str(self.path), QSettings.Format.IniFormat)
        settings.setValue("main/geometry", QByteArray(b"invalid geometry"))
        settings.setValue("main/maximized", True)
        settings.sync()
        _, windows = self.create_windows(persistent=True)
        self.show(windows[0])
        self.assertTrue(windows[0].isMaximized())

    def test_config_override_keeps_window_settings_in_the_same_local_folder(self):
        with patch.dict(os.environ, {"TSLIBRARY_CONFIG_PATH": str(self.path.parent / "custom-workplace.json")}):
            settings = create_window_settings()
        self.assertEqual(Path(settings.fileName()).resolve(), self.path.resolve())
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
