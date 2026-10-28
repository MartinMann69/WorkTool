"""Portable shared app references. No file lookup or registry access here."""

import ntpath
from pathlib import PureWindowsPath
import re


TOKENS = ("DESKTOP", "STARTMENU", "PUBLIC_DESKTOP", "COMMON_STARTMENU", "LOCALAPPDATA",
          "APPDATA", "USERPROFILE", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "WINDIR")


def portable_hint(value, roots=None):
    """Rebase user folders, including paths belonging to a different admin."""
    value = str(value).replace("/", "\\")
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    if roots:
        for token, root in sorted(roots.items(), key=lambda item: len(item[1]), reverse=True):
            root = root.replace("/", "\\")
            if root and (value.casefold() == root.casefold() or value.casefold().startswith(root.rstrip("\\/").casefold() + "\\")):
                return f"%{token}%" + value[len(root.rstrip("\\/")):]
    public = re.match(r"^[a-z]:\\Users\\Public\\Desktop(.*)$", value, re.I)
    if public:
        return "%PUBLIC_DESKTOP%" + public[1]
    user = re.match(r"^[a-z]:\\Users\\[^\\]+(.*)$", value, re.I)
    if user:
        tail = user[1]
        for prefix, token in ((r"\AppData\Roaming\Microsoft\Windows\Start Menu", "STARTMENU"),
                              (r"\AppData\Local", "LOCALAPPDATA"), (r"\AppData\Roaming", "APPDATA"),
                              (r"\Desktop", "DESKTOP")):
            if tail.casefold() == prefix.casefold() or tail.casefold().startswith(prefix.casefold() + "\\"):
                return f"%{token}%" + tail[len(prefix):]
        redirected = re.match(r"\\OneDrive[^\\]*\\Desktop(.*)$", tail, re.I)
        if redirected:
            return "%DESKTOP%" + redirected[1]
        return "%USERPROFILE%" + tail
    for prefix, token in ((r"C:\Program Files (x86)", "PROGRAMFILES(X86)"),
                          (r"C:\Program Files", "PROGRAMFILES"), (r"C:\ProgramData", "PROGRAMDATA"),
                          (r"C:\Windows", "WINDIR")):
        if value.casefold().startswith(prefix.casefold() + "\\"):
            return f"%{token}%" + value[len(prefix):]
    return value


def describe_target(filename, roots=None):
    hint = portable_hint(filename, roots)
    name = PureWindowsPath(hint).name
    suffix = PureWindowsPath(name).suffix.casefold()
    if suffix not in (".exe", ".lnk"):
        raise ValueError("A shared application must reference an .exe or .lnk file.")
    return dict(kind="shortcut" if suffix == ".lnk" else "installed", filename=name, hint=hint)


def validate_target(value):
    if not isinstance(value, dict) or value.get("kind") not in ("installed", "shortcut"):
        raise ValueError("Choose an installed application or a local shortcut reference.")
    name, hint = value.get("filename"), value.get("hint", "")
    extension = ".lnk" if value["kind"] == "shortcut" else ".exe"
    if (not isinstance(name, str) or not name or ntpath.basename(name) != name
            or any(char in name for char in '<>:"/\\|?*\x00') or not name.casefold().endswith(extension)):
        raise ValueError("Invalid application filename in the shared reference.")
    if not isinstance(hint, str) or "\x00" in hint or (hint and ntpath.basename(hint).casefold() != name.casefold()):
        raise ValueError("The application location hint must refer to the same file.")
    if re.search(r"^[a-z]:\\Users\\[^\\]+\\", hint, re.I):
        raise ValueError("Shared application hints must use portable user-folder placeholders.")
    result = dict(kind=value["kind"], filename=name, hint=hint)
    install = value.get("installation")
    if install is not None:
        if not isinstance(install, dict):
            raise ValueError("Invalid installed application identity.")
        for field in ("key", "name", "publisher", "relative_executable"):
            if not isinstance(install.get(field), str) or "\x00" in install[field]:
                raise ValueError("Invalid installed application identity.")
        relative = PureWindowsPath(install["relative_executable"])
        if relative.is_absolute() or relative.drive or ".." in relative.parts or relative.name.casefold() != name.casefold():
            raise ValueError("Invalid executable path within an installation.")
        result["installation"] = {field: install[field] for field in ("key", "name", "publisher", "relative_executable")}
    return result
