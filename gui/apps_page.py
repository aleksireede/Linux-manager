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
import shutil

from programs.apps_file import load_apps_from_file
from programs.installer_logic import open_terminal, package_manager, is_fedora

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
        self.fedora_repositories_page = None
        self.app_settings_page = None
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

        settings_btn = QPushButton("App Settings")
        settings_btn.setFixedWidth(self.BUTTON_WIDTH)
        settings_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        settings_btn.setIconSize(QSize(22, 22))
        settings_btn.clicked.connect(self.open_app_settings)

        fedora_repos_btn = None
        if is_fedora():
            fedora_repos_btn = QPushButton("Fedora Repositories and Keys")
            fedora_repos_btn.setFixedWidth(self.BUTTON_WIDTH)
            fedora_repos_btn.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
            fedora_repos_btn.setIconSize(QSize(22, 22))
            fedora_repos_btn.clicked.connect(self.open_fedora_repositories)

        button_icons = (
            (install_btn, QStyle.SP_ArrowDown),
            (uninstall_btn, QStyle.SP_TrashIcon),
            (update_btn, QStyle.SP_BrowserReload),
            (editor_btn, QStyle.SP_FileDialogDetailedView),
        )
        for button, icon_type in button_icons:
            button.setIcon(self.style().standardIcon(icon_type))
            button.setIconSize(QSize(22, 22))

        for btn in (install_btn, uninstall_btn, update_btn, editor_btn, settings_btn):
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(btn)
            row.addStretch()
            container_layout.addLayout(row)

        if fedora_repos_btn:
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(fedora_repos_btn)
            row.addStretch()
            container_layout.addLayout(row)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(settings_btn)
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

    def open_fedora_repositories(self):
        if self.fedora_repositories_page is None:
            try:
                from .fedora_repositories_page import FedoraRepositoriesPage
            except ImportError:
                from fedora_repositories_page import FedoraRepositoriesPage
            self.fedora_repositories_page = FedoraRepositoriesPage(self)
        self.hide()
        self.fedora_repositories_page.show()

    def open_app_settings(self):
        if self.app_settings_page is None:
            try:
                from .app_settings_page import AppSettingsPage
            except ImportError:
                from app_settings_page import AppSettingsPage
            self.app_settings_page = AppSettingsPage(self)
        self.hide()
        self.app_settings_page.show()

    def run_system_update(self):
        try:
            if package_manager() in {"dnf", "dnf5"}:
                open_terminal(["sudo", package_manager(), "upgrade", "--refresh", "-y"])
            elif package_manager() == "pacman":
                if shutil.which("paru"):
                    command = ["paru", "-Suy", "--needed", "--quiet", "--skipreview", "--color", "always"]
                else:
                    command = ["sudo", "pacman", "-Syu", "--needed", "--quiet", "--color", "always"]
                open_terminal(command)
            else:
                raise RuntimeError("No supported package manager was detected.")
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to start system update: {e}")
