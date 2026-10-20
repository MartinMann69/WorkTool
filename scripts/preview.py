"""Render the real Qt screen at desktop and compact sizes."""

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication

from main import create_app
from tslibrary_ui import LoginWindow


def main():
    app = create_app()
    output = ROOT / "previews"
    output.mkdir(exist_ok=True)
    window = LoginWindow(animate=False)
    for name, width, height in [("desktop", 1180, 820), ("compact", 480, 820),
                                ("wide", 1543, 790), ("tall", 1000, 1100)]:
        window.resize(width, height)
        window.show()
        for _ in range(4):
            QCoreApplication.sendPostedEvents()
            app.processEvents()
        destination = output / f"{name}.png"
        if not window.grab().save(str(destination)):
            raise RuntimeError(f"Could not save {destination}")
        print(destination)
    window.close()


if __name__ == "__main__":
    main()
