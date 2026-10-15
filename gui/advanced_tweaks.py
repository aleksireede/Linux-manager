import subprocess

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QLabel,
    QFrame,
)

try:
    from .ui_helpers import create_back_button
    from .theme import configure_main_window, create_page_header, apply_status_icon
    from .pacman_config_window import PacmanConfigWindow
    from .bash_config_window import BashConfigWindow
except ImportError:
    from ui_helpers import create_back_button
    from theme import configure_main_window, create_page_header, apply_status_icon
    from pacman_config_window import PacmanConfigWindow
    from bash_config_window import BashConfigWindow

from scripts.extra import (
    git_keystore,
    zeroconf_discover_pw,
    airplay_discover_pw,
)
from programs.config import (
    BLUE_RIGHT_ARROW_ICON_PATH,
    ZEROCONF_DEST_PATH,
    AIRPLAY_DEST_PATH,
)
from programs.installer_logic import package_manager


def set_status_icon(label: QLabel, enabled):
    apply_status_icon(label, enabled)


def is_airplay_enabled():
    return AIRPLAY_DEST_PATH.exists()


def is_zeroconf_enabled():
    return ZEROCONF_DEST_PATH.exists()


def is_git_keystore_enabled():
    result = subprocess.run(
        ["git", "config", "--global", "credential.helper"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return None
    return result.stdout.strip() == "store"


class AdvancedTweaks(QMainWindow):
    ADV_BUTTON_WIDTH = 300

    def __init__(self, setup_window=None):
        super().__init__()
        self.back_button_container = None
        self.status_labels = {}
        self.tweaks = []
        self.setup_window = setup_window
        self.pacman_config_window = None
        self.bash_config_window = None

        self.setWindowTitle("Advanced Tweaks")
        configure_main_window(self)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        content_layout = QHBoxLayout()

        self.back_button_container, _, _, _ = create_back_button(self.go_back_to_setup)
        header_widget = create_page_header(self.back_button_container, "Advanced Tweaks")

        self.tweaks = [
            ("git_keystore", "Enable Git Credential Store", git_keystore, "Git credential helper task completed.", is_git_keystore_enabled),
            ("zeroconf", "Enable PipeWire Zeroconf Discover", zeroconf_discover_pw, "Zeroconf discover task completed.", is_zeroconf_enabled),
            ("airplay", "Enable PipeWire AirPlay Discover", airplay_discover_pw, "AirPlay discover task completed.", is_airplay_enabled),
        ]

        tweaks_container = QFrame()
        tweaks_layout = QVBoxLayout(tweaks_container)

        pacman_page_button = QPushButton("Open Page: Pacman Config")
        pacman_page_button.setIcon(QIcon(str(BLUE_RIGHT_ARROW_ICON_PATH)))
        pacman_page_button.setFixedWidth(self.ADV_BUTTON_WIDTH)
        pacman_page_button.clicked.connect(self.open_pacman_config)
        pacman_page_button.setVisible(package_manager() == "pacman")
        pacman_row = QHBoxLayout()
        pacman_row.addStretch()
        pacman_row.addWidget(pacman_page_button)
        pacman_row.addStretch()
        tweaks_layout.addLayout(pacman_row)

        bash_page_button = QPushButton("Open Page: Bash Config")
        bash_page_button.setIcon(QIcon(str(BLUE_RIGHT_ARROW_ICON_PATH)))
        bash_page_button.setFixedWidth(self.ADV_BUTTON_WIDTH)
        bash_page_button.clicked.connect(self.open_bash_config)
        bash_row = QHBoxLayout()
        bash_row.addStretch()
        bash_row.addWidget(bash_page_button)
        bash_row.addStretch()
        tweaks_layout.addLayout(bash_row)
        tweaks_layout.addSpacing(8)

        for key, label, callback, success, _ in self.tweaks:
            row_layout = QHBoxLayout()
            button = QPushButton(label)
            button.setFixedWidth(self.ADV_BUTTON_WIDTH)
            button.clicked.connect(lambda _, cb=callback, msg=success: self.run_tweak(cb, msg))
            status_label = QLabel()
            status_label.setMinimumWidth(24)
            status_label.setMaximumWidth(24)
            row_layout.addStretch()
            row_layout.addWidget(button)
            row_layout.addWidget(status_label)
            row_layout.addStretch()
            tweaks_layout.addLayout(row_layout)
            self.status_labels[key] = status_label

        tweaks_layout.addStretch()

        content_layout.addWidget(tweaks_container, 1)

        layout.addWidget(header_widget)
        layout.addSpacing(12)
        layout.addLayout(content_layout)
        self.refresh_statuses()

    def run_tweak(self, callback, success_message):
        try:
            callback()
            QMessageBox.information(self, "Done", success_message)
            self.refresh_statuses()
        except subprocess.CalledProcessError as e:
            if e.returncode == 126:
                QMessageBox.critical(self, "Authentication Failed", "Authentication failed.")
            else:
                QMessageBox.critical(self, "Error", f"Action failed: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Action failed: {e}")

    def go_back_to_setup(self):
        if self.setup_window:
            self.setup_window.show()
        self.hide()

    def open_pacman_config(self):
        if self.pacman_config_window is None:
            self.pacman_config_window = PacmanConfigWindow(self)
        self.pacman_config_window.refresh_statuses()
        self.pacman_config_window.show()
        self.hide()

    def open_bash_config(self):
        if self.bash_config_window is None:
            self.bash_config_window = BashConfigWindow(self)
        self.bash_config_window.refresh_statuses()
        self.bash_config_window.show()
        self.hide()

    def refresh_statuses(self):
        for key, _, _, _, status_fn in self.tweaks:
            label = self.status_labels.get(key)
            if label is None:
                continue
            try:
                enabled = status_fn()
            except Exception:
                enabled = None
            set_status_icon(label, enabled)
