"""Reusable read-only library page for administration and the public window."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..graphics.brand import BrandMark
from ..graphics.icons import admin_icon
from ..graphics.shelf import ShelfArtwork
from ..shared.controls import FilterCombo
from ..shared.forms import caption
from ..state import LibrarySession
from ..styles import load_stylesheets
from .cards import CatalogGrid
from .models import CatalogModel, KINDS, catalog_entries, filter_entries


class LibraryPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None, *, session=None, standalone=False):
        super().__init__(parent)
        self.session = session if session is not None else LibrarySession()
        self.standalone = standalone
        self.setObjectName("libraryWindow" if standalone else "libraryPage")
        self.setStyleSheet(load_stylesheets("base", "library"))
        self.content_layout = QVBoxLayout(self)
        if standalone:
            self.content_layout.setContentsMargins(42, 25, 28, 24)
        else:
            self.content_layout.setContentsMargins(38, 30, 24, 23)
        self.content_layout.setSpacing(0)
        self._build_header()
        self._build_summary()
        self._build_toolbar()
        self._build_content()
        self.search.textChanged.connect(self.refresh)
        self.type_filter.currentIndexChanged.connect(self.refresh)
        self.sort_select.currentIndexChanged.connect(self.refresh)
        self.search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.search_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.search_shortcut.activated.connect(self._focus_search)
        self.refresh()

    def _build_header(self):
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 14, 0)
        if self.standalone:
            top.addWidget(BrandMark())
            top.addStretch()
            top.addWidget(caption("THE TEAM COLLECTION", "libraryEyebrow", wrap=False))
            top.addSpacing(24)
            self.back_button = QPushButton("  Back to welcome")
            self.back_button.setObjectName("libraryBack")
            self.back_button.setIcon(admin_icon("back"))
            self.back_button.setFixedHeight(38)
            self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.back_button.clicked.connect(self.back_requested.emit)
            top.addWidget(self.back_button)
        else:
            top.addWidget(caption("ADMINISTRATION  /  FULL LIBRARY", "libraryEyebrow", wrap=False))
            top.addStretch()
            top.addWidget(caption("COLLECTION OVERVIEW", "libraryEyebrow", wrap=False))
        self.content_layout.addLayout(top)
        self.content_layout.addSpacing(31 if self.standalone else 36)
        self.heading = caption("Your library." if self.standalone else "Full library", "libraryHeading", wrap=False)
        self.content_layout.addWidget(self.heading)
        self.content_layout.addSpacing(8)
        self.content_layout.addWidget(caption("The tools, sites and apps we use. All in one place.", "libraryDescription"))
        self.content_layout.addSpacing(25)

    def _build_summary(self):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 14, 0)
        row.setSpacing(12)
        self.type_counts = {}
        for kind, (name, _, color) in KINDS.items():
            tile = QFrame()
            tile.setObjectName("libraryStat")
            tile.setFixedHeight(76 if self.standalone else 70)
            layout = QHBoxLayout(tile)
            layout.setContentsMargins(13, 10, 11, 10)
            layout.setSpacing(10)
            symbol = QLabel()
            symbol.setPixmap(admin_icon("licenses" if kind == "licenses" else kind.replace("_", " "), color).pixmap(QSize(24, 24)))
            layout.addWidget(symbol)
            text = QVBoxLayout()
            text.setSpacing(3)
            count = caption("0", "libraryStatNumber", wrap=False)
            self.type_counts[kind] = count
            text.addWidget(count)
            text.addWidget(caption(name, "libraryStatLabel", wrap=False))
            layout.addLayout(text, 1)
            row.addWidget(tile, 1)
        self.content_layout.addLayout(row)
        self.content_layout.addSpacing(25)

    def _build_toolbar(self):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 14, 0)
        row.setSpacing(12)
        search_shell = QFrame()
        search_shell.setObjectName("librarySearch")
        search_shell.setFixedHeight(44)
        search_layout = QHBoxLayout(search_shell)
        search_layout.setContentsMargins(14, 0, 12, 0)
        symbol = QLabel()
        symbol.setPixmap(admin_icon("search").pixmap(QSize(18, 18)))
        search_layout.addWidget(symbol)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the collection…")
        self.search.setAccessibleName("Search library by name or details")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(100)
        search_layout.addWidget(self.search, 1)
        row.addWidget(search_shell, 1)
        self.type_filter = FilterCombo()
        self.type_filter.setAccessibleName("Resource type")
        self.type_filter.addItem("All types", "")
        for kind, (name, _, _) in KINDS.items():
            self.type_filter.addItem(name, kind)
        self.type_filter.setFixedSize(165, 44)
        row.addWidget(self.type_filter)
        self.sort_select = FilterCombo()
        self.sort_select.setAccessibleName("Sort library")
        for name, value in [("Name: A to Z", "name_asc"), ("Name: Z to A", "name_desc"),
                            ("Type, then name", "type")]:
            self.sort_select.addItem(name, value)
        self.sort_select.setFixedSize(175, 44)
        row.addWidget(self.sort_select)
        self.content_layout.addLayout(row)
        self.content_layout.addSpacing(13)
        status = QHBoxLayout()
        status.setContentsMargins(0, 0, 14, 0)
        self.count_label = caption("", "libraryMuted", wrap=False)
        status.addWidget(self.count_label)
        status.addStretch()
        self.clear_button = QPushButton("Clear filters")
        self.clear_button.setObjectName("libraryClear")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear_filters)
        status.addWidget(self.clear_button)
        self.content_layout.addLayout(status)
        self.content_layout.addSpacing(12)

    def _build_content(self):
        self.model = CatalogModel(self)
        self.grid = CatalogGrid()
        self.grid.setModel(self.model)
        self.grid.selectionModel().currentChanged.connect(self._show_details)
        self.empty_state = QFrame()
        self.empty_state.setObjectName("libraryEmpty")
        layout = QVBoxLayout(self.empty_state)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)
        layout.addStretch()
        layout.addWidget(ShelfArtwork(), 0, Qt.AlignmentFlag.AlignHCenter)
        self.empty_heading = caption("", "libraryEmptyHeading")
        self.empty_description = caption("", "libraryDescription")
        for widget in (self.empty_heading, self.empty_description):
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(widget)
        layout.addStretch()
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.grid)
        self.content_stack.addWidget(self.empty_state)
        self.content_layout.addWidget(self.content_stack, 1)
        self.content_layout.addSpacing(10)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 14, 0)
        self.detail_label = caption("Select an item to see its details.", "libraryMuted", wrap=False)
        self.detail_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        footer.addWidget(self.detail_label, 1)
        footer.addSpacing(15)
        footer.addWidget(caption("Managed by your administrator" if self.standalone else "All inventories · one collection", "libraryMuted", wrap=False))
        self.content_layout.addLayout(footer)

    def refresh(self, *_):
        entries = catalog_entries(self.session)
        for kind, label in self.type_counts.items():
            label.setText(str(sum(entry.kind == kind for entry in entries)))
        visible = filter_entries(entries, self.search.text(), self.type_filter.currentData(),
                                 self.sort_select.currentData())
        self.model.replace(visible)
        self.count_label.setText(f"{len(visible)} of {len(entries)} resources")
        filtered = bool(self.search.text() or self.type_filter.currentData())
        self.clear_button.setEnabled(filtered)
        self.detail_label.setText("Select an item to see its details.")
        self.detail_label.setToolTip("")
        self.content_stack.setCurrentWidget(self.grid if visible else self.empty_state)
        self.empty_heading.setText("No matches this time." if entries else "A little room for your tools.")
        self.empty_description.setText("Try a different search or clear your filters." if entries
                                       else "Items added by your administrator will appear here.")

    def clear_filters(self):
        self.search.blockSignals(True)
        self.type_filter.blockSignals(True)
        self.search.clear()
        self.type_filter.setCurrentIndex(0)
        self.search.blockSignals(False)
        self.type_filter.blockSignals(False)
        self.refresh()

    def _show_details(self, current, _previous):
        entry = current.data(Qt.ItemDataRole.UserRole)
        text = f"{entry.name} · {entry.type_label} · {entry.detail}" if entry else "Select an item to see its details."
        self.detail_label.setText(text)
        self.detail_label.setToolTip(text)

    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self.search.setFocus()
