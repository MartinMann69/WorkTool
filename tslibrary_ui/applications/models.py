"""Application entry data and display of its full launch target."""

from dataclasses import dataclass, field
from uuid import uuid4

from PySide6.QtGui import QIcon

from .targets import format_launch_target


@dataclass
class Application:
    name: str
    # Keep the chosen .exe or .lnk path. A shortcut must not be flattened to
    # its target, so its launch settings remain available for future launching.
    executable: str
    icon: QIcon = field(default_factory=QIcon, repr=False, compare=False)
    id: str = field(default_factory=lambda: uuid4().hex)
    arguments: str = ""

    @property
    def launch_target(self) -> str:
        return format_launch_target(self.executable, self.arguments)
