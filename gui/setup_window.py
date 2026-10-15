import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, QObject, QThread
from PyQt5.QtGui import QPixmap, QColor, QBrush
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QHBoxLayout, QMessageBox, QFrame, \
    QLineEdit, QSizePolicy, QDialog, QFormLayout, QDialogButtonBox, QApplication, QTreeWidget, QTreeWidgetItem, QHeaderView, QGridLayout

programs_dir = str(Path(__file__).resolve().parent.parent.joinpath("programs"))
sys.path.append(programs_dir)

scripts_dir = str(Path(__file__).resolve().parent.parent.joinpath("scripts"))
sys.path.append(scripts_dir)

from scripts.detect_gpu import detect_gpu_vendor
from programs.config import CHECKMARK_ICON_PATH, RED_X_ICON_PATH
from programs.installer_logic import install_paru, add_samba_drive, command_exists, open_terminal, parse_fstab_network_drives, get_mount_size
try:
    from .theme import configure_main_window, configure_dialog
except ImportError:
    from theme import configure_main_window, configure_dialog


def gpu_driver_installed():
    vendor = detect_gpu_vendor()
    mesa_installed = is_mesa_installed()
    if vendor == "AMD":
        return mesa_installed
    if vendor == "Intel":
        return shutil.which("intel-virtual-output") is not None
    if vendor == "NVIDIA":
        return shutil.which("nvidia-modprobe") is not None
    return False

def is_mesa_installed():
    """Check if the Mesa package is installed on the system."""
    if shutil.which("pacman"):
        command = ["pacman", "-Q", "mesa"]
    elif shutil.which("dnf"):
        command = ["dnf", "list", "installed", "mesa"]
    else:
        return False

    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return result.returncode == 0

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
                status_text = f"Latest release: {latest_tag} (local version unknown)"
                update_available = True
            else:
                status_text = f"Update available: {current_version} -> {latest_tag}"
                update_available = True

            self.finished.emit(status_text, update_available, current_version, latest_tag)
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def fetch_latest_release_tag():
        url = "https://api.github.com/repos/aleksireede/arch-mysetup/releases/latest"
        request = urllib.request.Request(url, headers={"User-Agent": "arch-mysetup"})
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        tag_name = payload.get("tag_name")
        if not tag_name:
            raise RuntimeError("Could not resolve latest release tag from GitHub")
        return tag_name

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


def run_sudo_command(command, validate_only=False):
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


def ensure_sudo_authenticated():
    return True


class SetupWindow(QMainWindow):
    open_installer = pyqtSignal()  # Signal to open the installer
    open_uninstaller = pyqtSignal()
    open_advanced_tweaks = pyqtSignal()
    open_apps_page = pyqtSignal()
    open_services_page = pyqtSignal()
    open_updates_page = pyqtSignal()
    open_network_drives_page = pyqtSignal()

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
        self.updates_page_button = None
        self.network_drives_page_button = None
        self.add_network_drive_button = None
        self.network_drives_card = None
        self.network_drives_tree = None
        self.refresh_network_drives_button = None
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

        # Network Drives section: lists existing network drives from fstab
        self.network_drives_card = QFrame()
        self.network_drives_card.setObjectName("serviceCard")
        network_card_layout = QVBoxLayout(self.network_drives_card)
        network_card_layout.setContentsMargins(16, 14, 16, 14)
        network_card_layout.setSpacing(12)

        network_title = QLabel("Network Drives")
        network_title.setObjectName("serviceTitle")

        self.network_drives_tree = QTreeWidget()
        self.network_drives_tree.setHeaderLabels(["Device", "Mount Point", "Type", "Options", "Size"])
        self.network_drives_tree.setMinimumHeight(150)
        self.network_drives_tree.setAlternatingRowColors(True)
        network_header = self.network_drives_tree.header()
        network_header.setStretchLastSection(False)
        # Let "Options" absorb extra width; keep "Size" tight to its content.
        network_header.setSectionResizeMode(3, QHeaderView.Stretch)
        network_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.add_network_drive_button = QPushButton("Add Network Drive (Samba)")
        self.add_network_drive_button.setObjectName("serviceAction")
        self.add_network_drive_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.add_network_drive_button.setFixedWidth(200)
        self.add_network_drive_button.clicked.connect(self.add_network_drive)

        self.refresh_network_drives_button = QPushButton("Refresh")
        self.refresh_network_drives_button.clicked.connect(self.refresh_network_drives)

        network_button_row = QHBoxLayout()
        network_button_row.setSpacing(12)
        network_button_row.addWidget(self.add_network_drive_button)
        network_button_row.addWidget(self.refresh_network_drives_button)
        network_button_row.addStretch()

        network_card_layout.addWidget(network_title)
        network_card_layout.addWidget(self.network_drives_tree)
        network_card_layout.addLayout(network_button_row)

        # Apps page button
        self.apps_page_button = QPushButton("Apps")
        self.apps_page_button.clicked.connect(self.open_apps_page.emit)

        self.services_page_button = QPushButton("Services")
        self.services_page_button.clicked.connect(self.open_services_page.emit)

        self.updates_page_button = QPushButton("Updates")
        self.updates_page_button.clicked.connect(self.open_updates_page.emit)

        self.network_drives_page_button = QPushButton("Network Drives")
        self.network_drives_page_button.clicked.connect(self.open_network_drives_page.emit)

        self.advanced_tweak_btn = QPushButton("Advanced Tweaks")
        self.advanced_tweak_btn.clicked.connect(self.open_advanced_tweaks.emit)

        # Build a compact launcher dashboard for the main page.
        self.install_paru_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.gpudrv_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.update_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        service_btn_width = 180
        self.install_paru_button.setFixedWidth(service_btn_width)
        self.gpudrv_button.setFixedWidth(service_btn_width)
        self.update_button.setFixedWidth(service_btn_width)

        self.layout.setContentsMargins(48, 36, 48, 36)
        self.layout.setSpacing(24)

        hero = QFrame()
        hero.setObjectName("pageHeader")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 22, 28, 22)
        hero_layout.setSpacing(6)
        title = QLabel("Arch MySetup")
        title.setStyleSheet("font-size: 30px; font-weight: 800; color: #ffffff; background: transparent;")
        subtitle = QLabel("Manage applications, system services, updates, and device settings.")
        subtitle.setStyleSheet("font-size: 15px; color: #f5f3ff; background: transparent;")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        self.layout.addWidget(hero)

        navigation_grid = QGridLayout()
        navigation_grid.setHorizontalSpacing(18)
        navigation_grid.setVerticalSpacing(18)
        for column in range(3):
            navigation_grid.setColumnStretch(column, 1)

        destinations = [
            (self.apps_page_button, "Apps", "Install, remove, and organize applications."),
            (self.services_page_button, "Services", "Manage system services and their state."),
            (self.updates_page_button, "Updates", "Update the app, install drivers, and set up Paru."),
            (self.network_drives_page_button, "Network Drives", "Add Samba shares and review mounted drives."),
            (self.advanced_tweak_btn, "Advanced Tweaks", "Configure desktop and system preferences."),
        ]

        def make_navigation_card(button, heading, description):
            card = QFrame()
            card.setObjectName("serviceCard")
            card.setMinimumHeight(160)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 18, 20, 18)
            card_layout.setSpacing(10)

            heading_label = QLabel(heading)
            heading_label.setObjectName("serviceTitle")
            heading_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #eaf2ff;")
            description_label = QLabel(description)
            description_label.setWordWrap(True)
            description_label.setStyleSheet("font-size: 14px; color: #aebdce;")

            button.setText("Open")
            button.setObjectName("serviceAction")
            button.setFixedWidth(104)
            action_row = QHBoxLayout()
            action_row.addStretch()
            action_row.addWidget(button)

            card_layout.addWidget(heading_label)
            card_layout.addWidget(description_label, 1)
            card_layout.addLayout(action_row)
            return card

        for column, destination in enumerate(destinations[:3]):
            navigation_grid.addWidget(make_navigation_card(*destination), 0, column)
        self.layout.addLayout(navigation_grid)

        secondary_navigation = QHBoxLayout()
        secondary_navigation.setSpacing(18)
        secondary_navigation.addStretch(1)
        for destination in destinations[3:]:
            card = make_navigation_card(*destination)
            card.setMaximumWidth(500)
            secondary_navigation.addWidget(card, 1)
        secondary_navigation.addStretch(1)
        self.layout.addLayout(secondary_navigation)
        self.layout.addStretch(1)

        self.refresh_network_drives()
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
            run_sudo_command(["pacman", "-S", "--needed", "--noconfirm", *packages])
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
                self.refresh_network_drives()
            else:
                QMessageBox.critical(self, "Error", "Failed to add network drive.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add network drive: {e}")

    def refresh_network_drives(self):
        """Re-read /etc/fstab and refresh the list of existing network drives.

        For each drive the Size column shows the live usage of its mount point
        (e.g. "12G / 50G (24%)") when the path is currently mounted, or
        "Not mounted" when the mount point is not an active mount point.
        """
        self.network_drives_tree.setUpdatesEnabled(False)
        self.network_drives_tree.clear()
        drives = parse_fstab_network_drives()
        if not drives:
            placeholder = QTreeWidgetItem(["No network drives found in /etc/fstab.", "", "", "", ""])
            placeholder.setToolTip(0, "No CIFS/NFS/SSHFS/WebDAV entries were detected in /etc/fstab")
            self.network_drives_tree.addTopLevelItem(placeholder)
        for drive in drives:
            mount_point = drive["mount_point"]
            mounted, size_text = get_mount_size(mount_point)
            item = QTreeWidgetItem([
                drive["device"],
                mount_point,
                drive["fs_type"],
                drive["options"],
                size_text,
            ])
            item.setToolTip(0, drive["raw"])
            item.setToolTip(3, drive["options"])
            item.setToolTip(4, size_text)
            if mounted:
                item.setForeground(4, QBrush(QColor("#4CAF50")))
            else:
                item.setForeground(4, QBrush(QColor("#EF5350")))
            self.network_drives_tree.addTopLevelItem(item)
        self.network_drives_tree.setUpdatesEnabled(True)
        for col in range(self.network_drives_tree.columnCount()):
            self.network_drives_tree.resizeColumnToContents(col)

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
