"""Website list-entry data."""

from dataclasses import dataclass, field
from uuid import uuid4

from PySide6.QtGui import QIcon

from .icons import website_icon


@dataclass
class Website:
    name: str
    url: str
    icon: QIcon = field(default_factory=website_icon, repr=False, compare=False)
    id: str = field(default_factory=lambda: uuid4().hex)
