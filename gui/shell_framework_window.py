from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from programs.shell_frameworks import (
    available_themes,
    available_login_shells,
    current_theme,
    framework_for_default_shell,
    install_framework,
    is_framework_installed,
    set_theme,
    set_default_shell,
)


class ShellFrameworkWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("embeddedConfig")
        self.shell, self.framework = framework_for_default_shell()
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        surface = QFrame()
        surface.setObjectName("embeddedConfigSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(8)

        shell_row = QHBoxLayout()
        shell_row.addWidget(QLabel("Default shell:"))
        self.shell_selector = QComboBox()
        self.shell_selector.addItem("Bash", "bash")
        self.shell_selector.addItem("Zsh", "zsh")
        self.shell_selector.currentIndexChanged.connect(self.update_shell_button)
        shell_row.addWidget(self.shell_selector)
        self.set_shell_button = QPushButton("Set as default")
        self.set_shell_button.clicked.connect(self.change_default_shell)
        shell_row.addWidget(self.set_shell_button)
        self.shell_status_label = QLabel()
        shell_row.addWidget(self.shell_status_label)
        shell_row.addStretch()
        surface_layout.addLayout(shell_row)

        shell_name = self.framework["name"] if self.framework else "Unsupported shell"
        self.shell_label = QLabel(f"Default login shell: {self.shell or 'unknown'} — {shell_name}")
        surface_layout.addWidget(self.shell_label)

        action_row = QHBoxLayout()
        self.install_button = QPushButton("Install shell framework")
        self.install_button.setFixedWidth(420)
        self.install_button.clicked.connect(self.install)
        action_row.addWidget(self.install_button)
        self.status_label = QLabel()
        action_row.addWidget(self.status_label)
        action_row.addStretch()
        surface_layout.addLayout(action_row)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self.theme_selector = QComboBox()
        self.theme_selector.setMaxVisibleItems(12)
        self.theme_selector.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.theme_selector.currentTextChanged.connect(self.change_theme)
        theme_row.addWidget(self.theme_selector)
        theme_row.addStretch()
        surface_layout.addLayout(theme_row)

        layout.addWidget(surface)

    def refresh(self):
        self.shell = framework_for_default_shell()[0]
        self.framework = framework_for_default_shell()[1]
        shell_name = self.framework["name"] if self.framework else "Unsupported shell"
        self.shell_label.setText(f"Default login shell: {self.shell or 'unknown'} — {shell_name}")
        current_index = self.shell_selector.findData(self.shell)
        self.shell_selector.blockSignals(True)
        self.shell_selector.setCurrentIndex(current_index)
        self.shell_selector.blockSignals(False)
        available = available_login_shells()
        if self.shell in {"bash", "zsh"}:
            current_path = available.get(self.shell)
            self.shell_status_label.setText(
                f"Current: {current_path}" if current_path else f"Current: {self.shell} (unavailable)"
            )
        else:
            self.shell_status_label.setText(f"Current shell: {self.shell or 'unknown'}")
        self.update_shell_button()

        if self.framework is None:
            self.install_button.setText("Install shell framework")
            self.install_button.setEnabled(False)
            self.theme_selector.clear()
            self.theme_selector.setEnabled(False)
            self.status_label.setText("Only Bash and Zsh login shells are supported.")
            return

        name = self.framework["name"]
        installed = is_framework_installed(self.shell)
        self.install_button.setText(f"{'Installed' if installed else 'Install'} {name}")
        self.install_button.setEnabled(not installed)
        self.theme_selector.blockSignals(True)
        self.theme_selector.clear()
        themes = available_themes(self.shell) if installed else []
        self.theme_selector.addItems(themes)
        selected = current_theme(self.shell)
        if selected not in themes:
            selected = "font" if self.shell == "bash" and "font" in themes else (
                "robbyrussell" if "robbyrussell" in themes else None
            )
        if selected:
            index = self.theme_selector.findText(selected)
            if index >= 0:
                self.theme_selector.setCurrentIndex(index)
        self.theme_selector.setEnabled(installed and bool(themes))
        self.theme_selector.blockSignals(False)
        self.status_label.setText(
            "Installed. Theme changes apply in new terminals." if installed
            else "Install adds a managed block to your shell config and saves a backup."
        )

    def update_shell_button(self, *_):
        selected_shell = self.shell_selector.currentData()
        available = available_login_shells()
        is_current = selected_shell == self.shell
        is_available = selected_shell in available
        self.set_shell_button.setEnabled(is_available and not is_current)
        if not is_available:
            self.set_shell_button.setToolTip("This shell must be installed and listed in /etc/shells first.")
        elif is_current:
            self.set_shell_button.setToolTip("This is already your default login shell.")
        else:
            self.set_shell_button.setToolTip("")

    def change_default_shell(self):
        selected_shell = self.shell_selector.currentData()
        if not selected_shell:
            return
        label = "Bash" if selected_shell == "bash" else "Zsh"
        answer = QMessageBox.question(
            self,
            "Change default shell",
            f"Set {label} as your default login shell? This takes effect in new login sessions.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            set_default_shell(selected_shell)
            self.refresh()
            parent = self.parent()
            if parent is not None and hasattr(parent, "refresh_shell_config"):
                parent.refresh_shell_config()
            QMessageBox.information(
                self,
                "Default shell changed",
                f"{label} is now your default login shell. Open a new login session to use it.",
            )
        except Exception as error:
            QMessageBox.critical(self, "Could not change default shell", str(error))
            self.refresh()

    def install(self):
        try:
            install_framework(self.shell)
            self.refresh()
            QMessageBox.information(
                self,
                "Shell framework installed",
                f"{self.framework['name']} is installed for your default shell.\n"
                "Your existing shell config was backed up if it existed. Open a new terminal to use it.",
            )
        except Exception as error:
            QMessageBox.critical(self, "Shell framework install failed", str(error))

    def change_theme(self, theme):
        if not theme or not self.framework or not is_framework_installed(self.shell):
            return
        try:
            set_theme(self.shell, theme)
            self.status_label.setText(f"Theme set to {theme}. It applies in new terminals.")
        except Exception as error:
            QMessageBox.critical(self, "Could not change shell theme", str(error))
            self.refresh()
