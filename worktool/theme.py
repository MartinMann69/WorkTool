"""Central visual tokens and Qt widget styles."""
from . import resources_rc  # noqa: F401 -- registers embedded Qt icons
from string import Template

from PySide6.QtGui import QColor, QPalette

DEFAULT_APPEARANCE = ("light", "purple")


def validate_appearance(mode, accent):
    if mode not in {"light", "dark"} or accent not in {"purple", "pink"}:
        raise ValueError("Choose Light or Dark mode and a Purple or Pink accent.")


def theme_colors(mode="light", accent="purple"):
    validate_appearance(mode, accent)
    dark = mode == "dark"
    colors = {
        "background": "#171621" if dark else "#f7f6fb",
        "surface": "#242231" if dark else "#ffffff",
        "text": "#eeeaf6" if dark else "#302a40",
        "title": "#faf7ff" if dark else "#241d35",
        "muted": "#b1aabd" if dark else "#71677f",
        "border": "#454052" if dark else "#e3dfea",
        "disabled": "#302c3c" if dark else "#eeebf3",
        "disabled_text": "#958ba5" if dark else "#8b8198",
        "header": "#302b3e" if dark else "#f0ecf6",
        "scrollbar": "#63596f" if dark else "#cec4dc",
        "notice_bg": "#403324" if dark else "#fff3d9",
        "notice_text": "#f0ce8f" if dark else "#85621e",
        "error": "#ff98aa" if dark else "#bb384a",
        "sidebar": "#121019" if dark else "#20172f",
        "side_text": "#c5b8d7",
        "side_muted": "#a494b8",
        "side_hover": "#31233f",
        "side_selected": "#413054",
        "avatar": "#4f3b66",
    }
    if accent == "purple":
        colors.update(primary="#7653d6", primary_hover="#6541c4",
                      accent_text="#c9b6ff" if dark else "#6942c2",
                      tint="#3b2d53" if dark else "#f0eafa",
                      focus="#b69af5", side_selected="#413054")
    else:
        colors.update(primary="#bb3575", primary_hover="#a52665",
                      accent_text="#ffacd2" if dark else "#af296a",
                      tint="#46293b" if dark else "#fce8f2",
                      focus="#ed91be", side_selected="#51283f")
    return colors

_STYLE_TEMPLATE = Template("""
* { font-family: 'Segoe UI'; font-size: 13px; color: $text; }
QWidget { background: $background; }
QMainWindow, QDialog { background: $background; }
QLabel { background: transparent; }
QWidget#appearanceControls { background: transparent; }
QLabel#eyebrow { color: $muted; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel#title { color: $title; font-size: 30px; font-weight: 700; }
QLabel#subtitle { color: $muted; font-size: 14px; }
QLabel#brand { color: #ffffff; font-size: 23px; font-weight: 700; }
QLabel#brandSmall { color: #8d9bb4; font-size: 11px; letter-spacing: 2px; }
QFrame#sidebar { background: $sidebar; border: none; }
QFrame#sidebar QLabel { color: $side_text; }
QFrame#sidebar QLabel#brand { color: #ffffff; }
QFrame#sidebar QLabel#sideTitle { color: $side_muted; font-size: 10px; letter-spacing: 2px; font-weight: 700; }
QFrame#sidebar QPushButton { background: transparent; color: $side_text; border: none; text-align: left; padding: 12px 16px; border-radius: 8px; }
QFrame#sidebar QPushButton:hover { background: $side_hover; color: #ffffff; }
QFrame#sidebar QPushButton:checked { background: $side_selected; color: #ffffff; font-weight: 600; }
QFrame#sidebar QLabel#avatar { background: $avatar; color: #ffffff; border-radius: 20px; font-size: 14px; font-weight: 700; }
QFrame#card, QFrame#panel { background: $surface; border: 1px solid $border; border-radius: 13px; }
QFrame#card:hover { border: 1px solid $focus; }
QFrame#card QLabel#cardTitle { color: $text; font-size: 15px; font-weight: 600; }
QLabel#muted { color: $muted; font-size: 12px; }
QLabel#badge { background: $tint; color: $accent_text; border-radius: 7px; padding: 6px 10px; font-size: 11px; font-weight: 600; }
QLabel#notice { background: $notice_bg; color: $notice_text; border-radius: 8px; padding: 10px; }
QLabel#error { color: $error; font-size: 12px; }
QLabel#toolIcon { background: $tint; color: $accent_text; border-radius: 11px; font-size: 18px; font-weight: 700; }
QPushButton { background: $surface; border: 1px solid $border; padding: 9px 16px; border-radius: 7px; font-weight: 600; }
QPushButton:hover { border-color: $focus; background: $tint; }
QPushButton:pressed { background: $tint; }
QPushButton:disabled { color: $disabled_text; background: $disabled; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 1px solid $focus; }
QPushButton#appearanceChoice { padding: 4px; border: 1px solid $border; font-weight: 600; }
QPushButton#appearanceChoice:checked { background: $tint; color: $accent_text; border: 1px solid $accent_text; }
QPushButton#primary { background: $primary; border: 1px solid $primary; color: white; }
QPushButton#primary:hover { background: $primary_hover; }
QPushButton#star { border: none; background: transparent; color: $muted; font-size: 20px; padding: 2px; }
QPushButton#star:checked { color: #d69b23; }
QPushButton#filter:checked { background: $tint; color: $accent_text; border-color: $focus; }
QLineEdit, QComboBox, QSpinBox { background: $surface; border: 1px solid $border; border-radius: 7px; padding: 10px; selection-background-color: $primary; selection-color: white; }
QLineEdit:disabled { color: $disabled_text; background: $disabled; }
QComboBox QAbstractItemView { background: $surface; color: $text; selection-background-color: $primary; selection-color: white; border: 1px solid $border; }
QCheckBox { spacing: 8px; background: transparent; padding: 4px; }
QCheckBox::indicator { width: 17px; height: 17px; background: $surface; border: 1px solid $muted; border-radius: 4px; }
QCheckBox::indicator:checked { background: $primary; border-color: $primary; image: url(:/icons/check.svg); }
QCheckBox::indicator:hover { border-color: $focus; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: transparent; color: $muted; padding: 12px 16px; border-bottom: 2px solid $border; font-weight: 600; }
QTabBar::tab:selected { color: $accent_text; border-bottom: 2px solid $accent_text; }
QTabBar::tab:hover { background: $tint; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 3px; }
QScrollBar::handle:vertical { background: $scrollbar; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTableWidget { background: $surface; border: 1px solid $border; border-radius: 7px; gridline-color: $border; selection-background-color: $tint; selection-color: $text; }
QTableWidget::item { padding: 9px; }
QHeaderView::section { background: $header; color: $muted; border: none; padding: 10px; font-weight: 600; }
QStatusBar { background: $surface; color: $muted; border-top: 1px solid $border; }
QToolTip { background: $sidebar; color: #ffffff; border: 1px solid $border; padding: 7px; }
""")


def build_stylesheet(mode="light", accent="purple"):
    return _STYLE_TEMPLATE.substitute(theme_colors(mode, accent))


def apply_theme(app, mode="light", accent="purple"):
    """Set both QSS and Qt's palette, including native popup/disabled colors."""
    colors = theme_colors(mode, accent)
    palette = QPalette()
    roles = {"Window": "background", "WindowText": "text", "Base": "surface",
             "AlternateBase": "header", "Text": "text", "Button": "surface",
             "ButtonText": "text", "Highlight": "primary", "HighlightedText": None,
             "ToolTipBase": "sidebar", "ToolTipText": None, "PlaceholderText": "muted",
             "Light": "border", "Midlight": "header", "Mid": "border",
             "Dark": "border", "Shadow": "background"}
    for role, token in roles.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(colors[token] if token else "#ffffff"))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled_text"]))
    app.setPalette(palette)
    app.setStyleSheet(build_stylesheet(mode, accent))


STYLE = build_stylesheet(*DEFAULT_APPEARANCE)
