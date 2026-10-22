"""Read-only workplace projections; catalog records retain their stable IDs."""

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from dataclasses import replace

from PySide6.QtGui import QIcon

from ..library.models import KINDS


@dataclass(frozen=True)
class WorkplaceEntry:
    id: str
    name: str
    kind: str
    detail: str
    icon: QIcon | None = None
    source: str = "catalog"
    added: bool = False
    favorite: bool = False
    available: bool = True

    @property
    def type_label(self):
        return KINDS[self.kind][1]


def entry_key(entry):
    return f"{entry.kind}:{entry.source}:{entry.id}"


def effective_application(record, config, *, source="catalog"):
    key = f"applications:{source}:{record.id}"
    path = config.application_overrides.get(key)
    return replace(record, executable=path) if path else record


def project(record, kind, *, source="catalog", added=False, config=None):
    if kind == "applications" and config is not None:
        record = effective_application(record, config, source=source)
    detail = record.url if kind == "websites" else PureWindowsPath(record.executable).name
    entry = WorkplaceEntry(record.id, record.name, kind, detail, record.icon, source, added)
    available = True
    if kind == "applications":
        try:
            available = Path(record.executable).is_file()
        except OSError:
            available = False
        if not available:
            entry = replace(entry, detail=f"Unavailable on this PC · {detail}")
    return replace(entry, available=available, favorite=bool(config and entry_key(entry) in config.favorites))


def collection_entries(session, config):
    entries = [project(record, "websites", added=record.id in config.website_ids, config=config)
               for record in session.websites]
    entries += [project(record, "applications", added=record.id in config.application_ids, config=config)
                for record in session.applications]
    return entries


def workplace_entries(session, config, kind):
    ids = config.website_ids if kind == "websites" else config.application_ids
    personal = config.personal_websites if kind == "websites" else config.personal_applications
    shared = session.websites if kind == "websites" else session.applications
    return ([project(record, kind, added=True, config=config) for record in shared if record.id in ids]
            + [project(record, kind, source="personal", added=True, config=config) for record in personal])


def resolve_entry(session, config, entry):
    if entry.source == "personal":
        records = config.personal_websites if entry.kind == "websites" else config.personal_applications
    else:
        records = session.websites if entry.kind == "websites" else session.applications
    return next((record for record in records if record.id == entry.id), None)
