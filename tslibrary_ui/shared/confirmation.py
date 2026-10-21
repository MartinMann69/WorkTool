"""Reusable confirmation dialog; feature-specific wording lives with each feature."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout

from .forms import action, caption


class ConfirmDeleteDialog(QDialog):
    def __init__(self, title, description, parent=None, *, section="LICENSES"):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        self.setWindowTitle(f"TSLibrary — {title}")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(16)
        layout.addWidget(caption(f"{section}  /  {title.upper()}", "adminEyebrow"))
        layout.addWidget(caption(f"{title}?", "dialogHeading"))
        self.description = caption(description)
        layout.addWidget(self.description)
        layout.addSpacing(8)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = action("Cancel")
        self.cancel_button.setDefault(True)
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        self.delete_button = action(title, "dangerAction")
        self.delete_button.clicked.connect(self.accept)
        buttons.addWidget(self.delete_button)
        layout.addLayout(buttons)
        self.cancel_button.setFocus()
