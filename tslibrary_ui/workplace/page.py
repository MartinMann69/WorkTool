"""Collection chooser and user workplace pages, with shared responsive cards."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLineEdit, QStackedWidget, QVBoxLayout, QWidget,
)

from ..graphics.icons import admin_icon
from ..graphics.shelf import ShelfArtwork
from ..library.models import CatalogModel, filter_entries
from ..shared.controls import FilterCombo
from ..shared.forms import action, caption
from .models import collection_entries, workplace_entries, entry_key
from .collection import CollectionGrid, CollectionModel
from .selection import SelectionSidebar
from .cards import WorkplaceGrid


class WorkplacePage(QWidget):
    add_personal_requested = Signal(str)
    browse_requested = Signal()
    refresh_requested = Signal()
    toggle_requested = Signal(object)
    edit_requested = Signal(object)
    remove_requested = Signal(object)
    open_requested = Signal(object)
    context_requested = Signal(object, object)
    view_requested = Signal(str)

    def __init__(self, kind, session, config, parent=None):
        super().__init__(parent)
        self.kind, self.session, self.config = kind, session, config
        self.collection = kind == "collection"
        self.setObjectName("workplacePage")
        singular = "website" if kind == "websites" else "application"
        root = QVBoxLayout(self)
        self.content_layout = root
        root.setContentsMargins(0, 27, 0, 0)
        root.setSpacing(0)
        root.addWidget(caption("THE SHARED CATALOG" if self.collection else "YOUR EVERYDAY WORKPLACE",
                               "workplaceEyebrow", wrap=False))
        root.addSpacing(9)
        title = QHBoxLayout()
        self.heading = caption("The collection." if self.collection else f"Your {kind}.",
                               "workplaceHeading", wrap=False)
        title.addWidget(self.heading, 1)
        self.add_button = action("Refresh collection" if self.collection else f"Add personal {singular}",
                                 "workplaceSecondary")
        self.add_button.setIcon(admin_icon("library" if self.collection else "plus"))
        if self.collection:
            self.add_button.clicked.connect(self.refresh_requested.emit)
        else:
            self.add_button.clicked.connect(lambda: self.add_personal_requested.emit(self.kind))
        title.addWidget(self.add_button)
        root.addLayout(title)
        root.addSpacing(9)
        description = ("Choose the team's apps and websites you want in your workplace."
                       if self.collection else "Your useful links, ready when you are."
                       if kind == "websites" else "Your everyday tools, just one click away.")
        root.addWidget(caption(description, "workplaceDescription"))
        root.addSpacing(23)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        self.search = QLineEdit()
        self.search.setObjectName("workplaceSearch")
        self.search.setPlaceholderText("Search the collection…" if self.collection else f"Search your {kind}…")
        self.search.setAccessibleName(self.search.placeholderText().replace("…", ""))
        self.search.setMinimumWidth(80)
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(43)
        toolbar.addWidget(self.search, 1)
        self.type_filter = FilterCombo(self)
        self.type_filter.addItem("All types", "")
        self.type_filter.addItem("Websites", "websites")
        self.type_filter.addItem("Applications", "applications")
        self.type_filter.setAccessibleName("Collection resource type")
        self.type_filter.setFixedSize(145, 43)
        self.type_filter.setVisible(self.collection)
        toolbar.addWidget(self.type_filter)
        self.sort_select = FilterCombo()
        self.sort_select.addItem("Name: A to Z", "name_asc")
        self.sort_select.addItem("Name: Z to A", "name_desc")
        self.sort_select.setAccessibleName("Sort workplace entries")
        self.sort_select.setFixedSize(155, 43)
        toolbar.addWidget(self.sort_select)
        root.addLayout(toolbar)
        root.addSpacing(12)
        status = QHBoxLayout()
        status.setSpacing(10)
        self.count_label = caption("", "workplaceMuted", wrap=False)
        status.addWidget(self.count_label)
        status.addStretch()
        self.group_filter = FilterCombo(self)
        self.group_filter.setAccessibleName("Filter workplace group")
        self.group_filter.setFixedSize(150, 33)
        self.group_filter.setVisible(not self.collection)
        status.addWidget(self.group_filter)
        self.view_select = FilterCombo()
        self.view_select.addItem("Cards", "cards")
        self.view_select.addItem("List", "list")
        self.view_select.setAccessibleName("Workplace view")
        self.view_select.setFixedSize(85, 33)
        status.addWidget(self.view_select)
        self.browse_button = action("Choose from Collection", "workplaceLink", parent=self)
        self.browse_button.setMinimumHeight(25)
        self.browse_button.setVisible(not self.collection)
        self.browse_button.clicked.connect(self.browse_requested.emit)
        status.addWidget(self.browse_button)
        root.addLayout(status)
        root.addSpacing(12)

        self.model = CollectionModel(self) if self.collection else CatalogModel(self)
        self.grid = CollectionGrid() if self.collection else WorkplaceGrid()
        self.grid.setAccessibleName("Collection entries" if self.collection else f"Your {kind}")
        if self.collection:
            self.model.toggle_requested.connect(self.toggle_requested.emit)
        else:
            self.grid.open_requested.connect(self.open_requested.emit)
            self.grid.edit_requested.connect(self.edit_requested.emit)
            self.grid.remove_requested.connect(self.remove_requested.emit)
            self.grid.context_requested.connect(self.context_requested.emit)
        self.grid.setModel(self.model)
        self.grid.activated.connect(self._activated)
        self.empty_state = QFrame()
        self.empty_state.setObjectName("workplaceEmpty")
        empty = QVBoxLayout(self.empty_state)
        empty.setContentsMargins(24, 24, 24, 24)
        empty.addStretch()
        empty.addWidget(ShelfArtwork(), 0, Qt.AlignmentFlag.AlignHCenter)
        self.empty_heading = caption("", "workplaceEmptyHeading")
        self.empty_description = caption("", "workplaceDescription")
        for widget in (self.empty_heading, self.empty_description):
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.addWidget(widget)
        self.empty_button = action("Choose from Collection", "workplaceSecondary", parent=self.empty_state)
        self.empty_button.setVisible(not self.collection)
        self.empty_button.clicked.connect(self.browse_requested.emit)
        empty.addWidget(self.empty_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addStretch()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.grid)
        self.stack.addWidget(self.empty_state)
        if self.collection:
            self.selection_sidebar = SelectionSidebar()
            self.selection_sidebar.remove_requested.connect(self.remove_requested.emit)
            body = QHBoxLayout()
            body.setContentsMargins(0, 0, 0, 0)
            body.setSpacing(18)
            body.addWidget(self.stack, 1)
            body.addWidget(self.selection_sidebar)
            root.addLayout(body, 1)
        else:
            root.addWidget(self.stack, 1)

        self.search.textChanged.connect(self.refresh)
        self.type_filter.currentIndexChanged.connect(self.refresh)
        self.sort_select.currentIndexChanged.connect(self.refresh)
        self.group_filter.currentIndexChanged.connect(self.refresh)
        self.view_select.currentIndexChanged.connect(lambda: self.view_requested.emit(self.view_select.currentData()))
        self.search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.search_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.search_shortcut.activated.connect(self.search.setFocus)
        self.refresh()

    def selected_entry(self):
        return self.grid.currentIndex().data(Qt.ItemDataRole.UserRole)

    def refresh(self, *_):
        selected = self.selected_entry()
        view_key = (self.search.text(), self.type_filter.currentData(), self.sort_select.currentData())
        scroll = self.grid.verticalScrollBar().value() if view_key == getattr(self, "_view_key", None) else 0
        self._view_key = view_key
        entries = (collection_entries(self.session, self.config) if self.collection
                   else workplace_entries(self.session, self.config, self.kind))
        if self.collection:
            self.selection_sidebar.refresh(entries)
        visible = filter_entries(entries, self.search.text(), self.type_filter.currentData()
                                 if self.collection else "", self.sort_select.currentData())
        if not self.collection:
            choice = self.group_filter.currentData()
            self.group_filter.blockSignals(True)
            self.group_filter.clear()
            self.group_filter.addItem("All groups", "")
            self.group_filter.addItem("Favorites", "favorites")
            for name in sorted(self.config.groups, key=str.casefold):
                self.group_filter.addItem(name, "group:" + name)
            index = self.group_filter.findData(choice)
            self.group_filter.setCurrentIndex(max(0, index))
            self.group_filter.blockSignals(False)
            choice = self.group_filter.currentData() or ""
            allowed = (set(self.config.favorites) if choice == "favorites" else
                       set(self.config.groups.get(choice[6:], [])) if choice.startswith("group:") else None)
            if allowed is not None:
                visible = [entry for entry in visible if entry_key(entry) in allowed]
            visible.sort(key=lambda entry: not entry.favorite)
        self.view_select.blockSignals(True)
        self.view_select.setCurrentIndex(1 if self.config.view_mode == "list" else 0)
        self.view_select.blockSignals(False)
        self.grid.set_dense(self.config.view_mode == "list")
        self.model.replace(visible)
        self.count_label.setText(f"{len(visible)} of {len(entries)} {'available' if self.collection else 'in your workplace'}")
        self.stack.setCurrentWidget(self.grid if visible else self.empty_state)
        if entries:
            self.empty_heading.setText("No matches this time.")
            self.empty_description.setText("Try a different search or resource type.")
        elif self.collection:
            self.empty_heading.setText("A little room for your tools.")
            self.empty_description.setText("Apps and websites added by your administrator will appear here.")
        else:
            self.empty_heading.setText(f"Make room for your {self.kind}.")
            self.empty_description.setText("Choose from the Collection, or add a personal entry above.")
        self.empty_button.setVisible(not self.collection and not entries)
        if selected:
            for row, entry in enumerate(visible):
                if (entry.id, entry.source, entry.kind) == (selected.id, selected.source, selected.kind):
                    self.grid.setCurrentIndex(self.model.index(row, 0))
                    break
        self.grid.doItemsLayout()
        self.grid.verticalScrollBar().setValue(scroll)

    def _emit_selection(self, signal):
        entry = self.selected_entry()
        if entry:
            signal.emit(entry)

    def _activated(self, _index):
        if not self.collection:
            self._emit_selection(self.open_requested)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.collection and hasattr(self, "selection_sidebar"):
            self.selection_sidebar.setFixedWidth(220 if self.width() < 1000 else 260)
