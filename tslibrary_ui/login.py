"""A reusable login view. Signals express intent; no authentication is performed."""

from pathlib import Path

from PySide6.QtCore import (
    QEvent, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize,
    Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from .artwork import BrandMark, ShojiPanel, draw_library_mark


def icon(name: str, color: str = "#9b9c89", size: int = 20) -> QIcon:
    """Small, crisp Qt-native icons that follow the display's pixel density."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 20, size / 20)
    p.setPen(QPen(QColor(color), 1.25, Qt.PenStyle.SolidLine,
                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if name == "user":
        p.drawEllipse(QPointF(10, 6), 3, 3)
        path = QPainterPath(QPointF(4, 17))
        path.lineTo(4, 15)
        path.cubicTo(4, 10, 16, 10, 16, 15)
        path.lineTo(16, 17)
        p.drawPath(path)
    elif name == "lock":
        p.drawRoundedRect(QRectF(4, 8.5, 12, 9), 2, 2)
        path = QPainterPath(QPointF(6.5, 8.5))
        path.lineTo(6.5, 6)
        path.cubicTo(6.5, 1.5, 13.5, 1.5, 13.5, 6)
        path.lineTo(13.5, 8.5)
        p.drawPath(path)
        p.drawLine(QPointF(10, 12), QPointF(10, 14))
    elif name in ("eye", "eye-off"):
        path = QPainterPath(QPointF(2, 10))
        path.cubicTo(6, 3, 14, 3, 18, 10)
        path.cubicTo(14, 17, 6, 17, 2, 10)
        p.drawPath(path)
        p.drawEllipse(QPointF(10, 10), 2.4, 2.4)
        if name == "eye-off":
            p.drawLine(QPointF(3, 3), QPointF(17, 17))
    elif name == "arrow":
        p.drawLine(QPointF(3, 10), QPointF(17, 10))
        p.drawLine(QPointF(12, 5), QPointF(17, 10))
        p.drawLine(QPointF(12, 15), QPointF(17, 10))
    elif name == "leaf":
        path = QPainterPath(QPointF(4, 16))
        path.cubicTo(0, 5, 12, 3, 17, 3)
        path.cubicTo(17, 13, 13, 18, 6, 15)
        path.moveTo(3, 18)
        path.quadTo(8, 10, 13, 7)
        p.drawPath(path)
    p.end()
    return QIcon(pixmap)


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


class SignInButton(QPushButton):
    def __init__(self):
        super().__init__("Sign in")
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


class LoginWindow(QWidget):
    """Self-contained UI with signals for optional future integration.

    sign_in_requested(username, password, remember) emits entered values only.
    No networking, credential storage, or authentication is implemented.
    The preview notice can be hidden with ``show_preview_feedback=False``.
    """

    sign_in_requested = Signal(str, str, bool)
    recovery_requested = Signal()

    def __init__(self, parent=None, *, show_preview_feedback=True, animate=True):
        super().__init__(parent)
        self.setObjectName("loginWindow")
        self.setWindowTitle("TSLibrary — Welcome back")
        self.setMinimumSize(440, 600)
        self.resize(1180, 820)
        self._show_preview_feedback = show_preview_feedback
        self._animate = animate
        self._animation_started = False
        directory = Path(__file__).resolve().parent
        stylesheet = (directory / "theme.qss").read_text(encoding="utf-8")
        self.setStyleSheet(stylesheet.replace("CHECK_ICON", (directory / "check.svg").as_posix()))

        logo = QPixmap(64, 64)
        logo.fill(QColor("#181b18"))
        painter = QPainter(logo)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_library_mark(painter, QRectF(8, 8, 48, 48), "#c9b18c")
        painter.end()
        self.setWindowIcon(QIcon(logo))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.artwork = ShojiPanel()
        root.addWidget(self.artwork, 49)

        self.form_panel = QWidget()
        self.form_panel.setObjectName("formPanel")
        root.addWidget(self.form_panel, 51)
        panel = QVBoxLayout(self.form_panel)
        self.panel_layout = panel
        panel.setContentsMargins(47, 29, 47, 25)
        panel.setSpacing(0)

        masthead = QHBoxLayout()
        self.compact_brand = BrandMark()
        self.compact_brand.hide()
        masthead.addWidget(self.compact_brand)
        self.collection_label = label("TSLIBRARY  /  YOUR PERSONAL SPACE", "muted")
        masthead.addWidget(self.collection_label)
        masthead.addStretch()
        masthead.addWidget(label("間", "footerNote"))
        panel.addLayout(masthead)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel.addWidget(scroll, 1)
        scroll_content = QWidget()
        scroll.setWidget(scroll_content)
        center = QVBoxLayout(scroll_content)
        center.setContentsMargins(0, 32, 0, 25)
        center.setSpacing(0)
        center.addStretch(1)
        self.form_content = QWidget()
        self.form_content.setObjectName("formContent")
        self.form_content.setMaximumWidth(354)
        self.form_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form_row = QHBoxLayout()
        form_row.setContentsMargins(0, 0, 0, 0)
        form_row.setSpacing(0)
        form_row.addStretch(1)
        form_row.addWidget(self.form_content, 100)
        form_row.addStretch(1)
        center.addLayout(form_row)
        center.addStretch(1)
        form = QVBoxLayout(self.form_content)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(0)
        form.addWidget(label("WELCOME HOME", "eyebrow"))
        form.addSpacing(14)
        form.addWidget(label("Welcome\nback.", "heading"))
        form.addSpacing(14)
        description = label("Take a breath. Make yourself at home.", "description")
        description.setWordWrap(True)
        form.addWidget(description)
        form.addSpacing(33)

        self.username_field = InputField("Enter your username", "user")
        username_label = label("Username", "fieldLabel")
        username_label.setBuddy(self.username_field.edit)
        form.addWidget(username_label)
        form.addSpacing(9)
        form.addWidget(self.username_field)
        form.addSpacing(20)
        self.password_field = InputField("Enter your password", "lock")
        password_label = label("Password", "fieldLabel")
        password_label.setBuddy(self.password_field.edit)
        form.addWidget(password_label)
        form.addSpacing(9)
        form.addWidget(self.password_field)
        form.addSpacing(13)

        options = QHBoxLayout()
        options.setContentsMargins(0, 0, 0, 0)
        self.remember_checkbox = QCheckBox("Remember me")
        self.remember_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recovery_button = link("Forgot password?")
        options.addWidget(self.remember_checkbox)
        options.addStretch()
        options.addWidget(self.recovery_button)
        form.addLayout(options)
        form.addSpacing(20)
        self.sign_in_button = SignInButton()
        form.addWidget(self.sign_in_button)
        form.addSpacing(12)
        self.notice = label("", "demoNotice")
        self.notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice.setWordWrap(True)
        self.notice.setMinimumHeight(29)
        form.addWidget(self.notice)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addStretch()
        leaf = QLabel()
        leaf.setPixmap(icon("leaf", "#9c9e87", 14).pixmap(QSize(14, 14)))
        footer.addWidget(leaf)
        footer.addWidget(label("A little intention. A new beginning.", "footerNote"))
        footer.addStretch()
        panel.addLayout(footer)

        self.sign_in_button.clicked.connect(self._submit)
        self.username_field.edit.returnPressed.connect(self.password_field.edit.setFocus)
        self.password_field.edit.returnPressed.connect(self._submit)
        self.recovery_button.clicked.connect(self.recovery_requested.emit)
        self.recovery_requested.connect(lambda: self._feedback("Password recovery"))
        self.notice_timer = QTimer(self)
        self.notice_timer.setSingleShot(True)
        self.notice_timer.timeout.connect(self.notice.clear)

        self.setTabOrder(self.username_field.edit, self.password_field.edit)
        self.setTabOrder(self.password_field.edit, self.password_field.toggle)
        self.setTabOrder(self.password_field.toggle, self.remember_checkbox)
        self.setTabOrder(self.remember_checkbox, self.recovery_button)
        self.setTabOrder(self.recovery_button, self.sign_in_button)
        self.username_field.edit.setFocus()

    def _submit(self):
        self.sign_in_requested.emit(self.username_field.edit.text(),
                                    self.password_field.edit.text(),
                                    self.remember_checkbox.isChecked())
        self._feedback("Sign in")

    def _feedback(self, action):
        if self._show_preview_feedback:
            self.notice.setText(f"UI preview · {action} selected")
            self.notice_timer.start(4000)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 900
        margin = 30 if compact else 47
        self.panel_layout.setContentsMargins(margin, 29, margin, 25)
        self.artwork.setVisible(not compact)
        self.compact_brand.setVisible(compact)
        self.collection_label.setVisible(not compact)

    def showEvent(self, event):
        super().showEvent(event)
        if self._animate and not self._animation_started:
            self._animation_started = True
            effect = QGraphicsOpacityEffect(self.form_content)
            self.form_content.setGraphicsEffect(effect)
            self.entrance = QPropertyAnimation(effect, b"opacity", self)
            self.entrance.setDuration(650)
            self.entrance.setStartValue(0.0)
            self.entrance.setEndValue(1.0)
            self.entrance.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.entrance.finished.connect(lambda: self.form_content.setGraphicsEffect(None))
            self.entrance.start()
