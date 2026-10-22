"""Licensed items and license-count calculations; independent of the UI."""

from dataclasses import dataclass, field
from math import inf, isinf
from uuid import uuid4
from datetime import date


MAX_LICENSE_COUNT = 1_000_000


def count_text(value):
    if value is None:
        return "—"
    return "∞" if isinf(value) else f"{value:,}"


@dataclass
class LicenseEntry:
    label: str
    available: int
    key: str = ""
    used: int = 0
    unlimited: bool = False
    keyed: bool = False

    @property
    def tracks_key(self):
        return bool(self.key) or self.keyed

    def can_change_usage(self, change: int) -> bool:
        """Whether one license can move between the available and used pools."""
        if self.unlimited:
            return False
        if change == 1:
            return self.available > 0 and self.used < MAX_LICENSE_COUNT
        if change == -1:
            return self.used > 0 and self.available < MAX_LICENSE_COUNT
        return False

    def change_usage(self, change: int) -> bool:
        """Transfer one license, preserving the total; return whether it moved."""
        if not self.can_change_usage(change):
            return False
        self.available -= change
        self.used += change
        return True

    @property
    def total(self):
        return inf if self.unlimited else self.available + self.used

    @property
    def available_text(self):
        return "∞" if self.unlimited else count_text(self.available)

    @property
    def used_text(self):
        return "—" if self.unlimited else count_text(self.used)


@dataclass
class LibraryItem:
    name: str
    category: str = "Uncategorised"
    licenses: list[LicenseEntry] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    owner: str = ""
    renewal_date: str = ""

    def renewal_status(self, today=None):
        if not self.renewal_date:
            return "No renewal date"
        days = (date.fromisoformat(self.renewal_date) - (today or date.today())).days
        unit = "day" if abs(days) == 1 else "days"
        return (f"Overdue by {-days} {unit}" if days < 0 else "Due today" if days == 0
                else f"Due in {days} {unit}")

    @property
    def available(self):
        return inf if self.has_unlimited else sum(entry.available for entry in self.licenses)

    @property
    def used(self):
        finite = [entry for entry in self.licenses if not entry.unlimited]
        return None if self.licenses and not finite else sum(entry.used for entry in finite)

    @property
    def total(self):
        return inf if self.has_unlimited else self.available + self.used

    @property
    def has_unlimited(self):
        return any(entry.unlimited for entry in self.licenses)

    @property
    def available_text(self):
        return count_text(self.available)

    @property
    def used_text(self):
        return count_text(self.used) + (" tracked" if self.has_unlimited and self.used is not None else "")
