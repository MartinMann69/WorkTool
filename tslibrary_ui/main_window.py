"""Empty main workspace, ready for future TSLibrary features."""

from PySide6.QtWidgets import QMainWindow, QWidget

from .graphics.icons import admin_icon
from .styles import load_stylesheets


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mainWindow")
        self.setWindowTitle("TSLibrary")
        self.setWindowIcon(admin_icon("library", "#c9b18c"))
        self.setMinimumSize(820, 650)
        self.resize(1320, 850)
        self.setStyleSheet(load_stylesheets("main"))
        content = QWidget()
        content.setObjectName("mainContent")
        self.setCentralWidget(content)
