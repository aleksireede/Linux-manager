import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget, QFrame

from programs.config import icon_checkmark, icon_red_cross, icon_question_mark
from programs.app_settings import accent_color, background_color

APP_DARK_THEME = """
QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 14px;
}
QDialog, QMessageBox, QInputDialog {
    background-color: #252526;
}
QLabel {
    background-color: transparent;
    padding: 2px 3px;
}
QLabel#serviceTitle {
    color: #f1f1f1;
    font-size: 14px;
    font-weight: 700;
    padding: 5px 2px;
}
QFrame#serviceCard {
    background-color: #252526;
    border: 1px solid #383838;
    border-radius: 10px;
}
QWidget#embeddedConfig, QFrame#embeddedConfigSurface {
    background-color: transparent;
    border: none;
}
QFrame#pageHeader {
    background-color: #252526;
    border: 1px solid #383838;
    border-bottom: 2px solid #007acc;
    border-radius: 9px;
}
QFrame#pageHeaderSeparator {
    background-color: #3c3c3c;
    border: none;
}
QLineEdit, QComboBox {
    background-color: #3c3c3c;
    color: #f0f0f0;
    border: 1px solid #505050;
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: #264f78;
}
QComboBox {
    max-width: 420px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #007acc;
}
QComboBox QAbstractItemView {
    max-width: 420px;
    background-color: #252526;
    color: #cccccc;
    selection-background-color: #094771;
    border: 1px solid #454545;
}
QPushButton {
    background-color: #2d2d30;
    color: #cccccc;
    border: 1px solid #454545;
    border-radius: 6px;
    min-height: 32px;
    padding: 6px 13px;
}
QPushButton:hover {
    background-color: #3e3e42;
    border-color: #5a5a5a;
}
QPushButton:pressed {
    background-color: #252526;
}
QPushButton:focus, QLineEdit:focus, QComboBox:focus {
    border: 1px solid #007acc;
}
QPushButton:disabled {
    background-color: #2a2a2a;
    color: #777777;
    border-color: #383838;
}
QPushButton#serviceAction {
    background-color: #0e639c;
    color: #ffffff;
    border: 1px solid #1177bb;
    border-radius: 6px;
    font-weight: 600;
}
QPushButton#serviceAction:hover {
    background-color: #1177bb;
}
QPushButton#serviceAction:pressed {
    background-color: #094771;
}
QPushButton#serviceAction[installed="true"] {
    background-color: #16825d;
    border-color: #25a879;
}
QPushButton#serviceAction[installed="true"]:hover {
    background-color: #1b9a70;
}
QPushButton#pageMenuButton {
    background-color: #252526;
    border: 1px solid #383838;
    border-radius: 7px;
    min-height: 38px;
    padding: 7px 16px;
    font-weight: 600;
}
QPushButton#pageMenuButton:hover {
    background-color: #2d2d30;
    border-color: #505050;
}
QPushButton#pageMenuButton:checked {
    background-color: #094771;
    border-color: #007acc;
    color: #ffffff;
}
QPushButton#categorySelectAll {
    background-color: #333337;
    color: #cccccc;
    border: 1px solid #4a4a4a;
    border-radius: 5px;
    min-height: 0;
    padding: 3px 7px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#categorySelectAll:hover {
    background-color: #3e3e42;
}
QWidget#categoryHeader {
    background-color: #2d2d30;
    border: 1px solid #3c3c3c;
    border-radius: 7px;
}
QWidget#categoryHeader QToolButton {
    background-color: transparent;
    border: none;
}
QLabel#categoryHeaderLabel {
    background: transparent;
    color: #f1f1f1;
    font-size: 14px;
    font-weight: 700;
}
QLabel#syncStatusLabel {
    background-color: #252526;
    color: #9cdcfe;
    border: 1px solid #007acc;
    border-radius: 7px;
    font-size: 14px;
    font-weight: 700;
    padding: 7px 11px;
}
QListWidget, QTreeWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #3c3c3c;
    border-radius: 8px;
    alternate-background-color: #252526;
    padding: 5px;
}
QListWidget::item, QTreeWidget::item {
    padding: 5px 7px;
    border-radius: 4px;
}
QListWidget::item:hover {
    background-color: #2a2d2e;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}
QTreeWidget::item {
    border-bottom: 1px solid #2d2d30;
}
QHeaderView::section {
    background-color: #252526;
    color: #cccccc;
    border: 1px solid #3c3c3c;
    padding: 8px 10px;
}
QFrame#backButtonCard {
    background-color: #2d2d30;
    border: 1px solid #454545;
    border-radius: 6px;
}
QFrame#backButtonCard:hover {
    background-color: #3e3e42;
}
QLabel#backButtonLabel, QPushButton#backButtonArrow {
    background-color: transparent;
    color: #f1f1f1;
    font-weight: bold;
    border: none;
    padding: 2px 4px;
}
QRadioButton {
    background-color: transparent;
    spacing: 8px;
    padding: 4px 2px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #777777;
    border-radius: 8px;
    background-color: #1e1e1e;
}
QRadioButton::indicator:checked {
    background-color: #007acc;
    border: 4px solid #1e1e1e;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background-color: #424242;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #5a5a5a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QMenu {
    background-color: #252526;
    color: #cccccc;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item:selected {
    background-color: #094771;
    border-radius: 4px;
}
QToolTip {
    background-color: #252526;
    color: #f1f1f1;
    border: 1px solid #454545;
    border-radius: 5px;
    padding: 5px 7px;
}
"""

DEFAULT_WINDOW_WIDTH = 1440
DEFAULT_WINDOW_HEIGHT = 810
DEFAULT_MIN_WINDOW_WIDTH = 1280
DEFAULT_MIN_WINDOW_HEIGHT = 720
DEFAULT_DIALOG_WIDTH = 560
DEFAULT_DIALOG_HEIGHT = 640
DEFAULT_MIN_DIALOG_WIDTH = 500
DEFAULT_MIN_DIALOG_HEIGHT = 560


def apply_dark_theme(widget):
    accent = QColor(accent_color())
    background = QColor(background_color())
    if background.lightnessF() > 0.55:
        surface = background.darker(108)
        field = background.darker(115)
        hover = background.darker(120)
        border = background.darker(130)
        foreground = QColor("#292929")
        bright_foreground = QColor("#111111")
    else:
        surface = background.lighter(120)
        field = background.lighter(145)
        hover = background.lighter(130)
        border = background.lighter(155)
        foreground = QColor("#cccccc")
        bright_foreground = QColor("#f1f1f1")
    replacements = {
        "#007acc": accent.name(),
        "#1177bb": accent.lighter(115).name(),
        "#094771": accent.darker(145).name(),
        "#0e639c": accent.darker(110).name(),
        "#1e1e1e": background.name(),
        "#252526": surface.name(),
        "#3c3c3c": field.name(),
        "#2d2d30": hover.name(),
        "#333337": hover.name(),
        "#3e3e42": hover.name(),
        "#454545": border.name(),
        "#383838": border.name(),
        "#505050": border.name(),
        "#424242": surface.darker(115).name(),
        "#5a5a5a": surface.lighter(120).name(),
        "#cccccc": foreground.name(),
        "#f1f1f1": bright_foreground.name(),
    }
    pattern = re.compile("|".join(re.escape(color) for color in replacements))
    stylesheet = pattern.sub(lambda match: replacements[match.group(0)], APP_DARK_THEME)
    widget.setStyleSheet(stylesheet)


def configure_main_window(window):
    window.resize(DEFAULT_MIN_WINDOW_WIDTH, DEFAULT_MIN_WINDOW_HEIGHT)
    window.setMinimumSize(DEFAULT_MIN_WINDOW_WIDTH, DEFAULT_MIN_WINDOW_HEIGHT)
    apply_dark_theme(window)


def configure_dialog(dialog, width=DEFAULT_DIALOG_WIDTH, height=DEFAULT_DIALOG_HEIGHT,
                     min_width=DEFAULT_MIN_DIALOG_WIDTH, min_height=DEFAULT_MIN_DIALOG_HEIGHT):
    dialog.resize(width, height)
    dialog.setMinimumSize(min_width, min_height)
    apply_dark_theme(dialog)


def create_page_header(back_button_container, title_text):
    header_container = QFrame()
    header_container.setObjectName("pageHeader")
    header_layout = QVBoxLayout(header_container)
    header_layout.setContentsMargins(10, 10, 10, 10)
    header_layout.setSpacing(8)

    title = QLabel(title_text)
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size: 24px; font-weight: 700; color: #f1f1f1; background: transparent;")

    if back_button_container is None:
        back_button_container = QWidget()
        back_button_container.setFixedSize(0, 0)
        back_button_container.setStyleSheet("background: transparent;")

    right_spacer = QWidget()
    right_spacer.setFixedSize(
        back_button_container.width(),
        back_button_container.height(),
    )
    right_spacer.setStyleSheet("background: transparent;")

    header_row = QHBoxLayout()
    header_row.addWidget(back_button_container)
    header_row.addStretch()
    header_row.addWidget(title)
    header_row.addStretch()
    header_row.addWidget(right_spacer)
    header_layout.addLayout(header_row)

    return header_container


def apply_status_icon(
    label,
    enabled,
    enabled_tooltip="Enabled",
    disabled_tooltip="Not enabled",
    unknown_tooltip="Unknown",
):
    if enabled is True:
        label.setPixmap(QPixmap(str(icon_checkmark)).scaled(20, 20))
        label.setToolTip(enabled_tooltip)
    elif enabled is False:
        label.setPixmap(QPixmap(str(icon_red_cross)).scaled(20, 20))
        label.setToolTip(disabled_tooltip)
    else:
        label.setPixmap(QPixmap(str(icon_question_mark)).scaled(20, 20))
        label.setToolTip(unknown_tooltip)
