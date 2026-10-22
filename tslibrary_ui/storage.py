"""Storage boundary: replace this file to use a DB instead of JSON.

The rest of the application uses only Repository's four methods and the
LibrarySession / WorkplaceConfig dataclasses, never JSON or filesystem paths.
Icons are reconstructed locally and are not persisted. License keys and the
phone/license inventories are outside this app/website catalog's scope.
"""

import json
import os
from pathlib import Path
import tempfile
from typing import Protocol

from .applications.icons import executable_icon
from .applications.models import Application
from .state import LibrarySession, WorkplaceConfig
from .websites.models import Website
from .websites.urls import normalize_website_url


class StorageError(Exception):
    """Readable storage failure; never silently replace unreadable user data."""


class Repository(Protocol):
    def load_catalog(self) -> LibrarySession: ...
    def save_catalog(self, session: LibrarySession) -> None: ...
    def load_workplace(self) -> WorkplaceConfig: ...
    def save_workplace(self, config: WorkplaceConfig) -> None: ...


def _text(record, field, *, allow_empty=False):
    value = record.get(field, "" if allow_empty else None)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"'{field}' must be {'a string' if allow_empty else 'a non-empty string'}.")
    return value


def _records(data, field):
    records = data.get(field, [])
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError(f"'{field}' must be a list of objects.")
    ids = [_text(item, "id") for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"'{field}' contains duplicate IDs.")
    return records


def _apps(data, field):
    return [Application(name=_text(item, "name"), executable=_text(item, "executable"),
                        id=_text(item, "id"), arguments=_text(item, "arguments", allow_empty=True),
                        icon=executable_icon(_text(item, "executable")))
            for item in _records(data, field)]


def _sites(data, field):
    return [Website(name=_text(item, "name"), id=_text(item, "id"),
                    url=normalize_website_url(_text(item, "url")))
            for item in _records(data, field)]


def _ids(data, field):
    values = data.get(field, [])
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"'{field}' must be a list of IDs.")
    return list(dict.fromkeys(values))


def _app_records(apps):
    return [dict(id=app.id, name=app.name, executable=app.executable, arguments=app.arguments)
            for app in apps]


def _site_records(sites):
    return [dict(id=site.id, name=site.name, url=site.url) for site in sites]


class JsonRepository:
    def __init__(self, catalog_path: Path, config_path: Path):
        self.catalog_path = Path(catalog_path)
        self.config_path = Path(config_path)
        if self.catalog_path.resolve() == self.config_path.resolve():
            raise StorageError("Catalog and personal config must use different files.")

    @staticmethod
    def _read(path, decode):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            data = {"version": 1}
        except (OSError, UnicodeError, ValueError) as error:
            raise StorageError(f"Could not read {path}: {error}") from error
        try:
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ValueError("Expected a version 1 JSON object.")
            return decode(data)
        except (ValueError, TypeError, KeyError) as error:
            raise StorageError(f"Invalid data in {path}: {error}") from error

    @staticmethod
    def _write(path, data):
        temporary = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=f".{path.name}.", suffix=".tmp",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except (OSError, ValueError, TypeError) as error:
            raise StorageError(f"Could not save {path}: {error}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def load_catalog(self):
        return self._read(self.catalog_path, lambda data: LibrarySession(
            applications=_apps(data, "applications"), websites=_sites(data, "websites")))

    def save_catalog(self, session):
        self._write(self.catalog_path, dict(version=1, applications=_app_records(session.applications),
                                           websites=_site_records(session.websites)))

    def load_workplace(self):
        return self._read(self.config_path, lambda data: WorkplaceConfig(
            application_ids=_ids(data, "application_ids"), website_ids=_ids(data, "website_ids"),
            personal_applications=_apps(data, "personal_applications"),
            personal_websites=_sites(data, "personal_websites")))

    def save_workplace(self, config):
        self._write(self.config_path, dict(
            version=1, application_ids=list(dict.fromkeys(config.application_ids)),
            website_ids=list(dict.fromkeys(config.website_ids)),
            personal_applications=_app_records(config.personal_applications),
            personal_websites=_site_records(config.personal_websites)))


def create_repository() -> Repository:
    """The single backend switch; environment paths also support testing/deployment."""
    catalog = Path(os.environ.get("TSLIBRARY_CATALOG_PATH", str(
        Path(__file__).resolve().parent.parent / "data" / "catalog.json")))
    user_root = Path(os.environ.get("APPDATA") or str(Path.home() / ".config"))
    config = Path(os.environ.get("TSLIBRARY_CONFIG_PATH", str(user_root / "TSLibrary" / "workplace.json")))
    return JsonRepository(catalog, config)
