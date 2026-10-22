"""Read-only projections of admin inventories; license keys stay out of this view."""

from dataclasses import dataclass
from pathlib import PureWindowsPath

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from PySide6.QtGui import QIcon


KINDS = {
    "applications": ("Applications", "Application", "#c9b18c"),
    "websites": ("Websites", "Website", "#a3c1b0"),
    "phone_apps": ("Phone apps", "Phone app", "#b5abc9"),
    "licenses": ("Licensed items", "Licensed item", "#d0aa85"),
}


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str
    kind: str
    detail: str
    icon: QIcon | None = None

    @property
    def type_label(self):
        return KINDS[self.kind][1]


def catalog_entries(session):
    """Rebuild from current lists so additions, edits, and deletions are reflected."""
    entries = [CatalogEntry(app.id, app.name, "applications",
                            PureWindowsPath(app.executable).name, app.icon)
               for app in session.applications]
    entries.extend(CatalogEntry(site.id, site.name, "websites", site.url, site.icon)
                   for site in session.websites)
    entries.extend(CatalogEntry(app.id, app.name, "phone_apps", "Mobile app")
                   for app in session.phone_apps)
    entries.extend(CatalogEntry(item.id, item.name, "licenses",
                               f"{item.category} · {item.available_text} available")
                   for item in session.items)
    return entries


def filter_entries(entries, query="", kind="", sort="name_asc"):
    words = query.casefold().split()
    visible = [entry for entry in entries if (not kind or entry.kind == kind)
               and all(word in f"{entry.name} {entry.type_label} {entry.detail}".casefold()
                       for word in words)]
    if sort == "type":
        return sorted(visible, key=lambda entry: (entry.type_label.casefold(), entry.name.casefold()))
    return sorted(visible, key=lambda entry: entry.name.casefold(), reverse=sort == "name_desc")


class CatalogModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []

    def replace(self, entries):
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.entries):
            return None
        entry = self.entries[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return entry.name
        if role == Qt.ItemDataRole.DecorationRole:
            return entry.icon
        if role in (Qt.ItemDataRole.ToolTipRole, Qt.ItemDataRole.AccessibleDescriptionRole):
            return f"{entry.name}\n{entry.type_label}\n{entry.detail}"
        if role == Qt.ItemDataRole.UserRole:
            return entry
        return None
