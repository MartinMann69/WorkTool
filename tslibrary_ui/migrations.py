"""Pure, sequential saved-data migrations, independent of the application version.

For a structural change, add a function under the OLD version number and raise
the schema's current_version. Each function returns the next version's object.
Never regenerate record IDs. Keep old steps so installations can skip releases.
File backups and atomic replacement are handled by storage.JsonFile.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Mapping


@dataclass(frozen=True)
class DataSchema:
    name: str
    current_version: int
    migrations: Mapping[int, Callable[[dict], dict]]

    def upgrade(self, data: dict) -> dict:
        if not isinstance(data, dict):
            raise ValueError(f"Expected a {self.name} JSON object.")
        version = data.get("version")
        if type(version) is not int or version < 1:
            raise ValueError(f"The {self.name} needs a positive integer data version.")
        if version > self.current_version:
            raise ValueError(
                f"This {self.name} uses newer data version {version}; this app supports "
                f"up to {self.current_version}. Install a newer app to open it.")
        result = deepcopy(data)
        while version < self.current_version:
            step = self.migrations.get(version)
            if step is None:
                raise ValueError(f"No {self.name} migration from data version {version}.")
            try:
                result = step(result)
            except Exception as error:
                raise ValueError(f"Could not migrate {self.name} from data version {version}: {error}") from error
            if (not isinstance(result, dict) or type(result.get("version")) is not int
                    or result["version"] != version + 1):
                raise ValueError(f"The {self.name} migration must advance exactly one version.")
            version += 1
        return result


def catalog_v1_to_v2(data):
    """Keep IDs/arguments; replace admin-specific paths with portable targets."""
    from .applications.portable import describe_target
    for application in data.get("applications", []):
        application["target"] = describe_target(application.pop("executable"))
    data["version"] = 2
    return data


def catalog_v2_to_v3(data):
    """Existing documentation entries are folders; retain their IDs and paths."""
    for item in data.get("documentation", {}).get("items", []):
        item.setdefault("kind", "folder")
    data["version"] = 3
    return data


def catalog_v3_to_v4(data):
    """Keep saved edges; older group-expanding writers must reject this format.

    Earlier writers did not record which links were selected or inferred, so
    deleting saved links automatically could remove intentional connections.
    """
    data["version"] = 4
    return data


CATALOG_SCHEMA = DataSchema("catalog", current_version=4,
                          migrations={1: catalog_v1_to_v2, 2: catalog_v2_to_v3, 3: catalog_v3_to_v4})
WORKPLACE_SCHEMA = DataSchema("workplace", current_version=1, migrations={})
