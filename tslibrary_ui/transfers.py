"""Validated portable backups and CSV exports. License key values are excluded."""

import csv
from datetime import datetime
from pathlib import Path

from .storage import (JsonRepository, StorageError, catalog_data, decode_catalog,
                      decode_workplace, workplace_data)


def export_backup(path, value, *, catalog=False):
    kind = "catalog" if catalog else "workplace"
    data = catalog_data(value) if catalog else workplace_data(value)
    JsonRepository._write(Path(path), dict(version=1, format=f"tslibrary.{kind}", **{kind: data}))


def import_backup(path, *, catalog=False):
    kind = "catalog" if catalog else "workplace"

    def decode(data):
        if data.get("format") != f"tslibrary.{kind}" or not isinstance(data.get(kind), dict):
            raise ValueError(f"Choose a TSLibrary {kind} backup.")
        nested = data[kind]
        if nested.get("version") != 1:
            raise ValueError("Unsupported backup version.")
        return decode_catalog(nested) if catalog else decode_workplace(nested)

    try:
        if Path(path).stat().st_size > 20_000_000:
            raise StorageError("That backup is too large (maximum 20 MB).")
    except OSError as error:
        raise StorageError(str(error)) from error
    return JsonRepository._read(Path(path), decode)


def recovery_path(path):
    path = Path(path)
    return path.with_name(f"{path.stem}.before-restore-{datetime.now():%Y%m%d-%H%M%S-%f}.json")


def export_catalog_csv(path, session):
    rows = []
    for app in session.applications:
        rows.append(("Application", app.name, app.launch_target, "", "", "", ""))
    rows += [("Website", site.name, site.url, "", "", "", "") for site in session.websites]
    rows += [("Phone app", app.name, "", "", "", "", "") for app in session.phone_apps]
    rows += [("Licensed item", item.name, item.category, item.owner, item.renewal_date,
              item.available_text, item.used_text) for item in session.items]
    try:
        with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("Type", "Name", "Details", "Owner", "Renewal date", "Available", "Used"))
            for row in rows:
                writer.writerow(["'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r"))
                                 else value for value in row])
    except OSError as error:
        raise StorageError(f"Could not export CSV: {error}") from error
