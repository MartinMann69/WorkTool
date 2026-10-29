# Windows releases and saved-data upgrades

The Windows installer contains Python and all runtime dependencies. Recipients need only the setup EXE. The current build targets Windows 10/11 x64-compatible systems and installs per Windows user, without requiring administrator access. The app supports local or shared-network JSON catalogs; a real online catalog and admin authentication are separate deployment work. Documentation metadata is included in catalog backups, but the referenced documentation files remain in their configured storage location and must be available on the target PC.

## Build a release

1. Set the app release number in `tslibrary_ui/version.py` (currently `0.7.0`). This is the single source used by the app and build script; it is independent of saved-data schema versions.
2. Run the regression suite: `.venv\Scripts\python -m unittest discover -s tests -v`. On a restricted Windows runner, set `TEMP` and `TMP` to a writable temporary directory. The single-instance tests need permission to create local named pipes.
3. Install build dependencies if needed: `.venv\Scripts\python -m pip install -r requirements.txt -r requirements-build.txt`. Install Inno Setup 6 on the build PC.
4. Run `scripts\build_windows.ps1` (or pass `-InnoCompiler 'C:\Path\To\ISCC.exe'`). It produces `dist\TSLibrary-Setup-<version>.exe` and a matching `.sha256` file. Keep the build on Windows; PyInstaller is not a cross-compiler.
5. Smoke-test `dist\TSLibrary\TSLibrary.exe --self-test`. For unattended runs, set `QT_QPA_PLATFORM=offscreen` and wait for exit code 0. This diagnostic uses only in-memory sample data.
6. On a test PC/VM without Python, run the installer, open the app, add personal entries, select catalog entries, close, and reopen it. Test application paths and documentation locations on that PC. The current development installer is unsigned; apply release signing before wider distribution if required by your environment.

Send the setup EXE to users. They should close the app and run the newer setup over their existing installation under the same Windows account. Keep the installer `AppId`, install mode, and per-user storage locations stable; changing those can create a second installation or make the app look in a different place for its data. Do not copy blank/default JSON files over existing user data during installation.

## Decide whether a data migration is needed

UI-only changes need no data migration. A new optional preference with a fallback can be read from old files, but consider whether an older app would discard that preference on save. Renaming stored fields, changing their types/nesting, removing required fields, or introducing information an older writer would lose requires a data-version change and a tested migration.

Catalog format is now 4; workplace and team-configuration formats remain 1. Catalog v1→v2 introduces portable app targets; v2→v3 marks existing documentation as folders; v3→v4 protects direct two-way connections from older group-expanding writers. All steps preserve IDs, arguments, paths, documentation metadata, and saved link pairs. Upgrade does not guess which previous links were automatically inferred; remove unwanted saved pairs once in the connection editor. Shared upgrades use the catalog lock and exact-backup/atomic-write mechanism. Install 0.7.0 on both admin PCs before using the upgraded shared catalog; 0.6.x and older reject format 4. App-only version changes need no format bump. For an actual future format change:

1. Add a pure conversion function in `tslibrary_ui/migrations.py`. Register it under its OLD version and increment the appropriate `DataSchema.current_version`. Keep previous steps.
2. Update the matching serializer and decoder in `storage.py` to use the new shape. Both serializers already emit their schema's current version.
3. Preserve IDs, selections, favorites, groups, workspace sets, launch arguments, local paths, documentation metadata, and catalog relationships. Never regenerate entries to perform a migration.
4. Test a frozen fixture from every supported old version, a user skipping releases, restart after conversion, invalid input, failed backup, and interrupted replacement. Check that the original file is retained on failure and the recovery copy is exact.
5. Test both catalog and workplace export/restore. Their outer backup wrapper has its own format version; the payload uses the catalog/workplace schema.

For example, if a future workplace format renames `start_in_workplace` to `open_workplace_on_startup`, the migration step could be:

```python
def workplace_v1_to_v2(data):
    data["open_workplace_on_startup"] = data.pop("start_in_workplace", False)
    data["version"] = 2
    return data

WORKPLACE_SCHEMA = DataSchema("workplace", 2, {1: workplace_v1_to_v2})
```

This is an example, not a migration shipped in 0.3.0. The corresponding version-2 serializer and decoder must also use that new field. The migration runner copies input before invoking steps, validates the full converted document, creates an exact original backup, and replaces the JSON atomically. Future-version files are rejected on load and save instead of being overwritten by an older app that supports these guards.

## Verify an upgrade and recovery

Use an isolated test PC/VM or copies of data with `TSLIBRARY_CATALOG_PATH` and `TSLIBRARY_CONFIG_PATH` pointing at test files. Never use a user's only copy for upgrade testing.

Install the previous release, populate both catalog and workplace data, then close it and save reference copies. Install the new release over it. Verify that personal entries, catalog IDs, selections, launch settings, documentation metadata and relationships remain correct, then change an entry, restart, and verify it again. Back up referenced documentation files separately; JSON backups contain metadata, not document contents.

For a release with a format conversion, also verify the `.before-migration-...bak` files beside the originals. To recover, close the app, copy the original backups back to the original catalog/workplace filenames, and use the matching older app. A program downgrade alone does not reverse a data migration. Do not let an old app rewrite newer-format data, especially app versions older than 0.3.0 that lack the new save guards.

When moving to a hosted catalog, enforce authentication, permissions, revisions/conflicts, and catalog migration backups on the server. Keep personal workplace migrations local. Automatic update delivery and an offline catalog cache are separate features; neither is provided by the installer or migration runner.
