"""Session-only data shared by administration and the read-only library."""

from dataclasses import dataclass, field

from .applications.models import Application
from .licenses.models import LibraryItem
from .phone_apps.models import PhoneApp
from .websites.models import Website


@dataclass
class LibrarySession:
    items: list[LibraryItem] = field(default_factory=list)
    applications: list[Application] = field(default_factory=list)
    websites: list[Website] = field(default_factory=list)
    phone_apps: list[PhoneApp] = field(default_factory=list)
