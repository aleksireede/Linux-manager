import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, QObject, QThread, Qt
from PyQt5.QtGui import QPixmap, QColor, QBrush
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QHBoxLayout, QMessageBox, QFrame, \
    QLineEdit, QSizePolicy, QDialog, QFormLayout, QDialogButtonBox, QApplication, QTreeWidget, QTreeWidgetItem, QHeaderView, QStackedWidget, QButtonGroup

programs_dir = str(Path(__file__).resolve().parent.parent.joinpath("programs"))
sys.path.append(programs_dir)

scripts_dir = str(Path(__file__).resolve().parent.parent.joinpath("scripts"))
sys.path.append(scripts_dir)

from scripts.detect_gpu import detect_gpu_vendor
from programs.config import icon_checkmark, icon_red_cross, icon_height, icon_width
from programs.installer_logic import install_paru, add_samba_drive, command_exists, open_terminal, parse_fstab_network_drives, get_mount_size, package_manager, set_network_drive_mounted
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
    elif package_manager() in {"dnf", "dnf5"}:
        command = ["rpm", "-q", "mesa-dri-drivers"]
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
        request = urllib.request.Request(url, headers={"User-Agent": "Linux-Manager"})
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


class NetworkDriveActionWorker(QObject):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, mount_point, operation):
        super().__init__()
        self.mount_point = mount_point
        self.operation = operation

    def run(self):
        try:
            set_network_drive_mounted(
                self.mount_point,
                mount=self.operation == "mount",
            )
            self.finished.emit(self.mount_point, self.operation)
        except Exception as error:
            self.error.emit(str(error))


class SetupWindow(QMainWindow):
    open_installer = pyqtSignal()  # Signal to open the installer
    open_uninstaller = pyqtSignal()
    open_advanced_tweaks = pyqtSignal()
    open_apps_page = pyqtSignal()
    open_updates_page = pyqtSignal()
    open_network_drives_page = pyqtSignal()
    open_settings_page = pyqtSignal()

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
        self.settings_page_button = None
        self.updates_page_button = None
        self.network_drives_page_button = None
        self.add_network_drive_button = None
        self.network_drives_card = None
        self.network_drives_tree = None
        self.refresh_network_drives_button = None
        self.mount_network_drive_button = None
        self.unmount_network_drive_button = None
        self.network_drive_thread = None
        self.network_drive_worker = None
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
        self.setWindowTitle("Linux-Manager")
        configure_main_window(self)
        self.init_ui()

    def init_ui(self):
        self.main_window = QWidget()
        self.setCentralWidget(self.main_window)
        self.layout = QVBoxLayout(self.main_window)  # Set layout directly on central widget
        self.layout.setContentsMargins(32, 24, 32, 24)
        self.layout.setSpacing(16)

        self.page_menu = QHBoxLayout()
        self.page_menu.setSpacing(8)
        self.page_header = QFrame()
        self.page_header.setObjectName("pageHeader")
        page_header_layout = QVBoxLayout(self.page_header)
        page_header_layout.setContentsMargins(10, 10, 10, 10)
        self.page_title = QLabel("Apps")
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_title.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #f1f1f1; background: transparent;"
        )
        page_header_layout.addWidget(self.page_title)
        self.layout.addWidget(self.page_header)
        self.layout.addLayout(self.page_menu)
        self.page_menu_buttons = QButtonGroup(self)
        self.page_menu_buttons.setExclusive(True)
        self.page_stack = QStackedWidget()
        self.layout.addWidget(self.page_stack, 1)
        self.page_widgets = {}

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
        # This card is displayed on the Updates page. Keep it hidden while it
        # has no parent; showing a parentless QWidget makes it a separate
        # top-level window at startup.

        # Update section
        self.update_card = QFrame()
        self.update_card.setObjectName("serviceCard")
        self.update_layout = QHBoxLayout(self.update_card)
        self.update_layout.setContentsMargins(16, 14, 16, 14)
        self.update_layout.setSpacing(12)
        update_title = QLabel("App Update")
        update_title.setObjectName("serviceTitle")
        self.update_status = QLabel("Checking latest release...")
        self.update_status.setWordWrap(True)
        self.update_status.setMinimumWidth(0)
        self.update_status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
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
        self.network_drives_tree.setMinimumWidth(0)
        self.network_drives_tree.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.network_drives_tree.setHeaderLabels(["Device", "Mount Point", "Type", "Options", "Size"])
        self.network_drives_tree.setMinimumHeight(150)
        self.network_drives_tree.setAlternatingRowColors(True)
        network_header = self.network_drives_tree.header()
        network_header.setStretchLastSection(False)
        # Give fixed, predictable widths to the short columns and let Options
        # use the remaining space so long mount data cannot widen the page.
        network_header.setSectionResizeMode(0, QHeaderView.Interactive)
        network_header.setSectionResizeMode(1, QHeaderView.Interactive)
        network_header.setSectionResizeMode(2, QHeaderView.Interactive)
        network_header.setSectionResizeMode(3, QHeaderView.Stretch)
        network_header.setSectionResizeMode(4, QHeaderView.Interactive)
        self.network_drives_tree.setColumnWidth(0, 220)
        self.network_drives_tree.setColumnWidth(1, 180)
        self.network_drives_tree.setColumnWidth(2, 80)
        self.network_drives_tree.setColumnWidth(4, 150)
        self.network_drives_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.network_drives_tree.setTextElideMode(Qt.ElideRight)

        self.add_network_drive_button = QPushButton("Add Network Drive (Samba)")
        self.add_network_drive_button.setObjectName("serviceAction")
        self.add_network_drive_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.add_network_drive_button.setFixedWidth(200)
        self.add_network_drive_button.clicked.connect(self.add_network_drive)

        self.refresh_network_drives_button = QPushButton("Refresh")
        self.refresh_network_drives_button.clicked.connect(self.refresh_network_drives)

        self.mount_network_drive_button = QPushButton("Mount Selected")
        self.mount_network_drive_button.setEnabled(False)
        self.mount_network_drive_button.clicked.connect(self.mount_selected_network_drive)
        self.unmount_network_drive_button = QPushButton("Unmount Selected")
        self.unmount_network_drive_button.setEnabled(False)
        self.unmount_network_drive_button.clicked.connect(self.unmount_selected_network_drive)
        self.network_drives_tree.currentItemChanged.connect(self.update_network_drive_actions)

        network_button_row = QHBoxLayout()
        network_button_row.setSpacing(12)
        network_button_row.addWidget(self.add_network_drive_button)
        network_button_row.addWidget(self.mount_network_drive_button)
        network_button_row.addWidget(self.unmount_network_drive_button)
        network_button_row.addWidget(self.refresh_network_drives_button)
        network_button_row.addStretch()

        network_card_layout.addWidget(network_title)
        network_card_layout.addWidget(self.network_drives_tree)
        network_card_layout.addLayout(network_button_row)

        # Apps page button
        self.apps_page_button = QPushButton("Apps")
        self.apps_page_button.clicked.connect(self.open_apps_page.emit)

        self.settings_page_button = QPushButton("Settings")
        self.settings_page_button.clicked.connect(self.open_settings_page.emit)

        self.updates_page_button = QPushButton("Updates")
        self.updates_page_button.clicked.connect(self.open_updates_page.emit)

        self.network_drives_page_button = QPushButton("Network Drives")
        self.network_drives_page_button.clicked.connect(self.open_network_drives_page.emit)

        self.advanced_tweak_btn = QPushButton("Advanced Tweaks")
        self.advanced_tweak_btn.clicked.connect(self.open_advanced_tweaks.emit)

        # Keep service actions sized consistently on their section pages.
        self.install_paru_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.gpudrv_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.update_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        service_btn_width = 180
        self.install_paru_button.setFixedWidth(service_btn_width)
        self.gpudrv_button.setFixedWidth(service_btn_width)
        self.update_button.setFixedWidth(service_btn_width)

        for button in (self.apps_page_button, self.network_drives_page_button,
                       self.advanced_tweak_btn, self.updates_page_button, self.settings_page_button):
            button.setObjectName("pageMenuButton")
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.setCheckable(True)
            self.page_menu_buttons.addButton(button)
            self.page_menu.addWidget(button)

        self.refresh_network_drives()
        self.start_update_check()

    def add_page(self, button, page):
        self.page_widgets[button] = page
        self.page_stack.addWidget(page)
        button.clicked.disconnect()
        button.clicked.connect(lambda: self.show_page(button))

    def show_page(self, button):
        page = self.page_widgets.get(button)
        if page is not None:
            self.page_stack.setCurrentWidget(page)
            self.page_title.setText(button.text())
            button.setChecked(True)

    def update_gpu_status(self):
        if gpu_driver_installed():
            self.gpudrv_status.setPixmap(QPixmap(str(icon_checkmark)).scaled(icon_height, icon_width))
            self.gpudrv_button.setText("Installed")
            self.set_service_button_state(self.gpudrv_button, installed=True)
        else:
            self.gpudrv_status.setPixmap(QPixmap(str(icon_red_cross)).scaled(icon_height, icon_width))
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
            if package_manager() in {"dnf", "dnf5"}:
                fedora_packages = {
                    "mesa": "mesa-dri-drivers", "lib32-mesa": "mesa-dri-drivers.i686",
                    "vulkan-intel": "mesa-vulkan-drivers", "lib32-vulkan-intel": "mesa-vulkan-drivers.i686",
                    "vulkan-radeon": "mesa-vulkan-drivers", "lib32-vulkan-radeon": "mesa-vulkan-drivers.i686",
                    "nvidia": "akmod-nvidia", "nvidia-utils": "xorg-x11-drv-nvidia-cuda",
                    "lib32-nvidia-utils": "xorg-x11-drv-nvidia-libs.i686",
                    "xf86-video-intel": "xorg-x11-drv-intel", "xf86-video-amdgpu": "xorg-x11-drv-amdgpu",
                }
                packages = list(dict.fromkeys(fedora_packages.get(package, package) for package in packages))
                run_sudo_command([package_manager(), "install", "-y", *packages])
            else:
                run_sudo_command(["pacman", "-S", "--needed", "--noconfirm", *packages])
            QMessageBox.information(self, "Success", f"{vendor} driver packages installed.")
            self.update_gpu_status()
        except RuntimeError as e:
            QMessageBox.critical(self, "Error", f"Failed to install GPU drivers: {e}")

    def update_paru_status(self):
        """Update the Paru status icon or text."""
        if command_exists("paru"):
            self.paru_status.setPixmap(QPixmap(str(icon_checkmark)).scaled(20, 20))
            self.install_paru_button.setText("Installed")
            self.set_service_button_state(self.install_paru_button, installed=True)
        else:
            self.paru_status.setPixmap(QPixmap(str(icon_red_cross)).scaled(20, 20))
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
        """todo: add more network drive types"""
        """Prompt for Samba share details in a single dialog and add to fstab."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Network Drive")
        dialog.setFixedSize(680,320)
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
            item.setData(1, Qt.UserRole, mounted)
            if mounted:
                item.setForeground(4, QBrush(QColor("#89d185")))
            else:
                item.setForeground(4, QBrush(QColor("#f48771")))
            self.network_drives_tree.addTopLevelItem(item)
        self.network_drives_tree.setUpdatesEnabled(True)
        self.update_network_drive_actions(self.network_drives_tree.currentItem(), None)

    def update_network_drive_actions(self, current, _previous):
        has_drive = current is not None and current.data(1, Qt.UserRole) is not None
        mounted = bool(current.data(1, Qt.UserRole)) if has_drive else False
        busy = self.network_drive_thread is not None and self.network_drive_thread.isRunning()
        self.mount_network_drive_button.setEnabled(has_drive and not mounted and not busy)
        self.unmount_network_drive_button.setEnabled(has_drive and mounted and not busy)

    def mount_selected_network_drive(self):
        self.run_network_drive_action("mount")

    def unmount_selected_network_drive(self):
        self.run_network_drive_action("unmount")

    def run_network_drive_action(self, operation):
        item = self.network_drives_tree.currentItem()
        if item is None or item.data(1, Qt.UserRole) is None:
            QMessageBox.warning(self, "Select a Drive", "Select a configured network drive first.")
            return
        if self.network_drive_thread and self.network_drive_thread.isRunning():
            return

        mount_point = item.text(1)
        self.mount_network_drive_button.setEnabled(False)
        self.unmount_network_drive_button.setEnabled(False)
        self.network_drive_thread = QThread(self)
        self.network_drive_worker = NetworkDriveActionWorker(mount_point, operation)
        self.network_drive_worker.moveToThread(self.network_drive_thread)
        self.network_drive_thread.started.connect(self.network_drive_worker.run)
        self.network_drive_worker.finished.connect(self.on_network_drive_action_finished)
        self.network_drive_worker.error.connect(self.on_network_drive_action_error)
        self.network_drive_worker.finished.connect(self.network_drive_thread.quit)
        self.network_drive_worker.error.connect(self.network_drive_thread.quit)
        self.network_drive_worker.finished.connect(self.network_drive_worker.deleteLater)
        self.network_drive_worker.error.connect(self.network_drive_worker.deleteLater)
        self.network_drive_thread.finished.connect(self.network_drive_thread.deleteLater)
        self.network_drive_thread.finished.connect(self.cleanup_network_drive_action)
        self.network_drive_thread.start()

    def on_network_drive_action_finished(self, mount_point, operation):
        self.refresh_network_drives()
        action = "mounted" if operation == "mount" else "unmounted"
        QMessageBox.information(self, "Network Drive", f"{mount_point} was {action}.")

    def on_network_drive_action_error(self, message):
        self.refresh_network_drives()
        QMessageBox.critical(self, "Network Drive Error", message)

    def cleanup_network_drive_action(self):
        self.network_drive_thread = None
        self.network_drive_worker = None
        self.update_network_drive_actions(self.network_drives_tree.currentItem(), None)

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

        updater_command = shutil.which("linux-manager-update") or shutil.which("arch-mysetup-update")
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
            self.update_status_icon.setPixmap(QPixmap(str(icon_checkmark)).scaled(18, 18))
            self.update_state_label.setText("Up to Date")
        elif state == "available":
            self.update_status_icon.setPixmap(QPixmap(str(icon_red_cross)).scaled(18, 18))
            self.update_state_label.setText("Update Available")
        elif state == "checking":
            self.update_status_icon.clear()
            self.update_state_label.setText("Checking...")
        else:
            self.update_status_icon.setPixmap(QPixmap(str(icon_red_cross)).scaled(18, 18))
            self.update_state_label.setText("Check Failed")

    @staticmethod
    def set_service_button_state(button, installed=False):
        button.setProperty("installed", installed)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()
