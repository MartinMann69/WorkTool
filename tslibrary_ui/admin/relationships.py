"""Admin-only editor field, link picker, and per-row navigation buttons."""

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFrame, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QToolButton, QVBoxLayout,
)

from ..graphics.icons import admin_icon
from ..relationships import ENTRY_TYPES, catalog_entries, related_entries
from ..shared.forms import action, caption


def entry_details(ref, entry):
    return (getattr(entry, "launch_target", "") or getattr(entry, "url", "")
            or getattr(entry, "category", "") or ENTRY_TYPES[ref.kind][0])


class RelatedEntriesDialog(QDialog):
    """Stage checkboxes locally; the owner applies them only after Save."""

    def __init__(self, session, source, parent=None, *, selected=None, name=None):
        super().__init__(parent)
        self.source = source
        self.original_group = {source, *related_entries(session, source)}
        self.session = session
        entries = catalog_entries(session)
        name = name or (entries[source].name if source in entries else "New item")
        self.setObjectName("inventoryDialog")
        self.setWindowTitle(f"Related entries — {name}")
        self.setMinimumSize(570, 460)
        self.resize(660, 570)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(14)
        layout.addWidget(caption("CONNECT YOUR LIBRARY", "adminEyebrow"))
        layout.addWidget(caption(name, "dialogHeading"))
        layout.addWidget(caption("Connected entries form one group: each member can reach all the others. Uncheck an entry to separate it from this group."))
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
            self.type_filter.addItem(label, kind)
        self.type_filter.setMinimumHeight(42)
        filters.addWidget(self.type_filter)
        layout.addLayout(filters)
        self.entries_list = QListWidget()
        self.entries_list.setObjectName("relatedPicker")
        self.entries_list.setAccessibleName("Existing catalog entries; check to link")
        self.entries_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.entries_list.setWordWrap(True)
        selected = set(related_entries(session, source) if selected is None else selected)
        for ref, target in sorted(entries.items(), key=lambda pair: (
                pair[0].kind, pair[1].name.casefold(), pair[0].id)):
            if ref == source:
                continue
            details = entry_details(ref, target)
            row = QListWidgetItem(f"{ENTRY_TYPES[ref.kind][0]}  ·  {target.name}\n{details}")
            row.setData(Qt.ItemDataRole.UserRole, ref)
            row.setToolTip(f"{target.name}\n{details}\nID: {ref.id}")
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked if ref in selected else Qt.CheckState.Unchecked)
            self.entries_list.addItem(row)
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
        return {self.entries_list.item(index).data(Qt.ItemDataRole.UserRole)
                for index in range(self.entries_list.count())
                if self.entries_list.item(index).checkState() == Qt.CheckState.Checked}

    def filter_entries(self, *_):
        query, kind = self.search.text().strip().casefold(), self.type_filter.currentData()
        visible = 0
        for index in range(self.entries_list.count()):
            row = self.entries_list.item(index)
            ref = row.data(Qt.ItemDataRole.UserRole)
            show = (not kind or kind == ref.kind) and query in row.text().casefold()
            row.setHidden(not show)
            visible += show
        self.summary.setText(f"{len(self.selected_refs())} selected · {visible} matching entries" if visible
                             else f"{len(self.selected_refs())} selected · No matching entries. Try another search or type.")

    def _selection_changed(self, row):
        ref = row.data(Qt.ItemDataRole.UserRole)
        if row.checkState() == Qt.CheckState.Checked and ref not in self.original_group:
            # Show the whole group being joined, including entries hidden by a
            # search/type filter. Further unchecking can split off any member.
            group = set(related_entries(self.session, ref))
            with QSignalBlocker(self.entries_list):
                for index in range(self.entries_list.count()):
                    candidate = self.entries_list.item(index)
                    if candidate.data(Qt.ItemDataRole.UserRole) in group:
                        candidate.setCheckState(Qt.CheckState.Checked)
        self.filter_entries()


class RelatedEntriesEditor(QFrame):
    """Draft link choices belong to the item editor until its Save succeeds."""

    def __init__(self, session, source, dialog):
        super().__init__(dialog)
        self.session, self.source, self.dialog = session, source, dialog
        self.selected_refs = set(related_entries(session, source))
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
                                      selected=self.selected_refs, name=self.dialog.name_edit.text().strip())
        self.picker = picker
        picker.accepted.connect(lambda: self._use_selection(picker))
        picker.open()

    def _use_selection(self, picker):
        self.selected_refs = picker.selected_refs()
        self.refresh()

    def close_picker(self, *_):
        if self.picker is not None and self.picker.isVisible():
            self.picker.reject()

    def refresh(self):
        entries = catalog_entries(self.session)
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
