"""Session-only data shared by admin pages; no persistence or backend yet."""

from dataclasses import dataclass, field

from .applications.models import Application
from .licenses.models import LibraryItem
from .websites.models import Website


@dataclass
class LibrarySession:
    items: list[LibraryItem] = field(default_factory=list)
    applications: list[Application] = field(default_factory=list)
    websites: list[Website] = field(default_factory=list)
