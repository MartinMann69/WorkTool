"""Read shared catalog bytes off the GUI thread; construct Qt icons on the GUI."""

from PySide6.QtCore import QObject, QRunnable, Signal

from .storage import StorageError


class RefreshSignals(QObject):
    finished = Signal(object, object, object)


class CatalogRefresh(QRunnable):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.signals = RefreshSignals()

    def run(self):
        try:
            raw, error = self.store.snapshot_bytes(), None
        except StorageError as failure:
            raw, error = None, failure
        self.signals.finished.emit(self, raw, error)
