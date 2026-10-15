import subprocess
import re

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
except ImportError:
    from ui_helpers import create_back_button
    from theme import configure_main_window, create_page_header, apply_status_icon

from programs.text_editor import (
    update_bash_extra,
    enable_bash_extra,
    bashrc_extra_text,
    update_bash_custom,
)
from programs.config import (
    BASH_EXTRA_PATH,
    BASHRC_PATH,
    BASH_EXTRA_VERSION, BASH_CUSTOM_VERSION,
)


def is_bash_hook_enabled():
    if not BASHRC_PATH.exists():
        return False
    return bashrc_extra_text in BASHRC_PATH.read_text()


class BashConfigWindow(QMainWindow):
    VERSION_PATTERN = re.compile(r"^#\s*(?:linux-manager|arch-mysetup)-bash-extra-version:\s*(.+?)\s*$", re.MULTILINE)
    PAGE_BUTTON_WIDTH = 300

    def __init__(self, advanced_window=None):
        super().__init__()
        self.advanced_window = advanced_window
        self.status_labels = {}
        self.version_labels = {}
        self.tweaks = []
        self.back_button_container = None

        self.setWindowTitle("Bash Config")
        configure_main_window(self)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.back_button_container, _, _, _ = create_back_button(self.go_back)
        header_widget = create_page_header(self.back_button_container, "Bash Config")

        self.tweaks = [
            (
                "bash_extra_file",
                "Install/Update Extra Bash config",
                update_bash_extra,
                "Extra Bash config updated.",
                self.is_bash_extra_up_to_date,
            ),
            (
                "bash_custom_file",
                "Install/Update Custom Bash config",
                update_bash_custom,
                "Extra Bash config updated.",
                self.is_bash_custom_up_to_date,
            ),
            (
                "bash_hook",
                "Enable Extra Bash config",
                enable_bash_extra,
                "Enabled Extra Bash config.",
                is_bash_hook_enabled,
            ),
        ]

        container = QFrame()
        container_layout = QVBoxLayout(container)

        for key, label, callback, success, _ in self.tweaks:
            row_layout = QHBoxLayout()
            button = QPushButton(label)
            button.setFixedWidth(self.PAGE_BUTTON_WIDTH)
            button.clicked.connect(lambda _, cb=callback, msg=success: self.run_tweak(cb, msg))
            version_label = QLabel("")
            version_label.setMinimumWidth(190)
            version_label.setStyleSheet("font-weight: 700;")
            status_label = QLabel()
            status_label.setMinimumWidth(24)
            status_label.setMaximumWidth(24)
            row_layout.addStretch()
            row_layout.addWidget(button)
            row_layout.addWidget(version_label)
            row_layout.addWidget(status_label)
            row_layout.addStretch()
            container_layout.addLayout(row_layout)
            self.status_labels[key] = status_label
            self.version_labels[key] = version_label

        container_layout.addStretch()

        layout.addWidget(header_widget)
        layout.addSpacing(12)
        layout.addWidget(container)
        self.refresh_statuses()

    def go_back(self):
        if self.advanced_window:
            self.advanced_window.refresh_statuses()
            self.advanced_window.show()
        self.hide()

    def run_tweak(self, callback, success_message):
        """
        todo: add return type
        """
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

    def get_installed_bash_extra_version(self) -> str | None:
        if not BASH_EXTRA_PATH.exists():
            return None
        match = self.VERSION_PATTERN.search(BASH_EXTRA_PATH.read_text())
        if not match:
            return None
        return match.group(1).strip()

    def get_installed_bash_custom_version(self) -> str | None:
        if not BASHRC_PATH.exists():
            return None
        match = self.VERSION_PATTERN.search(BASHRC_PATH.read_text())
        if not match:
            return None
        return match.group(1).strip()

    def is_bash_extra_up_to_date(self):
        """
        todo: add return type
        """
        installed_version = self.get_installed_bash_extra_version()
        return installed_version == BASH_EXTRA_VERSION

    def is_bash_custom_up_to_date(self):
        installed_version = self.get_installed_bash_custom_version()
        return installed_version == BASH_CUSTOM_VERSION

    def set_status_icon(self, label: QLabel, enabled):
        if enabled is False and label is self.status_labels.get("bash_extra_file"):
            installed = self.get_installed_bash_extra_version()
            if installed is None:
                disabled_tip = f"Missing or unmanaged (expected version {BASH_EXTRA_VERSION})"
            else:
                disabled_tip = f"Outdated: installed {installed}, expected {BASH_EXTRA_VERSION}"
        else:
            disabled_tip = "Not enabled"

        apply_status_icon(
            label,
            enabled,
            enabled_tooltip="Enabled / Up to date",
            disabled_tooltip=disabled_tip,
            unknown_tooltip="Unknown",
        )

    def update_version_labels(self):
        for key, version_label in self.version_labels.items():
            if key != "bash_extra_file":
                version_label.setText("")
                continue

            installed = self.get_installed_bash_extra_version()
            if installed is None:
                version_label.setText(f"Version: missing -> {BASH_EXTRA_VERSION}")
            elif installed == BASH_EXTRA_VERSION:
                version_label.setText(f"Version: {installed} (latest)")
            else:
                version_label.setText(f"Version: {installed} -> {BASH_EXTRA_VERSION}")

    def refresh_statuses(self):
        for key, _, _, _, status_fn in self.tweaks:
            label = self.status_labels.get(key)
            if label is None:
                continue
            try:
                enabled = status_fn()
            except Exception:
                enabled = None
            self.set_status_icon(label, enabled)
        self.update_version_labels()
