"""Local window placement shared by app screens and remembered for dialogs."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from weakref import WeakKeyDictionary, WeakSet

from PySide6.QtCore import QByteArray, QEvent, QObject, QRect, QSettings, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from .shared.confirmation import ConfirmDeleteDialog


def create_window_settings():
    """Keep display preferences local, beside the user's workplace config."""
    user_root = Path(os.environ.get("APPDATA") or str(Path.home() / ".config"))
    config = Path(os.environ.get("TSLIBRARY_CONFIG_PATH", str(user_root / "TSLibrary" / "workplace.json")))
    return QSettings(str(config.with_name("window-state.ini")), QSettings.Format.IniFormat)


@dataclass
class WindowPlacement:
    geometry: QByteArray
    maximized: bool = True
    normal_rect: QRect | None = None


class WindowStateManager(QObject):
    """Start maximized; carry user sizing through navigation and app restarts.

    The four main screens share one placement. Content dialogs initially follow
    their parent and then remember their own placement by dialog type. Native
    pickers, messages, and delete confirmations keep their usual dialog layout.
    Passing no QSettings makes previews/tests entirely in-memory.
    """

    _EVENTS = frozenset((QEvent.Type.Polish, QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Close,
                         QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.WindowStateChange))

    def __init__(self, windows, *, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.main_windows = set(windows)
        self.active_main = None
        self._keys = WeakKeyDictionary((window, "main") for window in windows)
        self._ready = WeakSet()
        self._restoring = WeakSet()
        self._placements = {}
        self._pending = set()
        self._dirty = set()
        self._reported_error = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.flush)
        app = QApplication.instance()
        app.installEventFilter(self)
        app.aboutToQuit.connect(self.flush)

    def _read(self, key):
        if key in self._placements:
            return self._placements[key]
        if self.settings is None or not self.settings.contains(f"{key}/maximized"):
            return None
        geometry = self.settings.value(f"{key}/geometry", QByteArray())
        if not isinstance(geometry, QByteArray):
            geometry = QByteArray()
        try:
            maximized = self.settings.value(f"{key}/maximized", True, type=bool)
        except (TypeError, ValueError):
            maximized = True
        placement = WindowPlacement(geometry, maximized)
        self._placements[key] = placement
        return placement

    def _owns(self, window):
        parent = window.parentWidget()
        while parent is not None:
            if parent in self.main_windows:
                return True
            parent = parent.parentWidget()
        return False

    def _key(self, window):
        key = self._keys.get(window)
        if key is None and (isinstance(window, QDialog) and window.isWindow()
                            and window.objectName() == "inventoryDialog"
                            and not isinstance(window, ConfirmDeleteDialog) and self._owns(window)):
            key = f"dialogs/{type(window).__module__}.{type(window).__qualname__}"
            self._keys[window] = key
        return key

    def _capture(self, window, key, *, previous_state=None):
        if (window not in self._ready or window in self._restoring
                or (window.isMinimized() and previous_state is None)):
            return
        if key == "main" and window is not self.active_main:
            return
        state = window.windowState() if previous_state is None else previous_state
        maximized = bool(state & Qt.WindowState.WindowMaximized)
        normal_rect = window.normalGeometry() if maximized or window.isMinimized() else window.geometry()
        placement = WindowPlacement(window.saveGeometry(), maximized, QRect(normal_rect))
        if self._placements.get(key) != placement:
            self._placements[key] = placement
            self._dirty.add(key)

    def _restore(self, window, placement):
        self._restoring.add(window)
        try:
            if placement.geometry:
                # Qt also moves windows back onto an available monitor when a
                # previously saved screen has been disconnected or rearranged.
                window.restoreGeometry(placement.geometry)
            if placement.normal_rect is not None and placement.normal_rect.isValid():
                # Navigation on the current desktop should preserve the exact
                # chosen rectangle. Qt's offscreen/small-screen restore may
                # otherwise shrink it to the destination's default size.
                window.setWindowState(Qt.WindowState.WindowNoState)
                window.setGeometry(placement.normal_rect)
            state = window.windowState() & ~(Qt.WindowState.WindowMinimized | Qt.WindowState.WindowFullScreen)
            if placement.maximized:
                state |= Qt.WindowState.WindowMaximized
            else:
                state &= ~Qt.WindowState.WindowMaximized
            window.setWindowState(state)
        finally:
            self._restoring.discard(window)

    def _show(self, window, key):
        if key == "main":
            if self.active_main is not None and self.active_main is not window:
                self._capture(self.active_main, "main")
            self.active_main = window
        placement = self._read(key)
        if placement is None:
            # First-time dialogs inherit their immediate content window's size
            # and state, including when the parent has been restored down.
            parent = window.parentWidget()
            while parent is not None:
                parent_key = self._keys.get(parent)
                if parent_key is not None:
                    self._capture(parent, parent_key)
                    placement = self._read(parent_key)
                    break
                parent = parent.parentWidget()
        self._restore(window, placement or WindowPlacement(QByteArray()))
        self._ready.add(window)
        self._pending.add(window)
        self._timer.start()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind not in self._EVENTS or not isinstance(watched, QWidget):
            return False
        key = self._key(watched)
        if key is None or watched in self._restoring:
            return False
        if kind == QEvent.Type.Polish and isinstance(watched, QDialog):
            # Inverting a PySide WindowType flag can truncate higher bits,
            # including WindowCloseButtonHint. Mask integer bits instead.
            flags = int(watched.windowFlags()) & ~int(Qt.WindowType.WindowContextHelpButtonHint)
            flags |= int(Qt.WindowType.WindowMaximizeButtonHint
                         | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
            watched.setWindowFlags(Qt.WindowType(flags))
        elif kind == QEvent.Type.Show:
            if watched in self._ready and (key != "main" or watched is self.active_main):
                # Maximize/restore/minimize can generate Show again for an
                # already displayed window. Do not replace the user's change
                # with a placement captured before that state transition.
                self._pending.add(watched)
                self._timer.start()
            else:
                self._show(watched, key)
        elif watched in self._ready:
            if kind == QEvent.Type.WindowStateChange and watched.isMinimized():
                self._capture(watched, key, previous_state=event.oldState())
                self._timer.start()
            elif kind in (QEvent.Type.Close, QEvent.Type.Hide):
                self._capture(watched, key)
                self.flush()
            elif watched.isVisible():
                self._pending.add(watched)
                self._timer.start()
        return False

    def flush(self):
        self._timer.stop()
        pending, self._pending = self._pending, set()
        for window in pending:
            try:
                key = self._keys.get(window)
                if key is not None and window.isVisible():
                    self._capture(window, key)
            except RuntimeError:
                # WA_DeleteOnClose dialogs may have been destroyed before the
                # resize debounce fires. Their Hide/Close event already saved.
                continue
        if self.settings is None or not self._dirty:
            return
        for key in self._dirty:
            placement = self._placements[key]
            self.settings.setValue(f"{key}/geometry", placement.geometry)
            self.settings.setValue(f"{key}/maximized", placement.maximized)
        self.settings.sync()
        if self.settings.status() == QSettings.Status.NoError:
            self._dirty.clear()
        elif not self._reported_error:
            logging.getLogger(__name__).warning("Could not save window placement to %s", self.settings.fileName())
            self._reported_error = True
