"""Storage boundary: replace this file to use a DB instead of JSON.

The rest of the application uses only Repository's four methods and the
LibrarySession / WorkplaceConfig dataclasses, never JSON or filesystem paths.
Icons are reconstructed locally and are not persisted. License counts, owners,
renewal dates, and tracking modes are saved, but license key values never are.
"""

import json
import os
import sys
from pathlib import Path
import tempfile
from typing import Protocol
from datetime import date

from .applications.icons import executable_icon
from .applications.models import Application
from .state import LibrarySession, WorkplaceConfig
from .websites.models import Website
from .websites.urls import normalize_website_url
from .licenses.models import LibraryItem, LicenseEntry, MAX_LICENSE_COUNT
from .phone_apps.models import PhoneApp


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


def _bool(data, field, default=False):
    value = data.get(field, default)
    if not isinstance(value, bool):
        raise ValueError(f"'{field}' must be a boolean.")
    return value


def _mapping(data, field, *, lists=False):
    value = data.get(field, {})
    if not isinstance(value, dict) or any(not isinstance(key, str) or not key.strip() for key in value):
        raise ValueError(f"'{field}' must be an object with non-empty names.")
    if lists:
        return {key: _ids({"ids": ids}, "ids") for key, ids in value.items()}
    if any(not isinstance(item, str) or not item.strip() for item in value.values()):
        raise ValueError(f"'{field}' must contain non-empty strings.")
    return dict(value)


def catalog_data(session):
    """Serializable inventory and renewal metadata; never serialize key values."""
    return dict(version=1, applications=_app_records(session.applications),
                websites=_site_records(session.websites),
                phone_apps=[dict(id=app.id, name=app.name) for app in session.phone_apps],
                items=[dict(id=item.id, name=item.name, category=item.category, owner=item.owner,
                            renewal_date=item.renewal_date, licenses=[dict(
                                label=entry.label, available=entry.available, used=entry.used,
                                unlimited=entry.unlimited, keyed=entry.tracks_key)
                                for entry in item.licenses]) for item in session.items])


def decode_catalog(data):
    session = LibrarySession(applications=_apps(data, "applications"), websites=_sites(data, "websites"),
                             phone_apps=[PhoneApp(_text(app, "name"), _text(app, "id"))
                                         for app in _records(data, "phone_apps")])
    for item in _records(data, "items"):
        renewal = _text(item, "renewal_date", allow_empty=True)
        if renewal:
            date.fromisoformat(renewal)
        entries = item.get("licenses", [])
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise ValueError("'licenses' must be a list of objects.")
        licenses = []
        for entry in entries:
            for field in ("available", "used"):
                value = entry.get(field)
                if type(value) is not int or not 0 <= value <= MAX_LICENSE_COUNT:
                    raise ValueError(f"'{field}' must be a valid license count.")
            unlimited, keyed = _bool(entry, "unlimited"), _bool(entry, "keyed")
            if unlimited and not keyed:
                raise ValueError("Unlimited entries must track a key.")
            licenses.append(LicenseEntry(_text(entry, "label"), entry["available"], used=entry["used"],
                                         unlimited=unlimited, keyed=keyed))
        session.items.append(LibraryItem(_text(item, "name"), _text(item, "category"), licenses,
                                         _text(item, "id"), _text(item, "owner", allow_empty=True), renewal))
    return session


def workplace_data(config):
    return dict(version=1, application_ids=list(dict.fromkeys(config.application_ids)),
                website_ids=list(dict.fromkeys(config.website_ids)),
                personal_applications=_app_records(config.personal_applications),
                personal_websites=_site_records(config.personal_websites),
                favorites=config.favorites, groups=config.groups, launch_sets=config.launch_sets,
                application_overrides=config.application_overrides,
                start_in_workplace=config.start_in_workplace, view_mode=config.view_mode)


def decode_workplace(data):
    mode = data.get("view_mode", "cards")
    if mode not in ("cards", "list"):
        raise ValueError("'view_mode' must be cards or list.")
    return WorkplaceConfig(
        application_ids=_ids(data, "application_ids"), website_ids=_ids(data, "website_ids"),
        personal_applications=_apps(data, "personal_applications"), personal_websites=_sites(data, "personal_websites"),
        favorites=_ids(data, "favorites"), groups=_mapping(data, "groups", lists=True),
        launch_sets=_mapping(data, "launch_sets", lists=True),
        application_overrides=_mapping(data, "application_overrides"),
        start_in_workplace=_bool(data, "start_in_workplace"), view_mode=mode)


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
        return self._read(self.catalog_path, decode_catalog)

    def save_catalog(self, session):
        self._write(self.catalog_path, catalog_data(session))

    def load_workplace(self):
        return self._read(self.config_path, decode_workplace)

    def save_workplace(self, config):
        self._write(self.config_path, workplace_data(config))


def create_repository() -> Repository:
    """The single backend switch; environment paths also support testing/deployment."""
    catalog = Path(os.environ.get("TSLIBRARY_CATALOG_PATH", str(
        (Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TSLibrary" / "catalog.json")
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent.parent / "data" / "catalog.json")))
    user_root = Path(os.environ.get("APPDATA") or str(Path.home() / ".config"))
    config = Path(os.environ.get("TSLIBRARY_CONFIG_PATH", str(user_root / "TSLibrary" / "workplace.json")))
    return JsonRepository(catalog, config)
