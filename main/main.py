#!/usr/bin/env python
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

# Ensure project root is importable when this file is run directly.
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from programs.apps_file import load_yaml
from gui.app_uninstaller import AppUninstaller
from gui.app_installer_window import ArchAppInstaller
from gui.apps_page import AppsPage
from gui.setup_window import SetupWindow
from gui.advanced_tweaks import AdvancedTweaks
from gui.setup_updates_page import SetupUpdatesPage
from gui.network_drives_page import NetworkDrivesPage
from gui.app_settings_page import AppSettingsPage

app = QApplication(sys.argv)

# Create the setup window first
setup_window = SetupWindow()
load_yaml()

# References to auxiliary windows and embedded pages
app_installer_window = None
app_uninstaller_window = None
advanced_tweaks_window = None
apps_page_window = None
updates_page_window = None
network_drives_page_window = None
settings_page_window = None


def open_app_installer():
    global app_installer_window
    if app_installer_window is None:
        app_installer_window = ArchAppInstaller(setup_window)
    setup_window.show_page(setup_window.apps_page_button)
    app_installer_window.show()
    setup_window.hide()


def open_app_uninstaller():
    global app_uninstaller_window
    if app_uninstaller_window is None:
        app_uninstaller_window = AppUninstaller(setup_window)
    setup_window.show_page(setup_window.apps_page_button)
    app_uninstaller_window.show()
    setup_window.hide()


def main():
    global apps_page_window, updates_page_window, network_drives_page_window, advanced_tweaks_window, settings_page_window
    apps_page_window = AppsPage(setup_window)
    updates_page_window = SetupUpdatesPage(setup_window)
    network_drives_page_window = NetworkDrivesPage(setup_window)
    advanced_tweaks_window = AdvancedTweaks(setup_window)
    settings_page_window = AppSettingsPage(setup_window)
    setup_window.add_page(setup_window.apps_page_button, apps_page_window)
    setup_window.add_page(setup_window.updates_page_button, updates_page_window)
    setup_window.add_page(setup_window.network_drives_page_button, network_drives_page_window)
    setup_window.add_page(setup_window.advanced_tweak_btn, advanced_tweaks_window)
    setup_window.add_page(setup_window.settings_page_button, settings_page_window)
    setup_window.show_page(setup_window.apps_page_button)

    # Keep install and uninstall actions connected to their auxiliary windows.
    setup_window.open_installer.connect(open_app_installer)
    setup_window.open_uninstaller.connect(open_app_uninstaller)
    setup_window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
