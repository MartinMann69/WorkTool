"""Run TSLibrary; --admin and --library open their windows directly."""

import os
from pathlib import Path
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from .navigation import PreviewController
from .single_instance import InstanceError, SingleInstance
from .storage import StorageError, create_repository


def create_app() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("TSLibrary")
    app.setOrganizationName("TSLibrary")
    app.setApplicationVersion("0.2.0")
    app.setStyle("Fusion")
    # Qt's offscreen Windows plugin does not enumerate installed fonts.
    # Load the same system fonts explicitly when rendering headless previews.
    if os.name == "nt" and not QFontDatabase.families():
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf",
                         "georgiai.ttf", "yumin.ttf"):
            QFontDatabase.addApplicationFont(str(font_dir / filename))
    app.setFont(QFont("Segoe UI", 10))
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#181b18"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e9e4d8"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1f231e"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e9e4d8"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#242920"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e9e4d8"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#909585"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#242920"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e9e4d8"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#c9b18c"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#181b18"))
    app.setPalette(palette)
    return app


def main() -> int:
    app = create_app()
    if "--self-test" in sys.argv:
        # Packaging diagnostic: in-memory windows only, no real data or locks.
        controller = PreviewController()
        for window in (controller.welcome, controller.main_window, controller.admin, controller.library):
            window.show()
            app.processEvents()
            if window.grab().isNull():
                return 1
            window.close()
        return 0
    instance = SingleInstance(app)
    try:
        primary = instance.start()
    except InstanceError as error:
        QMessageBox.critical(None, "Could not start TSLibrary", str(error))
        return 1
    if not primary:
        if not instance.notified:
            QMessageBox.information(None, "TSLibrary is already running",
                "TSLibrary is already running on this PC. Switch to its window, "
                "or to the Windows session that opened it.")
        return 0
    app.aboutToQuit.connect(instance.close)
    try:
        try:
            controller = PreviewController(repository=create_repository())
        except StorageError as error:
            QMessageBox.critical(None, "Could not load TSLibrary", str(error))
            return 1
        instance.activation_requested.connect(controller.activate_current_window)
        if "--admin" in sys.argv:
            controller.show_admin()
        elif "--library" in sys.argv:
            controller.show_library()
        elif controller.main_window.config.start_in_workplace and "--welcome" not in sys.argv:
            controller.show_main()
        else:
            controller.welcome.show()
        return app.exec()
    finally:
        instance.close()
