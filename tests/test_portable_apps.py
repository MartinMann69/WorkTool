"""Shared app references resolve on another PC without publishing a user path."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tslibrary_ui.app import create_app
from tslibrary_ui.applications.dialogs import ApplicationDialog
from tslibrary_ui.applications.models import Application
from tslibrary_ui.applications.portable import describe_target, portable_hint, validate_target
from tslibrary_ui.applications.resolver import capture_target, resolve_application, resolve_target
from tslibrary_ui.migrations import DataSchema
from tslibrary_ui.state import LibrarySession, WorkplaceConfig
from tslibrary_ui.storage import JsonRepository, catalog_data, decode_catalog, workplace_data
from tslibrary_ui.team_config import SharedJsonCatalogStore
from tslibrary_ui.workplace.launching import ResourceLauncher
from tslibrary_ui.workplace.models import effective_application


class PortableAppChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.app.processEvents()
        self.directory.cleanup()

    def file(self, relative):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture only; never executed")
        return path.resolve()

    def test_legacy_paths_rebase_different_admin_and_redirected_desktop(self):
        cases = {
            r"C:\Users\Alice\Desktop\Anki.lnk": r"%DESKTOP%\Anki.lnk",
            r"C:\Users\Alice\OneDrive - Company\Desktop\Word.lnk": r"%DESKTOP%\Word.lnk",
            r"C:\Users\Alice\AppData\Local\Programs\Anki\anki.exe": r"%LOCALAPPDATA%\Programs\Anki\anki.exe",
            r"C:\Users\Alice\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Word.lnk": r"%STARTMENU%\Programs\Word.lnk",
            r"C:\Users\Public\Desktop\Company.lnk": r"%PUBLIC_DESKTOP%\Company.lnk",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                target = describe_target(path)
                self.assertEqual(target["hint"], expected)
                self.assertNotIn("Alice", json.dumps(target))

    def test_shortcut_uses_current_users_redirected_desktop_and_is_not_flattened(self):
        alice = self.file("Alice/Desktop/Word.lnk")
        bob = self.file("Bob/OneDrive/Desktop/Word.lnk")
        with patch("tslibrary_ui.applications.resolver.local_roots", return_value={"DESKTOP": str(alice.parent)}):
            target = capture_target(alice)
        record = Application("Word", str(alice), arguments='--profile "Team profile"', target=target)
        payload = catalog_data(LibrarySession(applications=[record]))
        self.assertNotIn(str(alice), json.dumps(payload))
        self.assertNotIn("Alice", json.dumps(payload))
        with patch("tslibrary_ui.applications.resolver.local_roots", return_value={"DESKTOP": str(bob.parent)}), \
             patch("tslibrary_ui.applications.resolver.app_paths") as registry, \
             patch("tslibrary_ui.workplace.launching.os.startfile", create=True) as launch:
            loaded = decode_catalog(payload).applications[0]
            ResourceLauncher().open_application(loaded)
            launch.assert_called_once_with(str(bob), "open", arguments='--profile "Team profile"')
            registry.assert_not_called()
        self.assertEqual(alice.read_bytes(), bob.read_bytes())

    def test_redirected_custom_desktop_uses_qt_forward_slash_roots(self):
        self.assertEqual(portable_hint(r"D:\Company\Alice\Workspace\Word.lnk",
                         {"DESKTOP": "D:/Company/Alice/Workspace"}), r"%DESKTOP%\Word.lnk")
        self.assertEqual(portable_hint(r"\\?\C:\Users\Alice\Desktop\Word.lnk"), r"%DESKTOP%\Word.lnk")

    def test_missing_shortcut_never_falls_back_to_the_first_admins_path(self):
        alice = self.file("Alice/Desktop/Word.lnk")
        with patch("tslibrary_ui.applications.resolver.local_roots", return_value={"DESKTOP": str(alice.parent)}):
            target = capture_target(alice)
        with patch("tslibrary_ui.applications.resolver.local_roots", return_value={"DESKTOP": str(self.root / "Bob/Desktop")}), \
             patch("tslibrary_ui.workplace.launching.os.startfile", create=True) as launch:
            with self.assertRaisesRegex(ValueError, "shortcut"):
                ResourceLauncher().open_application(Application("Word", str(alice), target=target))
            launch.assert_not_called()

    def test_installed_executable_uses_local_app_paths_instead_of_the_admins_hint(self):
        installed = self.file("Bob/Apps/Office/WINWORD.EXE")
        target = describe_target(r"C:\Users\Alice\AppData\Local\OldOffice\WINWORD.EXE")
        with patch("tslibrary_ui.applications.resolver.app_paths", return_value=[installed]), \
             patch("tslibrary_ui.workplace.launching.os.startfile", create=True) as launch:
            ResourceLauncher().open_application(Application("Word", "", target=target, arguments="-safe"))
            launch.assert_called_once_with(str(installed), "open", arguments="-safe")

    def test_install_location_identity_follows_a_different_install_root(self):
        alice = self.file("Alice/Anki/bin/anki.exe")
        bob = self.file("Bob/Anki 2/bin/anki.exe")
        registered = dict(key="Anki-product", name="Anki", publisher="Anki", location=str(alice.parent.parent))
        with patch("tslibrary_ui.applications.resolver.local_roots", return_value={"USERPROFILE": str(self.root / "Alice")}), \
             patch("tslibrary_ui.applications.resolver.installations", return_value=[registered]):
            target = capture_target(alice)
        self.assertNotIn("Alice", json.dumps(target))
        with patch("tslibrary_ui.applications.resolver.installations", return_value=[dict(registered, location=str(bob.parent.parent))]), \
             patch("tslibrary_ui.applications.resolver.app_paths", return_value=[]):
            self.assertEqual(resolve_target(target), bob)

    def test_broad_install_location_cannot_publish_a_profile_in_the_relative_path(self):
        alice = self.file("Alice/Anki/bin/anki.exe")
        registered = dict(key="Too-broad", name="Installer", publisher="Vendor", location=str(self.root))
        with patch("tslibrary_ui.applications.resolver.local_roots", return_value={"USERPROFILE": str(self.root / "Alice")}), \
             patch("tslibrary_ui.applications.resolver.installations", return_value=[registered]):
            target = capture_target(alice)
        self.assertNotIn("installation", target)
        self.assertNotIn("Alice", json.dumps(target))

    def test_ambiguous_registration_requires_local_choice(self):
        first = self.file("one/app.exe")
        second = self.file("two/app.exe")
        with patch("tslibrary_ui.applications.resolver.app_paths", return_value=[first, second]):
            with self.assertRaisesRegex(ValueError, "More than one"):
                resolve_target(dict(kind="installed", filename="app.exe", hint=""))

    def test_existing_selected_installation_is_kept_when_windows_registers_another_version(self):
        selected = self.file("Selected version/app.exe")
        other = self.file("Different version/app.exe")
        with patch("tslibrary_ui.applications.resolver.app_paths", return_value=[other]):
            self.assertEqual(resolve_target(describe_target(str(selected))), selected)

    def test_unsafe_reference_paths_are_rejected(self):
        for target in (dict(kind="installed", filename="../app.exe", hint=""),
                       dict(kind="shortcut", filename="app.lnk", hint=r"C:\Users\Alice\Desktop\app.lnk"),
                       dict(kind="installed", filename="app.exe", hint="", installation=dict(
                           key="app", name="App", publisher="Vendor", relative_executable=r"..\app.exe"))):
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate_target(target)

    def test_personal_paths_stay_local_and_override_wins_over_shared_detection(self):
        local = self.file("Local/selected.exe")
        shared = Application("App", r"C:\Old\app.exe", id="app", target=describe_target(r"C:\Old\app.exe"))
        config = WorkplaceConfig(application_overrides={"applications:catalog:app": str(local)},
                                 personal_applications=[Application("Private", str(local))])
        with patch("tslibrary_ui.applications.resolver.app_paths") as registry:
            self.assertEqual(resolve_application(effective_application(shared, config)), local)
            registry.assert_not_called()
        data = workplace_data(config)
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["personal_applications"][0]["executable"], str(local))
        self.assertNotIn("target", data["personal_applications"][0])

    def test_legacy_local_and_shared_catalog_upgrade_preserves_ids_and_exact_backup(self):
        raw = ('\ufeff' + json.dumps(dict(version=1, applications=[dict(id="stable-app", name="Word",
               executable=r"C:\Users\Alice\Desktop\Word.lnk", arguments="-safe")]))).encode("utf-8")
        for shared in (False, True):
            with self.subTest(shared=shared):
                path = self.root / ("shared.json" if shared else "local.json")
                path.write_bytes(raw)
                store = SharedJsonCatalogStore(path) if shared else JsonRepository(path, self.root / "personal.json")
                loaded = store.load_catalog()
                self.assertEqual(loaded.applications[0].id, "stable-app")
                self.assertEqual(loaded.applications[0].arguments, "-safe")
                self.assertNotIn("Alice", path.read_text())
                backups = list(self.root.glob(path.name + ".before-migration-*.bak"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), raw)
                store.load_catalog()
                self.assertEqual(len(list(self.root.glob(path.name + ".before-migration-*.bak"))), 1)
                with self.assertRaisesRegex(ValueError, "newer data version"):
                    DataSchema("old catalog", 1, {}).upgrade(json.loads(path.read_text()))

    def test_renaming_a_missing_portable_entry_keeps_its_reference_and_arguments(self):
        original = Application("Word", "", id="stable", arguments="-safe", target=describe_target(r"C:\Missing\word.exe"))
        with patch("tslibrary_ui.applications.resolver.app_paths", return_value=[]):
            editor = ApplicationDialog(application=original)
        editor.name_edit.setText("Microsoft Word")
        editor.save_button.click()
        self.assertTrue(editor.result())
        updated = editor.application()
        self.assertEqual(updated.id, original.id)
        self.assertEqual(updated.target, original.target)
        self.assertEqual(updated.arguments, "-safe")
        editor.deleteLater()


if __name__ == "__main__":
    unittest.main()
