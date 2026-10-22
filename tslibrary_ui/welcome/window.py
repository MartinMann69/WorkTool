"""Welcome screen layout, admin sign-in intent, and normal-access intent."""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QScrollArea, QFrame, QSizePolicy,
    QGraphicsOpacityEffect, QLabel,
)

from ..graphics.brand import BrandMark, draw_library_mark
from ..graphics.shoji import ShojiPanel
from ..graphics.icons import icon
from ..styles import load_stylesheets
from .widgets import InputField, PrimaryButton, label, link


class LoginWindow(QWidget):
    """Self-contained UI with signals for optional future integration.

    open_requested() expresses normal access without credentials.
    sign_in_requested(username, password) expresses admin sign-in only.
    No networking, credential storage, or authentication is implemented.
    The preview notice can be hidden with ``show_preview_feedback=False``.
    """

    sign_in_requested = Signal(str, str)
    open_requested = Signal()

    def __init__(self, parent=None, *, show_preview_feedback=True, animate=True):
        super().__init__(parent)
        self.setObjectName("loginWindow")
        self.setWindowTitle("TSLibrary — Welcome")
        self.setMinimumSize(440, 600)
        self.resize(1180, 820)
        self._show_preview_feedback = show_preview_feedback
        self._animate = animate
        self._animation_started = False
        self.setStyleSheet(load_stylesheets("base"))

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
        form.addWidget(label("Welcome\nto TSLibrary.", "heading"))
        form.addSpacing(14)
        description = label("Open TSLibrary. Admins can sign in below.", "description")
        description.setWordWrap(True)
        form.addWidget(description)
        form.addSpacing(23)
        self.open_button = PrimaryButton("Open TSLibrary")
        form.addWidget(self.open_button)
        form.addSpacing(25)

        admin_divider = QHBoxLayout()
        admin_divider.setSpacing(14)
        for side in range(2):
            line = QFrame()
            line.setObjectName("sectionDivider")
            line.setFixedHeight(1)
            admin_divider.addWidget(line, 1)
            if side == 0:
                admin_divider.addWidget(label("ADMIN SIGN-IN", "sectionLabel"))
        form.addLayout(admin_divider)
        form.addSpacing(23)

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
        form.addSpacing(20)
        self.sign_in_button = link("Admin sign-in", "adminButton")
        self.sign_in_button.setFixedHeight(47)
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
        self.open_button.clicked.connect(self.open_requested.emit)
        self.open_requested.connect(lambda: self._feedback("Open TSLibrary"))
        self.username_field.edit.returnPressed.connect(self.password_field.edit.setFocus)
        self.password_field.edit.returnPressed.connect(self._submit)
        self.notice_timer = QTimer(self)
        self.notice_timer.setSingleShot(True)
        self.notice_timer.timeout.connect(self.notice.clear)

        self.setTabOrder(self.open_button, self.username_field.edit)
        self.setTabOrder(self.username_field.edit, self.password_field.edit)
        self.setTabOrder(self.password_field.edit, self.password_field.toggle)
        self.setTabOrder(self.password_field.toggle, self.sign_in_button)
        self.open_button.setFocus()

    def _submit(self):
        self.sign_in_requested.emit(self.username_field.edit.text(),
                                    self.password_field.edit.text())
        self._feedback("Admin sign-in")

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
