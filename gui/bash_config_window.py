import subprocess
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QLabel,
    QFrame,
)
from PyQt5.QtCore import Qt

try:
    from .theme import apply_status_icon
except ImportError:
    from theme import apply_status_icon

from programs.text_editor import (
    update_shell_custom,
    enable_shell_custom,
    get_shell_installed_version,
    is_shell_custom_enabled,
    shell_custom_version,
)
from programs.shell_frameworks import default_shell


def is_bash_hook_enabled():
    return is_shell_custom_enabled()


class BashConfigWindow(QWidget):
    PAGE_BUTTON_WIDTH = 420

    def __init__(self, advanced_window=None):
        super().__init__()
        self.setObjectName("embeddedConfig")
        self.advanced_window = advanced_window
        self.status_labels = {}
        self.version_labels = {}
        self.tweaks = []
        self.shell = default_shell()
        self.supported_shell = self.shell in {"bash", "zsh"}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("embeddedConfigSurface")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(10)

        shell_name = "Zsh" if self.shell == "zsh" else "Bash"
        if not self.supported_shell:
            shell_note = QLabel(f"Custom shell configs support Bash and Zsh; detected {self.shell or 'unknown'}.")
            container_layout.addWidget(shell_note)
        self.tweaks = [
            (
                "shell_custom_file",
                f"Install/Update Shared {shell_name} config",
                update_shell_custom,
                f"Shared {shell_name} config updated.",
                self.is_bash_custom_up_to_date,
            ),
            (
                "shell_hook",
                f"Enable Shared {shell_name} config",
                enable_shell_custom,
                f"Enabled Shared {shell_name} config.",
                is_bash_hook_enabled,
            ),
        ]

        for key, label, callback, success, _ in self.tweaks:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setAlignment(Qt.AlignLeft)
            button = QPushButton(label)
            button.setFixedWidth(self.PAGE_BUTTON_WIDTH)
            button.setEnabled(self.supported_shell)
            button.clicked.connect(lambda _, cb=callback, msg=success: self.run_tweak(cb, msg))
            version_label = QLabel("")
            version_label.setMinimumWidth(190)
            version_label.setStyleSheet("font-weight: 700;")
            status_label = QLabel()
            status_label.setMinimumWidth(24)
            status_label.setMaximumWidth(24)
            row_layout.addWidget(button, alignment=Qt.AlignLeft)
            row_layout.addWidget(status_label)
            row_layout.addWidget(version_label)
            row_layout.addStretch()
            container_layout.addLayout(row_layout)
            self.status_labels[key] = status_label
            self.version_labels[key] = version_label

        container_layout.addStretch()

        layout.addWidget(container)
        self.refresh_statuses()

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

    def get_installed_bash_custom_version(self) -> str | None:
        return get_shell_installed_version("custom")

    def is_bash_extra_up_to_date(self):
        """
        todo: add return type
        """
        installed_version = self.get_installed_bash_custom_version()
        return installed_version == shell_custom_version()

    def is_bash_custom_up_to_date(self):
        installed_version = self.get_installed_bash_custom_version()
        return installed_version == shell_custom_version()

    def set_status_icon(self, label: QLabel, enabled):
        if enabled is False and label is self.status_labels.get("shell_custom_file"):
            installed = self.get_installed_bash_custom_version()
            if installed is None:
                disabled_tip = f"Missing or unmanaged (expected version {shell_custom_version()})"
            else:
                disabled_tip = f"Outdated: installed {installed}, expected {shell_custom_version()}"
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
        if not self.supported_shell:
            for version_label in self.version_labels.values():
                version_label.setText("")
            return
        for key, version_label in self.version_labels.items():
            if key == "shell_custom_file":
                installed = self.get_installed_bash_custom_version()
                expected = shell_custom_version()
            else:
                version_label.setText("")
                continue

            if installed is None:
                version_label.setText(f"Version: missing -> {expected}")
            elif installed == expected:
                version_label.setText(f"Version: {installed} (latest)")
            else:
                version_label.setText(f"Version: {installed} -> {expected}")

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
