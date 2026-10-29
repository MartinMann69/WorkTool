"""Direct, bidirectional connections between typed catalog records."""

from dataclasses import dataclass


ENTRY_TYPES = {
    "application": ("Application", "Applications"),
    "phone_app": ("Phone app", "Phone apps"),
    "website": ("Website", "Websites"),
    "license": ("Licensed item", "Licenses"),
    "documentation": ("Documentation", "Documentation"),
}


@dataclass(frozen=True, order=True)
class EntryRef:
    kind: str
    id: str


@dataclass(frozen=True, order=True)
class CatalogLink:
    first: EntryRef
    second: EntryRef


def catalog_entries(session):
    """Resolve by type AND ID; different inventories can share the same ID."""
    return {EntryRef(kind, entry.id): entry
            for kind, entries in (
                ("application", session.applications), ("phone_app", session.phone_apps),
                ("website", session.websites), ("license", session.items),
                ("documentation", session.documentation.items))
            for entry in entries}


def link_between(first, second):
    if first == second:
        raise ValueError("An entry cannot link to itself.")
    return CatalogLink(*sorted((first, second)))


def valid_links(session):
    entries = catalog_entries(session)
    return sorted({link_between(link.first, link.second) for link in session.links
                   if link.first in entries and link.second in entries and link.first != link.second})


def related_entries(session, source):
    entries = catalog_entries(session)
    if source not in entries:
        return []
    refs = {link.second if link.first == source else link.first
            for link in valid_links(session) if source in (link.first, link.second)}
    return sorted(refs, key=lambda ref: (ref.kind, entries[ref].name.casefold(), ref.id))


def replace_links(session, source, targets):
    """Replace only this item's links, preserving every other item's links."""
    entries = catalog_entries(session)
    if source not in entries:
        return False
    targets = {ref for ref in targets if ref in entries and ref != source}
    updated = {link for link in valid_links(session) if source not in (link.first, link.second)}
    updated.update(link_between(source, ref) for ref in targets)
    updated = sorted(updated)
    changed = updated != session.links
    session.links[:] = updated
    return changed


def links_data(session):
    def endpoint(ref):
        return dict(kind=ref.kind, id=ref.id)
    return [dict(first=endpoint(link.first), second=endpoint(link.second))
            for link in valid_links(session)]


def decode_links(data, session):
    if not isinstance(data, list):
        raise ValueError("'links' must be a list of objects.")

    def endpoint(value):
        if (not isinstance(value, dict) or not isinstance(value.get("kind"), str)
                or value["kind"] not in ENTRY_TYPES or not isinstance(value.get("id"), str)
                or not value["id"].strip()):
            raise ValueError("Each link endpoint needs a known entry type and a non-empty ID.")
        return EntryRef(value["kind"], value["id"])

    links = set()
    for record in data:
        if not isinstance(record, dict):
            raise ValueError("Each link must be an object.")
        links.add(link_between(endpoint(record.get("first")), endpoint(record.get("second"))))
    entries = catalog_entries(session)
    # Old backups or externally removed records may leave references behind.
    return sorted(link for link in links if link.first in entries and link.second in entries)
