# Storage and per-user config

`tslibrary_ui/storage.py` separates the shared catalog from local personal data. `ApplicationRepository` routes the UI's four methods to two independent adapters: a replaceable `CatalogStore` and a local `WorkplaceStore`. `transfers.py` uses the JSON codecs for portable backups and CSV exports.

```text
Admin edits / Collection refresh -> ApplicationRepository -> CatalogStore
                                                           JsonCatalogStore for now
                                                           Server adapter later
Personal edits / selections      -> ApplicationRepository -> LocalWorkplaceStore
                                                           Per-user workplace.json
```

Personal websites/apps, favorites, groups, workspace sets, local executable overrides, selections, and preferences belong only to `LocalWorkplaceStore`. The catalog adapter never receives `WorkplaceConfig`. New admin entries become available in Collection; they do not select themselves into anyone's workplace.

## Files

| File | Purpose |
| --- | --- |
| `<project>/data/catalog.json` | Shared admin-managed applications and websites |
| `%APPDATA%\TSLibrary\workplace.json` | This Windows user's selected catalog IDs and personal entries |

The installed app's catalog placeholder defaults to `%LOCALAPPDATA%\TSLibrary\catalog.json`. In development it uses `<project>/data/catalog.json`. Neither default is a live server. Personal data uses the same existing per-user path in both modes, so this adapter split does not move files, reset entries, or require a data migration.

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

### Shared documentation folders

The optional `documentation` catalog field contains `parent_path`, `root_name`, and `items` (stable `id` and slash-separated `name`). Older catalogs without this field start with an unconfigured location and an empty documentation list. Metadata is saved by the same catalog adapter as the other admin inventories; file bytes are never embedded in JSON, CSV, workplace preferences, or backups.

Administration's **Documentation** page selects an existing shared parent and a single root folder name. An item such as `IT/Setup` creates `<parent>/<root>/IT/Setup/`; files are copied there, leaving originals intact and rejecting duplicate filenames. Copies use temporary `.tslibrary-*.upload` files (hidden from the in-app browser), then publish complete files without replacing existing destinations, including concurrent uploads. Batch preflight prevents partial imports on known collisions, and a failed copy attempts to remove only files created by that batch. Copies run on the Qt thread pool. Folder names reject traversal, reserved Windows names, and ambiguous characters; resolved paths must remain beneath the selected root.

Documentation is available in Administration, where item dialogs list the actual shared files. Network/cloud permissions and syncing are handled by the existing shared drive or sync client; selecting a local-only folder does not make it shared. Every PC must point `TSLIBRARY_CATALOG_PATH` at the same catalog. Set `TSLIBRARY_DOCUMENTS_PATH` to the locally mounted documentation **parent** when different PCs use different drive letters or sync paths. This does not change the persisted shared location. Disable the override on the admin PC before changing root settings.

Renaming a root or item moves its directory and preserves stable item IDs. Nested item names are updated on parent rename. Moves reject existing destinations instead of merging; cross-volume moves can fail and leave the original location intact. Removing an item only removes metadata; its directory and files remain. Catalog restore changes metadata and paths, and never restores or deletes the separately stored files. Back up the shared folder separately. The root/name fields and item rename should be changed by one admin at a time, after other clients finish copying files.

Shared catalog:

The optional `links` array stores groups through undirected relationships between typed record IDs, for example `{"first": {"kind": "application", "id": "editor-id"}, "second": {"kind": "website", "id": "portal-id"}}`. Supported kinds are `application`, `phone_app`, `website`, `license` (a licensed item), and `documentation` (a named documentation folder). Each connected component becomes a complete group when loading, saving, or opening Administration. Existing app-to-website/app-to-license links therefore also connect that website and license, without recreating them. Keeping all member pairs ensures deleting the original app preserves the remaining group. Editing membership splits excluded entries off as a separate group; the saved selection is exact, so indirect paths cannot restore unchecked entries. Old catalogs without links remain valid. Reverse duplicates are normalised, self-links and malformed endpoints are rejected, and references to deleted records are discarded. Groups survive renames and are included in catalog backups; the relationship UI exists only in Administration.

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

## Replacing the catalog placeholder with a server

The JSON catalog is a stand-in for a future service. Admin editing and restoring a catalog backup already call `save_catalog`; opening the workplace and **Refresh collection** call `load_catalog`. Personal actions call only the workplace methods.

Implement these **two catalog methods**, then select your adapter in `create_catalog_store(path)` in `storage.py`. Keep `create_repository()` constructing `LocalWorkplaceStore` for personal data. No feature page needs server URLs, authentication tokens, or filesystem paths.

```python
class CatalogStore(Protocol):
    def load_catalog(self) -> LibrarySession: ...
    def save_catalog(self, session: LibrarySession) -> None: ...
```

For serverless testing, inject any implementation directly:

```python
repository = create_repository(catalog_store=my_test_catalog_store)
controller = PreviewController(repository=repository)
```

`tests/test_catalog_storage.py` exercises a fake service and a JSON placeholder through the real admin and workplace windows. It verifies that admin publication reaches another user's Collection, leaves personal data byte-for-byte intact, does not automatically select new entries, and that personal saves continue to work if catalog calls fail. The existing `JsonRepository(catalog_path, config_path)` constructor remains available for tests and integrations.

The service adapter's contract:

- Use `catalog_data(session)` for outgoing data. It excludes session-only license keys and local icon objects. Never serialize a window, controller, or arbitrary dataclass graph.
- Use `decode_catalog(data)` to validate the version and apply registered catalog migrations before reconstructing records. Unsupported versions and malformed data must raise `StorageError` at the adapter boundary, not become an empty successful response. The current catalog format is still version 1. The future server should own persisted catalog migrations and backups; decoding a remote payload locally only converts the in-memory representation.
- Keep stable IDs across edits so each user's local selections, favorites, and groups stay linked. An intentionally deleted catalog entry no longer appears; personal entries remain untouched.
- Raise `StorageError` on transport, permission, validation, and publish failures. The current UI keeps the displayed Collection on failed refresh and blocks refresh over unsaved admin changes. A successful save means the service accepted the change; a local cache alone is not successful publication.
- Enforce admin write permissions on the server. The current welcome/admin sign-in remains a preview, not authentication.

Before using a real network backend, add asynchronous request handling so slow I/O does not block Qt, automatic refresh scheduling, and a separate last-known-good local catalog cache for offline startup. These are intentionally not simulated by the current JSON adapter: startup still requires a readable catalog, refresh is on workplace entry or explicit request, and a failed in-session refresh keeps the in-memory data. A cache must not replace the personal file or treat a network failure as an empty catalog. Add server revision/conflict handling before allowing concurrent admins; the JSON placeholder saves whole snapshots and does not merge concurrent writes.

To test a different catalog file today, set `TSLIBRARY_CATALOG_PATH` to that file. Keep `TSLIBRARY_CONFIG_PATH` unset for the normal per-user personal file. Use admin export/restore to move an existing catalog while preserving record IDs. Changing the catalog file or later the catalog adapter does not upload, migrate, or overwrite personal data.

Tests inject a temporary `JsonRepository` or omit the repository for an in-memory UI preview. Tests and screenshot generation do not use or overwrite the real user's config and do not launch actual resources.

## Workplace preference extensions

Version 1 configs remain backward-compatible. Optional fields are `favorites` (entry-key list), `groups` and `launch_sets` (name → entry-key lists), `application_overrides` (entry key → local executable/shortcut path), `view_mode` (`cards` or `list`), and `start_in_workplace` (boolean). An entry key is `kind:source:id`, so a personal record cannot collide with a shared record. Overrides change only the local executable path; the record's raw arguments are preserved.

Backups wrap versioned data in `format: tslibrary.workplace` / `tslibrary.catalog`. They are validated before restore, and a recovery backup is created before replacing the current data. CSV escapes formula prefixes and contains no license key values.

For frozen Windows builds the default catalog moves to `%LOCALAPPDATA%\TSLibrary\catalog.json` so installation directories can remain read-only. The shared-path environment override still takes precedence. Installer removal leaves user/catalog data intact. Conflict handling between separate PCs remains deferred.

## Format migrations and update safety

`migrations.py` defines separate `CATALOG_SCHEMA` and `WORKPLACE_SCHEMA` objects. Both are still version 1; upgrading the app to 0.3.0 does not convert or rewrite existing files just to change an app version. Structural changes go into numbered pure migration functions, registered under their source version. Each step must return an object with its version increased by exactly one, preserving record IDs and user choices. All intermediate steps stay registered so users can skip app releases.

For JSON files, `JsonFile._read(..., schema=...)` upgrades in memory and validates the entire result first. If conversion is necessary, it writes an exact byte-for-byte backup named `<filename>.before-migration-vN-to-vM-<timestamp>-<unique>.bak` beside the original, then replaces the source atomically. A conversion/validation failure does not modify the source. A backup failure prevents conversion. If final replacement fails, the original and complete backup remain. Successful migration is only applied once. Restore a raw `.bak` by closing the app and copying it back to its original filename; it is not an export-wrapper backup for the Restore menu.

Normal catalog/workplace saves also check the existing file before writing. Newer unsupported versions and invalid existing data cannot silently become an empty or older-format file. Backup imports apply payload migrations in memory and leave the chosen backup file unchanged. Backup wrapper version 1 is independent of the nested catalog/workplace schema versions.

These protections cannot determine the intent of arbitrary code changes. When changing persisted names, types, nesting, or required fields, write and test the conversion in the same change. Bump the relevant data version whenever an older writer could lose new information, including newly persisted fields it would discard. Keep optional defaults for older data; preserve all IDs and selection references. Earlier app releases that predate these guards should not be used to edit newer data. See [RELEASING.md](RELEASING.md) for the release checklist and an example migration.
