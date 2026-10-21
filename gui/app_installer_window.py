import subprocess

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QLabel, QProgressBar,
)

from programs.apps_file import load_apps_from_file, load_yaml
from programs.app_settings import package_conflict_policy
from programs.installer_logic import (
    is_app_installed, app_install, detect_install_method,
    get_install_method_from_source, is_fedora, fedora_app_name,
    fedora_catalog_app_name, fedora_install_type,
    list_apps, package_manager, fedora_packages_available,
    _fedora_repository_ready,
)

try:
    from .category_list import add_category_header
    from .ui_helpers import create_back_button, create_select_refresh_row
    from .theme import configure_main_window, create_page_header
except ImportError:
    from category_list import add_category_header
    from ui_helpers import create_back_button, create_select_refresh_row
    from theme import configure_main_window, create_page_header


class AppManagerWorker(QObject):
    finished = pyqtSignal(list, list, list, bool)  # all, installable, unavailable, checked
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    check_progress = pyqtSignal(int, int)

    def __init__(self, check_fedora_packages=False):
        super().__init__()
        self.check_fedora_packages = check_fedora_packages

    def run(self):
        try:
            # 1. Get the full list from the file
            all_apps = list(dict.fromkeys(load_apps_from_file()))
            if is_fedora() and package_manager() in {"dnf", "dnf5"}:
                # Fedora's installer should only show apps with a Fedora
                # package mapping or a dedicated Fedora install method.
                all_apps = [
                    app for app in all_apps
                    if fedora_app_name(app) or fedora_install_type(app)
                ]
            total = len(all_apps)
            self.progress.emit(f"Checking installed apps (0/{total})")
            self.check_progress.emit(0, total)
            # 2. Filter for what's actually missing
            if is_fedora() and package_manager() in {"dnf", "dnf5"}:
                _fedora_repository_ready.cache_clear()
                installed = set(list_apps("pacman"))
                candidates = []
                for index, app in enumerate(all_apps, 1):
                    if app not in installed and not is_app_installed(app):
                        candidates.append(app)
                    self.check_progress.emit(index, total)
                    self.progress.emit(f"Checking installed apps ({index}/{total})")
                if self.check_fedora_packages:
                    self.progress.emit(f"Checking apps 0/{len(candidates)}")
                    available = fedora_packages_available(candidates)
                    self.progress.emit(f"Checking apps {len(candidates)}/{len(candidates)}")
                    uninstalled = [app for app in candidates if app in available]
                    unavailable = [app for app in candidates if app not in available]
                else:
                    uninstalled = [app for app in candidates if fedora_app_name(app) or fedora_install_type(app)]
                    unavailable = []
                checked = self.check_fedora_packages
            else:
                uninstalled = []
                for index, app in enumerate(all_apps, 1):
                    if not is_app_installed(app) and detect_install_method(app) is not None:
                        uninstalled.append(app)
                    self.check_progress.emit(index, total)
                    self.progress.emit(f"Checking installed apps ({index}/{total})")
                unavailable = []
                checked = True
            # 3. Return both so the UI knows the full list AND the display list
            self.finished.emit(all_apps, uninstalled, unavailable, checked)
        except Exception as e:
            self.error.emit(str(e))


class InstallOperationWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    unavailable = pyqtSignal(list)
    nothing_available = pyqtSignal()
    summary_ready = pyqtSignal(dict)

    def __init__(self, operations, check_fedora_packages=False):
        super().__init__()
        self.operations = operations
        self.check_fedora_packages = check_fedora_packages
        self.unavailable_apps = []
        self.attempted_apps = []
        self.initial_rpm_packages = set()

    @staticmethod
    def installed_rpm_packages():
        try:
            result = subprocess.run(
                ["rpm", "-qa", "--qf", "%{NAME}\\n"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=20,
                check=True,
            )
            return {line.strip() for line in result.stdout.splitlines() if line.strip()}
        except (subprocess.SubprocessError, OSError):
            return set()

    def emit_fedora_summary(self):
        if not self.check_fedora_packages:
            return
        final_rpm_packages = self.installed_rpm_packages()
        skipped_apps = [app for app in self.attempted_apps if not is_app_installed(app)]
        replaced_packages = []
        if package_conflict_policy() == "replace" and self.initial_rpm_packages and final_rpm_packages:
            replaced_packages = sorted(self.initial_rpm_packages - final_rpm_packages, key=str.casefold)
        self.summary_ready.emit({
            "unavailable": list(dict.fromkeys(self.unavailable_apps)),
            "skipped": list(dict.fromkeys(skipped_apps)),
            "replaced": [fedora_catalog_app_name(name) for name in replaced_packages],
            "policy": package_conflict_policy(),
        })

    def run(self):
        try:
            if self.check_fedora_packages:
                self.initial_rpm_packages = self.installed_rpm_packages()
                _fedora_repository_ready.cache_clear()
                apps_to_check = list(dict.fromkeys(
                    app for apps, _method in self.operations for app in apps
                ))
                self.progress.emit(f"Checking apps 0/{len(apps_to_check)}")
                available_apps = fedora_packages_available(apps_to_check)
                self.progress.emit(f"Checking apps {len(apps_to_check)}/{len(apps_to_check)}")
                available_operations = []
                unavailable = [app for app in apps_to_check if app not in available_apps]
                self.unavailable_apps = unavailable
                for apps, method in self.operations:
                    available = [app for app in apps if app in available_apps]
                    if available:
                        available_operations.append((available, method))
                if unavailable:
                    self.unavailable.emit(unavailable)
                self.operations = available_operations
                if not self.operations:
                    self.emit_fedora_summary()
                    self.nothing_available.emit()
                    return

            for index, (apps, method) in enumerate(self.operations, 1):
                self.attempted_apps.extend(apps)
                self.progress.emit(f"Starting package operation {index}/{len(self.operations)}")
                process = app_install(apps, method)
                if not process:
                    raise RuntimeError("Could not start the package installer. Check that pkexec or a supported terminal is available.")
                output_tail = []
                if hasattr(process, "stdout") and process.stdout is not None:
                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            output_tail.append(line)
                            output_tail = output_tail[-12:]
                            self.progress.emit(line[-180:])
                return_code = process.wait() if hasattr(process, "wait") else 0
                if return_code:
                    if return_code in {126, 127}:
                        reason = "The authorization prompt was cancelled or permission was denied."
                    else:
                        reason = f"Package operation exited with status {return_code}."
                    if output_tail:
                        reason += "\n\n" + "\n".join(output_tail)
                    raise RuntimeError(reason)
            self.emit_fedora_summary()
            self.finished.emit()
        except Exception as e:
            self.emit_fedora_summary()
            self.error.emit(str(e))


class ArchAppInstaller(QMainWindow):
    def __init__(self, setup_window):
        super().__init__()
        self.back_btn = None
        self.frame_layout = None
        self.back_button_container = None
        self.back_lbl = None
        self.thread = None
        self.worker = None
        self.action_thread = None
        self.action_worker = None
        self.refresh_button = None
        self.install_button = None
        self.select_all_button = None
        self.back_button = None
        self.list_widget = None
        self.loading_label = None
        self.check_progress_bar = None
        self.bottom_layout = None
        self.third_layout = None
        self.secondary_layout = None
        self.main_layout = None
        self.central_widget = None
        self.loading_timer = None
        self.loading_base_text = ""
        self.loading_dot_count = 0
        self.setup_window = setup_window
        self.setWindowTitle("Arch App Installer")
        configure_main_window(self)
        self.apps = []
        self.uninstalled_apps = []
        self.unavailable_apps = []
        self.fedora_packages_checked = package_manager() not in {"dnf", "dnf5"}
        self.selected_apps = []
        self.last_install_summary = None
        self.collapsed_categories = set()
        self.init_ui()
        self.load_apps_async()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.secondary_layout = QHBoxLayout()
        self.third_layout = QHBoxLayout()
        self.bottom_layout = QHBoxLayout()

        # Loading label
        self.loading_label = QLabel("Loading apps...")
        self.loading_label.setObjectName("syncStatusLabel")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.check_progress_bar = QProgressBar()
        self.check_progress_bar.setFormat("%v/%m apps checked")
        self.check_progress_bar.setTextVisible(True)
        self.check_progress_bar.hide()

        # List widget to display Apps
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)

        # Add Apps to the list
        self.refresh_app_list()

        self.back_button_container, self.back_btn, self.back_lbl, self.frame_layout = create_back_button(
            self.go_back_to_setup
        )
        header_widget = create_page_header(self.back_button_container, "Install")

        self.install_button = QPushButton("Install Selected")
        self.install_button.clicked.connect(self.install_selected)
        self.install_button.setFixedWidth(200)
        self.install_button.setEnabled(
            self.fedora_packages_checked or package_manager() in {"dnf", "dnf5"}
        )

        self.third_layout, self.select_all_button, self.refresh_button = create_select_refresh_row(
            self.toggle_select_all_apps, lambda: self.load_apps_async()
        )
        self.bottom_layout.addWidget(self.install_button)

        # Add loading label and list widget
        self.main_layout.addWidget(header_widget)
        self.main_layout.addSpacing(10)
        self.main_layout.addLayout(self.third_layout)
        self.main_layout.addSpacing(20)
        self.main_layout.addWidget(self.loading_label)
        self.main_layout.addWidget(self.check_progress_bar)
        self.main_layout.addWidget(self.list_widget)
        self.main_layout.addSpacing(20)
        self.main_layout.addLayout(self.bottom_layout)

        self.central_widget.setLayout(self.main_layout)

    def load_apps_async(self, check_fedora_packages=False):
        if self.thread and self.thread.isRunning():
            return

        if package_manager() in {"dnf", "dnf5"}:
            self.install_button.setEnabled(False)
        self.loading_label.show()
        self.check_progress_bar.setRange(0, 0)
        self.check_progress_bar.setFormat("Preparing app check...")
        self.check_progress_bar.show()
        self.refresh_button.setEnabled(False)
        self.select_all_button.setEnabled(False)
        loading_text = (
            "Checking Fedora packages individually"
            if check_fedora_packages and package_manager() in {"dnf", "dnf5"}
            else "Syncing app list"
        )
        self.start_loading_animation(loading_text)

        self.thread = QThread()
        self.worker = AppManagerWorker(check_fedora_packages)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        # Connect to the final UI updater
        self.worker.finished.connect(self.update_ui_with_apps)
        self.worker.error.connect(self.on_error)
        self.worker.progress.connect(self.update_progress)
        self.worker.check_progress.connect(self.update_check_progress)

        # Standard Cleanup
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.cleanup_thread)

        self.thread.start()

    def cleanup_thread(self):
        self.thread = None
        self.worker = None

    def on_error(self, error_message):
        QMessageBox.critical(
            self, "Error", f"Failed to load apps: {error_message}")
        self.stop_loading_animation()
        self.loading_label.hide()
        self.check_progress_bar.hide()
        self.refresh_button.setEnabled(True)
        self.select_all_button.setEnabled(True)
        self.install_button.setEnabled(
            self.fedora_packages_checked or package_manager() in {"dnf", "dnf5"}
        )

    def update_progress(self, message):
        self.loading_base_text = message
        self.loading_dot_count = 0
        self.loading_label.setText(f"{message}.")

    def update_check_progress(self, checked, total):
        self.check_progress_bar.setRange(0, max(total, 1))
        self.check_progress_bar.setValue(checked)
        self.check_progress_bar.setFormat(f"{checked}/{total} apps checked")

    def refresh_app_list(self):
        """Only handles UI state before/during the check"""
        self.list_widget.clear()
        loading_item = QListWidgetItem("Checking system for installed apps...")
        loading_item.setFlags(loading_item.flags() & ~
        Qt.ItemFlag.ItemIsSelectable)
        self.list_widget.addItem(loading_item)
        # Don't start a thread here; let load_apps_async handle it.

    def closeEvent(self, event):
        self.stop_loading_animation()
        if self.action_thread and self.action_thread.isRunning():
            self.action_thread.quit()
            self.action_thread.wait(3000)
        if self.thread and self.thread.isRunning():
            # 1. Ask the thread to stop
            self.thread.quit()
            # 2. Block the UI for a moment to let it finish safely
            if not self.thread.wait(3000):  # Wait up to 3 seconds
                print("Thread timed out, terminating...")
                self.thread.terminate()
        self.setup_window.show_page(self.setup_window.apps_page_button)
        self.setup_window.show()
        event.accept()

    def toggle_select_all_apps(self):
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

    def toggle_category(self, category):
        app_categories = {
            app.get("name"): str(app.get("category") or "Universal").strip() or "Universal"
            for app in load_yaml() if app.get("name")
        }
        items = [self.list_widget.item(i) for i in range(self.list_widget.count())
                 if self.list_widget.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable
                 and app_categories.get(self.list_widget.item(i).text(), "Universal") == category]
        check = not items or not all(item.checkState() == Qt.CheckState.Checked for item in items)
        for item in items:
            item.setCheckState(Qt.CheckState.Checked if check else Qt.CheckState.Unchecked)

    def toggle_category_visibility(self, category):
        if category in self.collapsed_categories:
            self.collapsed_categories.remove(category)
        else:
            self.collapsed_categories.add(category)
        self.update_ui_with_apps(
            self.apps, self.uninstalled_apps, self.unavailable_apps,
            self.fedora_packages_checked,
        )

    def install_selected(self):
        selected_apps = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_apps.append(item.text())

        if selected_apps:
            confirm = QMessageBox.question(
                self, "Confirm Installation",
                f"Do you want to install the following apps?\n{', '.join(selected_apps)}",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                yaml_source_map = self.get_yaml_source_map()
                pacman_list = []
                paru_list = []
                fedora_archive_list = []
                unknown_apps = []
                for app in selected_apps:
                    if is_fedora() and package_manager() in {"dnf", "dnf5"}:
                        # Fedora has no AUR/pacman distinction; the package
                        # availability check in the install worker validates
                        # mapped packages against enabled repositories.
                        method = (
                            "fedora-archive"
                            if fedora_install_type(app) == "jetbrains-toolbox"
                            else "pacman" if fedora_app_name(app) else None
                        )
                    else:
                        method = self.get_install_method_from_source(yaml_source_map.get(app))
                        if method is None:
                            method = detect_install_method(app)
                    if method == "paru":
                        paru_list.append(app)
                    elif method == "pacman":
                        pacman_list.append(app)
                    elif method == "fedora-archive":
                        fedora_archive_list.append(app)
                    else:
                        unknown_apps.append(app)

                operations = []
                if pacman_list:
                    operations.append((pacman_list, "pacman"))
                if paru_list:
                    operations.append((paru_list, "paru"))
                if fedora_archive_list:
                    operations.append((fedora_archive_list, "fedora-archive"))

                if unknown_apps:
                    self.selected_apps = [app for app in self.selected_apps if app not in unknown_apps]
                    for index in range(self.list_widget.count()):
                        item = self.list_widget.item(index)
                        if item.text() in unknown_apps:
                            item.setCheckState(Qt.CheckState.Unchecked)
                    QMessageBox.warning(
                        self,
                        "Unknown Source",
                        f"Could not detect install source for: {', '.join(unknown_apps)}",
                    )
                if operations:
                    self.start_install_operations(
                        operations,
                        check_fedora_packages=is_fedora() and package_manager() in {"dnf", "dnf5"},
                    )
                    return
        else:
            QMessageBox.warning(self, "No Selection",
                                "No apps selected for installation.")
        self.load_apps_async()

    @staticmethod
    def get_install_method_from_source(source):
        return get_install_method_from_source(source)

    @staticmethod
    def get_yaml_source_map():
        yaml_data = load_yaml()
        source_map = {}
        for app in yaml_data:
            name = app.get("name")
            if not name:
                continue
            source_map[name] = app.get("source")
        return source_map

    def update_ui_with_apps(self, all_apps, uninstalled_apps, unavailable_apps=None, checked=True):
        """The single point of entry for your UI data"""
        self.selected_apps = [
            self.list_widget.item(i).text() for i in range(self.list_widget.count())
            if self.list_widget.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable
            and self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]
        self.apps = all_apps  # Keep the master list for the editor
        self.uninstalled_apps = list(uninstalled_apps)
        self.fedora_packages_checked = checked
        self.install_button.setEnabled(checked)
        if unavailable_apps is not None:
            self.unavailable_apps = list(unavailable_apps)
        self.stop_loading_animation()
        self.loading_label.hide()
        self.check_progress_bar.hide()
        self.refresh_button.setEnabled(True)
        self.select_all_button.setEnabled(True)
        self.install_button.setEnabled(
            self.fedora_packages_checked or package_manager() in {"dnf", "dnf5"}
        )
        self.list_widget.clear()

        app_categories = {
            app.get("name"): str(app.get("category") or "Universal").strip() or "Universal"
            for app in load_yaml() if app.get("name")
        }
        grouped_apps = {}
        for app in uninstalled_apps:
            grouped_apps.setdefault(app_categories.get(app, "Universal"), []).append(app)
        categories = sorted(grouped_apps, key=str.casefold)

        if not uninstalled_apps and not self.unavailable_apps:
            prompt = "All apps are currently installed!" if checked else "Select apps to check availability and install."
            item = QListWidgetItem(prompt)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.list_widget.addItem(item)
        if uninstalled_apps:
            for category in categories:
                add_category_header(
                    self.list_widget, category, category in self.collapsed_categories,
                    self.toggle_category_visibility, self.toggle_category
                )
                for app in sorted(grouped_apps[category], key=str.casefold):
                    item = QListWidgetItem(app)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if app in self.selected_apps else Qt.Unchecked)
                    self.list_widget.addItem(item)
                    item.setHidden(category in self.collapsed_categories)
        for app in self.unavailable_apps:
            item = QListWidgetItem(f"{app} -")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsUserCheckable)
            self.list_widget.addItem(item)

    def go_back_to_setup(self):
        self.setup_window.show_page(self.setup_window.apps_page_button)
        self.setup_window.show()
        self.hide()

    def start_loading_animation(self, base_text):
        self.loading_base_text = base_text
        self.loading_dot_count = 0
        self.loading_label.setText(f"{self.loading_base_text}.")
        if self.loading_timer is None:
            self.loading_timer = QTimer(self)
            self.loading_timer.setInterval(420)
            self.loading_timer.timeout.connect(self.update_loading_dots)
        self.loading_timer.start()

    def update_loading_dots(self):
        self.loading_dot_count = (self.loading_dot_count + 1) % 4
        dots = "." * self.loading_dot_count
        self.loading_label.setText(f"{self.loading_base_text}{dots}")

    def stop_loading_animation(self):
        if self.loading_timer and self.loading_timer.isActive():
            self.loading_timer.stop()

    def start_install_operations(self, operations, check_fedora_packages=False):
        if self.action_thread and self.action_thread.isRunning():
            return

        self.last_install_summary = None
        self.install_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.select_all_button.setEnabled(False)
        self.loading_label.show()
        self.start_loading_animation(
            "Checking selected apps" if check_fedora_packages else "Waiting installation to finish"
        )

        self.action_thread = QThread()
        self.action_worker = InstallOperationWorker(operations, check_fedora_packages)
        self.action_worker.moveToThread(self.action_thread)
        self.action_thread.started.connect(self.action_worker.run)
        self.action_worker.finished.connect(self.on_install_operations_finished)
        self.action_worker.error.connect(self.on_install_operations_error)
        self.action_worker.progress.connect(self.update_progress)
        self.action_worker.unavailable.connect(self.mark_fedora_apps_unavailable)
        self.action_worker.nothing_available.connect(self.on_no_fedora_packages_available)
        self.action_worker.summary_ready.connect(self.save_install_summary)
        self.action_worker.finished.connect(self.action_thread.quit)
        self.action_worker.error.connect(self.action_thread.quit)
        self.action_worker.nothing_available.connect(self.action_thread.quit)
        self.action_worker.finished.connect(self.action_worker.deleteLater)
        self.action_worker.error.connect(self.action_worker.deleteLater)
        self.action_worker.nothing_available.connect(self.action_worker.deleteLater)
        self.action_thread.finished.connect(self.action_thread.deleteLater)
        self.action_thread.finished.connect(self.cleanup_action_thread)
        self.action_thread.start()

    def mark_fedora_apps_unavailable(self, apps):
        self.unavailable_apps = list(dict.fromkeys([*self.unavailable_apps, *apps]))
        self.uninstalled_apps = [app for app in self.uninstalled_apps if app not in apps]
        self.selected_apps = [app for app in self.selected_apps if app not in apps]
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.text() in apps:
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setText(f"{item.text()} -")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

    def on_no_fedora_packages_available(self):
        self.stop_loading_animation()
        self.loading_label.setText("No selected apps are available from the configured Fedora repositories.")
        self.loading_label.show()
        self.install_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.select_all_button.setEnabled(True)
        self.show_install_summary()

    def save_install_summary(self, summary):
        self.last_install_summary = summary

    def format_install_summary(self):
        summary = self.last_install_summary
        if not summary:
            return ""
        sections = []
        for title, key in (
            ("Not found in enabled repositories", "unavailable"),
            ("Skipped or not installed", "skipped"),
            ("Replaced or removed packages", "replaced"),
        ):
            items = summary.get(key, [])
            sections.append(f"{title}:\n" + ("\n".join(f"• {app}" for app in items) if items else "• None"))
        return "\n\n".join(sections)

    def show_install_summary(self):
        summary = self.last_install_summary
        if not summary:
            return

        has_reported_issues = any(
            summary.get(key) for key in ("unavailable", "skipped", "replaced")
        )
        if has_reported_issues:
            QMessageBox.information(
                self, "Fedora Installation Results", self.format_install_summary()
            )
        else:
            QMessageBox.information(self, "Installation Complete", "Installation successful.")

    def on_install_operations_finished(self):
        self.stop_loading_animation()
        self.loading_label.hide()
        self.install_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.select_all_button.setEnabled(True)
        self.show_install_summary()
        self.load_apps_async()

    def on_install_operations_error(self, error_message):
        self.stop_loading_animation()
        self.loading_label.hide()
        # The package manager reports a batch failure without identifying which
        # individual packages failed. Clear the attempted selections so they
        # cannot be accidentally retried as still-selected apps.
        self.selected_apps = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.install_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.select_all_button.setEnabled(True)
        summary_text = self.format_install_summary()
        if summary_text:
            error_message = f"{error_message}\n\n{summary_text}"
        QMessageBox.critical(self, "Install Error", f"Installation failed: {error_message}")
        self.load_apps_async()

    def cleanup_action_thread(self):
        self.action_thread = None
        self.action_worker = None
