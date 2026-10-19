"""Render real Qt widgets for visual QA without opening applications or websites."""
import os
from pathlib import Path
import sys

if "--native" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "windows"
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from worktool.app import MainWindow
from worktool.dialogs import AdminDialog, GroupDialog
from worktool.store import Store
from worktool.theme import STYLE


def main():
    output = Path(__file__).resolve().parents[1] / "test-artifacts"
    output.mkdir(exist_ok=True)
    app = QApplication([])
    # The offscreen Windows plugin does not enumerate installed fonts. Register
    # the same system fonts explicitly for faithful screenshots (no font copies).
    for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf"):
        source = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font
        if source.exists():
            QFontDatabase.addApplicationFont(str(source))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    store = Store(output / "preview.sqlite3")
    store.seed_demo()
    window = MainWindow(store, demo=True)
    window.show()
    QTest.qWait(250)
    window.grab().save(str(output / "login.png"))
    user = store.authenticate("admin", "WorkTool!2026")
    store.save_appearance("light", "purple", user.id)
    window.signed_in(user)
    QTest.qWait(250)
    window.grab().save(str(output / "workspace.png"))
    workspace = window.centralWidget()
    for mode in ("light", "dark"):
        for accent in ("purple", "pink"):
            workspace.appearance.buttons[mode].click()
            workspace.appearance.buttons[accent].click()
            QTest.qWait(250)
            window.grab().save(str(output / f"workspace-{mode}-{accent}.png"))
    workspace.departments.widget(0).setCurrentIndex(1)
    QTest.qWait(250)
    window.grab().save(str(output / "links.png"))
    window.resize(1000, 720)
    QTest.qWait(250)
    window.grab().save(str(output / "compact.png"))
    window.resize(1280, 880)
    sample_user = store.authenticate('it.demo', 'WorkTool!2026')
    groups = store.groups(user.id)
    sample = next((g for g in groups if g['name'] == 'Project Atlas'), None)
    if sample is None:
        store.save_group(user.id, 'Project Atlas', 'A shared project workspace', [sample_user.id],
                         [e.id for e in store.entries(user.id, 'finance', 'link')[:2]])
    workspace.administration()
    panel = workspace.admin_panel
    panel.tabs.setCurrentIndex(1)
    QTest.qWait(250)
    window.grab().save(str(output / 'admin-groups.png'))
    panel.tabs.setCurrentIndex(2)
    panel.access_panel.user.setCurrentIndex(panel.access_panel.user.findData(sample_user.id))
    QTest.qWait(250)
    window.grab().save(str(output / 'admin-user-access.png'))
    group = next(g for g in store.groups(user.id) if g['name'] == 'Project Atlas')
    editor = GroupDialog(store, user, group, window)
    editor.show()
    QTest.qWait(250)
    editor.grab().save(str(output / 'group-editor.png'))
    editor.reject()
    admin = AdminDialog(store, window.user, window)
    admin.show()
    QTest.qWait(250)
    admin.grab().save(str(output / "administration.png"))
    admin.close()
    window.close()
    store.close()
    print(f"Screenshots saved in {output}")


if __name__ == "__main__":
    main()
