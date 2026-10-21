import re
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, QObject, QThread
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QHBoxLayout, QMessageBox, QFrame, \
    QLineEdit, QSizePolicy, QDialog, QFormLayout, QDialogButtonBox, QApplication

programs_dir = str(Path(__file__).resolve().parent.parent.joinpath("programs"))
sys.path.append(programs_dir)

scripts_dir = str(Path(__file__).resolve().parent.parent.joinpath("scripts"))
sys.path.append(scripts_dir)

from scripts.detect_gpu import detect_gpu_vendor
from programs.config import CHECKMARK_ICON_PATH, RED_X_ICON_PATH
from programs.installer_logic import install_paru, add_samba_drive, command_exists, open_terminal
try:
    from .theme import configure_main_window, configure_dialog
except ImportError:
    from theme import configure_main_window, configure_dialog


def gpu_driver_installed():
    vendor = detect_gpu_vendor()
    mesa_installed = subprocess.run(
        ["pacman", "-Q", "mesa"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0
    if vendor == "AMD":
        return mesa_installed
    if vendor == "Intel":
        return shutil.which("intel-virtual-output") is not None
    if vendor == "NVIDIA":
        return shutil.which("nvidia-modprobe") is not None
    return False


class UpdateCheckWorker(QObject):
    finished = pyqtSignal(str, bool, str, str)
    error = pyqtSignal(str)

    def run(self):
        try:
            latest_tag = self.fetch_latest_release_tag()
            current_version = self.get_current_version()

            if current_version == latest_tag:
                status_text = f"Up to date ({latest_tag})"
                update_available = False
            elif current_version == "unknown":
                status_text = f"Latest version: {latest_tag} (local version unknown)"
                update_available = True
            else:
                status_text = f"Update available: {current_version} -> {latest_tag}"
                update_available = True

            self.finished.emit(status_text, update_available, current_version, latest_tag)
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def fetch_latest_release_tag():
        output = subprocess.check_output(
            [
                "git", "ls-remote", "--tags", "--refs",
                "https://github.com/aleksireede/arch-mysetup.git",
            ],
            text=True,
            timeout=8,
        )
        tags = [
            line.rsplit("refs/tags/", 1)[-1]
            for line in output.splitlines()
            if "refs/tags/" in line
        ]
        version_tags = [tag for tag in tags if re.fullmatch(r"v?\d+(?:\.\d+)*", tag)]
        if not version_tags:
            raise RuntimeError("Could not resolve a version tag from GitHub")
        return max(
            version_tags,
            key=lambda tag: tuple(int(part) for part in tag.removeprefix("v").split(".")),
        )

    @staticmethod
    def get_current_version():
        repo_root = Path(__file__).resolve().parent.parent
        try:
            return subprocess.check_output(
                ["git", "-C", str(repo_root), "describe", "--tags", "--exact-match"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except subprocess.CalledProcessError:
            try:
                return subprocess.check_output(
                    ["git", "-C", str(repo_root), "describe", "--tags", "--abbrev=0"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
            except subprocess.CalledProcessError:
                return "unknown"


class SetupWindow(QMainWindow):
    open_installer = pyqtSignal()  # Signal to open the installer
    open_uninstaller = pyqtSignal()
    open_advanced_tweaks = pyqtSignal()
    open_apps_page = pyqtSignal()
    open_services_page = pyqtSignal()
    open_games_page = pyqtSignal()
    open_dev_tools_page = pyqtSignal()
    open_browsers_page = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Buttons
        self.paru_card = None
        self.gpu_card = None
        self.advanced_tweak_btn = None
        self.outer_bottom_layout = None
        self.bottom_layout = None
        self.update_layout = None
        self.update_card = None
        self.update_status = None
        self.update_status_icon = None
        self.update_state_label = None
        self.update_button = None
        self.update_check_thread = None
        self.update_check_worker = None
        self.latest_tag = ""
        self.sudo_password = None
        self.gpudrv_label = None
        self.gpudrv_status = None
        self.gpudrv_button = None
        self.gpudrv_layout = None
        self.install_button = None
        self.remove_button = None
        self.apps_page_button = None
        self.services_page_button = None
        self.games_page_button = None
        self.dev_tools_page_button = None
        self.browsers_page_button = None
        self.add_network_drive_button = None
        self.install_paru_button = None
        # end buttons
        self.paru_status = None
        self.paru_label = None
        # layout horizontal or vertical
        self.paru_layout = None
        self.layout = None
        # main window
        self.main_window = None
        # Set the window title text
        self.setWindowTitle("Arch advanced setup")
        configure_main_window(self)
        self.init_ui()

    def init_ui(self):
        self.main_window = QWidget()
        self.setCentralWidget(self.main_window)
        self.layout = QVBoxLayout(self.main_window)  # Set layout directly on central widget

        # GPU Driver Section
        self.gpu_card = QFrame()
        self.gpu_card.setObjectName("serviceCard")
        self.gpudrv_layout = QHBoxLayout(self.gpu_card)
        self.gpudrv_layout.setContentsMargins(16, 14, 16, 14)
        self.gpudrv_layout.setSpacing(12)
        self.gpudrv_button = QPushButton("Install GPU Drivers")
        self.gpudrv_button.setObjectName("serviceAction")
        self.gpudrv_label = QLabel("GPU Drivers")
        self.gpudrv_label.setObjectName("serviceTitle")
        self.gpudrv_button.clicked.connect(self.handle_gpu_driver_install)
        self.gpudrv_status = QLabel()
        self.update_gpu_status()

        # Gpu driver layout setup
        self.gpudrv_layout.addWidget(self.gpudrv_label, 1)
        self.gpudrv_layout.addWidget(self.gpudrv_status)
        self.gpudrv_layout.addWidget(self.gpudrv_button)

        # Paru section
        self.paru_card = QFrame()
        self.paru_card.setObjectName("serviceCard")
        self.paru_layout = QHBoxLayout(self.paru_card)
        self.paru_layout.setContentsMargins(16, 14, 16, 14)
        self.paru_layout.setSpacing(12)
        self.paru_label = QLabel("Paru (AUR Helper)")
        self.paru_label.setObjectName("serviceTitle")
        self.paru_status = QLabel()
        self.install_paru_button = QPushButton("Install Paru")
        self.install_paru_button.setObjectName("serviceAction")
        self.update_paru_status()
        self.install_paru_button.clicked.connect(self.handle_install_paru)

        # add paru widgets to paru layout
        self.paru_layout.addWidget(self.paru_label, 1)
        self.paru_layout.addWidget(self.paru_status)
        self.paru_layout.addWidget(self.install_paru_button)

        # Update section
        self.update_card = QFrame()
        self.update_card.setObjectName("serviceCard")
        self.update_layout = QHBoxLayout(self.update_card)
        self.update_layout.setContentsMargins(16, 14, 16, 14)
        self.update_layout.setSpacing(12)
        update_title = QLabel("App Update")
        update_title.setObjectName("serviceTitle")
        self.update_status = QLabel("Checking latest release...")
        self.update_status_icon = QLabel()
        self.update_state_label = QLabel("Checking...")
        update_info_layout = QVBoxLayout()
        update_meta_layout = QHBoxLayout()
        update_meta_layout.addWidget(self.update_status_icon)
        update_meta_layout.addWidget(self.update_state_label)
        update_meta_layout.addStretch()
        update_info_layout.addWidget(update_title)
        update_info_layout.addLayout(update_meta_layout)
        update_info_layout.addWidget(self.update_status)
        self.update_button = QPushButton("Checking...")
        self.update_button.setObjectName("serviceAction")
        self.update_button.setEnabled(False)
        self.update_button.clicked.connect(self.run_app_update)
        self.update_layout.addLayout(update_info_layout, 1)
        self.update_layout.addWidget(self.update_button)

        # Add Network Drive button
        self.add_network_drive_button = QPushButton("Add Network Drive (Samba)")
        self.add_network_drive_button.clicked.connect(self.add_network_drive)

        # Apps page button
        self.apps_page_button = QPushButton("Apps")
        self.apps_page_button.clicked.connect(self.open_apps_page.emit)

        self.services_page_button = QPushButton("Services")
        self.services_page_button.clicked.connect(self.open_services_page.emit)

        self.games_page_button = QPushButton("Games")
        self.games_page_button.clicked.connect(self.open_games_page.emit)

        self.dev_tools_page_button = QPushButton("Developer Tools")
        self.dev_tools_page_button.clicked.connect(self.open_dev_tools_page.emit)

        self.browsers_page_button = QPushButton("Web Browsers")
        self.browsers_page_button.clicked.connect(self.open_browsers_page.emit)

        self.advanced_tweak_btn = QPushButton("Advanced Tweaks")
        self.advanced_tweak_btn.clicked.connect(self.open_advanced_tweaks.emit)

        # Set size policies for buttons
        self.install_paru_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.gpudrv_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.update_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        service_btn_width = 180
        main_button_width = 240
        self.install_paru_button.setFixedWidth(service_btn_width)
        self.gpudrv_button.setFixedWidth(service_btn_width)
        self.update_button.setFixedWidth(service_btn_width)
        self.add_network_drive_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.apps_page_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.services_page_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.games_page_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.dev_tools_page_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.browsers_page_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.add_network_drive_button.setFixedWidth(main_button_width)
        self.apps_page_button.setFixedWidth(main_button_width)
        self.services_page_button.setFixedWidth(main_button_width)
        self.games_page_button.setFixedWidth(main_button_width)
        self.dev_tools_page_button.setFixedWidth(main_button_width)
        self.browsers_page_button.setFixedWidth(main_button_width)
        self.advanced_tweak_btn.setFixedWidth(main_button_width)

        # Bottom Button layout
        self.bottom_layout = QVBoxLayout()
        self.bottom_layout.setSpacing(10)
        self.bottom_layout.addWidget(self.apps_page_button)
        self.bottom_layout.addWidget(self.games_page_button)
        self.bottom_layout.addWidget(self.dev_tools_page_button)
        self.bottom_layout.addWidget(self.browsers_page_button)
        self.bottom_layout.addWidget(self.services_page_button)
        self.bottom_layout.addWidget(self.add_network_drive_button)
        self.bottom_layout.addWidget(self.advanced_tweak_btn)

        # Bottom outer layout
        self.outer_bottom_layout = QHBoxLayout()
        self.outer_bottom_layout.addStretch()
        self.outer_bottom_layout.addLayout(self.bottom_layout)
        self.outer_bottom_layout.addStretch()

        # Add to main layout with stretch
        self.layout.addSpacing(16)
        self.layout.addWidget(self.paru_card)
        self.layout.addWidget(self.gpu_card)
        self.layout.addWidget(self.update_card)
        self.layout.addSpacing(16)
        self.layout.addLayout(self.outer_bottom_layout)
        self.layout.addSpacing(16)
        self.layout.addStretch()

        self.start_update_check()

    def update_gpu_status(self):
        if gpu_driver_installed():
            self.gpudrv_status.setPixmap(QPixmap(str(CHECKMARK_ICON_PATH)).scaled(20, 20))
            self.gpudrv_button.setText("Installed")
            self.set_service_button_state(self.gpudrv_button, installed=True)
        else:
            self.gpudrv_status.setPixmap(QPixmap(str(RED_X_ICON_PATH)).scaled(20, 20))
            self.gpudrv_button.setText("Install GPU Drivers")
            self.set_service_button_state(self.gpudrv_button, installed=False)

    def handle_gpu_driver_install(self):
        if gpu_driver_installed():
            QMessageBox.information(self, "Installed", "GPU drivers are already installed.")
            return
        vendor = detect_gpu_vendor()
        if vendor is None:
            QMessageBox.warning(self, "GPU Not Detected", "Could not detect GPU vendor.")
            return
        packages = []
        if vendor == "Intel":
            packages = ["mesa", "lib32-mesa", "vulkan-intel", "lib32-vulkan-intel", "xf86-video-intel"]
        elif vendor == "NVIDIA":
            packages = ["nvidia", "nvidia-utils", "lib32-nvidia-utils"]
        elif vendor == "AMD":
            packages = ["mesa", "lib32-mesa", "vulkan-radeon", "lib32-vulkan-radeon", "xf86-video-amdgpu"]

        if not packages:
            QMessageBox.warning(self, "Unsupported GPU", f"No package rule for vendor: {vendor}")
            return

        try:
            self.run_sudo_command(["pacman", "-S", "--needed", "--noconfirm", *packages])
            QMessageBox.information(self, "Success", f"{vendor} driver packages installed.")
            self.update_gpu_status()
        except RuntimeError as e:
            QMessageBox.critical(self, "Error", f"Failed to install GPU drivers: {e}")

    def update_paru_status(self):
        """Update the Paru status icon or text."""
        if command_exists("paru"):
            self.paru_status.setPixmap(QPixmap(str(CHECKMARK_ICON_PATH)).scaled(20, 20))
            self.install_paru_button.setText("Installed")
            self.set_service_button_state(self.install_paru_button, installed=True)
        else:
            self.paru_status.setPixmap(QPixmap(str(RED_X_ICON_PATH)).scaled(20, 20))
            self.install_paru_button.setText("Install Paru")
            self.set_service_button_state(self.install_paru_button, installed=False)

    def handle_install_paru(self):
        if command_exists("paru"):
            QMessageBox.information(self, "Installed", "Paru is already installed!")
        else:
            if install_paru():
                QMessageBox.information(self, "Success", "Paru installed successfully!")
                self.update_paru_status()
            else:
                QMessageBox.critical(self, "Error", "Failed to install Paru.")

    def add_network_drive(self):
        """Prompt for Samba share details in a single dialog and add to fstab."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Network Drive")
        configure_dialog(dialog, width=680, height=360, min_width=600, min_height=320)
        form_layout = QFormLayout(dialog)

        share_input = QLineEdit(dialog)
        share_input.setPlaceholderText("192.168.1.177/backup")
        mount_input = QLineEdit(dialog)
        mount_input.setPlaceholderText("/media/server")
        username_input = QLineEdit(dialog)
        password_input = QLineEdit(dialog)
        password_input.setEchoMode(QLineEdit.Password)

        form_layout.addRow("Share Path:", share_input)
        form_layout.addRow("Mount Point:", mount_input)
        form_layout.addRow("Username:", username_input)
        form_layout.addRow("Password:", password_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form_layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        share_path = share_input.text().strip()
        mount_point = mount_input.text().strip()
        username = username_input.text().strip()
        password = password_input.text()

        if not share_path or not mount_point or not username or not password:
            QMessageBox.warning(self, "Missing Data", "All fields are required.")
            return

        try:
            if add_samba_drive(share_path, mount_point, username, password):
                QMessageBox.information(self, "Success", "Network drive added successfully!")
            else:
                QMessageBox.critical(self, "Error", "Failed to add network drive.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add network drive: {e}")

    def open_app_installer(self):
        self.app_installer_callback()
        self.close()

    def start_update_check(self):
        if self.update_check_thread and self.update_check_thread.isRunning():
            return

        self.update_status.setText("Checking latest release...")
        self.set_update_indicator("checking")
        self.update_button.setText("Checking...")
        self.update_button.setEnabled(False)
        self.set_service_button_state(self.update_button, installed=False)

        self.update_check_thread = QThread()
        self.update_check_worker = UpdateCheckWorker()
        self.update_check_worker.moveToThread(self.update_check_thread)
        self.update_check_thread.started.connect(self.update_check_worker.run)
        self.update_check_worker.finished.connect(self.on_update_check_finished)
        self.update_check_worker.error.connect(self.on_update_check_error)
        self.update_check_worker.finished.connect(self.update_check_thread.quit)
        self.update_check_worker.finished.connect(self.update_check_worker.deleteLater)
        self.update_check_thread.finished.connect(self.update_check_thread.deleteLater)
        self.update_check_thread.finished.connect(self.cleanup_update_thread)
        self.update_check_thread.start()

    def on_update_check_finished(self, status_text, update_available, _current_version, latest_tag):
        self.latest_tag = latest_tag
        self.update_status.setText(status_text)
        if update_available:
            self.set_update_indicator("available")
            self.update_button.setText("Update Now")
            self.update_button.setEnabled(True)
            self.set_service_button_state(self.update_button, installed=False)
        else:
            self.set_update_indicator("latest")
            self.update_button.setText("Up to Date")
            self.update_button.setEnabled(False)
            self.set_service_button_state(self.update_button, installed=True)

    def on_update_check_error(self, error_message):
        self.update_status.setText(f"Could not check updates: {error_message}")
        self.set_update_indicator("error")
        self.update_button.setText("Retry Check")
        self.update_button.setEnabled(True)
        self.set_service_button_state(self.update_button, installed=False)

    def run_app_update(self):
        if self.update_button.text() == "Retry Check":
            self.start_update_check()
            return

        updater_command = shutil.which("arch-mysetup-update")
        if updater_command:
            command = [updater_command]
        else:
            local_updater = Path(__file__).resolve().parent.parent.joinpath("main", "update.sh")
            if local_updater.exists():
                command = ["bash", str(local_updater)]
            else:
                QMessageBox.warning(self, "Updater Missing", "Updater command not found.")
                return

        try:
            open_terminal(command)
            app = QApplication.instance()
            if app is not None:
                app.quit()
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to start updater: {e}")

    def cleanup_update_thread(self):
        self.update_check_thread = None
        self.update_check_worker = None

    def set_update_indicator(self, state):
        if state == "latest":
            self.update_status_icon.setPixmap(QPixmap(str(CHECKMARK_ICON_PATH)).scaled(18, 18))
            self.update_state_label.setText("Up to Date")
        elif state == "available":
            self.update_status_icon.setPixmap(QPixmap(str(RED_X_ICON_PATH)).scaled(18, 18))
            self.update_state_label.setText("Update Available")
        elif state == "checking":
            self.update_status_icon.clear()
            self.update_state_label.setText("Checking...")
        else:
            self.update_status_icon.setPixmap(QPixmap(str(RED_X_ICON_PATH)).scaled(18, 18))
            self.update_state_label.setText("Check Failed")

    @staticmethod
    def set_service_button_state(button, installed=False):
        button.setProperty("installed", installed)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def closeEvent(self, event):
        if self.update_check_thread and self.update_check_thread.isRunning():
            self.update_check_thread.quit()
            self.update_check_thread.wait(1500)
        super().closeEvent(event)

    def ensure_sudo_authenticated(self):
        return True

    def run_sudo_command(self, command, validate_only=False):
        full_command = ["pkexec", *command]
        result = subprocess.run(
            full_command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            error_text = result.stderr.strip() or "privileged command failed"
            raise RuntimeError(error_text)
        if validate_only:
            return None
        return result
