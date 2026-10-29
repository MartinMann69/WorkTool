"""Admin-only editor field, link picker, and per-row navigation buttons."""

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFrame, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QTabWidget, QToolButton, QVBoxLayout,
)

from ..graphics.icons import admin_icon
from ..relationships import ENTRY_TYPES, EntryRef, catalog_entries, related_entries
from ..shared.forms import action, caption
from ..documentation.picker import DocumentationPicker


def entry_details(ref, entry):
    return (getattr(entry, "launch_target", "") or getattr(entry, "url", "")
            or getattr(entry, "category", "") or ENTRY_TYPES[ref.kind][0])


def materialize_documentation(session, selected, pending):
    """Register selected draft paths only when the owning item is saved."""
    refs = set(selected)
    by_path = {entry.name.casefold(): entry for entry in session.documentation.items}
    for entry in pending.values():
        ref = EntryRef("documentation", entry.id)
        if ref not in refs:
            continue
        existing = by_path.get(entry.name.casefold())
        if existing is None:
            session.documentation.items.append(entry)
            by_path[entry.name.casefold()] = entry
        elif existing.id != entry.id:
            refs.discard(ref)
            refs.add(EntryRef("documentation", existing.id))
    return refs


class RelatedEntriesDialog(QDialog):
    """Stage checkboxes locally; the owner applies them only after Save."""

    def __init__(self, session, source, parent=None, *, selected=None, name=None, pending=()):
        super().__init__(parent)
        self.source = source
        self.session = session
        self._selected = set(related_entries(session, source) if selected is None else selected)
        self.pending_documentation = {entry.id: entry for entry in pending}
        self.separate_documentation = (source.kind if source is not None else getattr(parent, "entry_kind", "")) != "documentation"
        entries = catalog_entries(session)
        name = name or (entries[source].name if source in entries else "New item")
        self.setObjectName("inventoryDialog")
        self.setWindowTitle(f"Related entries — {name}")
        self.setMinimumSize(570, 460)
        if self.separate_documentation:
            self.resize(720, 680)
        else:
            self.resize(660, 570)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(14)
        layout.addWidget(caption("CONNECT YOUR LIBRARY", "adminEyebrow"))
        layout.addWidget(caption(name, "dialogHeading"))
        layout.addWidget(caption("Choose the entries linked directly to this item. Each connection works both ways."))
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("dialogInput")
        self.search.setPlaceholderText("Search entries by name or details")
        self.search.setAccessibleName("Search entries to link")
        self.search.setClearButtonEnabled(True)
        filters.addWidget(self.search, 1)
        self.type_filter = QComboBox()
        self.type_filter.setAccessibleName("Related entry type")
        self.type_filter.addItem("All types", "")
        for kind, (label, _) in ENTRY_TYPES.items():
            if kind != "documentation" or not self.separate_documentation:
                self.type_filter.addItem(label, kind)
        self.type_filter.setMinimumHeight(42)
        filters.addWidget(self.type_filter)
        layout.addLayout(filters)
        self.entries_list = QListWidget()
        self.entries_list.setObjectName("relatedPicker")
        self.entries_list.setAccessibleName("Existing catalog entries; check to link")
        self.entries_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.entries_list.setWordWrap(True)
        for ref, target in sorted(entries.items(), key=lambda pair: (
                pair[0].kind, pair[1].name.casefold(), pair[0].id)):
            if ref == source or (ref.kind == "documentation" and self.separate_documentation):
                continue
            details = entry_details(ref, target)
            row = QListWidgetItem(f"{ENTRY_TYPES[ref.kind][0]}  ·  {target.name}\n{details}")
            row.setData(Qt.ItemDataRole.UserRole, ref)
            row.setToolTip(f"{target.name}\n{details}\nID: {ref.id}")
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked if ref in self._selected else Qt.CheckState.Unchecked)
            self.entries_list.addItem(row)
        self.documentation_picker = None
        self.tabs = None
        if self.separate_documentation:
            self.tabs = QTabWidget()
            self.tabs.setObjectName("relatedTabs")
            self.tabs.addTab(self.entries_list, "Library entries")
            self.documentation_picker = DocumentationPicker(session.documentation, self._selected, pending, self)
            self.documentation_picker.selection_changed.connect(self.set_ref_checked)
            self.tabs.addTab(self.documentation_picker, "Documentation")
            self.tabs.currentChanged.connect(self._tab_changed)
            layout.addWidget(self.tabs, 1)
        else:
            layout.addWidget(self.entries_list, 1)
        self.summary = caption("", "adminMuted")
        layout.addWidget(self.summary)
        buttons = QHBoxLayout()
        self.cancel_button = action("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()
        self.save_button = action("Use selection", "adminPrimary")
        self.save_button.clicked.connect(self.accept)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.search.textChanged.connect(self.filter_entries)
        self.type_filter.currentIndexChanged.connect(self.filter_entries)
        self.entries_list.itemChanged.connect(self._selection_changed)
        self.filter_entries()

    def selected_refs(self):
        return set(self._selected)

    def _tab_changed(self, *_):
        documentation = self.tabs.currentIndex() == 1
        self.type_filter.setVisible(not documentation)
        self.search.setPlaceholderText("Search documentation folders and files" if documentation else "Search entries by name or details")
        self.filter_entries()

    def filter_entries(self, *_):
        query, kind = self.search.text().strip().casefold(), self.type_filter.currentData()
        visible = 0
        for index in range(self.entries_list.count()):
            row = self.entries_list.item(index)
            ref = row.data(Qt.ItemDataRole.UserRole)
            show = (not kind or kind == ref.kind) and query in row.text().casefold()
            row.setHidden(not show)
            visible += show
        if self.documentation_picker is not None:
            self.documentation_picker.search(self.search.text() if self.tabs.currentIndex() == 1 else "")
        if self.tabs is not None and self.tabs.currentIndex() == 1:
            docs = sum(ref.kind == "documentation" for ref in self._selected)
            self.summary.setText(f"{len(self._selected)} selected · {docs} documentation files/folders")
            return
        self.summary.setText(f"{len(self.selected_refs())} selected · {visible} matching entries" if visible
                             else f"{len(self.selected_refs())} selected · No matching entries. Try another search or type.")

    def _selection_changed(self, row):
        ref = row.data(Qt.ItemDataRole.UserRole)
        self.set_ref_checked(ref, row.checkState() == Qt.CheckState.Checked)

    def set_ref_checked(self, ref, checked):
        if ref == self.source:
            return
        if checked:
            self._selected.add(ref)
        else:
            self._selected.discard(ref)
        with QSignalBlocker(self.entries_list):
            for index in range(self.entries_list.count()):
                candidate = self.entries_list.item(index)
                candidate.setCheckState(Qt.CheckState.Checked if candidate.data(Qt.ItemDataRole.UserRole) in self._selected else Qt.CheckState.Unchecked)
        if self.documentation_picker is not None:
            self.pending_documentation.update(self.documentation_picker.pending)
            self.documentation_picker.set_selected(self._selected)
        self.filter_entries()


class RelatedEntriesEditor(QFrame):
    """Draft link choices belong to the item editor until its Save succeeds."""

    def __init__(self, session, source, dialog):
        super().__init__(dialog)
        self.session, self.source, self.dialog = session, source, dialog
        self.selected_refs = set(related_entries(session, source))
        self.pending_documentation = {}
        self.picker = None
        self.setObjectName("relatedEntriesEditor")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        header = QHBoxLayout()
        header.addWidget(caption("Related entries (optional)", "fieldLabel"), 1)
        self.choose_button = action("Choose entries…")
        self.choose_button.setIcon(admin_icon("links"))
        self.choose_button.setMinimumHeight(32)
        self.choose_button.clicked.connect(self.choose_entries)
        header.addWidget(self.choose_button)
        layout.addLayout(header)
        self.summary = caption("", "adminMuted")
        layout.addWidget(self.summary)
        dialog.finished.connect(self.close_picker)
        self.refresh()

    def choose_entries(self):
        if self.picker is not None:
            self.picker.deleteLater()
        picker = RelatedEntriesDialog(self.session, self.source, self.dialog,
                                      selected=self.selected_refs, name=self.dialog.name_edit.text().strip(),
                                      pending=self.pending_documentation.values())
        self.picker = picker
        picker.accepted.connect(lambda: self._use_selection(picker))
        picker.open()

    def _use_selection(self, picker):
        self.selected_refs = picker.selected_refs()
        self.pending_documentation = {identifier: entry for identifier, entry in picker.pending_documentation.items()
                                      if EntryRef("documentation", identifier) in self.selected_refs}
        self.refresh()

    def close_picker(self, *_):
        if self.picker is not None and self.picker.isVisible():
            self.picker.reject()

    def refresh(self):
        entries = catalog_entries(self.session)
        entries.update({EntryRef("documentation", entry.id): entry for entry in self.pending_documentation.values()})
        selected = [ref for ref in self.selected_refs if ref in entries]
        types = [label for kind, (label, _) in ENTRY_TYPES.items() if any(ref.kind == kind for ref in selected)]
        self.summary.setText(f"{len(selected)} related · {', '.join(types)}. Saved with this item."
                             if selected else "Connect apps, websites, licenses, or documentation. Saved with this item.")
        self.summary.setToolTip("\n".join(entries[ref].name for ref in sorted(selected)))


def row_links_button(session, source, navigate, parent):
    """One link opens directly; several offer a menu with typed destinations."""
    refs = related_entries(session, source)
    if not refs:
        return None
    entries = catalog_entries(session)
    button = QToolButton(parent)
    button.setObjectName("relatedLinksButton")
    button.setIcon(admin_icon("links", "#d6c4a2"))
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setText(str(len(refs)))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedSize(64, 34)
    button.source = source
    button.target_refs = refs
    button.setAccessibleName(f"Related entries for {entries[source].name}: {len(refs)}")
    button.setToolTip("\n".join(f"{ENTRY_TYPES[ref.kind][0]}: {entries[ref].name}" for ref in refs))
    if len(refs) == 1:
        button.clicked.connect(lambda: navigate(refs[0]))
    else:
        menu = QMenu(button)
        for ref in refs:
            label, page_name = ENTRY_TYPES[ref.kind]
            item = menu.addAction(admin_icon(page_name.lower()), f"{label}: {entries[ref].name}".replace("&", "&&"))
            item.triggered.connect(lambda checked=False, target=ref: navigate(target))
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setProperty("multiple", True)
    return button
