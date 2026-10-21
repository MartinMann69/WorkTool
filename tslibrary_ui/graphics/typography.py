"""Painter font helpers for artwork and branding."""

from PySide6.QtGui import QFont


def serif(size: int, italic: bool = False) -> QFont:
    font = QFont("Georgia")
    font.setPixelSize(size)
    font.setItalic(italic)
    return font


def sans(size: int, spacing: float = 0) -> QFont:
    font = QFont("Segoe UI")
    font.setPixelSize(size)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font
