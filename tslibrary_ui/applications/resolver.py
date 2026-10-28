"""Resolve shared references on this PC. Read Windows registration; never run it."""

from functools import lru_cache
import os
from pathlib import Path, PureWindowsPath
import re
import time

from PySide6.QtCore import QStandardPaths

from .portable import describe_target, validate_target


def local_roots():
    env = {key.upper(): value for key, value in os.environ.items()}
    roots = {token: env.get(token, "") for token in ("LOCALAPPDATA", "APPDATA", "USERPROFILE",
             "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "WINDIR")}
    roots["USERPROFILE"] = roots["USERPROFILE"] or str(Path.home())
    desktop = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    roots["DESKTOP"] = str(Path(desktop)) if desktop else ""
    roots["STARTMENU"] = str(Path(roots["APPDATA"]) / "Microsoft/Windows/Start Menu") if roots["APPDATA"] else ""
    roots["COMMON_STARTMENU"] = str(Path(roots["PROGRAMDATA"]) / "Microsoft/Windows/Start Menu") if roots["PROGRAMDATA"] else ""
    roots["PUBLIC_DESKTOP"] = str(Path(env["PUBLIC"]) / "Desktop") if env.get("PUBLIC") else ""
    return roots


def expand_hint(hint, roots=None):
    roots = local_roots() if roots is None else roots
    missing = False
    def substitute(match):
        nonlocal missing
        value = roots.get(match[1].upper(), "")
        if not value:
            missing = True
        return value
    result = re.sub(r"%([^%]+)%", substitute, hint)
    return None if missing else Path(result)


def _registry_locations():
    if os.name != "nt":
        return []
    import winreg
    return [(hive, view) for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)]


def app_paths(filename):
    if os.name != "nt":
        return []
    import winreg
    paths = []
    for hive, view in _registry_locations():
        try:
            with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + filename,
                                0, winreg.KEY_READ | view) as key:
                value = winreg.QueryValueEx(key, "")[0]
                if isinstance(value, str):
                    paths.append(Path(os.path.expandvars(value.strip().strip('"'))))
        except OSError:
            pass
    return paths


@lru_cache(maxsize=1)
def _installations(_time_bucket):
    if os.name != "nt":
        return []
    import winreg
    result = []
    for hive, view in _registry_locations():
        try:
            with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0,
                                winreg.KEY_READ | view) as parent:
                for index in range(winreg.QueryInfoKey(parent)[0]):
                    try:
                        name = winreg.EnumKey(parent, index)
                        with winreg.OpenKey(parent, name) as key:
                            def text(field):
                                try:
                                    value = winreg.QueryValueEx(key, field)[0]
                                    return value if isinstance(value, str) else ""
                                except OSError:
                                    return ""
                            location = os.path.expandvars(text("InstallLocation").strip().strip('"'))
                            if location:
                                result.append(dict(key=name, name=text("DisplayName"), publisher=text("Publisher"), location=location))
                    except OSError:
                        continue
        except OSError:
            continue
    return result


def installations():
    return _installations(int(time.monotonic() // 30))


def capture_target(path):
    roots = local_roots()
    target = describe_target(str(path), roots)
    if target["kind"] == "installed":
        matches = []
        for record in installations():
            try:
                install_root = Path(record["location"]).resolve()
                # Some uninstall entries report a drive or profile ancestor.
                # Such roots do not identify the app and could put an admin's
                # username into the otherwise-relative executable reference.
                if (len(install_root.parts) < 2
                        or any(value and (Path(value).resolve() == install_root
                               or (token == "USERPROFILE" and Path(value).resolve().is_relative_to(install_root)))
                               for token, value in roots.items())):
                    continue
                relative = Path(path).resolve().relative_to(install_root)
                matches.append((len(str(record["location"])), record, relative))
            except (ValueError, OSError):
                continue
        if matches:
            _, record, relative = max(matches, key=lambda match: match[0])
            target["installation"] = {field: record[field] for field in ("key", "name", "publisher")}
            target["installation"]["relative_executable"] = str(relative)
    return target


def _existing(paths, filename):
    result = {}
    for path in paths:
        try:
            if path is not None and path.name.casefold() == filename.casefold() and path.is_absolute() and path.is_file():
                result[str(path.resolve()).casefold()] = path.resolve()
        except OSError:
            continue
    return list(result.values())


def resolve_target(target):
    target = validate_target(target)
    name = target["filename"]
    hint = expand_hint(target["hint"]) if target["hint"] else None
    if target["kind"] == "shortcut":
        found = _existing([hint], name)
        if found:
            return found[0]
        raise ValueError(f'The shortcut “{name}” is missing in this user\'s matching folder. Create it there, or use Locate application on this PC.')
    # Keep the selected installation when it exists locally, then consult
    # Windows registration. Never scan drives for arbitrary same-named files.
    identity = target.get("installation")
    if identity:
        matches = [record for record in installations() if record["key"].casefold() == identity["key"].casefold()
                   or (identity["name"] and record["name"].casefold() == identity["name"].casefold()
                       and record["publisher"].casefold() == identity["publisher"].casefold())]
        paths = [Path(record["location"]).joinpath(*PureWindowsPath(identity["relative_executable"]).parts) for record in matches]
        found = _existing(paths, name)
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise ValueError(f'More than one installation matches “{name}”. Use Locate application on this PC to choose one.')
    found = _existing([hint], name)
    if found:
        return found[0]
    registered = _existing(app_paths(name), name)
    if len(registered) == 1:
        return registered[0]
    if len(registered) > 1:
        raise ValueError(f'More than one registered application matches “{name}”. Use Locate application on this PC.')
    # PATH lookup is restricted to explicit PATH directories, excluding CWD.
    found = _existing([Path(part) / name for part in os.get_exec_path() if part and Path(part).is_absolute()], name)
    if len(found) > 1:
        raise ValueError(f'More than one PATH entry matches “{name}”. Use Locate application on this PC.')
    if found:
        return found[0]
    raise ValueError(f'“{name}” was not found on this PC. Install it, or use Locate application on this PC to select its executable.')


def resolve_application(application):
    if application.target is not None:
        return resolve_target(application.target)
    from .targets import executable_path
    return executable_path(application.executable)
