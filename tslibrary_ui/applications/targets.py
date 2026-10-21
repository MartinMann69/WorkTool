"""Parse and validate executable/shortcut paths and raw arguments; never runs files."""

import os
from pathlib import Path
import re


def _file_path(value: str) -> Path:
    """Validate a single file path without treating arguments as filenames."""
    if not value:
        raise ValueError("Choose an application (.exe) or Windows shortcut (.lnk) first.")
    path = Path(os.path.expandvars(value)).expanduser()
    if path.suffix.casefold() not in (".exe", ".lnk"):
        raise ValueError("Choose a Windows executable (.exe) or shortcut (.lnk).")
    try:
        if not path.is_file():
            raise ValueError("That file could not be found. Choose an existing .exe or .lnk file.")
        # Path.resolve() normalizes filesystem paths; Windows .lnk files stay
        # files. Do not use QFileInfo.symLinkTarget(), which would lose the
        # shortcut's arguments, working directory, and custom icon location.
        return path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError("That path could not be read. Choose an accessible .exe or .lnk file.") from error


def parse_launch_target(text: str) -> tuple[Path, str]:
    """Split a shortcut-style target, preserving the raw Windows arguments.

    Only the leading filename is parsed. Argument quotes and backslashes belong
    to the selected application and are kept verbatim; no shell is involved.
    """
    value = text.strip()
    if value.startswith('"'):
        closing = value.find('"', 1)
        if closing < 0:
            raise ValueError("Close the quotation mark around the application path.")
        remainder = value[closing + 1:]
        if remainder and not remainder[0].isspace():
            raise ValueError("Add a space between the quoted path and its arguments.")
        return _file_path(value[1:closing]), remainder.lstrip()
    # Continue accepting bare paths with spaces when there are no arguments.
    try:
        return _file_path(value), ""
    except ValueError as whole_path_error:
        match = re.fullmatch(r"(\S+)\s+(.*)", value, flags=re.DOTALL)
        if match is None:
            raise whole_path_error
        filename, arguments = match.groups()
        if Path(os.path.expandvars(filename)).suffix.casefold() not in (".exe", ".lnk"):
            raise ValueError('Put quotes around paths with spaces, e.g. "C:\\My App\\app.exe" -launch.') from whole_path_error
        return _file_path(filename), arguments


def executable_path(text: str) -> Path:
    """Return the executable or shortcut file portion of a launch target."""
    return parse_launch_target(text)[0]


def format_launch_target(filename: str, arguments: str = "") -> str:
    return f'"{filename}" {arguments}' if arguments else filename
