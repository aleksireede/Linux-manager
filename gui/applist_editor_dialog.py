import subprocess
from pathlib import Path

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QMessageBox, QInputDialog, QHBoxLayout, \
    QListWidgetItem, QWidget, QToolButton, QLabel, QStyle, QComboBox, QLineEdit, QDialogButtonBox, QSizePolicy

from programs.apps_file import add_app_to_yaml, load_yaml, set_apps_category
from programs.installer_logic import (
    command_exists,
)
try:
    from .theme import configure_dialog
    from .category_list import add_category_header
except ImportError:
    from theme import configure_dialog
    from category_list import add_category_header


class AppListEditorDialog(QDialog):
    def __init__(self, parent=None, apps=None):
        super().__init__(parent)
        self.setWindowTitle("App List Editor")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        configure_dialog(self, width=620, height=720, min_width=560, min_height=640)
        self.selected_item = None
        self.apps = apps
        self.collapsed_categories = set()
        self.category_apps = {}
        self.search_icon_path = Path(__file__).resolve().parent.parent.joinpath("icons", "search.svg")

        # use vertical box layout
        layout = QHBoxLayout(self)
        button_layout = QVBoxLayout()
        list_layout = QVBoxLayout()

        # List widget
        self.list_widget = QListWidget(self)
        self.populate_list()

        # Add button
        add_btn = QPushButton("Add app", self)
        add_btn.clicked.connect(self.add_apps)

        # OK button
        ok_btn = QPushButton("Apply", self)
        ok_btn.clicked.connect(self.accept)

        # Remove button
        remove_btn = QPushButton("Remove Selected", self)
        remove_btn.clicked.connect(self.remove_selected)

        category_btn = QPushButton("Change Category", self)
        category_btn.clicked.connect(self.change_category)

        # Search button
        search_btn = QPushButton("Search", self)
        search_btn.setIcon(QIcon(str(self.search_icon_path)))
        search_btn.clicked.connect(self.search_app)

        # Cancel button
        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)

        # list
        list_layout.addWidget(self.list_widget)

        # button layout
        button_layout.addStretch()
        button_layout.addWidget(add_btn)
        button_layout.addWidget(search_btn)
        button_layout.addWidget(remove_btn)
        button_layout.addWidget(category_btn)
        button_layout.addSpacing(15)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)

        # main layout
        layout.addLayout(list_layout)
        layout.addLayout(button_layout)

    def populate_list(self):
        self.list_widget.clear()
        app_categories = {}
        for entry in load_yaml():
            if entry.get("name"):
                app_categories[entry["name"]] = str(entry.get("category") or "Universal").strip() or "Universal"
        grouped = {}
        for app in self.apps:
            grouped.setdefault(app_categories.get(app, "Universal"), []).append(app)
        self.category_apps = {category: set(apps) for category, apps in grouped.items()}

        for category in sorted(grouped, key=str.casefold):
            add_category_header(
                self.list_widget,
                category,
                category in self.collapsed_categories,
                self.toggle_category,
                self.toggle_category_apps,
            )

            for app in sorted(grouped[category], key=str.casefold):
                item = QListWidgetItem(f"    {app}")
                item.setData(Qt.ItemDataRole.UserRole, app)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.list_widget.addItem(item)
                item.setHidden(category in self.collapsed_categories)

    def toggle_category_apps(self, category):
        apps = self.category_apps.get(category, set())
        items = [
            self.list_widget.item(index) for index in range(self.list_widget.count())
            if self.list_widget.item(index).data(Qt.ItemDataRole.UserRole) in apps
        ]
        check = not items or not all(item.checkState() == Qt.CheckState.Checked for item in items)
        for item in items:
            item.setCheckState(Qt.CheckState.Checked if check else Qt.CheckState.Unchecked)

    def toggle_category(self, category):
        if category in self.collapsed_categories:
            self.collapsed_categories.remove(category)
        else:
            self.collapsed_categories.add(category)
        self.populate_list()

    def change_category(self):
        selected_apps = self.get_checked_apps()
        if not selected_apps:
            QMessageBox.information(self, "No selection", "Check one or more apps to change their category.")
            return
        categories = sorted({
            str(app.get("category") or "Universal").strip() or "Universal"
            for app in load_yaml() if isinstance(app, dict)
        }, key=str.casefold)
        if "Universal" not in categories:
            categories.insert(0, "Universal")
        category, ok = QInputDialog.getItem(
            self, "Change Category", "Category (type a new name to create it):", categories, 0, True
        )
        if not ok:
            return
        category = category.strip()
        if not category:
            QMessageBox.information(self, "Change Category", "Please enter a category name.")
            return
        set_apps_category(selected_apps, category)
        self.populate_list()

    def get_checked_apps(self):
        checked_apps = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                checked_apps.append(item.data(Qt.ItemDataRole.UserRole) or item.text().strip())
        return checked_apps

    def remove_selected(self):
        selected_apps = self.get_checked_apps()
        if not selected_apps:
            QMessageBox.information(
                self, "No selection", "Please check at least one application to move.")
            return
        confirm = QMessageBox.question(
            self,
            "Move to Uninstall",
            "Move the selected applications to the Uninstall category? This will not uninstall them yet.\n"
            f"{', '.join(selected_apps)}",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            set_apps_category(selected_apps, "Uninstall")
            self.populate_list()
            QMessageBox.information(
                self, "Moved to Uninstall", f"Moved to the Uninstall category: {', '.join(selected_apps)}"
            )

    def add_apps(self):
        """Open a dialog to add one or more apps, checking availability first."""
        categories = sorted({
            str(app.get("category", "Universal")).strip() or "Universal"
            for app in load_yaml() if isinstance(app, dict)
        }, key=str.casefold)
        if "Universal" not in categories:
            categories.insert(0, "Universal")

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Application")
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(QLabel("Application names (separate multiple names with commas):", dialog))
        app_names_input = QLineEdit(dialog)
        dialog_layout.addWidget(app_names_input)
        dialog_layout.addWidget(QLabel("Category (choose one or type a new category name):", dialog))
        category_selector = QComboBox(dialog)
        category_selector.setEditable(True)
        category_selector.addItems(categories)
        category_selector.setCurrentText("Universal")
        dialog_layout.addWidget(category_selector)
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        dialog_buttons.accepted.connect(dialog.accept)
        dialog_buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(dialog_buttons)
        if dialog.exec() != QDialog.Accepted:
            return

        new_apps_text = app_names_input.text()
        category = category_selector.currentText().strip()
        if not category:
            QMessageBox.information(self, "Choose Category", "Please enter a category name.")
            return

        requested_apps = []
        seen = set()
        for raw_name in new_apps_text.split(","):
            app_name = raw_name.strip()
            if not app_name:
                continue
            normalized = app_name.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            requested_apps.append(app_name)

        if not requested_apps:
            QMessageBox.information(self, "Add Application", "Please enter at least one application name.")
            return

        added_apps = []
        duplicate_apps = []
        not_found_apps = []

        for new_app in requested_apps:
            if new_app in self.apps:
                duplicate_apps.append(new_app)
                continue

            available_in = []
            try:
                subprocess.run(
                    ["pacman", "-Si", new_app],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                )
                available_in.append("pacman")
            except subprocess.CalledProcessError:
                pass

            if command_exists("paru"):
                try:
                    subprocess.run(
                        ["paru", "-Si", new_app],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                    )
                    available_in.append("AUR")
                except subprocess.CalledProcessError:
                    pass

            if available_in:
                self.apps.append(new_app)
                add_app_to_yaml(new_app, category)
                added_apps.append(f"{new_app} ({', '.join(available_in)})")
            else:
                not_found_apps.append(new_app)

        self.apps.sort()
        self.populate_list()

        messages = []
        if added_apps:
            messages.append(f"Added: {', '.join(added_apps)}")
        if duplicate_apps:
            messages.append(f"Already in list: {', '.join(duplicate_apps)}")
        if not_found_apps:
            messages.append(f"Not found in pacman or AUR: {', '.join(not_found_apps)}")

        if not added_apps:
            QMessageBox.warning(self, "Add Application", "\n".join(messages))
        else:
            QMessageBox.information(self, "Add Application", "\n".join(messages))

    def get_apps(self):
        return self.apps

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
            if lower_query in item.text().lower():
                self.list_widget.setCurrentRow(index)
                self.list_widget.scrollToItem(item)
                return

        QMessageBox.information(self, "Not Found", f"No application found for '{query}'.")
