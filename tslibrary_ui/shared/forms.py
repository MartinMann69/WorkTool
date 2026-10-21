"""Small label and button factories for dialogs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton


def caption(text, name="adminDescription", *, wrap=True):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


def action(text, name="emptyAction"):
    button = QPushButton(text)
    button.setObjectName(name)
    button.setAutoDefault(False)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(40)
    return button
