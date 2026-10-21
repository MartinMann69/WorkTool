"""Admin navigation, branding, and the back-to-welcome action."""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QPushButton, QVBoxLayout

from ..graphics.brand import BrandMark
from ..graphics.icons import admin_icon
from ..graphics.shelf import ShelfArtwork
from ..shared.forms import caption


class AdminSidebar(QFrame):
    page_requested = Signal(str)
    back_requested = Signal()

    def __init__(self, page_names, parent=None):
        super().__init__(parent)
        self.setObjectName("adminSidebar")
        self.setFixedWidth(244)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 28, 14, 22)
        layout.setSpacing(7)
        layout.addWidget(BrandMark())
        title = caption("ADMINISTRATION", "sideCaption", wrap=False)
        title.setContentsMargins(12, 4, 0, 0)
        layout.addWidget(title)
        layout.addSpacing(39)
        workspace = caption("WORKSPACE", "sideCaption", wrap=False)
        workspace.setContentsMargins(14, 0, 0, 8)
        layout.addWidget(workspace)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = {}
        for name in page_names:
            button = QPushButton("   " + name)
            button.setObjectName("adminNav")
            button.setCheckable(True)
            button.setFixedHeight(44)
            button.setIcon(admin_icon(name.lower()))
            button.setIconSize(QSize(20, 20))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked, page=name: self.page_requested.emit(page))
            self.nav_group.addButton(button)
            self.nav_buttons[name] = button
            layout.addWidget(button)
        layout.addStretch(1)
        layout.addWidget(ShelfArtwork(), 0, Qt.AlignmentFlag.AlignHCenter)
        quote = caption("A little order.\nA little room to breathe.", "sideQuote", wrap=False)
        quote.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(quote)
        layout.addSpacing(30)
        self.back_button = QPushButton("   Back to welcome")
        self.back_button.setObjectName("backButton")
        self.back_button.setIcon(admin_icon("back"))
        self.back_button.setFixedHeight(40)
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self.back_requested.emit)
        layout.addWidget(self.back_button)
