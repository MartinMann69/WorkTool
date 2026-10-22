"""One Windows process per PC, with a local wake-up signal for later launches.

A Global Windows mutex is the exclusive lease; a local Qt socket only asks the
first process to raise its current window. No credentials or startup flags are
forwarded. The OS releases mutex handles even when a process crashes.

References:
https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw
https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QLocalServer.html
"""

import os
from pathlib import Path
import time

from PySide6.QtCore import QDir, QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class InstanceError(RuntimeError):
    """Single-instance startup could not be established safely."""


class SingleInstance(QObject):
    activation_requested = Signal()
    DEFAULT_NAME = "TSLibrary.Desktop.80d069e4"

    def __init__(self, parent=None, *, name=DEFAULT_NAME):
        super().__init__(parent)
        self.name = name
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._activate)
        self.notified = False
        self._primary = False
        self._handle = None
        self._kernel = None
        self._file_lock = None

    def _claim(self):
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle.restype = wintypes.BOOL
            ctypes.set_last_error(0)
            handle = kernel.CreateMutexW(None, False, "Global\\" + self.name)
            error = ctypes.get_last_error()
            if not handle:
                # Another Windows user's existing mutex can deny access. Still
                # refuse a second instance instead of creating a separate one.
                if error == 5:
                    return False
                raise InstanceError(f"Could not reserve the TSLibrary instance: {ctypes.WinError(error)}")
            if error == 183:  # ERROR_ALREADY_EXISTS
                kernel.CloseHandle(handle)
                return False
            self._kernel, self._handle = kernel, handle
            return True

        # Non-Windows UI previews use Qt's crash-aware file lock.
        self._file_lock = QLockFile(str(Path(QDir.tempPath()) / f"{self.name}.lock"))
        self._file_lock.setStaleLockTime(0)
        if self._file_lock.tryLock(0):
            return True
        if self._file_lock.error() == QLockFile.LockError.LockFailedError:
            return False
        raise InstanceError("Could not reserve the TSLibrary instance in the temporary directory.")

    def start(self):
        """Return True for the owner; otherwise notify it and return False."""
        if self._primary:
            return True
        if not self._claim():
            self.notified = self._notify_existing()
            return False
        self._primary = True
        # Only the exclusive owner may clean up a stale Unix socket. QLocalServer
        # by itself is not an exclusive lock on Windows (multiple listeners work).
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            message = self.server.errorString()
            self.close()
            raise InstanceError(f"Could not start TSLibrary's activation channel: {message}")
        return True

    def _notify_existing(self):
        # The winning process may be between acquiring its lease and listening.
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            socket = QLocalSocket()
            socket.connectToServer(self.name)
            if socket.waitForConnected(100):
                socket.disconnectFromServer()
                return True
            socket.abort()
            time.sleep(.05)
        return False

    def _activate(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            # A connection means only 'show your current window'. No payload is
            # accepted, so this cannot navigate into administration.
            socket.disconnectFromServer()
            socket.deleteLater()
            self.activation_requested.emit()

    def close(self):
        if not self._primary:
            return
        self.server.close()
        if self._handle is not None:
            self._kernel.CloseHandle(self._handle)
            self._handle = None
        if self._file_lock is not None:
            self._file_lock.unlock()
        self._primary = False
