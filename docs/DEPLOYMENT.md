# Deployment and operations

## Scope

WorkTool is a Windows desktop launcher with local accounts. Permissions are checked in the application's SQLite service immediately before protected operations. It organizes tools and provides access-aware navigation on a managed workstation. It is not an identity provider or a replacement for permissions in launched applications.

The default data folder belongs to the current Windows profile. Copying the source to another PC does not share users or configuration. Company-wide deployment with centrally managed identities needs a hosted API/database and organizational sign-in (for example Entra ID/OIDC), with authorization enforced on that backend. Do not place SQLite on a network share to share accounts.

## Implemented controls

- PBKDF2-HMAC-SHA256 with 600,000 iterations, random 16-byte salts and constant-time digest comparison. Encoded hashes record algorithm, salt and iteration count. Passwords need 12–128 characters.
- Five-minute account lockout after five failed sign-ins, surviving restarts. Generic failure messages and password-hash work for nonexistent users. An admin password reset clears the lockout.
- No normal-mode default credentials. Demo mode has separate storage, a visible indicator and seven known test accounts.
- Required password change before protected access after account creation/admin reset.
- Group membership and direct tool assignments, with unique relationships and deduplicated effective access. Tools can be restricted to explicitly assigned users/groups. Existing department defaults are preserved during the schema upgrade. Revocation is checked before every launch; visible tabs refresh within 30 seconds or on manual refresh.
- Fifteen-minute default inactivity timeout, configurable from 1–120 minutes. Account changes checked every 30 seconds; every protected operation rechecks access immediately. Input after an already-expired session does not revive it, including after sleep.
- Local `.exe` targets launched with separate argument lists through Qt, without shell interpolation. HTTP/HTTPS website targets only, without embedded credentials. Network executable targets and scripts rejected.
- Parameterized SQL, transactional writes, unique usernames, per-folder process locking and safeguards against disabling/demoting the current administrator.
- Login, password, account, catalog and launch events. The admin view shows the latest 500, while the database retains all events. Launch events store entry IDs rather than arguments/URLs and represent requests handed to the OS, not proof of successful external completion.

## Boundaries

Someone who can modify the local database or Python source can bypass local authorization. There is no encrypted database, MFA, domain integration, automatic provisioning, email recovery, centralized audit collector or tamper-resistant audit log. Login throttling is local and per known account; the signed-in password-change form checks the current password but has no separate rate limiting.

Use Windows account separation and IT-managed filesystem permissions. Admins are trusted to configure executables/arguments: an interpreter executable can run code through its arguments. Applications launch under the current Windows identity. Hiding a WorkTool button does not prevent launching the same app elsewhere. Enforce real access in the destination system.

Before wider managed deployment, integrate central identity/backend services, organization-managed configuration, signed distribution/updates, a security review and audit retention/collection policy. Review the pinned Qt version against your supported-software policy; WorkTool does not automatically update dependencies.

## Backups and restore

1. Close WorkTool for the data folder being backed up.
2. Copy the entire folder to your approved encrypted backup storage. The SQLite database contains users, password hashes, permissions, tools, favorites and audit history; treat it as sensitive.
3. Verify the backup and retain it under your organization's policy.
4. To restore, close the app, preserve the current folder, restore your backup and start in the same mode. Passwords and permissions revert to the backup date and should be reviewed.

Do not copy a live SQLite file for backups. Do not distribute a personal or demo account database as a production template. Automated backups and audit-retention cleanup are not enabled.

## Administrator recovery

Retain a second administrator account for operational recovery. Another admin can reset credentials through Administration. There is no backdoor/recovery password. If every admin credential is lost, restore an appropriate backup. If data does not need preserving, an authorized local administrator can archive the data folder and initialize a fresh installation; this does not recover users, favorites or catalog changes from the old database.

## Runtime and distribution

Target: 64-bit Windows 10/11 and standard CPython 3.11–3.15 with PySide6 6.12.0. The supported range now includes Python 3.14 and 3.15; it excludes free-threaded interpreter builds and Python 3.16+. Password hashing, SQLite and logging use Python's standard library. `pytest` 9.x is development-only. `build.bat` optionally installs PyInstaller 6.22.3 or later in the 6.x series and creates a folder-based executable distribution; that build needs independent smoke testing, scanning and signing before rollout.

An existing virtual environment retains its original Python version. To select a different interpreter, close WorkTool, rename the `.venv` folder as a backup and run `setup.bat` with the full path to the desired Python executable. Setup prints the actual environment version. Account and configuration data remains in the separate application data directory. Upgrading the GUI dependency does not require a database reset.

Upgrade validation on 19 October 2026: all 37 automated tests passed independently on standard 64-bit CPython 3.12.10, 3.14.8 and 3.15.0 with PySide6 6.12.0 and pytest 9.1.1. Dependency consistency checks passed in each environment. The native Windows GUI preview also ran on Python 3.15.0. Python 3.11/3.13 and packaged executable builds were not rerun as part of this upgrade.

Third-party starter tools are installed/licensed separately. External links and initial package installation need network access; local login, catalog administration and installed-app launching do not need a WorkTool server. Qt/PySide is third-party software: retain its notices and have your organization evaluate distribution obligations using [Qt's licensing documentation](https://doc.qt.io/qtforpython-6/licenses.html).
