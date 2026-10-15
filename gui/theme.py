from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget, QFrame

from programs.config import CHECKMARK_ICON_PATH, RED_X_ICON_PATH, QUESTION_MARK_ICON_PATH

APP_DARK_THEME = """
QWidget {
    background-color: #0e141c;
    color: #d9e2ee;
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
}
QLabel {
    padding: 3px 5px;
}
QDialog, QMessageBox, QInputDialog {
    font-size: 16px;
}
QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {
    font-size: 16px;
    padding: 4px 5px;
}
QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {
    font-size: 15px;
    min-height: 38px;
    padding: 8px 12px;
}
QDialog QLineEdit, QInputDialog QLineEdit {
    font-size: 16px;
    min-height: 38px;
    padding: 6px 10px;
}
QDialog QListWidget {
    font-size: 15px;
}
QLineEdit, QComboBox {
    background-color: #111a25;
    color: #e4edf8;
    border: 1px solid #34475e;
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: #3478c9;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #65a9ff;
}
QComboBox QAbstractItemView {
    background-color: #172231;
    color: #e4edf8;
    selection-background-color: #285d99;
    border: 1px solid #34475e;
}
QFrame#serviceCard {
    background-color: #17212d;
    border: 1px solid #2b3b4e;
    border-radius: 12px;
}
QLabel#serviceTitle {
    font-size: 14px;
    font-weight: 700;
    color: #eaf2ff;
    padding: 4px 5px;
}
QLabel#categoryHeaderLabel {
    background-color: transparent;
    color: #eaf2ff;
    font-size: 14px;
    font-weight: 700;
    padding: 0px 4px;
}
QWidget#categoryHeader {
    background-color: #17212d;
    border-radius: 5px;
}
QWidget#categoryHeader QToolButton {
    background-color: transparent;
}
QPushButton {
    background-color: #1b2837;
    color: #dce7f4;
    border: 1px solid #34475e;
    border-radius: 7px;
    min-height: 34px;
    padding: 8px 14px;
}
QPushButton:hover {
    background-color: #26384c;
    border-color: #496582;
}
QPushButton:pressed {
    background-color: #142131;
}
QPushButton:focus {
    border: 1px solid #65a9ff;
}
QPushButton:disabled {
    background-color: #18212c;
    color: #7f8d9e;
    border-color: #2a3542;
}
QPushButton#serviceAction {
    background-color: #3478d4;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 8px 15px;
    font-weight: 600;
}
QPushButton#categorySelectAll {
    background-color: #243448;
    color: #dce7f4;
    border: 1px solid #41566f;
    border-radius: 5px;
    min-height: 0;
    padding: 3px 7px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#categorySelectAll:hover {
    background-color: #314761;
}
QPushButton#serviceAction:hover {
    background-color: #458be8;
}
QPushButton#serviceAction:pressed {
    background-color: #2866b6;
}
QPushButton#serviceAction[installed="true"] {
    background-color: #278650;
    border: 1px solid #39a96a;
    font-weight: 700;
}
QPushButton#serviceAction[installed="true"]:hover {
    background-color: #319b5e;
}
QLabel#syncStatusLabel {
    background-color: #142530;
    color: #d8f4ff;
    border: 1px solid #248db2;
    border-radius: 9px;
    font-size: 15px;
    font-weight: 700;
    padding: 8px 12px;
    letter-spacing: 0.6px;
}
QListWidget {
    background-color: #101923;
    border: 1px solid #2c3c50;
    border-radius: 9px;
    padding: 5px;
}
QListWidget::item {
    padding: 3px 6px;
    border-radius: 5px;
}
QListWidget::item:hover {
    background-color: #1a2a3a;
}
QListWidget::item:selected {
    background-color: #234a73;
    color: #ffffff;
}
QFrame#backButtonCard {
    background-color: #243448;
    border: 1px solid #41566f;
    border-radius: 7px;
}
QFrame#backButtonCard:hover {
    background-color: #314761;
}
QLabel#backButtonLabel, QPushButton#backButtonArrow {
    background-color: transparent;
    color: #ffffff;
    font-weight: bold;
    border: none;
    padding: 2px 4px;
}
QFrame#pageHeader {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #243b65,
        stop: 0.5 #4b367f,
        stop: 1 #24527b
    );
    border: 1px solid #ffffff30;
    border-radius: 12px;
}
QFrame#pageHeaderSeparator {
    background-color: #ffffffdd;
    border: none;
}
QTreeWidget {
    background-color: #101923;
    border: 1px solid #2c3c50;
    border-radius: 9px;
    font-size: 14px;
    alternate-background-color: #161f2a;
    color: #d6dee8;
}
QTreeWidget::item {
    border-bottom: 1px solid #1b2430;
    padding: 5px 7px;
}
QTreeWidget::item:selected {
    background-color: #234a73;
}
QHeaderView::section {
    background-color: #17212d;
    color: #eaf2ff;
    border: 1px solid #2e3f53;
    padding: 7px 10px;
    font-size: 13px;
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
    widget.setStyleSheet(APP_DARK_THEME)


def configure_main_window(window):
    window.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
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
    title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff; background: transparent;")

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
        label.setPixmap(QPixmap(str(CHECKMARK_ICON_PATH)).scaled(20, 20))
        label.setToolTip(enabled_tooltip)
    elif enabled is False:
        label.setPixmap(QPixmap(str(RED_X_ICON_PATH)).scaled(20, 20))
        label.setToolTip(disabled_tooltip)
    else:
        label.setPixmap(QPixmap(str(QUESTION_MARK_ICON_PATH)).scaled(20, 20))
        label.setToolTip(unknown_tooltip)
