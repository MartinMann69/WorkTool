# WorkTool

A polished Windows desktop home for your team's applications and websites, built with Python, PySide6 (Qt), and SQLite.

## Start here

**On this computer the virtual environment and dependencies are already installed. Double-click `demo.bat` to try it.**

For a new computer:

1. Install **standard 64-bit CPython 3.11–3.15**, including **Python 3.14 and 3.15**, from [python.org](https://www.python.org/downloads/windows/), with **Add Python to PATH** enabled. Use the standard build, not the optional free-threaded build. Python 3.16 and later are outside the currently supported range.
2. Copy the project into a writable local folder on **Windows 10 or 11**.
3. Double-click `setup.bat`. It creates `.venv` and installs the pinned **PySide6 6.12.0** dependency, whose [published compatibility range includes Python 3.14 and 3.15](https://pypi.org/project/PySide6/6.12.0/). Internet access is needed during installation. Qt is included; no separate Qt installation, database server, Node.js or Office installation is needed to start WorkTool. See [Qt's installation documentation](https://doc.qt.io/qtforpython-6/gettingstarted.html).
4. Open `demo.bat` for example accounts, or `start.bat` to create your own first administrator in a separate, fresh workspace.

Equivalent PowerShell commands, from this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --demo
```

Calling the virtual environment's Python directly avoids PowerShell activation-policy issues. Regular users do not need Windows administrator rights. WorkTool launches applications under the current Windows user's permissions.

### Upgrading an existing installation / choosing Python 3.14 or 3.15

Close WorkTool and run `setup.bat` again to update its GUI dependency. Existing accounts, groups, assignments, favorites and appearance settings remain in the app's separate data folder.

An existing `.venv` keeps the Python version with which it was created. Installing a newer system Python does not change that environment. Setup prints the project environment's actual Python version. To switch an existing installation to Python 3.14 or 3.15:

1. Install the desired standard 64-bit CPython version and close WorkTool.
2. Rename the project's `.venv` folder to `.venv-backup` using File Explorer; do not overwrite an existing backup.
3. Run setup with the full path to the desired interpreter, for example:

   ```powershell
   .\setup.bat "C:\Users\YourName\AppData\Local\Programs\Python\Python315\python.exe"
   ```

   Replace the example path with your actual installed Python path. A new `.venv` is created with that interpreter. You can also use this explicit-path option on a fresh installation.
4. Open `demo.bat` or `start.bat` as usual. Keep the backup until the new environment is working.

The virtual environment contains software dependencies, not your WorkTool account database. Changing it does not reset normal or demo accounts. The app's supported interpreter range is defined in `pyproject.toml` and checked by setup; removing an upper-bound check alone is not a compatibility upgrade.

## Demo accounts

All seven demo accounts initially use **`WorkTool!2026`**. Usernames are case-insensitive. Accounts are created only by `--demo`, and only when its database has no accounts. Passwords are not reset on later runs.

| Username | Name | Visible tabs |
|---|---|---|
| `admin` | Alex Morgan | All five; Administration available |
| `it.demo` | Jordan Lee | General, IT |
| `finance.demo` | Sam Rivera | General, Finance |
| `people.demo` | Taylor Brooks | General, People & HR |
| `operations.demo` | Casey Parker | General, Operations |
| `multi.demo` | Jamie Chen | General, IT, Operations |
| `general.demo` | Robin Ellis | General |

Sign out at the bottom left to switch users. A normal installation (`start.bat`) has **no default accounts or known passwords** and asks you to create its first administrator.

## Features

- Five main tabs: **General, IT, Finance, People & HR, Operations**. General is included for everyone. Administrators see everything.
- **Applications** and **Links** subtabs within each workspace, with **10 starter buttons in each**: 100 entries altogether.
- A dark sidebar, selectable light/dark workspace, responsive card grid, installation indicators and keyboard navigation.
- Search by title/description and per-user favorites. Search and Favorites filter the displayed department/subtab; the same filters apply when switching tabs.
- Light/dark mode and purple/pink selection buttons at the top right. Changes apply throughout the app after the click completes. Each account remembers its own choices across sign-ins and restarts. The sign-in screen has its own saved appearance; the default is light purple.
- Administration for accounts, multiple department assignments, disabled accounts, temporary passwords and administrator roles.
- An editable tool catalog and latest 500 audit events.
- Password changes, required changes after account creation/reset, persistent login lockout and an inactivity timeout.
- Persistent SQLite storage, rotating diagnostic logs, friendly launch errors and one running instance per data folder.

### Starter tools

Examples include Calculator, Notepad, File Explorer, Paint, Snipping Tool, Character Map and Microsoft Office; IT also includes VS Code, Remote Desktop and System Information. These are **not bundled with WorkTool**. Each application button checks its configured executable path. **Setup needed** means it could not find that executable; clicking explains how to fix the entry. Windows versions, Store apps and Office editions can use different paths.

Starter links point to real public portals, including Microsoft 365, Teams, GitHub, Azure, DATEV, Personio and Trello. Some are product homepages: replace them with your company's tenant-specific URLs. Subscriptions and sign-in to those services remain separate. Websites open in the default browser; WorkTool cannot verify whether a remote page actually loads.

## Administration

Administrators have an **Admin** main tab. The sidebar's **Administration** button takes you to that tab. It contains **Accounts**, **Groups**, **User access**, **Tool catalog**, and **Activity log**. Ordinary users cannot open the admin tools.

### Groups and individual tool assignments

1. Open **Admin → Groups → Create group**. Name the group, select its members, and check the applications/links it grants. Save the group. Groups can span departments; they grant the selected tools, not every tool in those departments.
2. Open **Admin → User access**, select an account, and check its group memberships. Changes save immediately. The tools list shows **Effective access**, including group names, department access, and direct assignments.
3. Check a tool in **Direct grant** to assign it to that individual. If the user already receives it through a group, the source column shows that inheritance. A direct grant adds another source of access, **never another copy of the button**.
4. To limit a tool to selected groups/users, edit it in **Tool catalog** and enable **Only assigned users / groups**. Newly created tools default to this option. Existing starter tools keep their original department access after the upgrade, preserving existing users' access.

Access is the union of department defaults (when enabled), all group grants, and direct grants, deduplicated by catalog tool ID. Removing one group does not remove access still granted by another group or a direct assignment. Removing the final source revokes launch access immediately. An assigned tool from another department makes that department tab visible with only the tools the account can access. Administrators always see all tools.

Use the same catalog record when assigning a tool to several groups/users. Separate catalog entries remain separate buttons, even if they happen to point to the same executable or website; they may have different arguments or purposes. Assignments do not copy catalog records.

Group changes refresh an active workspace within 30 seconds, or immediately with **Refresh tools**. Launch permission is always checked against current grants before opening a tool. Group/direct access changes refresh tabs without requiring a new login. Changes to the account's enabled status, administrator role or department assignment still require a new sign-in.

The upgrade adds assignment tables and a tool restriction flag to existing databases without resetting accounts, passwords, favorites, themes or the catalog. Group edits are saved together; user-access checkboxes save immediately. Deleting a group removes its memberships/grants and preserves other access sources. Deleting a tool removes its related grants and favorites.

### Accounts and departments

1. Sign in as an admin and open **Administration → Accounts → Create account**.
2. Enter a unique username, display name and temporary password (12–128 characters), then choose their departments.
3. Everyone receives General automatically. Administrators receive every workspace regardless of department checkboxes.
4. Users must change a new/reset temporary password before opening tools. Deliver passwords using your organization's approved channel.
5. To reset a password or clear a login lockout, edit the user and enter a new temporary password. Leave it blank to preserve their password. Uncheck **Account enabled** to disable access.

An admin cannot disable or demote their own account. Keep a second admin for operational recovery. Members cannot list users, edit the catalog or retrieve tools outside their departments through the application's service methods.

### Applications and links

Open **Administration → Tool catalog** to add, edit or delete buttons. Double-click a row to edit it.

| Field | Purpose / example |
|---|---|
| Workspace | Department where the button appears |
| Type | Application or Website |
| Title / description | Button name and short explanation |
| Path / URL | `C:\Program Files\Vendor\Tool.exe` or `https://your-company.example/portal` |
| Arguments | A JSON list such as `["--profile", "work"]`; use `[]` for none |

**Browse…** selects a local executable. Environment variables such as `%ProgramFiles%`, `%LOCALAPPDATA%` and `%WINDIR%` are expanded when resolving paths. Bare executable names are searched through PATH; prefer full paths for managed deployments. Only local `.exe` application targets are supported. Batch scripts, network executables and shell-command strings are rejected. Arguments are passed separately without a command shell. Admins must configure approved executables/arguments; an interpreter executable can still execute code when configured to do so.

Website targets must use HTTP/HTTPS, without embedded credentials; prefer HTTPS. Website entries have no arguments. Deleting a button does not uninstall its application, and removes its saved favorites. Changes save immediately. **Refresh tools** reloads catalog changes.

Workspace names/identifiers live in `worktool/catalog.py`. Display names can be renamed there; changing existing internal identifiers needs a migration of saved assignments and entries. The starter catalog seeds only new databases. Use Administration to update an existing installation.

## Structure and important files

| File | Responsibility |
|---|---|
| `main.py` | Small entry point that starts the application |
| `worktool/app.py` | Login, workspace, cards, startup and session lifecycle |
| `worktool/dialogs.py` | Account, catalog, audit and password dialogs |
| `worktool/theme.py` | Central colors, typography, spacing and widget styles |
| `worktool/resources.qrc`, `worktool/resources_rc.py` | Source and generated embedded Qt icon resources |
| `worktool/catalog.py` | Five departments, 100 starter entries and target validation |
| `worktool/security.py` | Password policy, salted hashing and verification |
| `worktool/store.py` | SQLite schema, persistence, permission checks and audit records |
| `worktool/launcher.py` | Authorized browser and executable launch requests |
| `requirements.txt` | Pinned runtime dependency |
| `requirements-dev.txt` | Optional testing dependencies |
| `pyproject.toml` | Project metadata and pytest configuration |
| `setup.bat`, `start.bat`, `demo.bat` | Install and run without terminal commands |
| `build.bat` | Optional standalone Windows build |
| `tests/test_store.py` | Passwords, permissions, lockout, persistence and validation |
| `tests/test_ui.py` | Login, tabs, favorites, session expiry and launch integration |
| `tests/test_groups.py` | Groups, direct grants, deduplication, revocation and real mouse-click regression checks |
| `scripts/preview.py` | Render real Qt screens as PNG files for visual checks |
| `docs/DEPLOYMENT.md` | Storage, backups, security boundaries and recovery |

Views call `store.py` rather than issuing SQL. Protected operations recheck enabled status, required password changes and role/department access. `launcher.py` fetches the current authorized entry immediately before launch, so an old card cannot grant access after department removal. `app.py` checks account changes every 30 seconds and returns to sign-in when access settings change. Visual branding can be changed in `theme.py` independently of authentication and storage.

## Storage and workplace deployment

Normal data: **`%LOCALAPPDATA%\WorkTool`**. Demo data: **`%LOCALAPPDATA%\WorkTool-Demo`**. Each holds `worktool.sqlite3`, `worktool.log` (three rotated backups) and a lock file while running. Passwords are hashed, never stored in plaintext. The header date uses workstation local time; audit times are UTC.

**This version uses local accounts per Windows profile.** It does not synchronize accounts or tools across PCs/profiles. A different data folder has independent accounts. Local login controls the WorkTool interface and launch requests; anyone able to modify its source/database can alter that local authorization. Company-wide identity and access enforcement needs a central identity/backend integration and permissions in Windows and destination systems. See [the deployment guide](docs/DEPLOYMENT.md) for these boundaries, backups and operational guidance.

Advanced commands:

```powershell
# Inactivity timeout: 1–120 minutes, default 15
.\.venv\Scripts\python.exe main.py --idle-minutes 10

# Separate local data folder
.\.venv\Scripts\python.exe main.py --data-dir "C:\Company\WorkToolData"
```

Do not use a network share/cloud-sync folder for SQLite. Custom folders are tagged as demo or normal and cannot be opened in the other mode. Do not use demo credentials for real access.

## Verification

Optional development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\preview.py
```

Pass `--native` to the preview script to check the actual Windows Qt platform instead of the offscreen renderer. If you edit the SVG icons, regenerate the embedded resource module using `.\.venv\Scripts\pyside6-rcc.exe worktool/resources.qrc -o worktool/resources_rc.py`.

Tests use isolated databases. UI tests run offscreen without opening real websites. A process integration test launches a temporary Python child process and checks argument boundaries. Screenshots go into the ignored `test-artifacts` folder. External subscriptions, network access and installed tools need checking on your representative company workstation.

Compatibility verified on Windows on 19 October 2026 with PySide6 6.12.0 and pytest 9.1.1:

| Standard 64-bit CPython | Full test suite |
|---|---|
| 3.12.10 | 37 passed |
| 3.14.8 | 37 passed |
| 3.15.0 | 37 passed |

The native Windows screenshot preview was also run successfully on Python 3.15.0. Python 3.11 and 3.13 remain in the supported dependency range, but were not rerun during this upgrade. Optional packaged executable builds require their own validation.

## Optional executable build

Run `build.bat` on Windows with a working virtual environment. It installs PyInstaller as a build dependency and creates `dist\WorkTool\WorkTool.exe`. Distribute the **entire `dist\WorkTool` folder**, including `_internal`. Recipients do not need Python. Run `WorkTool.exe --demo` for demo mode. The source version is the verified delivery; smoke-test, scan and sign packaged builds through your organization's deployment process before distributing them.

## Troubleshooting

- **Python not found / Store opens:** install standard 64-bit CPython 3.11–3.15 with PATH enabled and reopen your terminal. Check Windows App Execution Aliases if a Store alias conflicts, or pass the full Python path to `setup.bat`.
- **Package install fails:** verify connectivity/proxy settings or have IT use your approved package mirror.
- **Setup needed on a card:** install that app separately or edit its executable path. Office/Store installations can differ from the examples.
- **Links do not open:** configure your default browser and check the URL/connectivity.
- **Login fails:** passwords are case-sensitive. After five failed attempts, wait five minutes or ask an admin for a reset. Demo accounts apply only to demo mode.
- **Another instance running:** close the existing instance using that data directory. Do not delete a lock file while its process runs.
- **Unexpected error:** inspect `worktool.log` in the data folder. Review internal paths/details before sharing diagnostics externally.
