"""File operations restricted to a selected documentation root; no cloud API."""

import os
from pathlib import Path
import shutil
from uuid import uuid4

from .models import DocumentationCatalog, folder_name, item_name


class DocumentationError(Exception):
    pass


class DocumentationFiles:
    def __init__(self, catalog):
        self.catalog = catalog

    def root(self):
        parent = os.environ.get("TSLIBRARY_DOCUMENTS_PATH") or self.catalog.parent_path
        if not parent:
            raise DocumentationError("Choose the shared documentation location in Administration first.")
        parent = Path(parent).expanduser()
        if not parent.is_absolute():
            raise DocumentationError("Choose an absolute shared or cloud-synced folder path.")
        if not parent.is_dir():
            raise DocumentationError("The shared location is unavailable. Connect or sync the folder and try again.")
        parent = parent.resolve()
        result = parent / folder_name(self.catalog.root_name)
        self._inside(result, parent)
        return result

    @staticmethod
    def _inside(path, parent):
        if not path.resolve().is_relative_to(parent.resolve()):
            raise DocumentationError("This folder points outside the documentation location.")

    def item_path(self, name, *, create=False):
        root = self.root()
        path = root.joinpath(*item_name(name).split("/"))
        self._inside(path, root)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def directory_path(self, name=""):
        return self.item_path(name) if name else self.root()

    def list_directory(self, name="", *, recursive=False):
        """Read actual folders/files without following directory links."""
        folder = self.directory_path(name)
        if not folder.is_dir():
            raise DocumentationError("This folder is unavailable. Connect the shared location and refresh.")
        root = self.root()
        pending, result = [folder], []
        while pending:
            current = pending.pop()
            for path in current.iterdir():
                if path.name.startswith(".tslibrary-"):
                    continue
                self._inside(path, root)
                is_folder = path.is_dir()
                if not is_folder and not path.is_file():
                    continue
                stat = path.stat()
                result.append(dict(path=path.relative_to(root).as_posix(), folder=is_folder,
                                   size=0 if is_folder else stat.st_size, modified=stat.st_mtime))
                if recursive and is_folder and not path.is_symlink() and not getattr(path, "is_junction", lambda: False)():
                    pending.append(path)
        return result

    def managed_path(self, name):
        """A non-root item that can be moved/deleted without following links."""
        name = item_name(name)
        root = self.root()
        path = root
        for part in name.split("/"):
            if part.startswith(".tslibrary-"):
                raise DocumentationError("Temporary TSLibrary files cannot be managed here.")
            path = path / part
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise DocumentationError("Move or delete the original item, rather than a linked folder.")
        self._inside(path, root)
        if not path.exists():
            raise DocumentationError("This item is unavailable. Refresh the folder and try again.")
        return path

    def move(self, name, destination):
        """Move within the root; update registered descendants without new IDs."""
        name = item_name(name)
        source = self.managed_path(name)
        parent = self.managed_path(destination) if destination else self.root()
        if not parent.is_dir():
            raise DocumentationError("Choose an existing destination folder.")
        if parent == source.parent:
            raise DocumentationError("This item is already in that folder.")
        if parent == source or parent.is_relative_to(source):
            raise DocumentationError("A folder cannot be moved into itself or one of its subfolders.")
        target = parent / source.name
        relative = item_name(target.relative_to(self.root()).as_posix())
        affected = [entry for entry in self.catalog.items
                    if entry.name.casefold() == name.casefold() or entry.name.casefold().startswith(name.casefold() + "/")]
        replacements = {entry.id: item_name(relative + entry.name[len(name):]) for entry in affected}
        names = [replacements.get(entry.id, entry.name).casefold() for entry in self.catalog.items]
        occupied = any(entry not in affected and (entry.name.casefold() == relative.casefold()
                       or entry.name.casefold().startswith(relative.casefold() + "/")) for entry in self.catalog.items)
        if occupied or len(names) != len(set(names)) or target.exists():
            raise DocumentationError("An item with this name already exists in the destination. Nothing was replaced.")
        source.rename(target)
        for entry in affected:
            entry.name = replacements[entry.id]
        return source, target

    def stage_delete(self, name):
        """Keep deletion reversible until the catalog save has succeeded."""
        name = item_name(name)
        source = self.managed_path(name)
        staged = source.with_name(f".tslibrary-{uuid4().hex}.deleted")
        source.rename(staged)
        self.catalog.items[:] = [entry for entry in self.catalog.items
                                if entry.name.casefold() != name.casefold()
                                and not entry.name.casefold().startswith(name.casefold() + "/")]
        return source, staged

    @staticmethod
    def finish_delete(staged):
        if staged.is_dir():
            shutil.rmtree(staged)
        else:
            staged.unlink()

    def create_item(self, name):
        name = item_name(name)
        if any(item.name.casefold() == name.casefold() for item in self.catalog.items):
            raise DocumentationError("An item already uses this folder name.")
        return self.item_path(name, create=True)

    def rename_item(self, item, name):
        name = item_name(name)
        if name == item.name:
            return
        affected = [entry for entry in self.catalog.items
                    if entry is item or entry.name.casefold().startswith(item.name.casefold() + "/")]
        replacements = {entry.id: name + entry.name[len(item.name):] for entry in affected}
        all_names = [replacements.get(entry.id, entry.name).casefold() for entry in self.catalog.items]
        if len(all_names) != len(set(all_names)):
            raise DocumentationError("Another item already uses that folder name.")
        old, new = self.item_path(item.name), self.item_path(name)
        if new.is_relative_to(old) or old.is_relative_to(new):
            raise DocumentationError("Choose a different folder branch for this rename.")
        if not old.is_dir():
            raise DocumentationError("The current folder is unavailable; it has not been renamed.")
        if new.exists():
            raise DocumentationError("The destination folder already exists; its files will not be overwritten.")
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        for entry in affected:
            entry.name = replacements[entry.id]

    def configure(self, parent_path, root_name):
        updated = DocumentationCatalog(parent_path, folder_name(root_name), self.catalog.items)
        # Validate the entered path even if this PC has an environment override.
        candidate = Path(parent_path).expanduser()
        if not candidate.is_absolute() or not candidate.is_dir():
            raise DocumentationError("Choose an existing, accessible shared or cloud-synced folder.")
        if os.environ.get("TSLIBRARY_DOCUMENTS_PATH"):
            if parent_path != self.catalog.parent_path or root_name != self.catalog.root_name:
                raise DocumentationError("Remove TSLIBRARY_DOCUMENTS_PATH on this admin PC before changing shared storage.")
        destination = DocumentationFiles(updated).root()
        old = self.root() if self.catalog.parent_path else None
        if old is not None and old.resolve() != destination.resolve() and old.exists():
            if destination.exists():
                raise DocumentationError("The destination already exists. Choose another root name to avoid merging files.")
            if destination.is_relative_to(old) or old.is_relative_to(destination):
                raise DocumentationError("Choose a separate parent folder for the documentation root.")
            old.rename(destination)
        else:
            if self.catalog.items and old is not None and not old.exists() and old != destination:
                raise DocumentationError("The existing documentation folder is unavailable; restore access before moving it.")
            destination.mkdir(exist_ok=True)
        self.catalog.parent_path, self.catalog.root_name = parent_path, root_name

    def list_files(self, name):
        folder = self.item_path(name)
        if not folder.is_dir():
            raise DocumentationError("This item folder is unavailable. Connect or sync the shared location.")
        files = []
        for path in folder.rglob("*"):
            self._inside(path, folder)
            if path.is_file() and not path.name.startswith(".tslibrary-"):
                files.append(path.relative_to(folder).as_posix())
        return sorted(files, key=str.casefold)

    def file_path(self, name, relative):
        folder = self.directory_path(name)
        target = folder.joinpath(*item_name(relative).split("/"))
        self._inside(target, folder)
        if not target.is_file():
            raise DocumentationError("This file is unavailable. Wait for it to sync and try again.")
        return target

    def add_files(self, name, sources):
        folder = self.directory_path(name)
        if not folder.is_dir():
            raise DocumentationError("The item folder is unavailable; no files were copied.")
        sources = [Path(source) for source in sources]
        existing = {path.name.casefold() for path in folder.iterdir()}
        for source in sources:
            folder_name(source.name)
            if source.name.startswith(".tslibrary-"):
                raise DocumentationError("Filenames starting with .tslibrary- are reserved for temporary imports.")
            if not source.is_file():
                raise DocumentationError(f"The source file is unavailable: {source.name}")
            if source.name.casefold() in existing:
                raise DocumentationError(f"{source.name} already exists. Rename the incoming file before adding it.")
            existing.add(source.name.casefold())
        created, pending = [], []
        try:
            for source in sources:
                destination = folder / source.name
                self._inside(destination, folder)
                temporary = folder / f".tslibrary-{uuid4().hex}.upload"
                pending.append(temporary)
                with source.open("rb") as origin, temporary.open("xb") as target:
                    shutil.copyfileobj(origin, target, length=1024 * 1024)
                # Publish only complete files. Both paths fail if another user
                # created the destination during the copy; neither overwrites.
                if os.name == "nt":
                    temporary.rename(destination)
                else:
                    os.link(temporary, destination)
                    temporary.unlink()
                created.append(destination)
                pending.remove(temporary)
            return [path.name for path in created]
        except (OSError, DocumentationError):
            for path in created + pending:
                try:
                    path.unlink()
                except OSError:
                    pass
            raise
