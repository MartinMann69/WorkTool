"""Shared table setup and cells; feature pages own row content."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QTableWidgetItem, QHBoxLayout, QWidget,
)

from .controls import TrashButton


def setup_table(table, headers):
    table.setObjectName("inventoryTable")
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(64)
    table.setShowGrid(False)
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setMinimumSectionSize(60)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setWordWrap(False)


def cell(text, centered=False):
    item = QTableWidgetItem(str(text))
    if centered:
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


def button_cell(*buttons):
    host = QWidget()
    layout = QHBoxLayout(host)
    layout.setContentsMargins(8, 0, 8, 0)
    layout.setSpacing(8)
    for button in buttons:
        button.setFixedHeight(34)
        layout.addWidget(button, 0 if isinstance(button, TrashButton) else 1,
                         Qt.AlignmentFlag.AlignVCenter)
    return host
