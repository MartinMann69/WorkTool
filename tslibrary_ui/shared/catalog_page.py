"""Shared admin page layout: heading, search, filters, empty state, and table.

Feature pages provide their copy, columns, row actions, and refresh behavior.
No application, website, or license data is owned by this layout.
"""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget, QTableWidget,
    QVBoxLayout, QWidget,
)

from ..graphics.icons import admin_icon
from ..graphics.shelf import ShelfArtwork
from .controls import FilterCombo
from .forms import caption
from .tables import setup_table


class CatalogPage(QWidget):
    """Common layout for admin inventory pages."""

    add_requested = Signal()
    title = ""
    description = ""
    empty_title = ""
    empty_description_text = ""
    add_text = ""
    empty_action = ""
    search_text = ""
    headers = ()
    has_categories = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("adminMain")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(38, 30, 38, 23)
        self.content_layout.setSpacing(0)
        self._build_header()
        self._build_toolbar()
        self._build_content()
        self._build_footer()
        self.search.textChanged.connect(self.refresh)
        self.category_filter.currentTextChanged.connect(self.refresh)
        self.sort_select.currentIndexChanged.connect(self.refresh)

    def _build_header(self):
        top = QHBoxLayout()
        self.breadcrumb = caption(f"ADMINISTRATION  /  {self.title.upper()}", "adminEyebrow", wrap=False)
        top.addWidget(self.breadcrumb)
        top.addStretch()
        top.addWidget(caption("ADMINISTRATOR", "adminBadge", wrap=False))
        self.content_layout.addLayout(top)
        self.content_layout.addSpacing(36)
        heading = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(9)
        self.heading = caption(self.title, "adminHeading", wrap=False)
        self.subtitle = caption(self.description)
        title_block.addWidget(self.heading)
        title_block.addWidget(self.subtitle)
        heading.addLayout(title_block, 1)
        heading.addSpacing(16)
        self.add_button = QPushButton("  " + self.add_text)
        self.add_button.setObjectName("adminPrimary")
        self.add_button.setIcon(admin_icon("plus", "#20251c"))
        self.add_button.setFixedHeight(43)
        self.add_button.setMinimumWidth(126)
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(self.add_requested.emit)
        heading.addWidget(self.add_button)
        self.content_layout.addLayout(heading)
        self.content_layout.addSpacing(30)

    def _build_toolbar(self):
        self.toolbar = QWidget()
        toolbar = QHBoxLayout(self.toolbar)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(12)
        search_shell = QFrame()
        search_shell.setObjectName("adminSearchShell")
        search_shell.setFixedHeight(42)
        search_layout = QHBoxLayout(search_shell)
        search_layout.setContentsMargins(12, 0, 10, 0)
        search_symbol = QLabel()
        search_symbol.setPixmap(admin_icon("search").pixmap(QSize(18, 18)))
        search_layout.addWidget(search_symbol)
        self.search = QLineEdit()
        self.search.setAccessibleName(self.search_text)
        self.search.setPlaceholderText(self.search_text)
        self.search.setMinimumWidth(80)
        self.search.setClearButtonEnabled(True)
        search_layout.addWidget(self.search, 1)
        toolbar.addWidget(search_shell, 1)
        self.category_filter = FilterCombo()
        self.category_filter.setAccessibleName("Category filter")
        self.category_filter.addItem("All categories")
        self.category_filter.setFixedSize(154, 42)
        self.category_filter.setVisible(self.has_categories)
        toolbar.addWidget(self.category_filter)
        self.sort_select = FilterCombo()
        self.sort_select.setAccessibleName("Sort order")
        self.sort_select.addItems(["Recently added", "Name: A to Z"])
        self.sort_select.setFixedSize(154, 42)
        toolbar.addWidget(self.sort_select)
        self.content_layout.addWidget(self.toolbar)
        self.content_layout.addSpacing(20)

    def _build_content(self):
        self.empty_state = QFrame()
        self.empty_state.setObjectName("adminEmptyState")
        empty = QVBoxLayout(self.empty_state)
        empty.setContentsMargins(24, 24, 24, 24)
        empty.setSpacing(0)
        empty.addStretch(2)
        empty.addWidget(ShelfArtwork(), 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addSpacing(18)
        self.empty_heading = caption(self.empty_title, "emptyHeading")
        self.empty_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(self.empty_heading)
        empty.addSpacing(10)
        self.empty_description = caption(self.empty_description_text)
        self.empty_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(self.empty_description)
        empty.addSpacing(23)
        self.empty_button = QPushButton(self.empty_action)
        self.empty_button.setObjectName("emptyAction")
        self.empty_button.setFixedHeight(40)
        self.empty_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.empty_button.clicked.connect(self.add_requested.emit)
        empty.addWidget(self.empty_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addStretch(3)
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.empty_state)
        self.table = QTableWidget()
        setup_table(self.table, self.headers)
        self.table.verticalHeader().setDefaultSectionSize(72)
        self.content_stack.addWidget(self.table)
        self.content_layout.addWidget(self.content_stack, 1)
        self.content_layout.addSpacing(18)

    def _build_footer(self):
        bottom = QHBoxLayout()
        self.count_label = caption("", "adminMuted", wrap=False)
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        bottom.addWidget(caption("SESSION PREVIEW · NOT SAVED", "adminEyebrow", wrap=False))
        self.content_layout.addLayout(bottom)

    def refresh(self, *_):
        """Feature pages populate their own rows, empty state, and totals."""
        raise NotImplementedError
