from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QMessageBox, QInputDialog, QHBoxLayout, \
    QListWidgetItem, QLabel, QComboBox, QLineEdit, QDialogButtonBox, QCheckBox

from programs.apps_file import (
    add_app_to_yaml, load_yaml, remove_app_from_yaml, set_apps_category, update_app_in_yaml,
)
from programs.installer_logic import is_fedora, arch_app_name, fedora_app_name
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
        self.is_fedora = is_fedora()
        self.distro_icon_path = Path(__file__).resolve().parent.parent.joinpath(
            "icons", "fedora_logo.svg" if self.is_fedora else "arch_logo.svg"
        )

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

        edit_btn = QPushButton("Edit App", self)
        edit_btn.clicked.connect(self.edit_app)

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
        button_layout.addWidget(edit_btn)
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
        catalog_entries = load_yaml()
        entries_by_name = {
            entry["name"]: entry for entry in catalog_entries
            if isinstance(entry, dict) and entry.get("name")
        }
        for entry in catalog_entries:
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
                item = QListWidgetItem(app)
                item.setData(Qt.ItemDataRole.UserRole, app)
                entry = entries_by_name.get(app, {})
                package_name = fedora_app_name(app) if self.is_fedora else arch_app_name(app)
                source_label = "Fedora package" if self.is_fedora else entry.get("source", "Arch package")
                item.setIcon(QIcon(str(self.distro_icon_path)))
                item.setToolTip(f"{source_label}: {package_name or 'not configured'}")
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
                self, "No selection", "Please check at least one application to remove.")
            return

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Remove Applications")
        dialog.setText(f"Remove these applications from the current list?\n{', '.join(selected_apps)}")
        mark_for_uninstall = QCheckBox("Also mark for uninstallation (move to the Uninstall category)")
        dialog.setCheckBox(mark_for_uninstall)
        dialog.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        dialog.button(QMessageBox.Yes).setText("Remove")
        if dialog.exec() != QMessageBox.Yes:
            return

        if mark_for_uninstall.isChecked():
            set_apps_category(selected_apps, "Uninstall")
            QMessageBox.information(
                self, "Moved to Uninstall", f"Moved to the Uninstall category: {', '.join(selected_apps)}"
            )
        else:
            for app in selected_apps:
                remove_app_from_yaml(app)
        self.apps = [app for app in self.apps if app not in selected_apps]
        self.populate_list()

    def add_apps(self):
        """Add an app with optional package names for Arch and Fedora."""
        categories = sorted({
            str(app.get("category", "Universal")).strip() or "Universal"
            for app in load_yaml() if isinstance(app, dict)
        }, key=str.casefold)
        if "Universal" not in categories:
            categories.insert(0, "Universal")

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Application")
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(QLabel("Application name:", dialog))
        app_name_input = QLineEdit(dialog)
        dialog_layout.addWidget(app_name_input)
        dialog_layout.addWidget(QLabel("Arch package name:", dialog))
        arch_package_input = QLineEdit(dialog)
        dialog_layout.addWidget(arch_package_input)
        dialog_layout.addWidget(QLabel("Arch conflicting packages (comma-separated):", dialog))
        arch_conflicts_input = QLineEdit(dialog)
        arch_conflicts_input.setPlaceholderText("e.g. package-one, package-two")
        dialog_layout.addWidget(arch_conflicts_input)
        dialog_layout.addWidget(QLabel("Fedora package name:", dialog))
        fedora_package_input = QLineEdit(dialog)
        dialog_layout.addWidget(fedora_package_input)
        dialog_layout.addWidget(QLabel("Arch source:", dialog))
        source_selector = QComboBox(dialog)
        source_selector.addItems(["pacman", "paru"])
        dialog_layout.addWidget(source_selector)
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

        app_name = app_name_input.text().strip()
        arch_package = arch_package_input.text().strip()
        fedora_package = fedora_package_input.text().strip()
        category = category_selector.currentText().strip()
        if not category:
            QMessageBox.information(self, "Choose Category", "Please enter a category name.")
            return

        if not app_name or not arch_package and not fedora_package:
            QMessageBox.information(
                self, "Add Application", "Enter an application name and at least one distro package name."
            )
            return
        if any(app.casefold() == app_name.casefold() for app in self.apps):
            QMessageBox.information(self, "Add Application", f"'{app_name}' is already in the app list.")
            return

        add_app_to_yaml(
            app_name,
            category,
            arch_app_name=arch_package or None,
            fedora_app_name=fedora_package or None,
            source=source_selector.currentText(),
            conflicts=self.parse_conflicts(arch_conflicts_input.text()),
        )
        self.apps.append(app_name)
        self.apps.sort(key=str.casefold)
        self.populate_list()
        QMessageBox.information(self, "Add Application", f"Added {app_name} for this distro.")

    def edit_app(self):
        item = self.list_widget.currentItem()
        app_name = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not app_name:
            QMessageBox.information(self, "Edit App", "Select an app row to edit.")
            return

        entry = next((record for record in load_yaml() if record.get("name") == app_name), None)
        if entry is None:
            QMessageBox.warning(self, "Edit App", f"Could not find '{app_name}' in the app catalog.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit {app_name}")
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(QLabel("Application name:", dialog))
        app_name_input = QLineEdit(app_name, dialog)
        dialog_layout.addWidget(app_name_input)

        current_arch_package = entry.get("arch_app_name", app_name) or ""
        current_fedora_package = (
            entry.get("fedora_app_name", app_name)
            if "fedora_app_name" in entry else app_name
        ) or ""
        dialog_layout.addWidget(QLabel("Arch package name:", dialog))
        arch_package_input = QLineEdit(current_arch_package, dialog)
        dialog_layout.addWidget(arch_package_input)
        dialog_layout.addWidget(QLabel("Arch conflicting packages (comma-separated):", dialog))
        arch_conflicts_input = QLineEdit(
            ", ".join(entry.get("conflicts", [])), dialog
        )
        arch_conflicts_input.setPlaceholderText("e.g. package-one, package-two")
        dialog_layout.addWidget(arch_conflicts_input)
        dialog_layout.addWidget(QLabel("Fedora package name:", dialog))
        fedora_package_input = QLineEdit(current_fedora_package, dialog)
        dialog_layout.addWidget(fedora_package_input)
        dialog_layout.addWidget(QLabel("Arch source:", dialog))
        source_selector = QComboBox(dialog)
        source_selector.addItems(["pacman", "paru"])
        current_source = str(entry.get("source", "pacman")).lower()
        source_selector.setCurrentText("paru" if current_source in {"paru", "aur"} else "pacman")
        dialog_layout.addWidget(source_selector)

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, dialog)
        dialog_buttons.accepted.connect(dialog.accept)
        dialog_buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(dialog_buttons)
        if dialog.exec() != QDialog.Accepted:
            return

        new_name = app_name_input.text().strip()
        arch_package = arch_package_input.text().strip()
        fedora_package = fedora_package_input.text().strip()
        if not new_name or not arch_package and not fedora_package:
            QMessageBox.information(
                self, "Edit App", "Enter an application name and at least one distro package name."
            )
            return
        if new_name.casefold() != app_name.casefold() and any(
            existing.casefold() == new_name.casefold() for existing in self.apps
        ):
            QMessageBox.information(self, "Edit App", f"'{new_name}' is already in the app list.")
            return

        saved = update_app_in_yaml(
            app_name,
            new_name,
            arch_app_name=arch_package,
            fedora_app_name=fedora_package,
            source=source_selector.currentText(),
            conflicts=self.parse_conflicts(arch_conflicts_input.text()),
        )
        if not saved:
            QMessageBox.warning(self, "Edit App", "The app could not be updated in the catalog.")
            return
        self.apps = [new_name if existing == app_name else existing for existing in self.apps]
        self.apps.sort(key=str.casefold)
        self.populate_list()

    @staticmethod
    def parse_conflicts(value):
        return list(dict.fromkeys(
            package.strip() for package in value.split(",") if package.strip()
        ))

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
