"""Portable team connections and guarded writes to one shared JSON catalog.

The connection belongs to the team; only its selected path is stored on this PC.
Personal workplace data never enters either shared file.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from PySide6.QtCore import QLockFile

from .migrations import CATALOG_SCHEMA
from .storage import JsonCatalogStore, JsonFile, StorageError, catalog_data, decode_catalog


class CatalogConflict(StorageError):
    """The catalog changed after this admin loaded it."""


def read_required(path):
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise StorageError(f"Could not open {path}: {error}. Reconnect the shared folder and try again.") from error


def decode_json(raw, path):
    try:
        data = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object.")
        return data
    except (UnicodeError, ValueError) as error:
        raise StorageError(f"Invalid JSON in {path}: {error}") from error


def profile_catalog(path):
    path = Path(path).expanduser().resolve()
    data = decode_json(read_required(path), path)
    if data.get("format") != "tslibrary.team" or type(data.get("version")) is not int or data["version"] != 1:
        raise StorageError("Choose a TSLibrary team configuration (format tslibrary.team, version 1).")
    relative = data.get("catalog")
    if not isinstance(relative, str) or not relative.strip() or "\x00" in relative:
        raise StorageError("The team configuration needs a catalog file path.")
    catalog = Path(relative).expanduser()
    if not catalog.is_absolute():
        catalog = path.parent / catalog
    catalog = catalog.resolve()
    if catalog == path:
        raise StorageError("The team configuration and catalog must be different files.")
    return catalog


def selected_profile(connection_path):
    path = Path(connection_path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise StorageError(f"Could not read this PC's team connection: {error}") from error
    data = decode_json(raw, path)
    if type(data.get("version")) is not int or data["version"] != 1 or not isinstance(data.get("team_config"), str):
        raise StorageError(f"Invalid local team connection in {path}.")
    chosen = Path(data["team_config"])
    if not chosen.is_absolute():
        raise StorageError("The saved team configuration path must be absolute.")
    return chosen


def remember_profile(connection_path, profile):
    JsonFile._write(Path(connection_path), dict(version=1, team_config=str(Path(profile).resolve())))


@contextmanager
def catalog_lock(path):
    # No timed stealing of a lock on another PC. A failed write releases it;
    # an abandoned lock is an explicit recovery task, never an automatic overwrite.
    lock = QLockFile(str(path) + ".lock")
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise StorageError("The shared catalog is busy or its folder is not writable. Wait for the other admin's save, then try again.")
    try:
        yield
    finally:
        lock.unlock()


class SharedJsonCatalogStore(JsonCatalogStore):
    """Strict reads, atomic writes, a shared lock, and an optimistic revision.

    Unlike a fresh local catalog, a missing shared file is an error. A stale
    session cannot overwrite another admin's additions, edits, or deletions.
    """

    def __init__(self, path):
        super().__init__(path)
        self._revision = None
        self.profile_path = None
        self._writing = False

    def snapshot_bytes(self):
        if self.profile_path is not None and profile_catalog(self.profile_path) != self.path:
            raise StorageError("The team configuration now points to another catalog. Open the configuration again in Settings before continuing.")
        return read_required(self.path)

    def accept_snapshot(self, raw):
        data = decode_json(raw, self.path)
        try:
            session = decode_catalog(data)
        except (ValueError, TypeError, KeyError) as error:
            raise StorageError(f"Invalid catalog in {self.path}: {error}") from error
        # Shared migrations need a coordinated upgrade, rather than a reader
        # rewriting a file while another admin is editing it.
        if data["version"] != CATALOG_SCHEMA.current_version:
            raise StorageError("This shared catalog needs a coordinated format upgrade. Keep all admins on the same app version.")
        self._revision = hashlib.sha256(raw).digest()
        return session

    def load_catalog(self):
        raw = self.snapshot_bytes()
        data = decode_json(raw, self.path)
        if type(data.get("version")) is int and data["version"] < CATALOG_SCHEMA.current_version:
            # A shared upgrade uses the same lock as admin writes. JsonFile
            # validates first and keeps an exact recovery backup before replacing.
            with catalog_lock(self.path):
                self.snapshot_bytes()
                JsonFile._read(self.path, decode_catalog, schema=CATALOG_SCHEMA)
                raw = self.snapshot_bytes()
        return self.accept_snapshot(raw)

    @contextmanager
    def write_transaction(self):
        """Check freshness before a documentation folder mutation, too.

        A nested catalog save reuses the lock held by that short UI operation.
        This store's mutating calls run on the GUI thread.
        """
        if self._writing:
            yield
            return
        with catalog_lock(self.path):
            self._check_revision(self.snapshot_bytes())
            self._writing = True
            try:
                yield
            finally:
                self._writing = False

    def _check_revision(self, raw):
        if self._revision is None or hashlib.sha256(raw).digest() != self._revision:
            raise CatalogConflict("Another admin changed the shared catalog. Your changes have not overwritten theirs. Export a catalog backup to keep your draft, then reload the catalog in Settings and reapply your change.")

    def save_catalog(self, session):
        payload = catalog_data(session)
        try:
            decode_catalog(payload)
        except (ValueError, TypeError, KeyError) as error:
            raise StorageError(f"Could not validate shared catalog: {error}") from error
        with self.write_transaction():
            raw = self.snapshot_bytes()
            self._check_revision(raw)
            # Also reject invalid/newer data even if a caller reused this store.
            existing = decode_json(raw, self.path)
            try:
                decode_catalog(existing)
            except (ValueError, TypeError, KeyError) as error:
                raise StorageError(f"Invalid shared catalog: {error}") from error
            JsonFile._write(self.path, payload)
            # Hash the bytes we wrote, not a second read that could see a later
            # publisher after the lock is released.
            encoded = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
            # JsonFile writes in text mode, which uses CRLF on Windows.
            if os.name == "nt":
                encoded = encoded.replace(b"\n", b"\r\n")
            self._revision = hashlib.sha256(encoded).digest()


def _create_exclusive(path, payload):
    created = False
    try:
        with Path(path).open("x", encoding="utf-8") as stream:
            created = True
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, ValueError, TypeError) as error:
        if created:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
        raise StorageError(f"Could not create {path}: {error}. Choose a new filename; existing files are kept.") from error


def create_profile(path, session):
    """Publish a new pair, preserving record IDs and excluding license keys."""
    path = Path(path).expanduser().resolve()
    catalog = path.with_name(path.stem + ".catalog.json")
    if path.exists() or catalog.exists():
        raise StorageError("That configuration or its catalog already exists. Open the existing configuration, or choose a new filename.")
    payload = catalog_data(session)
    try:
        decode_catalog(payload)
    except (ValueError, TypeError, KeyError) as error:
        raise StorageError(f"Could not validate the catalog: {error}") from error
    _create_exclusive(catalog, payload)
    try:
        _create_exclusive(path, dict(version=1, format="tslibrary.team", catalog=catalog.name))
    except StorageError:
        try:
            catalog.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path
