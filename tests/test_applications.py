"""Executable selection, icon propagation, and independent application editing."""

import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QFile, QFileInfo
from PySide6.QtWidgets import QDialog, QFileDialog, QPushButton

from tslibrary_ui.app import create_app
from tslibrary_ui import AdminWindow
from tslibrary_ui.applications import executable_path, parse_launch_target
from tslibrary_ui.shared.controls import TrashButton
from tslibrary_ui.licenses import LibraryItem


class ApplicationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.temp = TemporaryDirectory(prefix=".applications-test-", dir=root)
        # Keep automatic recursive cleanup confined to this test workspace.
        if Path(self.temp.name).resolve().parent != root:
            raise RuntimeError("Unexpected temporary test directory")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "Tools ツール"
        self.folder.mkdir()
        self.exe = self.folder / "Sample tool.EXE"
        shutil.copyfile(sys.executable, self.exe)
        self.other = self.folder / "Second tool.exe"
        shutil.copyfile(sys.executable, self.other)
        self.admin = AdminWindow()
        self.admin.set_page("Applications")
        self.admin.show()
        self.app.processEvents()

    def tearDown(self):
        for dialog in self.admin.findChildren(QDialog):
            dialog.close()
        self.admin.close()
        self.admin.deleteLater()
        self.app.processEvents()

    def add(self, path, name=None):
        self.admin.current_page.add_button.click()
        editor = self.admin.applications_page.application_dialog
        editor.path_edit.setText(str(path))
        if name:
            editor.name_edit.setText(name)
        editor.save_button.click()
        self.app.processEvents()
        return self.admin.applications_page.applications[-1]

    def test_browse_adds_executable_name_and_icon_without_running_it(self):
        self.admin.current_page.empty_button.click()
        editor = self.admin.applications_page.application_dialog
        with patch("tslibrary_ui.applications.dialogs.QFileDialog.getOpenFileName",
                   return_value=(str(self.exe), "Windows executables (*.exe)")) as picker:
            editor.browse_button.click()
        self.assertIn("*.exe", picker.call_args.args[3])
        self.assertEqual(editor.name_edit.text(), "Sample tool")
        self.assertEqual(editor.path_edit.text(), str(self.exe))
        self.assertFalse(editor.icon_preview.pixmap().isNull())
        selected_icon = editor._selected_icon.cacheKey()
        self.assertIn(self.exe.name, editor.icon_description.text())
        editor.save_button.click()
        self.app.processEvents()
        entry = self.admin.applications_page.applications[0]
        self.assertEqual((entry.name, entry.executable), ("Sample tool", str(self.exe.resolve())))
        self.assertFalse(entry.icon.isNull())
        self.assertEqual(entry.icon.cacheKey(), selected_icon)
        self.assertEqual(self.admin.applications_page.table.item(0, 0).icon().cacheKey(), selected_icon)
        self.assertEqual(self.admin.applications_page.table.item(0, 1).text(), entry.executable)
        self.assertIs(self.admin.current_page.content_stack.currentWidget(), self.admin.applications_page.table)

    def test_invalid_paths_are_rejected_and_cancel_does_not_add_anything(self):
        text_file = self.folder / "notes.txt"
        text_file.write_text("not an executable", encoding="utf-8")
        directory = self.folder / "directory.exe"
        directory.mkdir()
        self.admin.current_page.add_button.click()
        editor = self.admin.applications_page.application_dialog
        for path in ("", str(text_file), str(directory), str(self.folder / "missing.exe")):
            with self.subTest(path=path):
                editor.path_edit.setText(path)
                editor.save_button.click()
                self.assertEqual(editor.result(), QDialog.DialogCode.Rejected)
                self.assertTrue(editor.error.text())
                self.assertEqual(self.admin.applications_page.applications, [])
        editor.path_edit.setText(str(self.exe))
        editor.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(self.admin.applications_page.applications, [])

    def test_quoted_paths_custom_name_and_cancelled_picker(self):
        self.admin.current_page.add_button.click()
        editor = self.admin.applications_page.application_dialog
        editor.path_edit.setText(f'"{self.exe}"')
        editor.name_edit.setText("Custom name")
        with patch("tslibrary_ui.applications.dialogs.QFileDialog.getOpenFileName", return_value=("", "")):
            editor.browse_button.click()
        self.assertEqual(editor.path_edit.text(), f'"{self.exe}"')
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(self.admin.applications_page.applications[0].name, "Custom name")
        self.assertEqual(self.admin.applications_page.applications[0].executable, str(self.exe.resolve()))
        self.assertEqual(executable_path(f'  "{self.exe}"  '), self.exe.resolve())

    def test_edit_changes_path_and_icon_but_keeps_id_and_other_tabs(self):
        item = LibraryItem("License item")
        self.admin.licenses_page.items.append(item)
        entry = self.add(self.exe, "Original")
        application_id = entry.id
        self.admin.applications_page.table.cellWidget(0, 2).findChild(QPushButton).click()
        editor = self.admin.applications_page.application_dialog
        editor.path_edit.setText(str(self.other))
        editor.name_edit.setText("Updated")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((entry.id, entry.name, entry.executable),
                         (application_id, "Updated", str(self.other.resolve())))
        self.assertFalse(entry.icon.isNull())
        self.admin.set_page("Licenses")
        self.assertEqual(self.admin.licenses_page.table.item(0, 0).text(), "License item")
        self.admin.set_page("Websites")
        self.assertIs(self.admin.current_page.content_stack.currentWidget(), self.admin.current_page.empty_state)
        self.admin.set_page("Applications")
        self.assertEqual(self.admin.applications_page.table.item(0, 0).text(), "Updated")
        self.assertEqual(self.admin.licenses_page.items, [item])

    def test_search_sort_and_edit_use_the_selected_application_id(self):
        first = self.add(self.exe, "Alpha")
        second = self.add(self.other, "Beta")
        self.assertEqual(self.admin.applications_page.table.item(0, 0).text(), "Beta")
        self.admin.current_page.sort_select.setCurrentIndex(1)
        self.assertEqual(self.admin.applications_page.table.item(0, 0).text(), "Alpha")
        self.admin.current_page.search.setText(self.other.name)
        self.assertEqual(self.admin.applications_page.table.rowCount(), 1)
        self.admin.applications_page._edit_application_row(0, 0)
        editor = self.admin.applications_page.application_dialog
        editor.name_edit.setText("Renamed")
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((first.name, second.name), ("Alpha", "Renamed"))
        self.admin.current_page.search.setText("no match")
        self.assertIs(self.admin.current_page.content_stack.currentWidget(), self.admin.current_page.empty_state)
        self.assertEqual(self.admin.current_page.empty_heading.text(), "No matching applications.")
        self.assertFalse(self.admin.current_page.empty_button.isVisible())
        self.admin.current_page.search.clear()
        self.assertEqual(self.admin.applications_page.table.rowCount(), 2)

    def test_remove_is_confirmed_only_changes_list_and_keeps_executable(self):
        first = self.add(self.exe, "Same name")
        second = self.add(self.other, "Same name")
        self.admin.applications_page.table.cellWidget(0, 2).findChild(TrashButton).click()
        self.admin.applications_page.remove_application_dialog.cancel_button.click()
        self.app.processEvents()
        self.assertEqual(len(self.admin.applications_page.applications), 2)
        self.admin.applications_page.table.cellWidget(0, 2).findChild(TrashButton).click()
        self.admin.applications_page.remove_application_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual([entry.id for entry in self.admin.applications_page.applications], [first.id])
        self.assertTrue(Path(second.executable).is_file())
        self.admin.applications_page.confirm_remove_application(first)
        self.admin.applications_page.remove_application_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(self.admin.applications_page.applications, [])
        self.assertIs(self.admin.current_page.content_stack.currentWidget(), self.admin.current_page.empty_state)
        self.assertTrue(self.admin.current_page.empty_button.isVisible())

    def test_edit_cancel_keeps_name_path_and_icon(self):
        entry = self.add(self.exe, "Keep this name")
        original_icon = entry.icon.cacheKey()
        self.admin.applications_page.add_application(entry)
        editor = self.admin.applications_page.application_dialog
        editor.path_edit.setText(str(self.other))
        editor.name_edit.setText("Discard this name")
        editor.cancel_button.click()
        self.app.processEvents()
        self.assertEqual((entry.name, entry.executable, entry.icon.cacheKey()),
                         ("Keep this name", str(self.exe.resolve()), original_icon))

    def test_target_arguments_quotes_and_backslashes_survive_save_and_edit(self):
        arguments = r'-launch -reg --config "C:\Data Folder\settings.json" --empty "" --value \\"quoted\\"'
        target = f'"{self.exe}" {arguments}'
        entry = self.add(target)
        self.assertEqual(entry.executable, str(self.exe.resolve()))
        self.assertEqual(entry.arguments, arguments)
        self.assertEqual(entry.launch_target, f'"{self.exe.resolve()}" {arguments}')
        self.assertEqual(self.admin.applications_page.table.item(0, 1).text(), entry.launch_target)
        self.admin.current_page.search.setText("--config")
        self.assertEqual(self.admin.applications_page.table.rowCount(), 1)
        self.admin.applications_page.add_application(entry)
        editor = self.admin.applications_page.application_dialog
        self.assertEqual(editor.path_edit.text(), entry.launch_target)
        icon_key = editor._selected_icon.cacheKey()
        editor.path_edit.setText(f'"{self.exe}" -reg')
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(entry.arguments, "-reg")
        self.assertEqual(entry.icon.cacheKey(), icon_key)
        self.admin.applications_page.add_application(entry)
        editor = self.admin.applications_page.application_dialog
        editor.path_edit.setText(str(self.exe))
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(entry.arguments, "")

    def test_unquoted_simple_and_environment_paths_with_arguments(self):
        plain = Path(self.temp.name) / "plain.exe"
        shutil.copyfile(sys.executable, plain)
        path, arguments = parse_launch_target(f'{plain} -launch -reg "two words"')
        self.assertEqual(path, plain.resolve())
        self.assertEqual(arguments, '-launch -reg "two words"')
        with patch.dict(os.environ, {"TSLIBRARY_TEST_APP": str(self.exe)}):
            path, arguments = parse_launch_target('$TSLIBRARY_TEST_APP -launch "$KEEP_THIS"')
        self.assertEqual(path, self.exe.resolve())
        self.assertEqual(arguments, '-launch "$KEEP_THIS"')

    def test_browse_replaces_file_but_preserves_arguments(self):
        entry = self.add(f'"{self.exe}" -launch -reg')
        self.admin.applications_page.add_application(entry)
        editor = self.admin.applications_page.application_dialog
        with patch("tslibrary_ui.applications.dialogs.QFileDialog.getOpenFileName",
                   return_value=(str(self.other), "Executables (*.exe)")) as picker:
            editor.browse_button.click()
        self.assertEqual(picker.call_args.args[2], str(self.exe.resolve()))
        self.assertEqual(editor.path_edit.text(), f'"{self.other}" -launch -reg')
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((entry.executable, entry.arguments), (str(self.other.resolve()), "-launch -reg"))

    def test_invalid_or_ambiguous_targets_are_rejected(self):
        self.admin.current_page.add_button.click()
        editor = self.admin.applications_page.application_dialog
        for target in (f'"{self.exe} -launch', f'"{self.exe}"-launch',
                       f'{self.exe} -launch', f'"{self.folder / "missing.exe"}" -reg', '"" -launch'):
            with self.subTest(target=target):
                editor.path_edit.setText(target)
                editor.save_button.click()
                self.assertEqual(editor.result(), QDialog.DialogCode.Rejected)
                self.assertTrue(editor.error.text())
                self.assertEqual(self.admin.applications_page.applications, [])

    @unittest.skipUnless(os.name == "nt", "Windows shell shortcuts")
    def test_browse_keeps_shortcut_path_name_and_icon_instead_of_target(self):
        shortcut = self.folder / "My application shortcut.lnk"
        self.assertTrue(QFile(str(self.exe)).link(str(shortcut)))
        self.assertTrue(QFileInfo(str(shortcut)).isShortcut())
        original_bytes = shortcut.read_bytes()
        self.admin.current_page.add_button.click()
        editor = self.admin.applications_page.application_dialog
        with patch("tslibrary_ui.applications.dialogs.QFileDialog.getOpenFileName",
                   return_value=(str(shortcut), "Applications and shortcuts (*.exe *.lnk)")) as picker:
            editor.browse_button.click()
        self.assertIn("*.lnk", picker.call_args.args[3])
        self.assertTrue(picker.call_args.kwargs["options"] & QFileDialog.Option.DontResolveSymlinks)
        self.assertEqual(editor.name_edit.text(), shortcut.stem)
        self.assertIn(shortcut.name, editor.icon_description.text())
        selected_icon = editor._selected_icon.cacheKey()
        editor.save_button.click()
        self.app.processEvents()
        entry = self.admin.applications_page.applications[0]
        self.assertEqual(entry.executable, str(shortcut.resolve()))
        self.assertNotEqual(entry.executable, str(self.exe.resolve()))
        self.assertEqual(entry.icon.cacheKey(), selected_icon)
        self.assertFalse(entry.icon.isNull())
        self.assertEqual(shortcut.read_bytes(), original_bytes)
        self.assertEqual(self.admin.applications_page.table.item(0, 1).text(), str(shortcut.resolve()))

    @unittest.skipUnless(os.name == "nt", "Windows shell shortcuts")
    def test_quoted_shortcut_path_can_be_edited_and_removed_without_changing_files(self):
        shortcut = self.folder / "Shortcut ツール.lnk"
        self.assertTrue(QFile(str(self.exe)).link(str(shortcut)))
        entry = self.add(f'"{shortcut}"', "Friendly name")
        entry_id = entry.id
        self.admin.applications_page.add_application(entry)
        editor = self.admin.applications_page.application_dialog
        self.assertEqual(editor.path_edit.text(), str(shortcut.resolve()))
        editor.path_edit.setText(str(self.other))
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual((entry.id, entry.name, entry.executable),
                         (entry_id, "Friendly name", str(self.other.resolve())))
        self.admin.applications_page.add_application(entry)
        editor = self.admin.applications_page.application_dialog
        editor.path_edit.setText(str(shortcut))
        editor.save_button.click()
        self.app.processEvents()
        self.assertEqual(entry.executable, str(shortcut.resolve()))
        self.admin.applications_page.confirm_remove_application(entry)
        self.admin.applications_page.remove_application_dialog.delete_button.click()
        self.app.processEvents()
        self.assertEqual(self.admin.applications_page.applications, [])
        self.assertTrue(shortcut.is_file())
        self.assertTrue(self.exe.is_file())


if __name__ == "__main__":
    unittest.main()
