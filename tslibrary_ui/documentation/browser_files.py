"""Background directory reads for the inline documentation file browser."""

from PySide6.QtCore import QObject, QRunnable, Signal

from .files import DocumentationError, DocumentationFiles


class DirectorySignals(QObject):
    finished = Signal(object, object, str)


class ReadDirectory(QRunnable):
    def __init__(self, catalog, folder, recursive):
        super().__init__()
        self.catalog, self.folder, self.recursive = catalog, folder, recursive
        self.signals = DirectorySignals()

    def run(self):
        try:
            entries = DocumentationFiles(self.catalog).list_directory(self.folder, recursive=self.recursive)
        except (OSError, ValueError, DocumentationError) as error:
            self.signals.finished.emit(self, [], str(error))
        else:
            self.signals.finished.emit(self, entries, "")


class DeleteSignals(QObject):
    finished = Signal(str)


class DeleteStaged(QRunnable):
    """Remove already committed contents without blocking the file browser."""
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.signals = DeleteSignals()

    def run(self):
        try:
            DocumentationFiles.finish_delete(self.path)
        except OSError as error:
            self.signals.finished.emit(f"The item was removed from the library, but some files could not be deleted at {self.path}: {error}")
        else:
            self.signals.finished.emit("")

