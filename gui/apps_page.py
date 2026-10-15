from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QStyle,
)
from PyQt5.QtCore import QSize

from programs.apps_file import load_apps_from_file
from programs.installer_logic import open_terminal

try:
    from .applist_editor_dialog import AppListEditorDialog
    from .ui_helpers import create_back_button
    from .theme import configure_main_window, create_page_header
except ImportError:
    from applist_editor_dialog import AppListEditorDialog
    from ui_helpers import create_back_button
    from theme import configure_main_window, create_page_header


class AppsPage(QMainWindow):
    BUTTON_WIDTH = 320

    def __init__(self, setup_window=None):
        super().__init__()
        self.setup_window = setup_window
        self.back_button_container = None
        self.setWindowTitle("Apps")
        configure_main_window(self)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.back_button_container, _, _, _ = create_back_button(self.go_back_to_setup)
        header_widget = create_page_header(self.back_button_container, "Apps")

        container_layout = QVBoxLayout()

        install_btn = QPushButton("Install Apps")
        install_btn.setFixedWidth(self.BUTTON_WIDTH)
        install_btn.clicked.connect(self.open_installer)

        uninstall_btn = QPushButton("Uninstall Apps")
        uninstall_btn.setFixedWidth(self.BUTTON_WIDTH)
        uninstall_btn.clicked.connect(self.open_uninstaller)

        update_btn = QPushButton("System Update")
        update_btn.setFixedWidth(self.BUTTON_WIDTH)
        update_btn.clicked.connect(self.run_system_update)

        editor_btn = QPushButton("Open App List Editor")
        editor_btn.setFixedWidth(self.BUTTON_WIDTH)
        editor_btn.clicked.connect(self.open_app_list_editor)

        button_icons = (
            (install_btn, QStyle.SP_ArrowDown),
            (uninstall_btn, QStyle.SP_TrashIcon),
            (update_btn, QStyle.SP_BrowserReload),
            (editor_btn, QStyle.SP_FileDialogDetailedView),
        )
        for button, icon_type in button_icons:
            button.setIcon(self.style().standardIcon(icon_type))
            button.setIconSize(QSize(22, 22))

        for btn in (install_btn, uninstall_btn, update_btn, editor_btn):
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(btn)
            row.addStretch()
            container_layout.addLayout(row)

        container_layout.addStretch()

        layout.addWidget(header_widget)
        layout.addSpacing(12)
        layout.addLayout(container_layout)

    def go_back_to_setup(self):
        if self.setup_window:
            self.setup_window.show()
        self.hide()

    def open_installer(self):
        if self.setup_window:
            self.hide()
            self.setup_window.open_installer.emit()

    def open_uninstaller(self):
        if self.setup_window:
            self.hide()
            self.setup_window.open_uninstaller.emit()

    def open_app_list_editor(self):
        apps = load_apps_from_file()
        dialog = AppListEditorDialog(self, apps)
        dialog.exec()

    def run_system_update(self):
        try:
            open_terminal([
                "paru",
                "-Suy",
                "--needed",
                "--quiet",
                "--skipreview",
                "--color",
                "always",
            ])
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to start system update: {e}")
