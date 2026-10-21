"""Read a selected Windows file/shortcut icon without launching it."""

from pathlib import Path

from PySide6.QtCore import QFileInfo
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileIconProvider, QStyle


def executable_icon(path: str | Path) -> QIcon:
    # QFileInfo makes the Windows shell inspect this specific file rather than
    # asking for a generic association. For .lnk files this also respects the
    # shortcut's own icon. This reads the file's icon, never runs it.
    result = QFileIconProvider().icon(QFileInfo(str(path)))
    if result.isNull():
        result = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
    return result
