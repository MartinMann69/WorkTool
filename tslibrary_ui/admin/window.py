"""Admin shell: compose feature pages and route sidebar navigation.

Editing, searching, and row rendering live in each feature's page.py.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QWidget

from ..applications.page import ApplicationsPage
from ..graphics.icons import admin_icon
from ..licenses.page import LicensesPage
from ..library.page import LibraryPage
from ..phone_apps.page import PhoneAppsPage
from ..state import LibrarySession
from ..styles import load_stylesheets
from ..websites.page import WebsitesPage
from .sidebar import AdminSidebar


class AdminWindow(QWidget):
    back_requested = Signal()
    LICENSES_PAGE = "Licenses"

    def __init__(self, parent=None, *, session=None):
        super().__init__(parent)
        self.session = session if session is not None else LibrarySession()
        self.setObjectName("adminWindow")
        self.setWindowTitle("TSLibrary — Administration")
        self.setMinimumSize(1000, 680)
        self.resize(1320, 850)
        self.setStyleSheet(load_stylesheets("base", "admin"))
        self.setWindowIcon(admin_icon("library", "#c9b18c"))
        self.licenses_page = LicensesPage(self.session.items)
        self.applications_page = ApplicationsPage(self.session.applications)
        self.phone_apps_page = PhoneAppsPage(self.session.phone_apps)
        self.websites_page = WebsitesPage(self.session.websites)
        self.full_library_page = LibraryPage(session=self.session)
        self.pages = {
            "Full library": self.full_library_page,
            "Licenses": self.licenses_page,
            "Applications": self.applications_page,
            "Phone apps": self.phone_apps_page,
            "Websites": self.websites_page,
        }
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = AdminSidebar(self.pages)
        self.sidebar.page_requested.connect(self.set_page)
        self.sidebar.back_requested.connect(self.back_requested.emit)
        root.addWidget(self.sidebar)
        self.page_stack = QStackedWidget()
        for page in self.pages.values():
            self.page_stack.addWidget(page)
        root.addWidget(self.page_stack, 1)
        self._inventory_sort_index = 0
        self.set_page(self.LICENSES_PAGE)

    @property
    def current_page(self):
        return self.page_stack.currentWidget()

    def set_page(self, name):
        page = self.pages[name]
        # Inventory tabs share their name/recent sort. The combined library has
        # its own sort options, so keep that choice independent of these tabs.
        if self.current_page is not self.full_library_page:
            self._inventory_sort_index = self.current_page.sort_select.currentIndex()
        if page is not self.full_library_page:
            page.sort_select.setCurrentIndex(self._inventory_sort_index)
        self.sidebar.nav_buttons[name].setChecked(True)
        self.page_stack.setCurrentWidget(page)
        page.search.clear()
        page.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 26 if self.width() < 1150 else 38
        for page in self.pages.values():
            page.content_layout.setContentsMargins(margin, 30, margin, 23)
