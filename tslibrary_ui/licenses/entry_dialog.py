"""Add/edit a license entry and confirm entry deletion."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QWidget

from ..shared.forms import action, caption
from ..shared.controls import FilterCombo, CountSpinBox, CheckBox
from ..shared.confirmation import ConfirmDeleteDialog
from .models import LicenseEntry, MAX_LICENSE_COUNT


class LicenseEntryDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.setObjectName("inventoryDialog")
        self.setWindowTitle("TSLibrary — Edit license entry" if entry else "TSLibrary — Add license entry")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(10)
        layout.addWidget(caption("MANAGE LICENSES  /  LICENSE ENTRY", "adminEyebrow"))
        layout.addWidget(caption("Edit license entry" if entry else "Add license entry", "dialogHeading"))
        layout.addWidget(caption("Track available and used licenses, with or without a key."))
        layout.addSpacing(12)
        layout.addWidget(caption("License label", "fieldLabel"))
        self.label_edit = QLineEdit(entry.label if entry else "")
        self.label_edit.setObjectName("dialogInput")
        self.label_edit.setAccessibleName("License label")
        self.label_edit.setPlaceholderText("e.g. Standard licenses")
        self.label_edit.setMaxLength(150)
        layout.addWidget(self.label_edit)
        layout.addWidget(caption("Tracking type", "fieldLabel"))
        self.mode_select = FilterCombo()
        self.mode_select.setAccessibleName("Tracking type")
        self.mode_select.addItems(["Count only", "Count + license key"])
        self.mode_select.setMinimumHeight(42)
        layout.addWidget(self.mode_select)
        self.type_hint = caption("")
        layout.addWidget(self.type_hint)
        self.unlimited_checkbox = CheckBox("Unlimited uses")
        self.unlimited_checkbox.setObjectName("unlimitedOption")
        self.unlimited_checkbox.setToolTip("This key can be used without a usage limit.")
        self.unlimited_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.unlimited_checkbox)
        self.count_fields = QWidget()
        counts = QHBoxLayout(self.count_fields)
        counts.setContentsMargins(0, 0, 0, 0)
        counts.setSpacing(16)
        self.available_spin = CountSpinBox()
        self.used_spin = CountSpinBox()
        for title, control, value in [("Available licenses", self.available_spin, entry.available if entry else 1),
                                      ("Used licenses", self.used_spin, entry.used if entry else 0)]:
            column = QVBoxLayout()
            column.setSpacing(10)
            column.addWidget(caption(title, "fieldLabel"))
            control.setAccessibleName(title)
            control.setRange(0, MAX_LICENSE_COUNT)
            control.setValue(value)
            control.setMinimumHeight(42)
            column.addWidget(control)
            counts.addLayout(column, 1)
        layout.addWidget(self.count_fields)
        self.unlimited_fields = QWidget()
        unlimited_counts = QHBoxLayout(self.unlimited_fields)
        unlimited_counts.setContentsMargins(0, 0, 0, 0)
        for title, value in [("Available licenses", "∞"), ("Used licenses", "—")]:
            column = QVBoxLayout()
            column.addWidget(caption(title, "fieldLabel"))
            column.addWidget(caption(value, "licenseSummary"))
            unlimited_counts.addLayout(column, 1)
        layout.addWidget(self.unlimited_fields)
        self.total_label = caption("", "adminMuted")
        layout.addWidget(self.total_label)
        self.available_spin.valueChanged.connect(self._update_total)
        self.used_spin.valueChanged.connect(self._update_total)
        self._update_total()
        self.key_section = QWidget()
        key_layout = QVBoxLayout(self.key_section)
        key_layout.setContentsMargins(0, 6, 0, 0)
        key_layout.setSpacing(10)
        key_layout.addWidget(caption("License key", "fieldLabel"))
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit(entry.key if entry else "")
        self.key_edit.setObjectName("dialogInput")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setAccessibleName("License key")
        self.key_edit.setPlaceholderText("Enter or paste the license key")
        self.key_edit.setInputMethodHints(Qt.InputMethodHint.ImhSensitiveData
                                          | Qt.InputMethodHint.ImhNoPredictiveText)
        key_row.addWidget(self.key_edit, 1)
        show = action("Show key")
        show.setCheckable(True)
        show.toggled.connect(lambda visible: self.key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password))
        show.toggled.connect(lambda visible: show.setText("Hide key" if visible else "Show key"))
        key_row.addWidget(show)
        key_layout.addLayout(key_row)
        layout.addWidget(self.key_section)
        self.error = caption("", "formError")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = action("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save_button = action("Save changes" if entry else "Add license entry", "adminPrimary")
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.mode_select.currentIndexChanged.connect(self._mode_changed)
        self.unlimited_checkbox.toggled.connect(self._usage_mode_changed)
        self.mode_select.setCurrentIndex(1 if entry and entry.key else 0)
        self.unlimited_checkbox.setChecked(bool(entry and entry.key and entry.unlimited))
        self._mode_changed()
        self.label_edit.setFocus()

    def _mode_changed(self):
        keyed = self.mode_select.currentIndex() == 1
        self.key_section.setVisible(keyed)
        self.unlimited_checkbox.setVisible(keyed)
        if not keyed:
            self.unlimited_checkbox.setChecked(False)
        self.error.clear()
        self._usage_mode_changed()
        self.adjustSize()

    def _usage_mode_changed(self, *_):
        unlimited = self.unlimited_checkbox.isChecked()
        self.type_hint.setText("This key has no usage limit. Its used count is not tracked." if unlimited else
                               "Track available and used counts alongside a license key."
                               if self.mode_select.currentIndex() == 1 else
                               "Track available and used counts without a license key.")
        self.count_fields.setVisible(not unlimited)
        self.unlimited_fields.setVisible(unlimited)
        self.available_spin.setEnabled(not unlimited)
        self.used_spin.setEnabled(not unlimited)
        self._update_total()
        self.adjustSize()

    def _save(self):
        if not self.label_edit.text().strip():
            self.error.setText("Give this license entry a label first.")
            self.label_edit.setFocus()
            return
        if self.mode_select.currentIndex() == 1 and not self.key_edit.text().strip():
            self.error.setText("Enter a license key, or choose Count only.")
            self.key_edit.setFocus()
            return
        self.accept()

    def entry(self):
        return LicenseEntry(self.label_edit.text().strip(), self.available_spin.value(),
                            self.key_edit.text().strip() if self.mode_select.currentIndex() == 1 else "",
                            self.used_spin.value(),
                            self.mode_select.currentIndex() == 1 and self.unlimited_checkbox.isChecked())

    def _update_total(self, *_):
        self.total_label.setText("Unlimited uses · usage is not tracked." if self.unlimited_checkbox.isChecked()
                                 else f"Total licenses: {self.available_spin.value() + self.used_spin.value():,}")


class DeleteLicenseDialog(ConfirmDeleteDialog):
    def __init__(self, entry, parent=None):
        super().__init__("Delete license entry", f'Delete “{entry.label}”? Its license key and counts '
                         "will be removed. The item and its other license entries will stay.", parent)
