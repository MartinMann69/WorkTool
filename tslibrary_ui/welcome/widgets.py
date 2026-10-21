"""Welcome form fields, password toggle, and action buttons."""

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton, QToolButton, QHBoxLayout

from ..graphics.icons import icon


class InputField(QFrame):
    def __init__(self, placeholder: str, kind: str, parent=None):
        super().__init__(parent)
        self.setObjectName("inputShell")
        self.setFixedHeight(51)
        self.setProperty("focused", False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(12)
        symbol = QLabel()
        symbol.setPixmap(icon(kind).pixmap(QSize(18, 18)))
        symbol.setFixedSize(18, 18)
        layout.addWidget(symbol)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setAccessibleName("Password" if kind == "lock" else "Username")
        self.edit.setMinimumWidth(0)
        self.edit.installEventFilter(self)
        layout.addWidget(self.edit, 1)
        self.setFocusProxy(self.edit)
        self.toggle = None
        if kind == "lock":
            self.edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.edit.setInputMethodHints(Qt.InputMethodHint.ImhSensitiveData
                                         | Qt.InputMethodHint.ImhNoPredictiveText)
            self.toggle = QToolButton()
            self.toggle.setObjectName("eyeButton")
            self.toggle.setFixedSize(30, 30)
            self.toggle.setIcon(icon("eye"))
            self.toggle.setIconSize(QSize(18, 18))
            self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            self.toggle.setCheckable(True)
            self.toggle.setToolTip("Show password")
            self.toggle.setAccessibleName("Show password")
            self.toggle.toggled.connect(self._toggle_password)
            layout.addWidget(self.toggle)
        else:
            self.edit.setInputMethodHints(Qt.InputMethodHint.ImhNoAutoUppercase
                                         | Qt.InputMethodHint.ImhNoPredictiveText)

    def _toggle_password(self, visible):
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if visible
                              else QLineEdit.EchoMode.Password)
        self.toggle.setIcon(icon("eye-off" if visible else "eye"))
        label = "Hide password" if visible else "Show password"
        self.toggle.setToolTip(label)
        self.toggle.setAccessibleName(label)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.setProperty("focused", event.type() == QEvent.Type.FocusIn)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        return super().eventFilter(watched, event)


class PrimaryButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setObjectName("primary")
        self.setFixedHeight(51)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        icon("arrow", "#24291f").paint(p, self.width() - 40, 16, 20, 20)


def label(text, name, parent=None):
    result = QLabel(text, parent)
    result.setObjectName(name)
    return result


def link(text, name="textLink"):
    result = QPushButton(text)
    result.setObjectName(name)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    return result
