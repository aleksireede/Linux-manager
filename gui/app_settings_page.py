from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QLabel,
    QComboBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QColorDialog,
    QScrollArea,
    QSizePolicy,
    QLayout,
    QHBoxLayout,
)

from programs.app_settings import (
    accent_color, background_color, external_terminal, package_conflict_policy,
    set_accent_color, set_background_color, set_external_terminal,
    set_package_conflict_policy,
)
from programs.installer_logic import external_terminal_options
from .theme import apply_dark_theme


APP_THEMES = {
    "Classic Dark": {"background": "#1e1e1e", "accent": "#007acc"},
    "Ocean": {"background": "#172632", "accent": "#42a5f5"},
    "Forest": {"background": "#202923", "accent": "#65b884"},
    "Plum": {"background": "#2a202d", "accent": "#c084fc"},
    "Warm Slate": {"background": "#292522", "accent": "#e39b62"},
}


class AppSettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("Changes are saved automatically.")
        self.status_label.setObjectName("syncStatusLabel")
        layout.addWidget(self.status_label)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        content_layout = QVBoxLayout(content)
        content_layout.setSizeConstraint(QLayout.SetMinimumSize)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("serviceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)

        title = QLabel("Package conflicts")
        title.setObjectName("serviceTitle")
        description = QLabel(
            "Choose how package conflicts are handled during app installation."
        )
        description.setWordWrap(True)

        self.skip_radio = QRadioButton("Skip conflicting apps")
        self.skip_radio.setToolTip(
            "Continue with other apps when a package conflict prevents installation."
        )
        self.ask_radio = QRadioButton("Ask about conflicting packages")
        self.ask_radio.setToolTip(
            "Show the package manager's conflict prompt so you can decide whether to replace packages."
        )
        self.replace_radio = QRadioButton("Replace conflicting packages")
        self.replace_radio.setToolTip(
            "Allow the package manager to replace conflicting installed packages."
        )
        self.policy_group = QButtonGroup(self)
        self.policy_group.addButton(self.skip_radio)
        self.policy_group.addButton(self.ask_radio)
        self.policy_group.addButton(self.replace_radio)
        card_layout.addWidget(title)
        card_layout.addWidget(description)
        card_layout.addWidget(self.skip_radio)
        card_layout.addWidget(self.ask_radio)
        card_layout.addWidget(self.replace_radio)

        terminal_card = QFrame()
        terminal_card.setObjectName("serviceCard")
        terminal_layout = QVBoxLayout(terminal_card)
        terminal_layout.setContentsMargins(20, 18, 20, 18)
        terminal_layout.setSpacing(12)
        terminal_title = QLabel("External terminal")
        terminal_title.setObjectName("serviceTitle")
        terminal_layout.addWidget(terminal_title)
        terminal_layout.addWidget(QLabel("Choose which terminal opens package and system commands."))
        self.terminal_selector = QComboBox()
        for terminal_id, label in external_terminal_options():
            self.terminal_selector.addItem(label, terminal_id)
        selected_terminal = external_terminal()
        terminal_index = self.terminal_selector.findData(selected_terminal)
        self.terminal_selector.setCurrentIndex(terminal_index if terminal_index >= 0 else 0)
        self.terminal_selector.currentIndexChanged.connect(self.save_external_terminal)
        terminal_layout.addWidget(self.terminal_selector)

        current_policy = package_conflict_policy()
        self.skip_radio.setChecked(current_policy == "skip")
        self.ask_radio.setChecked(current_policy == "ask")
        self.replace_radio.setChecked(current_policy == "replace")
        self.skip_radio.toggled.connect(self.save_skip_policy)
        self.ask_radio.toggled.connect(self.save_ask_policy)
        self.replace_radio.toggled.connect(self.save_replace_policy)

        content_layout.addWidget(card)
        content_layout.addWidget(terminal_card)

        appearance_card = QFrame()
        appearance_card.setObjectName("serviceCard")
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(20, 18, 20, 18)
        appearance_layout.setSpacing(12)
        appearance_title = QLabel("Appearance")
        appearance_title.setObjectName("serviceTitle")
        appearance_layout.addWidget(appearance_title)
        appearance_layout.addWidget(QLabel("Choose a preset theme or customize the background and accent colors."))
        self.theme_selector = QComboBox()
        self.theme_selector.addItems([*APP_THEMES, "Custom"])
        saved_theme = next(
            (
                name for name, colors in APP_THEMES.items()
                if colors["background"] == background_color() and colors["accent"] == accent_color()
            ),
            "Custom",
        )
        self.theme_selector.setCurrentText(saved_theme)
        self.theme_selector.currentTextChanged.connect(self.select_theme)
        appearance_layout.addWidget(self.theme_selector)

        custom_color_row = QHBoxLayout()
        self.background_color_button = QPushButton()
        self.background_color_button.clicked.connect(self.choose_background_color)
        self.accent_color_button = QPushButton()
        self.accent_color_button.clicked.connect(self.choose_accent_color)
        custom_color_row.addWidget(self.background_color_button)
        custom_color_row.addWidget(self.accent_color_button)
        appearance_layout.addLayout(custom_color_row)
        content_layout.addWidget(appearance_card)
        self.update_color_buttons()
        self.update_custom_color_visibility()

        content_layout.addStretch()
        content_layout.activate()
        content.setMinimumHeight(content_layout.sizeHint().height())
        scroll_area.setWidget(content)
        layout.addWidget(scroll_area, 1)

    def save_skip_policy(self, checked):
        if checked:
            self.save_policy("skip")

    def save_replace_policy(self, checked):
        if checked:
            self.save_policy("replace")

    def save_ask_policy(self, checked):
        if checked:
            self.save_policy("ask")

    def save_policy(self, policy):
        try:
            set_package_conflict_policy(policy)
            self.status_label.setText("Saved. This setting applies to the next app installation.")
        except Exception as error:
            self.status_label.setText(f"Could not save setting: {error}")

    def save_external_terminal(self, _index):
        try:
            set_external_terminal(self.terminal_selector.currentData())
            self.status_label.setText("External terminal preference saved.")
        except Exception as error:
            self.status_label.setText(f"Could not save terminal preference: {error}")

    def choose_accent_color(self):
        color = QColorDialog.getColor(self.current_accent_color, self, "Choose app accent color")
        if not color.isValid():
            return
        try:
            set_accent_color(color.name())
            self.apply_saved_theme("Accent color saved.")
        except Exception as error:
            self.status_label.setText(f"Could not save accent color: {error}")

    def choose_background_color(self):
        color = QColorDialog.getColor(self.current_background_color, self, "Choose app background color")
        if not color.isValid():
            return
        try:
            set_background_color(color.name())
            self.apply_saved_theme("Background color saved.")
        except Exception as error:
            self.status_label.setText(f"Could not save background color: {error}")

    def select_theme(self, theme_name):
        self.update_custom_color_visibility()
        colors = APP_THEMES.get(theme_name)
        if colors is None:
            return
        try:
            set_background_color(colors["background"])
            set_accent_color(colors["accent"])
            self.apply_saved_theme(f"{theme_name} theme saved.")
        except Exception as error:
            self.status_label.setText(f"Could not save theme: {error}")

    def apply_saved_theme(self, message):
        for widget in QApplication.topLevelWidgets():
            apply_dark_theme(widget)
        self.update_color_buttons()
        self.status_label.setText(message)

    def update_custom_color_visibility(self, *_):
        is_custom = self.theme_selector.currentText() == "Custom"
        self.background_color_button.setVisible(is_custom)
        self.accent_color_button.setVisible(is_custom)

    def update_color_buttons(self):
        background = background_color()
        accent = accent_color()
        self.background_color_button.setText(f"Background: {background}")
        self.background_color_button.setStyleSheet(
            f"background-color: {background}; color: white; font-weight: 600;"
        )
        self.accent_color_button.setText(f"Accent: {accent}")
        self.accent_color_button.setStyleSheet(
            f"background-color: {accent}; color: white; font-weight: 600;"
        )

    @property
    def current_accent_color(self):
        from PyQt5.QtGui import QColor
        return QColor(accent_color())

    @property
    def current_background_color(self):
        from PyQt5.QtGui import QColor
        return QColor(background_color())
