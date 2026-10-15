import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QListWidget, QListWidgetItem, \
    QMessageBox, QInputDialog

parent_dir = str(Path(__file__).resolve().parent.parent.joinpath("programs"))
sys.path.append(parent_dir)

from programs.installer_logic import (list_all_installed_apps, remove_apps)
from programs.apps_file import load_yaml, remove_app_from_yaml

try:
    from .category_list import add_category_header
    from .ui_helpers import create_back_button, create_select_refresh_row
    from .theme import configure_main_window, create_page_header
except ImportError:
    from category_list import add_category_header
    from ui_helpers import create_back_button, create_select_refresh_row
    from theme import configure_main_window, create_page_header


class AppListWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.finished.emit(list_all_installed_apps())
        except Exception as e:
            self.error.emit(str(e))


class RemoveOperationWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, apps):
        super().__init__()
        self.apps = apps

    def run(self):
        try:
            process = remove_apps(self.apps, "pacman")
            if not process:
                raise RuntimeError("Could not start the uninstall command.")
            if hasattr(process, "wait") and process.wait() != 0:
                raise RuntimeError("The uninstall command did not complete successfully.")
            self.finished.emit(self.apps)
        except Exception as e:
            self.error.emit(str(e))


class AppUninstaller(QMainWindow):
    def __init__(self, setup_window):
        super().__init__()
        self.thread = None
        self.worker = None
        self.action_thread = None
        self.action_worker = None
        # Buttons
        self.back_lbl = None
        self.back_btn = None
        self.frame_layout = None
        self.back_button_container = None
        self.install_button = None
        self.select_all_button = None
        self.search_button = None
        self.back_button = None
        self.refresh_button = None
        # layouts
        self.list_widget = None
        self.bottom_layout = None
        self.third_layout = None
        self.app_layout = None
        self.secondary_layout = None
        self.main_layout = None
        self.main_window_frame = None
        # Main window for back button reference
        self.previous_window = setup_window  # Store the reference
        # Window title text
        self.setWindowTitle("Arch App Uninstaller")
        configure_main_window(self)
        # app list
        self.apps = []
        self.selected_apps = []
        self.collapsed_categories = set()
        self.search_icon_path = Path(__file__).resolve().parent.parent.joinpath("icons", "search.svg")
        self.init_ui()

    def init_ui(self):
        self.main_window_frame = QWidget()
        self.setCentralWidget(self.main_window_frame)
        self.main_layout = QVBoxLayout()
        self.secondary_layout = QHBoxLayout()
        self.app_layout = QHBoxLayout()
        self.third_layout = QHBoxLayout()
        self.bottom_layout = QHBoxLayout()

        # List widget to display Apps
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)

        # Add Apps to the list
        self.refresh_app_list_async()

        self.back_button_container, self.back_btn, self.back_lbl, self.frame_layout = create_back_button(
            self.go_back_to_setup
        )
        header_widget = create_page_header(self.back_button_container, "Uninstall")

        self.install_button = QPushButton("Remove Selected")
        self.install_button.clicked.connect(self.remove_selected)
        self.install_button.setFixedWidth(200)

        # select and refresh layout
        self.third_layout, self.select_all_button, self.refresh_button = create_select_refresh_row(
            self.toggle_select_all_apps, self.refresh_app_list_async
        )
        self.search_button = QPushButton("Search")
        self.search_button.setIcon(QIcon(str(self.search_icon_path)))
        self.search_button.clicked.connect(self.search_app)
        self.third_layout.insertWidget(1, self.search_button)

        # bottom layout
        self.bottom_layout.addWidget(self.install_button)

        # add the layouts to the main one
        self.main_layout.addWidget(header_widget)
        self.main_layout.addSpacing(20)
        self.main_layout.addLayout(self.app_layout)
        self.main_layout.addLayout(self.third_layout)
        self.main_layout.addWidget(self.list_widget)
        self.main_layout.addSpacing(20)
        self.main_layout.addLayout(self.bottom_layout)

        self.main_window_frame.setLayout(self.main_layout)

    def refresh_app_list(self):
        """Render current installed apps in the list widget."""
        self.selected_apps = [
            self.list_widget.item(i).text() for i in range(self.list_widget.count())
            if self.list_widget.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable
            and self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        ] or self.selected_apps
        self.list_widget.clear()
        app_categories = {
            entry.get("name"): str(entry.get("category") or "Universal").strip() or "Universal"
            for entry in load_yaml() if entry.get("name")
        }
        grouped_apps = {}
        for app in self.apps:
            grouped_apps.setdefault(app_categories.get(app, "Universal"), []).append(app)

        if not grouped_apps:
            item = QListWidgetItem("No apps to remove.!")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable &
                          ~Qt.ItemFlag.ItemIsUserCheckable)
            self.list_widget.addItem(item)
            return

        for category in sorted(grouped_apps, key=str.casefold):
            add_category_header(
                self.list_widget, category, category in self.collapsed_categories,
                self.toggle_category_visibility, self.toggle_category
            )
            for app in sorted(grouped_apps[category], key=str.casefold):
                item = QListWidgetItem(app)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if app in self.selected_apps else Qt.CheckState.Unchecked
                )
                item.setHidden(category in self.collapsed_categories)
                self.list_widget.addItem(item)

    def toggle_category_visibility(self, category):
        if category in self.collapsed_categories:
            self.collapsed_categories.remove(category)
        else:
            self.collapsed_categories.add(category)
        self.refresh_app_list()

    def toggle_category(self, category):
        app_categories = {
            entry.get("name"): str(entry.get("category") or "Universal").strip() or "Universal"
            for entry in load_yaml() if entry.get("name")
        }
        items = [self.list_widget.item(i) for i in range(self.list_widget.count())
                 if self.list_widget.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable
                 and app_categories.get(self.list_widget.item(i).text(), "Universal") == category]
        check = not items or not all(item.checkState() == Qt.CheckState.Checked for item in items)
        for item in items:
            item.setCheckState(Qt.CheckState.Checked if check else Qt.CheckState.Unchecked)

    def refresh_app_list_async(self):
        if self.thread and self.thread.isRunning():
            return

        self.list_widget.clear()
        loading_item = QListWidgetItem("Refreshing installed app list...")
        loading_item.setFlags(loading_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.list_widget.addItem(loading_item)

        self.thread = QThread()
        self.worker = AppListWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)

        self.worker.finished.connect(self.on_apps_loaded)
        self.worker.error.connect(self.on_refresh_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.cleanup_thread)

        self.thread.start()

    def on_apps_loaded(self, apps):
        self.apps = apps
        self.refresh_app_list()

    def on_refresh_error(self, error_message):
        QMessageBox.critical(self, "Error", f"Failed to refresh app list: {error_message}")
        self.apps = []
        self.refresh_app_list()

    def cleanup_thread(self):
        self.thread = None
        self.worker = None

    def toggle_select_all_apps(self):
        """Toggle between selecting and deselecting all apps."""
        all_selected = all(
            self.list_widget.item(i).checkState() == Qt.CheckState.Checked
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable
        )
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(
                    Qt.CheckState.Unchecked if all_selected else Qt.CheckState.Checked)

    def remove_selected(self):
        selected_apps = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_apps.append(item.text())

        if selected_apps:
            confirm = QMessageBox.question(
                self, "Confirm Remove",
                f"Do you want to remove the following apps?\n{', '.join(selected_apps)}",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.start_remove_operation(selected_apps)
                return
        else:
            QMessageBox.warning(self, "No Selection",
                                "No apps selected for installation.")
        self.refresh_app_list_async()

    def go_back_to_setup(self):
        self.previous_window.show()  # Show the setup window
        self.hide()  # Hide the current window

    def closeEvent(self, event):
        if self.action_thread and self.action_thread.isRunning():
            self.action_thread.quit()
            self.action_thread.wait(3000)
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(3000)
        event.accept()

    def start_remove_operation(self, selected_apps):
        if self.action_thread and self.action_thread.isRunning():
            return

        self.install_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.select_all_button.setEnabled(False)
        self.search_button.setEnabled(False)

        self.action_thread = QThread()
        self.action_worker = RemoveOperationWorker(selected_apps)
        self.action_worker.moveToThread(self.action_thread)
        self.action_thread.started.connect(self.action_worker.run)
        self.action_worker.finished.connect(self.on_remove_operation_finished)
        self.action_worker.error.connect(self.on_remove_operation_error)
        self.action_worker.finished.connect(self.action_thread.quit)
        self.action_worker.finished.connect(self.action_worker.deleteLater)
        self.action_thread.finished.connect(self.action_thread.deleteLater)
        self.action_thread.finished.connect(self.cleanup_action_thread)
        self.action_thread.start()

    def on_remove_operation_finished(self, removed_apps):
        self.install_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.select_all_button.setEnabled(True)
        self.search_button.setEnabled(True)
        for app in removed_apps:
            remove_app_from_yaml(app)
        self.refresh_app_list_async()

    def on_remove_operation_error(self, error_message):
        self.install_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.select_all_button.setEnabled(True)
        self.search_button.setEnabled(True)
        QMessageBox.critical(self, "Remove Error", f"Removal failed: {error_message}")
        self.refresh_app_list_async()

    def cleanup_action_thread(self):
        self.action_thread = None
        self.action_worker = None

    def search_app(self):
        search_text, ok = QInputDialog.getText(
            self, "Search Application", "Enter app name to search:"
        )
        if not ok:
            return

        query = search_text.strip()
        if not query:
            QMessageBox.information(self, "Search", "Please enter an application name.")
            return

        lower_query = query.lower()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                continue
            if lower_query in item.text().lower():
                self.list_widget.setCurrentRow(index)
                self.list_widget.scrollToItem(item)
                return

        QMessageBox.information(self, "Not Found", f"No application found for '{query}'.")
