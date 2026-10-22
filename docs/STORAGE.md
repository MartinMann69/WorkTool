# Storage and per-user config

`tslibrary_ui/storage.py` owns repository JSON, paths, serialization, and atomic writes. `transfers.py` wraps those codecs for portable backups and CSV exports. The UI works with `LibrarySession`, `WorkplaceConfig`, and a four-method repository.

## Files

| File | Purpose |
| --- | --- |
| `<project>/data/catalog.json` | Shared admin-managed applications and websites |
| `%APPDATA%\TSLibrary\workplace.json` | This Windows user's selected catalog IDs and personal entries |

On systems without APPDATA, config defaults to `~/.config/TSLibrary/workplace.json`. Desktop executable/shortcut launching requires Windows.

Missing files start empty and are created on the first saved change. Saving any admin inventory edit writes the catalog; changing a user's selections or personal entries writes only that user's config. The catalog is not copied into each config. IDs keep selections linked to admin edits; deleting an admin entry removes it from displayed workplaces. Its unused ID can stay in a user's config, so restoring the same record can restore the selection.

Override deployment/test locations without editing the UI:

```powershell
$env:TSLIBRARY_CATALOG_PATH = 'C:\Shared\TSLibrary\catalog.json'
$env:TSLIBRARY_CONFIG_PATH = 'C:\MyConfig\workplace.json'
.venv\Scripts\python main.py
```

For multiple users on different PCs to see the same catalog, point `TSLIBRARY_CATALOG_PATH` at the same accessible shared location. Keep the config path per user. The JSON adapter writes through a temporary file and atomic replacement; read-only paths and invalid data are reported rather than silently overwritten. Malformed files block startup so empty data cannot replace them. It does not merge concurrent admin writes.

## JSON shapes (version 1)

Shared catalog:

```json
{
  "version": 1,
  "applications": [
    {"id": "editor-id", "name": "Team editor", "executable": "C:\\Tools\\Editor.exe", "arguments": "--profile Team"}
  ],
  "websites": [
    {"id": "portal-id", "name": "Team portal", "url": "https://portal.example.com"}
  ]
}
```

Each user's config:

```json
{
  "version": 1,
  "application_ids": ["editor-id"],
  "website_ids": ["portal-id"],
  "personal_applications": [],
  "personal_websites": [
    {"id": "personal-id", "name": "My notes", "url": "https://notes.example.com"}
  ]
}
```

Personal records use the same record shape as shared records. Icon data is rebuilt locally, never serialized. Phone apps and licensed items now persist in optional `phone_apps` and `items` arrays. Items retain owner, ISO renewal date, counts, and keyed/unlimited tracking flags. License entry key strings are never serialized, loaded from backups, or exported. A restored keyed entry displays that its key needs to be re-entered; metadata/counts can still be edited without entering a replacement key. Admin authentication is still a preview.

## Replacing JSON with a database

Change only `tslibrary_ui/storage.py`: implement the same repository methods and return that implementation from `create_repository()`.

```python
class DatabaseRepository:
    def load_catalog(self) -> LibrarySession: ...
    def save_catalog(self, session: LibrarySession) -> None: ...
    def load_workplace(self) -> WorkplaceConfig: ...
    def save_workplace(self, config: WorkplaceConfig) -> None: ...

def create_repository() -> Repository:
    return DatabaseRepository(...)
```

Keep `StorageError` for readable failures. Preserve stable record IDs. The backend should select the current OS user's workplace/config internally; the windows do not need to know a database username, table name, or SQL schema. Convert database rows to the existing dataclasses on reads. Existing windows and feature pages need no database-specific changes. A network/database adapter may later need asynchronous operations if its calls are slow.

Tests inject a temporary `JsonRepository` or omit the repository for an in-memory UI preview. Tests and screenshot generation do not use or overwrite the real user's config and do not launch actual resources.

## Workplace preference extensions

Version 1 configs remain backward-compatible. Optional fields are `favorites` (entry-key list), `groups` and `launch_sets` (name → entry-key lists), `application_overrides` (entry key → local executable/shortcut path), `view_mode` (`cards` or `list`), and `start_in_workplace` (boolean). An entry key is `kind:source:id`, so a personal record cannot collide with a shared record. Overrides change only the local executable path; the record's raw arguments are preserved.

Backups wrap versioned data in `format: tslibrary.workplace` / `tslibrary.catalog`. They are validated before restore, and a recovery backup is created before replacing the current data. CSV escapes formula prefixes and contains no license key values.

For frozen Windows builds the default catalog moves to `%LOCALAPPDATA%\TSLibrary\catalog.json` so installation directories can remain read-only. The shared-path environment override still takes precedence. Installer removal leaves user/catalog data intact. Conflict handling between separate PCs remains deferred.
