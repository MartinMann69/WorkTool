"""Portable documentation names and shared folder configuration."""

from dataclasses import dataclass, field
import re
from uuid import uuid4


def folder_name(value):
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or value in (".", "..") or len(value) > 120
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)
            or value.endswith((".", " "))
            or value.split(".")[0].upper() in
            {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}):
        raise ValueError("Use a folder name without reserved characters, trailing dots, or spaces.")
    return value


def item_name(value):
    if not isinstance(value, str):
        raise ValueError("Enter a documentation name.")
    value = value.strip().replace("\\", "/")
    if len(value) > 220:
        raise ValueError("Keep the documentation path under 220 characters.")
    return "/".join(folder_name(part) for part in value.split("/"))


@dataclass
class DocumentationItem:
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
    kind: str = "folder"


@dataclass
class DocumentationCatalog:
    parent_path: str = ""
    root_name: str = "TSLibrary Documentation"
    items: list[DocumentationItem] = field(default_factory=list)


def documentation_data(catalog):
    return dict(parent_path=catalog.parent_path, root_name=catalog.root_name,
                items=[dict(id=item.id, name=item.name, kind=item.kind) for item in catalog.items])


def decode_documentation(data):
    if not isinstance(data, dict):
        raise ValueError("'documentation' must be an object.")
    parent = data.get("parent_path", "")
    if not isinstance(parent, str) or "\x00" in parent:
        raise ValueError("The documentation location must be a folder path.")
    root = folder_name(data.get("root_name", "TSLibrary Documentation"))
    records = data.get("items", [])
    if not isinstance(records, list):
        raise ValueError("Documentation items must be a list.")
    items, ids, names = [], set(), set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid documentation item.")
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in ids:
            raise ValueError("Documentation items need unique IDs.")
        name = item_name(record.get("name"))
        if name.casefold() in names:
            raise ValueError("Documentation folder names must be unique.")
        kind = record.get("kind", "folder")
        if kind not in ("folder", "file"):
            raise ValueError("Documentation must refer to a file or folder.")
        ids.add(identifier)
        names.add(name.casefold())
        items.append(DocumentationItem(name, identifier, kind))
    file_names = {item.name.casefold() for item in items if item.kind == "file"}
    if any("/".join(item.name.casefold().split("/")[:depth]) in file_names
           for item in items for depth in range(1, len(item.name.split("/")))):
        raise ValueError("A documentation file cannot contain other documentation entries.")
    return DocumentationCatalog(parent, root, items)
