"""SQLite persistence and authorization. All privileged operations recheck the actor."""
from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3
import time

from .catalog import DEPARTMENTS, Entry, starter_entries, validate_entry
from .security import hash_password, verify_password


@dataclass(frozen=True)
class User:
    id: int
    username: str
    display_name: str
    admin: bool
    departments: tuple[str, ...]
    must_change: bool

    def can_access(self, department):
        return department in DEPARTMENTS and (self.admin or department == "general" or department in self.departments)


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              display_name TEXT NOT NULL, password TEXT NOT NULL,
              admin INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
              departments TEXT NOT NULL DEFAULT '[]', must_change INTEGER NOT NULL DEFAULT 1,
              failures INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS entries (
              id INTEGER PRIMARY KEY, department TEXT NOT NULL, kind TEXT NOT NULL,
              title TEXT NOT NULL, description TEXT NOT NULL, target TEXT NOT NULL,
              arguments TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY, occurred TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
              actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS favorites (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
              PRIMARY KEY(user_id, entry_id)
            );
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS appearance (
              user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              mode TEXT NOT NULL CHECK(mode IN ('light','dark')),
              accent TEXT NOT NULL CHECK(accent IN ('purple','pink'))
            );
            CREATE TABLE IF NOT EXISTS access_groups (
              id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
              description TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS group_members (
              group_id INTEGER NOT NULL REFERENCES access_groups(id) ON DELETE CASCADE,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              PRIMARY KEY(group_id,user_id)
            );
            CREATE TABLE IF NOT EXISTS group_tools (
              group_id INTEGER NOT NULL REFERENCES access_groups(id) ON DELETE CASCADE,
              entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
              PRIMARY KEY(group_id,entry_id)
            );
            CREATE TABLE IF NOT EXISTS user_tools (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
              PRIMARY KEY(user_id,entry_id)
            );
            CREATE INDEX IF NOT EXISTS group_members_by_user ON group_members(user_id);
            CREATE INDEX IF NOT EXISTS group_tools_by_entry ON group_tools(entry_id);
            CREATE INDEX IF NOT EXISTS user_tools_by_entry ON user_tools(entry_id);
        """)
        if 'restricted' not in {r[1] for r in self.db.execute('PRAGMA table_info(entries)')}:
            self.db.execute('ALTER TABLE entries ADD COLUMN restricted INTEGER NOT NULL DEFAULT 0')
            self.db.commit()
        if not self.db.execute("SELECT 1 FROM metadata WHERE key='seeded'").fetchone():
            with self.db:
                for entry in starter_entries():
                    self._insert_entry(*entry)
                self.db.execute("INSERT INTO metadata VALUES ('seeded', '1')")
        self._dummy_hash = hash_password("Nonexistent-user-dummy-password")

    def close(self):
        self.db.close()

    def appearance(self, actor_id=None):
        if actor_id is None:
            row = self.db.execute("SELECT value FROM metadata WHERE key='login_appearance'").fetchone()
            if row:
                try:
                    mode, accent = json.loads(row[0])
                except (ValueError, TypeError):
                    return "light", "purple"
            else:
                return "light", "purple"
        else:
            self.current(actor_id, allow_change=True)
            row = self.db.execute("SELECT mode,accent FROM appearance WHERE user_id=?", (actor_id,)).fetchone()
            if not row:
                return "light", "purple"
            mode, accent = row
        return (mode, accent) if mode in {"light", "dark"} and accent in {"purple", "pink"} else ("light", "purple")

    def save_appearance(self, mode, accent, actor_id=None):
        if mode not in {"light", "dark"} or accent not in {"purple", "pink"}:
            raise ValueError("Choose Light or Dark mode and a Purple or Pink accent.")
        if actor_id is not None:
            self.current(actor_id, allow_change=True)
        with self.db:
            if actor_id is None:
                self.db.execute("INSERT INTO metadata(key,value) VALUES ('login_appearance',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                (json.dumps([mode, accent]),))
            else:
                self.db.execute("INSERT INTO appearance VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode,accent=excluded.accent",
                                (actor_id, mode, accent))

    @contextmanager
    def transaction(self):
        with self.db:
            yield

    def _audit(self, actor, action, detail=""):
        self.db.execute("INSERT INTO audit(actor,action,detail) VALUES (?,?,?)", (actor, action, detail))

    @staticmethod
    def _user(row):
        return User(row["id"], row["username"], row["display_name"], bool(row["admin"]),
                    tuple(json.loads(row["departments"])), bool(row["must_change"]))

    def has_users(self):
        return bool(self.db.execute("SELECT 1 FROM users LIMIT 1").fetchone())

    def current(self, user_id, *, admin=False, allow_change=False):
        row = self.db.execute("SELECT * FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
        if not row or (admin and not row["admin"]):
            raise PermissionError("Your account does not have permission for this action. Please sign in again.")
        user = self._user(row)
        if user.must_change and not allow_change:
            raise PermissionError("Change your temporary password before continuing.")
        return user

    def bootstrap(self, username, name, password):
        with self.db:
            if self.has_users():
                raise PermissionError("An administrator has already been configured.")
            self._insert_user(username, name, password, True, [], False)
            self._audit(username, "installation_initialized")

    def seed_demo(self):
        with self.db:
            if self.has_users():
                return
            accounts = [
                ("admin", "Alex Morgan", True, []),
                ("it.demo", "Jordan Lee", False, ["it"]),
                ("finance.demo", "Sam Rivera", False, ["finance"]),
                ("people.demo", "Taylor Brooks", False, ["people"]),
                ("operations.demo", "Casey Parker", False, ["operations"]),
                ("multi.demo", "Jamie Chen", False, ["it", "operations"]),
                ("general.demo", "Robin Ellis", False, []),
            ]
            for username, name, admin, depts in accounts:
                self._insert_user(username, name, "WorkTool!2026", admin, depts, False)
            self._audit("system", "demo_initialized")

    def authenticate(self, username, password):
        username = username.strip().lower()[:64]
        row = self.db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        correct = verify_password(password, row["password"] if row else self._dummy_hash)
        now = time.time()
        with self.db:
            if not row or not row["active"] or row["locked_until"] > now or not correct:
                if row and row["active"] and row["locked_until"] <= now:
                    failures = row["failures"] + 1
                    self.db.execute("UPDATE users SET failures=?, locked_until=? WHERE id=?",
                                    (0 if failures >= 5 else failures, now + 300 if failures >= 5 else 0, row["id"]))
                self._audit(username or "unknown", "login_failed")
                return None
            self.db.execute("UPDATE users SET failures=0, locked_until=0 WHERE id=?", (row["id"],))
            self._audit(row["username"], "login_success")
        return self._user(row)

    def _insert_user(self, username, name, password, admin, departments, must_change):
        username, name, departments = self._validate_user(username, name, departments)
        self.db.execute("INSERT INTO users(username,display_name,password,admin,departments,must_change) VALUES (?,?,?,?,?,?)",
                        (username, name, hash_password(password), int(admin), json.dumps(departments), int(must_change)))

    @staticmethod
    def _validate_user(username, name, departments):
        username, name = username.strip().lower(), name.strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", username):
            raise ValueError("Username needs 3–64 letters, numbers, dots, underscores or hyphens.")
        if not name or len(name) > 80:
            raise ValueError("Display name needs 1–80 characters.")
        if any(d not in DEPARTMENTS or d == "general" for d in departments):
            raise ValueError("Invalid department assignment.")
        return username, name, sorted(set(departments))

    def save_user(self, actor_id, username, name, admin, departments, *, user_id=None, password="", active=True):
        actor = self.current(actor_id, admin=True)
        username, name, departments = self._validate_user(username, name, departments)
        with self.db:
            if user_id is None:
                self._insert_user(username, name, password, admin, departments, True)
            else:
                old = self.db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                if not old:
                    raise ValueError("This account no longer exists.")
                if actor_id == user_id and (not admin or not active):
                    raise ValueError("You cannot disable or remove administrator access from your own account.")
                if old["admin"] and old["active"] and (not admin or not active):
                    count = self.db.execute("SELECT count(*) FROM users WHERE active=1 AND admin=1").fetchone()[0]
                    if count <= 1:
                        raise ValueError("At least one active administrator is required.")
                self.db.execute("UPDATE users SET username=?,display_name=?,admin=?,departments=?,active=? WHERE id=?",
                                (username, name, int(admin), json.dumps(departments), int(active), user_id))
                if password:
                    self.db.execute("UPDATE users SET password=?,must_change=1,failures=0,locked_until=0 WHERE id=?",
                                    (hash_password(password), user_id))
            self._audit(actor.username, "user_saved", username)

    def users(self, actor_id):
        self.current(actor_id, admin=True)
        return self.db.execute("SELECT id,username,display_name,admin,active,departments,must_change FROM users ORDER BY username").fetchall()

    def change_password(self, user_id, old_password, new_password):
        user = self.current(user_id, allow_change=True)
        row = self.db.execute("SELECT password FROM users WHERE id=?", (user_id,)).fetchone()
        if not verify_password(old_password, row[0]):
            raise ValueError("The current password is incorrect.")
        if verify_password(new_password, row[0]):
            raise ValueError("Choose a different password.")
        encoded = hash_password(new_password)
        with self.db:
            self.db.execute("UPDATE users SET password=?,must_change=0 WHERE id=?", (encoded, user_id))
            self._audit(user.username, "password_changed")

    def entries(self, actor_id, department=None, kind=None):
        user = self.current(actor_id)
        rows = self.db.execute("SELECT * FROM entries ORDER BY title COLLATE NOCASE").fetchall()
        grants = self._grant_sources(user.id)
        visible = [self._entry(r) for r in rows if self._sources(user, r, grants)]
        if department is not None and not user.can_access(department) and not any(e.department == department for e in visible):
            raise PermissionError("You are not assigned to this workspace.")
        # Iterate catalog records once: multiple grants never duplicate a button.
        return [e for e in visible if (department is None or department == e.department) and (kind is None or kind == e.kind)]

    def available_departments(self, actor_id):
        user = self.current(actor_id)
        granted = {e.department for e in self.entries(actor_id)}
        return [d for d in DEPARTMENTS if user.can_access(d) or d in granted]

    def _grant_sources(self, user_id, group_ids=None, direct_ids=None):
        if group_ids is None:
            group_ids = [r[0] for r in self.db.execute('SELECT group_id FROM group_members WHERE user_id=?', (user_id,))]
        if direct_ids is None:
            direct_ids = [r[0] for r in self.db.execute('SELECT entry_id FROM user_tools WHERE user_id=?', (user_id,))]
        sources = {entry_id: ['Direct assignment'] for entry_id in direct_ids}
        # This also supports previewing unsaved group selections in the admin UI.
        if group_ids:
            placeholders = ','.join('?' for _ in group_ids)
            for row in self.db.execute(f'SELECT gt.entry_id,g.name FROM group_tools gt JOIN access_groups g ON g.id=gt.group_id WHERE g.id IN ({placeholders})', tuple(group_ids)):
                sources.setdefault(row['entry_id'], []).append(f"Group: {row['name']}")
        return sources

    @staticmethod
    def _sources(user, row, grants):
        if user.admin:
            return ['Administrator']
        sources = list(grants.get(row['id'], []))
        if not row['restricted'] and user.can_access(row['department']):
            sources.insert(0, 'Everyone' if row['department'] == 'general' else f"Department: {DEPARTMENTS[row['department']][0]}")
        return sources

    @staticmethod
    def _entry(row):
        return Entry(row["id"], row["department"], row["kind"], row["title"], row["description"], row["target"], tuple(json.loads(row["arguments"])), bool(row['restricted']))

    def authorized_entry(self, actor_id, entry_id):
        user = self.current(actor_id)
        row = self.db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
        if not row or not self._sources(user, row, self._grant_sources(user.id)):
            raise PermissionError("This tool is unavailable or you no longer have access.")
        entry = self._entry(row)
        validate_entry(entry.department, entry.kind, entry.title, entry.description, entry.target, entry.arguments)
        return entry

    def _insert_entry(self, department, kind, title, description, target, arguments):
        validate_entry(department, kind, title, description, target, arguments)
        self.db.execute("INSERT INTO entries(department,kind,title,description,target,arguments) VALUES (?,?,?,?,?,?)",
                        (department, kind, title.strip(), description.strip(), target.strip(), json.dumps(arguments)))

    def save_entry(self, actor_id, department, kind, title, description, target, arguments, entry_id=None, *, restricted=None):
        actor = self.current(actor_id, admin=True)
        validate_entry(department, kind, title, description, target, arguments)
        with self.db:
            if entry_id is None:
                self._insert_entry(department, kind, title, description, target, arguments)
                entry_id = self.db.execute('SELECT last_insert_rowid()').fetchone()[0]
            else:
                cursor = self.db.execute("UPDATE entries SET department=?,kind=?,title=?,description=?,target=?,arguments=? WHERE id=?",
                                        (department, kind, title.strip(), description.strip(), target.strip(), json.dumps(arguments), entry_id))
                if cursor.rowcount != 1:
                    raise ValueError("This entry no longer exists.")
            if restricted is not None:
                self.db.execute('UPDATE entries SET restricted=? WHERE id=?', (int(bool(restricted)), entry_id))
            self._bump_access_revision()
            self._audit(actor.username, "entry_saved", title)
        return entry_id

    def delete_entry(self, actor_id, entry_id):
        actor = self.current(actor_id, admin=True)
        with self.db:
            self.db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
            self._bump_access_revision()
            self._audit(actor.username, "entry_deleted", str(entry_id))

    def favorites(self, actor_id):
        self.current(actor_id)
        return {r[0] for r in self.db.execute("SELECT entry_id FROM favorites WHERE user_id=?", (actor_id,))}

    def toggle_favorite(self, actor_id, entry_id):
        self.authorized_entry(actor_id, entry_id)
        with self.db:
            if entry_id in self.favorites(actor_id):
                self.db.execute("DELETE FROM favorites WHERE user_id=? AND entry_id=?", (actor_id, entry_id))
            else:
                self.db.execute("INSERT INTO favorites VALUES (?,?)", (actor_id, entry_id))

    def record_event(self, actor_id, action, detail=""):
        actor = self.current(actor_id, allow_change=True)
        with self.db:
            self._audit(actor.username, action, detail)

    def audit(self, actor_id):
        self.current(actor_id, admin=True)
        return self.db.execute("SELECT occurred,actor,action,detail FROM audit ORDER BY id DESC LIMIT 500").fetchall()

    def access_revision(self):
        row = self.db.execute("SELECT value FROM metadata WHERE key='access_revision'").fetchone()
        return int(row[0]) if row else 0

    def _bump_access_revision(self):
        self.db.execute("INSERT INTO metadata VALUES ('access_revision','1') ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1")

    def groups(self, actor_id):
        self.current(actor_id, admin=True)
        return self.db.execute('SELECT g.*, (SELECT count(*) FROM group_members WHERE group_id=g.id) AS members, (SELECT count(*) FROM group_tools WHERE group_id=g.id) AS tools FROM access_groups g ORDER BY name COLLATE NOCASE').fetchall()

    def group_access(self, actor_id, group_id):
        self.current(actor_id, admin=True)
        if not self.db.execute('SELECT 1 FROM access_groups WHERE id=?', (group_id,)).fetchone():
            raise ValueError('This group no longer exists.')
        members = {r[0] for r in self.db.execute('SELECT user_id FROM group_members WHERE group_id=?', (group_id,))}
        entries = {r[0] for r in self.db.execute('SELECT entry_id FROM group_tools WHERE group_id=?', (group_id,))}
        return members, entries

    def save_group(self, actor_id, name, description, member_ids, entry_ids, group_id=None):
        actor = self.current(actor_id, admin=True)
        name, description = name.strip(), description.strip()
        if not name or len(name) > 80 or len(description) > 180:
            raise ValueError('Use a group name of 1–80 characters and a description up to 180 characters.')
        with self.db:
            if group_id is None:
                group_id = self.db.execute('INSERT INTO access_groups(name,description) VALUES (?,?)', (name, description)).lastrowid
            elif self.db.execute('UPDATE access_groups SET name=?,description=? WHERE id=?', (name, description, group_id)).rowcount != 1:
                raise ValueError('This group no longer exists.')
            self.db.execute('DELETE FROM group_members WHERE group_id=?', (group_id,))
            self.db.execute('DELETE FROM group_tools WHERE group_id=?', (group_id,))
            self.db.executemany('INSERT INTO group_members VALUES (?,?)', [(group_id, uid) for uid in set(member_ids)])
            self.db.executemany('INSERT INTO group_tools VALUES (?,?)', [(group_id, eid) for eid in set(entry_ids)])
            self._bump_access_revision()
            self._audit(actor.username, 'group_saved', name)
        return group_id

    def delete_group(self, actor_id, group_id):
        actor = self.current(actor_id, admin=True)
        with self.db:
            self.db.execute('DELETE FROM access_groups WHERE id=?', (group_id,))
            self._bump_access_revision()
            self._audit(actor.username, 'group_deleted', str(group_id))

    def user_access(self, actor_id, user_id):
        self.current(actor_id, admin=True)
        if not self.db.execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone():
            raise ValueError('This account no longer exists.')
        groups = {r[0] for r in self.db.execute('SELECT group_id FROM group_members WHERE user_id=?', (user_id,))}
        entries = {r[0] for r in self.db.execute('SELECT entry_id FROM user_tools WHERE user_id=?', (user_id,))}
        return groups, entries

    def set_user_access(self, actor_id, user_id, group_ids, entry_ids):
        actor = self.current(actor_id, admin=True)
        if not self.db.execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone():
            raise ValueError('This account no longer exists.')
        with self.db:
            self.db.execute('DELETE FROM group_members WHERE user_id=?', (user_id,))
            self.db.execute('DELETE FROM user_tools WHERE user_id=?', (user_id,))
            self.db.executemany('INSERT INTO group_members VALUES (?,?)', [(gid, user_id) for gid in set(group_ids)])
            self.db.executemany('INSERT INTO user_tools VALUES (?,?)', [(user_id, eid) for eid in set(entry_ids)])
            self._bump_access_revision()
            self._audit(actor.username, 'user_access_saved', str(user_id))

    def preview_access(self, actor_id, user_id, group_ids=None, direct_ids=None):
        self.current(actor_id, admin=True)
        row = self.db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not row:
            raise ValueError('This account no longer exists.')
        user = self._user(row)
        grants = self._grant_sources(user_id, group_ids, direct_ids)
        return {r['id']: (self._sources(user, r, grants) if row['active'] else ['Account disabled'])
                for r in self.db.execute('SELECT * FROM entries')}
