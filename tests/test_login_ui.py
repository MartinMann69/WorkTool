"""Interaction and layout checks; no authentication or external services."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QLineEdit, QScrollArea

from tslibrary_ui import LoginWindow
from tslibrary_ui.app import create_app


class LoginUiChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.window = LoginWindow(animate=False)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_keyboard_submission_emits_values_without_changing_screen(self):
        spy = QSignalSpy(self.window.sign_in_requested)
        self.window.username_field.edit.setText("marti_01")
        QTest.keyClick(self.window.username_field.edit, Qt.Key.Key_Return)
        self.assertTrue(self.window.password_field.edit.hasFocus())
        QTest.keyClicks(self.window.password_field.edit, "quiet-morning")
        QTest.keyClick(self.window.password_field.edit, Qt.Key.Key_Return)
        self.assertEqual(spy.count(), 1)
        self.assertEqual(spy.at(0), ["marti_01", "quiet-morning"])
        self.assertTrue(self.window.isVisible())
        self.assertNotIn("quiet-morning", self.window.notice.text())

    def test_password_toggle_keeps_input_and_updates_accessible_name(self):
        field = self.window.password_field
        field.edit.setText("sample-password")
        self.assertEqual(field.edit.echoMode(), QLineEdit.EchoMode.Password)
        QTest.mouseClick(field.toggle, Qt.MouseButton.LeftButton)
        self.assertEqual(field.edit.echoMode(), QLineEdit.EchoMode.Normal)
        self.assertEqual(field.toggle.accessibleName(), "Hide password")
        QTest.mouseClick(field.toggle, Qt.MouseButton.LeftButton)
        self.assertEqual(field.edit.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(field.edit.text(), "sample-password")

    def test_open_library_does_not_request_admin_sign_in(self):
        open_spy = QSignalSpy(self.window.open_requested)
        admin_spy = QSignalSpy(self.window.sign_in_requested)
        # Normal access works with both empty and filled-in admin fields.
        for username, password in [("", ""), ("admin", "sample-password")]:
            self.window.username_field.edit.setText(username)
            self.window.password_field.edit.setText(password)
            self.window.open_button.click()
        self.assertEqual(open_spy.count(), 2)
        self.assertEqual(open_spy.at(0), [])
        self.assertEqual(admin_spy.count(), 0)

    def test_default_keyboard_action_opens_library(self):
        open_spy = QSignalSpy(self.window.open_requested)
        admin_spy = QSignalSpy(self.window.sign_in_requested)
        self.assertTrue(self.window.open_button.hasFocus())
        QTest.keyClick(self.window.open_button, Qt.Key.Key_Space)
        self.assertEqual(open_spy.count(), 1)
        self.assertEqual(admin_spy.count(), 0)

    def test_layout_adapts_without_horizontal_overflow(self):
        for width, height in [(1180, 820), (900, 700), (899, 700),
                              (480, 820), (440, 600), (1600, 1000)]:
            self.window.resize(width, height)
            self.app.processEvents()
            self.assertEqual(self.window.artwork.isVisible(), width >= 900)
            self.assertEqual(self.window.compact_brand.isVisible(), width < 900)
            scroll = self.window.findChild(QScrollArea)
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            self.assertGreaterEqual(self.window.username_field.width(), 260)
            self.assertGreater(self.window.sign_in_button.width(), 250)

    def test_preview_feedback_can_be_disabled(self):
        other = LoginWindow(show_preview_feedback=False, animate=False)
        spy = QSignalSpy(other.sign_in_requested)
        other.sign_in_button.click()
        self.assertEqual(spy.count(), 1)
        self.assertEqual(other.notice.text(), "")
        other.close()
        other.deleteLater()

    def test_artwork_background_has_no_bands_after_resizing(self):
        # Check empty margins, where fitting the illustration must not leave
        # visible canvas edges, and the join with the adjacent form panel.
        for width, height in [(1543, 790), (1180, 820), (1000, 1100),
                              (1900, 700), (901, 601), (1543, 790)]:
            with self.subTest(size=(width, height)):
                self.window.resize(width, height)
                self.app.processEvents()
                pixels = self.window.artwork.grab().toImage()
                for y in (2, pixels.height() - 3):
                    for x in range(1, pixels.width()):
                        before = pixels.pixelColor(x - 1, y)
                        after = pixels.pixelColor(x, y)
                        self.assertLessEqual(max(
                            abs(before.red() - after.red()),
                            abs(before.green() - after.green()),
                            abs(before.blue() - after.blue()),
                        ), 2, f"Background edge at {(x, y)}")
                for y in (2, pixels.height() // 2, pixels.height() - 3):
                    edge = pixels.pixelColor(pixels.width() - 1, y)
                    self.assertLessEqual(max(abs(edge.red() - 24),
                                             abs(edge.green() - 27),
                                             abs(edge.blue() - 24)), 1)


if __name__ == "__main__":
    unittest.main()
