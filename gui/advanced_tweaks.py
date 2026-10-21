import subprocess

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QLabel,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QLayout,
)

try:
    from .theme import apply_dark_theme, apply_status_icon
    from .pacman_config_window import PacmanConfigWindow
    from .bash_config_window import BashConfigWindow
    from .shell_framework_window import ShellFrameworkWindow
except ImportError:
    from theme import apply_dark_theme, apply_status_icon
    from pacman_config_window import PacmanConfigWindow
    from bash_config_window import BashConfigWindow
    from shell_framework_window import ShellFrameworkWindow

from scripts.extra import (
    git_keystore,
    zeroconf_discover_pw,
    airplay_discover_pw,
)
from programs.config import (
    icon_blue_arrow,
    file_zeroconf_pw,
    file_airplay_pw,
)
from programs.installer_logic import package_manager


def set_status_icon(label: QLabel, enabled):
    apply_status_icon(label, enabled)


def is_airplay_enabled():
    return file_airplay_pw.exists()


def is_zeroconf_enabled():
    return file_zeroconf_pw.exists()


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


class AdvancedTweaks(QWidget):
    ADV_BUTTON_WIDTH = 420

    def __init__(self, setup_window=None):
        super().__init__(setup_window)
        self.status_labels = {}
        self.tweaks = []
        self.setup_window = setup_window
        self.pacman_config_window = None
        self.bash_config_widget = None
        self.shell_framework_widget = None

        self.setWindowTitle("Advanced Tweaks")
        apply_dark_theme(self)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        page_content = QWidget()
        page_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        page_layout = QVBoxLayout(page_content)
        page_layout.setSizeConstraint(QLayout.SetMinimumSize)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addSpacing(12)
        content_layout = QHBoxLayout()

        self.tweaks = [
            ("git_keystore", "Enable Git Credential Store", git_keystore, "Git credential helper task completed.", is_git_keystore_enabled),
            ("zeroconf", "Enable PipeWire Zeroconf Discover", zeroconf_discover_pw, "Zeroconf discover task completed.", is_zeroconf_enabled),
            ("airplay", "Enable PipeWire AirPlay Discover", airplay_discover_pw, "AirPlay discover task completed.", is_airplay_enabled),
        ]

        tweaks_container = QFrame()
        tweaks_container.setObjectName("serviceCard")
        tweaks_layout = QVBoxLayout(tweaks_container)
        tweaks_layout.setContentsMargins(22, 20, 22, 20)
        tweaks_layout.setSpacing(12)

        pacman_page_button = QPushButton("Open Page: Pacman Config")
        pacman_page_button.setIcon(QIcon(str(icon_blue_arrow)))
        pacman_page_button.setFixedWidth(self.ADV_BUTTON_WIDTH)
        pacman_page_button.clicked.connect(self.open_pacman_config)
        pacman_page_button.setVisible(package_manager() == "pacman")
        tweaks_layout.addWidget(pacman_page_button, alignment=Qt.AlignLeft)

        tweaks_layout.addSpacing(8)

        for key, label, callback, success, _ in self.tweaks:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            button = QPushButton(label)
            button.setFixedWidth(self.ADV_BUTTON_WIDTH)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.clicked.connect(lambda _, cb=callback, msg=success: self.run_tweak(cb, msg))
            status_label = QLabel()
            status_label.setMinimumWidth(24)
            status_label.setMaximumWidth(24)
            row_layout.addWidget(button, alignment=Qt.AlignLeft)
            row_layout.addWidget(status_label, alignment=Qt.AlignLeft)
            row_layout.addStretch()
            tweaks_layout.addLayout(row_layout)
            self.status_labels[key] = status_label

        bash_title = QLabel("Shell Config")
        bash_title.setObjectName("serviceTitle")
        tweaks_layout.addWidget(bash_title)
        self.bash_config_widget = BashConfigWindow(self)
        tweaks_layout.addWidget(self.bash_config_widget)

        shell_framework_title = QLabel("Oh My Bash / Oh My Zsh")
        shell_framework_title.setObjectName("serviceTitle")
        tweaks_layout.addWidget(shell_framework_title)
        self.shell_framework_widget = ShellFrameworkWindow(self)
        tweaks_layout.addWidget(self.shell_framework_widget)

        tweaks_layout.addStretch()

        content_layout.addWidget(tweaks_container, 1)

        page_layout.addLayout(content_layout)
        page_layout.addStretch()
        page_layout.activate()
        page_content.setMinimumHeight(page_layout.sizeHint().height())
        scroll_area.setWidget(page_content)
        layout.addWidget(scroll_area)
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

    def open_pacman_config(self):
        if self.pacman_config_window is None:
            self.pacman_config_window = PacmanConfigWindow(self)
        self.pacman_config_window.refresh_statuses()
        self.pacman_config_window.show()
        self.hide()

    def refresh_shell_config(self):
        old_widget = self.bash_config_widget
        if old_widget is None:
            return
        parent_layout = old_widget.parentWidget().layout()
        index = parent_layout.indexOf(old_widget)
        parent_layout.removeWidget(old_widget)
        old_widget.deleteLater()
        self.bash_config_widget = BashConfigWindow(self)
        parent_layout.insertWidget(index, self.bash_config_widget)

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
