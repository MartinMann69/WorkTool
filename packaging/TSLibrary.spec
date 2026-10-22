# Run with: python -m PyInstaller packaging/TSLibrary.spec
from pathlib import Path
from importlib.metadata import distribution
import sys

root = Path(SPECPATH).parent
datas = [(str(path), "tslibrary_ui/styles") for path in (root / "tslibrary_ui" / "styles").glob("*.qss")]
datas += [(str(path), "licenses/Qt") for path in (root / "packaging" / "licenses").glob("*.txt")]
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    datas.append((str(python_license), "licenses/Python"))
for package in ("PySide6", "PySide6_Essentials", "shiboken6", "PyInstaller"):
    installed = distribution(package)
    for path in installed.files or []:
        if "licenses" in str(path).casefold():
            source = Path(installed.locate_file(path))
            if source.is_file():
                datas.append((str(source), f"licenses/{package}/{path.parent.name}"))

analysis = Analysis([str(root / "main.py")], pathex=[str(root)], datas=datas,
    hiddenimports=[], excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick", "PySide6.QtPdf", "PySide6.QtPdfWidgets"],
    noarchive=False)
# Qt's Windows build uses the OS's unversioned ICU API. A different icuuc.dll
# on a build machine's PATH (e.g. Poppler's suffixed ICU exports) can otherwise
# be collected and break QtCore at startup. Use Windows' own System32 ICU.
analysis.binaries = [entry for entry in analysis.binaries
    if Path(entry[0]).name.casefold() != "icuuc.dll"
    and not Path(entry[0]).name.casefold().startswith("icudt")]
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="TSLibrary",
    console=False, debug=False, strip=False, upx=False,
    icon=str(root / "packaging" / "TSLibrary.ico"))
bundle = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name="TSLibrary")
