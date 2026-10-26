"""Connected catalog groups, represented by compatible typed link records."""

from dataclasses import dataclass
from itertools import combinations


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
    return _complete_groups(link for link in session.links
                            if link.first in entries and link.second in entries
                            and link.first != link.second)


def _complete_groups(links):
    """Every member can reach every other member, including old star links.

    Materialise the groups so deleting their original connecting item does not
    disconnect the other members. The existing catalog/backup format is kept.
    """
    neighbours = {}
    for link in links:
        neighbours.setdefault(link.first, set()).add(link.second)
        neighbours.setdefault(link.second, set()).add(link.first)
    remaining = set(neighbours)
    result = []
    while remaining:
        pending = [remaining.pop()]
        group = set(pending)
        while pending:
            for ref in neighbours[pending.pop()] - group:
                group.add(ref)
                remaining.discard(ref)
                pending.append(ref)
        result.extend(CatalogLink(first, second) for first, second in combinations(sorted(group), 2))
    return sorted(result)


def related_entries(session, source):
    entries = catalog_entries(session)
    if source not in entries:
        return []
    refs = {link.second if link.first == source else link.first
            for link in valid_links(session) if source in (link.first, link.second)}
    return sorted(refs, key=lambda ref: (ref.kind, entries[ref].name.casefold(), ref.id))


def replace_links(session, source, targets):
    """Save exact group membership; excluded members remain grouped together.

    Chosen members are moved out of their old groups before joining the source,
    so an unchecked item cannot reappear through a remaining indirect link.
    The picker includes an existing target's whole group when first selected.
    """
    entries = catalog_entries(session)
    if source not in entries:
        return False
    group = {source} | {ref for ref in targets if ref in entries}
    updated = {link for link in valid_links(session) if link.first not in group and link.second not in group}
    updated.update(CatalogLink(first, second) for first, second in combinations(sorted(group), 2))
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
    return _complete_groups(link for link in links if link.first in entries and link.second in entries)
