"""Standalone library window, using the same collection page as administration."""

from ..graphics.icons import admin_icon
from .page import LibraryPage


class LibraryWindow(LibraryPage):
    def __init__(self, parent=None, *, session=None):
        super().__init__(parent, session=session, standalone=True)
        self.setWindowTitle("TSLibrary — Library")
        self.setWindowIcon(admin_icon("library", "#c9b18c"))
        self.setMinimumSize(820, 650)
        self.resize(1320, 850)
