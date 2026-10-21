"""Load QSS files relative to the package, independent of the working directory."""

from pathlib import Path


def load_stylesheets(*names: str) -> str:
    folder = Path(__file__).resolve().parent
    return "\n".join((folder / f"{name}.qss").read_text(encoding="utf-8") for name in names)
