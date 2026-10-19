"""Launch only validated, authorized catalog records; never invoke a command shell."""
from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QDesktopServices

from .catalog import resolve_executable


def launch(store, user_id, entry_id):
    entry = store.authorized_entry(user_id, entry_id)
    if entry.kind == "link":
        if not QDesktopServices.openUrl(QUrl(entry.target)):
            store.record_event(user_id, "launch_failed", f"entry:{entry.id}")
            raise OSError("Windows could not open the default browser. Check your default browser settings.")
    else:
        executable = resolve_executable(entry.target)
        if not executable:
            store.record_event(user_id, "launch_missing", f"entry:{entry.id}")
            raise FileNotFoundError(
                f"{entry.title} is not installed at the configured location.\n\n"
                f"Configured path: {entry.target}\n\n"
                "Ask your administrator to install the application or update its path in Administration → Tool catalog."
            )
        success, _pid = QProcess.startDetached(executable, list(entry.arguments))
        if not success:
            store.record_event(user_id, "launch_failed", f"entry:{entry.id}")
            raise OSError("Windows could not start this application. Check its installation and your Windows permissions.")
    store.record_event(user_id, "launch_requested", f"entry:{entry.id}")
    return entry.title
