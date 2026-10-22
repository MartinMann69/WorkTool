"""Phone app inventory entries, independent of desktop applications."""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class PhoneApp:
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
