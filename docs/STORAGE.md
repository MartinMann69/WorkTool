# Storage and per-user config

`tslibrary_ui/storage.py` separates the shared catalog from local personal data. `ApplicationRepository` routes the UI's four methods to two independent adapters: a replaceable `CatalogStore` and a local `WorkplaceStore`. `transfers.py` uses the JSON codecs for portable backups and CSV exports.

```text
Admin edits / Collection refresh -> ApplicationRepository -> CatalogStore
                                                           JsonCatalogStore locally / SharedJsonCatalogStore for a team
                                                           Server adapter later
Personal edits / selections      -> ApplicationRepository -> LocalWorkplaceStore
                                                           Per-user workplace.json
```

Personal websites/apps, favorites, groups, workspace sets, local executable overrides, selections, and preferences belong only to `LocalWorkplaceStore`. The catalog adapter never receives `WorkplaceConfig`. New admin entries become available in Collection; they do not select themselves into anyone's workplace.

## Files

| File | Purpose |
| --- | --- |
| `<project>/data/catalog.json` | Default development catalog, until a team is selected |
| `<chosen shared folder>/Team.json` | Portable team configuration pointing to its catalog |
| `<chosen shared folder>/Team.catalog.json` | Shared inventories, links, documentation defaults and license metadata |
| `%APPDATA%\TSLibrary\team-connection.json` | This PC/user's selected team configuration path |
| `%APPDATA%\TSLibrary\workplace.json` | This Windows user's selected catalog IDs and personal entries |
| `%APPDATA%\TSLibrary\window-state.ini` | Local window geometry/maximized state; shared across main screens and remembered per dialog type |

The installed app's catalog placeholder defaults to `%LOCALAPPDATA%\TSLibrary\catalog.json`. In development it uses `<project>/data/catalog.json`. Neither default is a live server. Personal data uses the same existing per-user path in both modes, so this adapter split does not move files, reset entries, or require a data migration.

On systems without APPDATA, config defaults to `~/.config/TSLibrary/workplace.json`. Desktop executable/shortcut launching requires Windows.

Window placement uses a separate Qt settings file beside the selected workplace config, so `TSLIBRARY_CONFIG_PATH` also relocates `window-state.ini`. It is machine-local display state and is excluded from catalog/workplace backups. A fresh profile opens maximized; later user resizing/restoring overrides that default. Minimized state is not restored on startup. Qt's geometry restoration brings windows back to an available monitor if an old screen is no longer connected. Invalid geometry falls back without blocking catalog access. No JSON format migration or change to personal selections is required. In-memory previews and self-tests never read or write the real display-preference file.

Missing default local catalog/workplace files start empty and are created on the first saved change. Selected team configurations and catalogs are required: missing or invalid shared files raise StorageError and are never replaced by empty data. Saving any admin inventory edit writes the catalog; changing a user's selections or personal entries writes only that user's config. The catalog is not copied into each config. IDs keep selections linked to admin edits; deleting an admin entry removes it from displayed workplaces. Its unused ID can stay in a user's config, so restoring the same record can restore the selection.

Override deployment/test locations without editing the UI:

```powershell
$env:TSLIBRARY_CATALOG_PATH = 'C:\Shared\TSLibrary\catalog.json'
$env:TSLIBRARY_CONFIG_PATH = 'C:\MyConfig\workplace.json'
.venv\Scripts\python main.py
```

For shared administration, use Settings to select the same live team configuration on both PCs; that enables revision checks and locking. `TSLIBRARY_CATALOG_PATH` remains a default local/testing override without shared coordination. Keep the config path per user. The JSON adapter writes through a temporary file and atomic replacement; read-only paths and invalid data are reported rather than silently overwritten. Malformed files block startup so empty data cannot replace them. It does not merge concurrent admin writes.

## JSON shapes (catalog 2, workplace 1)

### Portable application references

A shared application stores `target: {kind, filename, hint, installation?}` instead of an admin-specific `executable` path. `kind` is `shortcut` or `installed`. Hints use `%DESKTOP%`, `%STARTMENU%`, `%PUBLIC_DESKTOP%`, `%COMMON_STARTMENU%`, `%USERPROFILE%`, `%LOCALAPPDATA%`, `%APPDATA%`, `%PROGRAMFILES%`, `%PROGRAMFILES(X86)%`, `%PROGRAMDATA%`, or `%WINDIR%` where appropriate. New captures use the current known-folder roots, including redirected Desktop paths; legacy `C:\Users\<admin>` paths are rebased during the pure migration. A common custom location such as `D:\Tools\app.exe` can remain a hint without a username.

Installed entries can also record a product key/name/publisher and the executable's relative path within its install folder. The absolute InstallLocation is never serialized in that identity. Resolution checks matching current-PC installations, the portable hint, Windows App Paths, and explicit absolute PATH directories. Windows documents [App Paths registration](https://learn.microsoft.com/en-us/windows/win32/shell/app-registration) and the [Uninstall InstallLocation property](https://learn.microsoft.com/en-us/windows/win32/msi/uninstall-registry-key). Only the selected `.exe` filename is accepted; ambiguous matches raise a readable error. No recursive disk search, installer launch, or registry write occurs. A current-PC override wins and remains in the private workplace file.

Shortcuts are resolved only in their rebased matching location. The local `.lnk` is opened intact, preserving its own target/settings; another admin's shortcut is not copied or followed. Each PC must have that shortcut locally. Unchanged shared references can be renamed without the app being installed on the editing PC. Arguments remain separate and verbatim; machine-specific paths in arguments are not rewritten. Personal applications still use local absolute paths in workplace format 1.

The migration keeps the exact original catalog in a `.before-migration-v1-to-v3-...bak` file when upgrading from v1 to the current release before atomic replacement. Those recovery bytes naturally retain the original paths; the upgraded live catalog uses portable descriptors. Older supported releases refuse format 2 instead of overwriting the new target objects.

### Shared documentation folders

The optional `documentation` catalog field contains `parent_path`, `root_name`, and `items` (stable `id`, slash-separated `name`, and `kind` set to `folder` or `file`). Older catalogs without this field start with an unconfigured location and an empty documentation list. Metadata is saved by the same catalog adapter as the other admin inventories; file bytes are never embedded in JSON, CSV, workplace preferences, or backups.

Administration's **Settings → Documentation** section selects an existing shared parent and a single root folder name. The **Documentation** page combines actual directory files/subfolders with registered catalog folders in one inline view. Registered locations can be folders or individual files, retaining their IDs and relationships. Ordinary physical files/folders acquire a catalog ID when their connections are saved. The chain button and Connections menu action work on every row; file references open the file directly and folder references open the folder browser. Double-click/Open launches a file directly through its default application after validating that it remains inside the documentation root. New folder registers a documentation folder; Add files copies into the current directory, including the root, with the existing exclusive-copy and duplicate-name protections. Catalog v2 to v3 adds the file/folder kind, marking existing records as folders without moving files or changing IDs. Search is explicitly recursive; normal browsing shows one level. Folder navigation changes no stored data. Directory reads run on the Qt thread pool and return plain metadata; rendering and file opening stay on the GUI thread. Navigation/configuration changes invalidate old results. Failed refreshes preserve the same folder's last displayed listing and show an error. Imports use a snapshot of their destination; admin navigation/catalog switching and close are blocked until the copy finishes. External file additions appear with Refresh. An item such as `IT/Setup` creates `<parent>/<root>/IT/Setup/`; files are copied there, leaving originals intact and rejecting duplicate filenames. Copies use temporary `.tslibrary-*.upload` files (hidden from the in-app browser), then publish complete files without replacing existing destinations, including concurrent uploads. Batch preflight prevents partial imports on known collisions, and a failed copy attempts to remove only files created by that batch. Copies run on the Qt thread pool. Folder names reject traversal, reserved Windows names, and ambiguous characters; resolved paths must remain beneath the selected root. Shared documentation creates/renames also acquire the catalog write lock and check the revision before changing a folder, so a stale editor cannot rename files before its save is rejected.

Documentation is available in Administration. Non-documentation entry connection pickers use separate Library entries and Documentation tabs; documentation uses a lazy folder/file tree and recursive background search. Checks select only that file or folder, without checking descendants. New references remain staged until the owner is saved; cancelling the picker or owner does not create records. Existing registered references remain selectable if the share is offline. The documentation page itself keeps the regular entry picker for its connections. Network/cloud permissions and syncing are handled by the existing shared drive or sync client; selecting a local-only folder does not make it shared. Every PC must select the same team configuration/catalog. Set `TSLIBRARY_DOCUMENTS_PATH` to the locally mounted documentation **parent** when different PCs use different drive letters or sync paths. This does not change the persisted shared location. Disable the override on the admin PC before changing root settings.

Renaming a root or item moves its directory and preserves stable item IDs. Nested item names are updated on parent rename. The documentation browser's Move to action relocates files/folders inside the root, preserving IDs and connections and updating registered descendants. Existing destinations are rejected instead of merged. Root items, traversal, linked folders, and moving a folder into its own descendants are rejected. Cross-volume moves can fail and leave the original location intact.

Delete requires confirmation and removes physical contents, registered descendants, and their relationship references. Move/delete acquire the shared catalog write guard before filesystem changes. Moves can be renamed back if saving fails. Deletion first renames the source to a hidden `.tslibrary-<id>.deleted` sibling, then commits the metadata; a failed save restores the original name and records. After a successful save, a worker removes the staged contents. Navigation and close are blocked during cleanup. Cleanup failures show the retained location for manual recovery. An abrupt process/power failure can leave a staged folder; no automatic cleanup removes it, and backups of the shared folder are still required. Catalog restore changes metadata and paths, and never restores or deletes the separately stored files. The root/name fields and item rename should be changed by one admin at a time, after other clients finish copying files.

Shared catalog:

The optional `links` array stores groups through undirected relationships between typed record IDs, for example `{"first": {"kind": "application", "id": "editor-id"}, "second": {"kind": "website", "id": "portal-id"}}`. Supported kinds are `application`, `phone_app`, `website`, `license` (a licensed item), and `documentation` (a named documentation folder). Each connected component becomes a complete group when loading, saving, or opening Administration. Existing app-to-website/app-to-license links therefore also connect that website and license, without recreating them. Keeping all member pairs ensures deleting the original app preserves the remaining group. Editing membership splits excluded entries off as a separate group; the saved selection is exact, so indirect paths cannot restore unchecked entries. Old catalogs without links remain valid. Reverse duplicates are normalised, self-links and malformed endpoints are rejected, and references to deleted records are discarded. Groups survive renames and are included in catalog backups; the relationship UI exists only in Administration.

```json
{
  "version": 2,
  "applications": [
    {"id": "editor-id", "name": "Team editor", "target": {"kind": "installed", "filename": "Editor.exe", "hint": "%LOCALAPPDATA%\\Programs\\Editor\\Editor.exe"}, "arguments": "--profile Team"}
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

Personal application records retain the version-1 executable-path shape; shared applications use portable target objects. Website shapes are unchanged. Icon data is rebuilt locally, never serialized. Phone apps and licensed items now persist in optional `phone_apps` and `items` arrays. Items retain owner, ISO renewal date, counts, and keyed/unlimited tracking flags. License entry key strings are never serialized, loaded from backups, or exported. A restored keyed entry displays that its key needs to be re-entered; metadata/counts can still be edited without entering a replacement key. Admin authentication is still a preview.

## Team configuration and concurrent admins

In **Administration → Settings**, Create configuration publishes a new pair in an existing shared folder. Open configuration connects to an existing pair. Creation copies `catalog_data(session)`, retains IDs/relationships/defaults, and excludes license key values and personal data. It never overwrites an existing configuration or catalog. Both files must be accessible at the chosen location; the app does not create share permissions. The config is a separate version-1 format:

```json
{
  "version": 1,
  "format": "tslibrary.team",
  "catalog": "Team.catalog.json"
}
```

The relative catalog path is resolved beside the config, independent of the working directory. An absolute/UNC catalog path is also accepted. The catalog owns documentation location/root defaults, inventories, and links; the config does not duplicate those settings or need a reverse pointer. Keep the pair together. Copying both files creates a separate catalog; selecting a copied config that still points to an absolute shared catalog continues to use that original catalog. Each user stores only `{ "version": 1, "team_config": "<absolute selected config path>" }` in `team-connection.json` beside their workplace file, including when `TSLIBRARY_CONFIG_PATH` is set. The team never receives that workplace file or window-state.ini. Config selection validates the entire catalog and saves the local pointer before committing a switch. Invalid/missing files preserve the current connection and session. Startup can Retry or Choose team configuration if a saved share is unavailable.

`SharedJsonCatalogStore` requires an existing file and tracks the SHA-256 of the bytes it loaded. Save acquires `<catalog>.lock` via QLockFile, rereads the file, rejects any changed revision, validates the outgoing payload, and replaces the JSON atomically. A failure leaves the prior file and local draft intact. It never merges or force-overwrites a stale edit. A changed config pointer requires reopening it. Locks are released on success or failure; cross-host locks are not stolen on a timer. If a PC crashes during a save, an administrator may need to remove an abandoned lock **after verifying no writer is active**. All writers must use this version and the same actual live network files. Direct edits, older apps, or cloud-synced local copies bypass this coordination; do not use those for concurrent administration. Network filesystem semantics still matter; this has been tested using independent local processes, not your production share.

Admin refresh reads the shared bytes in a worker every 5 seconds while the admin window is visible. Decoding and Qt icon construction stay on the GUI thread. It defers while an editor/documentation window, unsaved catalog change, or documentation-settings draft is open. A result is discarded if a local edit/save, connection switch, or editor intervened during the read. It replaces all inventories/links together, preserving list identities and session-only keys only when their license metadata is unchanged. Settings offers Reload catalog and Retry saving. Before discarding unsaved data on reload/switch, the UI asks for confirmation; Data tools can export the draft. A retry cannot override a stale revision: reload and reapply it after exporting a draft backup. An unavailable share retains the displayed catalog and reports the error.

Documentation path/root controls live in Settings. They are part of the same catalog save/revision boundary. Changing the path does not move folders. When items exist, all registered folders and individual files must already exist in the new location; copy the documents first. Catalog backups include these defaults and item names, not the files. Back up the documentation folder separately. Shared format upgrades acquire the catalog write lock before using the validated, backed-up JsonFile migration path. Upgrade both admin PCs to 0.6.0 before reopening their shared catalog; older writers reject format 3. A background reader that encounters a restored older schema asks the user to reopen the configuration for the locked upgrade. Local and shared upgrades both keep exact original backups.

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
- Use `decode_catalog(data)` to validate the version and apply registered catalog migrations before reconstructing records. Unsupported versions and malformed data must raise `StorageError` at the adapter boundary, not become an empty successful response. The current catalog format is version 3; decoding version 1 applies the portable-target migration first, then the file/folder documentation migration. The future server should own persisted catalog migrations and backups; decoding a remote payload locally only converts the in-memory representation.
- Keep stable IDs across edits so each user's local selections, favorites, and groups stay linked. An intentionally deleted catalog entry no longer appears; personal entries remain untouched.
- Raise `StorageError` on transport, permission, validation, and publish failures. The current UI keeps the displayed Collection on failed refresh and blocks refresh over unsaved admin changes. A successful save means the service accepted the change; a local cache alone is not successful publication.
- Enforce admin write permissions on the server. The current welcome/admin sign-in remains a preview, not authentication.

Before using a real network backend, add asynchronous request handling so slow I/O does not block Qt, automatic refresh scheduling, and a separate last-known-good local catalog cache for offline startup. These are intentionally not simulated by the current JSON adapter: startup still requires a readable catalog, refresh is on workplace entry or explicit request, and a failed in-session refresh keeps the in-memory data. A cache must not replace the personal file or treat a network failure as an empty catalog. A future server needs its own revision/conflict handling. The local JSON placeholder saves whole snapshots; the team JSON adapter already rejects stale revisions under a shared lock and intentionally does not merge concurrent edits.

To test a different catalog file today, set `TSLIBRARY_CATALOG_PATH` to that file. Keep `TSLIBRARY_CONFIG_PATH` unset for the normal per-user personal file. Use admin export/restore to move an existing catalog while preserving record IDs. Changing the catalog file or later the catalog adapter does not upload, migrate, or overwrite personal data.

Tests inject a temporary `JsonRepository` or omit the repository for an in-memory UI preview. Tests and screenshot generation do not use or overwrite the real user's config and do not launch actual resources.

## Workplace preference extensions

Version 1 configs remain backward-compatible. Optional fields are `favorites` (entry-key list), `groups` and `launch_sets` (name → entry-key lists), `application_overrides` (entry key → local executable/shortcut path), `view_mode` (`cards` or `list`), and `start_in_workplace` (boolean). An entry key is `kind:source:id`, so a personal record cannot collide with a shared record. Overrides change only the local executable path; the record's raw arguments are preserved.

Backups wrap versioned data in `format: tslibrary.workplace` / `tslibrary.catalog`. They are validated before restore, and a recovery backup is created before replacing the current data. CSV escapes formula prefixes and contains no license key values.

For frozen Windows builds the default catalog moves to `%LOCALAPPDATA%\TSLibrary\catalog.json` so installation directories can remain read-only. Without a selected team, the catalog environment override takes precedence over this default. Installer removal leaves user/catalog data intact. A selected team configuration takes precedence over the default catalog/environment path and enables guarded writes between separate PCs. Removing or uninstalling the app does not remove the shared pair or the local selection.

## Format migrations and update safety

`migrations.py` defines separate `CATALOG_SCHEMA` and `WORKPLACE_SCHEMA` objects. The catalog is version 3 and the workplace is version 1. Catalog v1→v2 replaces shared executable paths with portable target descriptors; v2→v3 marks existing documentation entries as folders. Both preserve all record IDs, arguments, documentation paths, and relationships. App-only version changes do not trigger conversions. Structural changes go into numbered pure migration functions, registered under their source version. Each step must return an object with its version increased by exactly one, preserving record IDs and user choices. All intermediate steps stay registered so users can skip app releases.

For JSON files, `JsonFile._read(..., schema=...)` upgrades in memory and validates the entire result first. If conversion is necessary, it writes an exact byte-for-byte backup named `<filename>.before-migration-vN-to-vM-<timestamp>-<unique>.bak` beside the original, then replaces the source atomically. A conversion/validation failure does not modify the source. A backup failure prevents conversion. If final replacement fails, the original and complete backup remain. Successful migration is only applied once. Restore a raw `.bak` by closing the app and copying it back to its original filename; it is not an export-wrapper backup for the Restore menu.

Normal catalog/workplace saves also check the existing file before writing. Newer unsupported versions and invalid existing data cannot silently become an empty or older-format file. Backup imports apply payload migrations in memory and leave the chosen backup file unchanged. Backup wrapper version 1 is independent of the nested catalog/workplace schema versions.

These protections cannot determine the intent of arbitrary code changes. When changing persisted names, types, nesting, or required fields, write and test the conversion in the same change. Bump the relevant data version whenever an older writer could lose new information, including newly persisted fields it would discard. Keep optional defaults for older data; preserve all IDs and selection references. Earlier app releases that predate these guards should not be used to edit newer data. See [RELEASING.md](RELEASING.md) for the release checklist and an example migration.
