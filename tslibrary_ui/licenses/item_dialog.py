"""Add/edit item details and confirm item deletion."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit

from ..shared.forms import action, caption
from ..shared.confirmation import ConfirmDeleteDialog
from .models import LibraryItem


class ItemDialog(QDialog):
    def __init__(self, parent=None, *, item=None):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        self.setWindowTitle("TSLibrary — Edit item" if item else "TSLibrary — Add item")
        self.setMinimumWidth(480)
        self.resize(500, 350)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(10)
        layout.addWidget(caption("LICENSES  /  ITEM DETAILS" if item else "LICENSES  /  NEW ITEM", "adminEyebrow"))
        layout.addWidget(caption("Edit item" if item else "Add item", "dialogHeading"))
        layout.addWidget(caption("Update its name and category. Its licenses stay together." if item else
                                 "Give it a name. You can add its licenses next."))
        layout.addSpacing(12)
        layout.addWidget(caption("Item name", "fieldLabel"))
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("dialogInput")
        self.name_edit.setAccessibleName("Item name")
        self.name_edit.setPlaceholderText("e.g. Design software")
        self.name_edit.setMaxLength(150)
        self.name_edit.setText(item.name if item else "")
        layout.addWidget(self.name_edit)
        layout.addWidget(caption("Category (optional)", "fieldLabel"))
        self.category_edit = QLineEdit()
        self.category_edit.setObjectName("dialogInput")
        self.category_edit.setAccessibleName("Category")
        self.category_edit.setPlaceholderText("e.g. Creative tools")
        self.category_edit.setMaxLength(80)
        self.category_edit.setText(item.category if item else "")
        layout.addWidget(self.category_edit)
        self.error = caption("", "formError")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = action("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save_button = action("Save changes" if item else "Add item", "adminPrimary")
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.name_edit.returnPressed.connect(self.category_edit.setFocus)
        self.category_edit.returnPressed.connect(self._save)
        self.name_edit.setFocus()

    def _save(self):
        if not self.name_edit.text().strip():
            self.error.setText("Give the item a name first.")
            self.name_edit.setFocus()
            return
        self.accept()

    def item(self):
        return LibraryItem(*self.details())

    def details(self):
        return (self.name_edit.text().strip(),
                self.category_edit.text().strip() or "Uncategorised")


class DeleteItemDialog(ConfirmDeleteDialog):
    def __init__(self, item, parent=None):
        count = len(item.licenses)
        entries = "license entry" if count == 1 else "license entries"
        super().__init__("Delete item", f'Delete “{item.name}” and its {count} {entries}? '
                         "This also removes their license keys and counts from this preview session.", parent)
