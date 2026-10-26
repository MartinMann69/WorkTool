"""Shared catalog data and each user's separate workplace preferences."""

from dataclasses import dataclass, field

from .applications.models import Application
from .licenses.models import LibraryItem
from .phone_apps.models import PhoneApp
from .websites.models import Website
from .documentation.models import DocumentationCatalog
from .relationships import CatalogLink


@dataclass
class LibrarySession:
    items: list[LibraryItem] = field(default_factory=list)
    applications: list[Application] = field(default_factory=list)
    websites: list[Website] = field(default_factory=list)
    phone_apps: list[PhoneApp] = field(default_factory=list)
    documentation: DocumentationCatalog = field(default_factory=DocumentationCatalog)
    links: list[CatalogLink] = field(default_factory=list)


@dataclass
class WorkplaceConfig:
    application_ids: list[str] = field(default_factory=list)
    website_ids: list[str] = field(default_factory=list)
    personal_applications: list[Application] = field(default_factory=list)
    personal_websites: list[Website] = field(default_factory=list)
    favorites: list[str] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)
    launch_sets: dict[str, list[str]] = field(default_factory=dict)
    application_overrides: dict[str, str] = field(default_factory=dict)
    start_in_workplace: bool = False
    view_mode: str = "cards"
