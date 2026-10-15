from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from programs.app_settings import fedora_conflict_policy, set_fedora_conflict_policy

try:
    from .theme import configure_main_window, create_page_header
    from .ui_helpers import create_back_button
except ImportError:
    from theme import configure_main_window, create_page_header
    from ui_helpers import create_back_button


class AppSettingsPage(QWidget):
    def __init__(self, apps_page):
        super().__init__()
        self.apps_page = apps_page
        self.setWindowTitle("App Settings")
        configure_main_window(self)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        back_button, _, _, _ = create_back_button(self.go_back)
        layout.addWidget(create_page_header(back_button, "App Settings"))
        layout.addSpacing(12)

        card = QFrame()
        card.setObjectName("serviceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)

        title = QLabel("Fedora package conflicts")
        title.setObjectName("serviceTitle")
        description = QLabel(
            "Choose how Fedora handles conflicting packages during app installation. "
            "This setting is used for DNF and DNF5 installations."
        )
        description.setWordWrap(True)

        self.skip_radio = QRadioButton("Skip conflicting apps")
        self.skip_radio.setToolTip(
            "Use --skip-broken so DNF can continue with other installable apps."
        )
        self.replace_radio = QRadioButton("Replace conflicting packages")
        self.replace_radio.setToolTip(
            "Use --allowerasing; DNF may remove installed packages to complete the install."
        )
        self.policy_group = QButtonGroup(self)
        self.policy_group.addButton(self.skip_radio)
        self.policy_group.addButton(self.replace_radio)
        card_layout.addWidget(title)
        card_layout.addWidget(description)
        card_layout.addWidget(self.skip_radio)
        card_layout.addWidget(self.replace_radio)

        current_policy = fedora_conflict_policy()
        self.skip_radio.setChecked(current_policy == "skip")
        self.replace_radio.setChecked(current_policy == "replace")
        self.skip_radio.toggled.connect(self.save_skip_policy)
        self.replace_radio.toggled.connect(self.save_replace_policy)

        self.status_label = QLabel("Changes are saved automatically.")
        self.status_label.setObjectName("syncStatusLabel")
        card_layout.addWidget(self.status_label)
        layout.addWidget(card)
        layout.addStretch()

    def save_skip_policy(self, checked):
        if checked:
            self.save_policy("skip")

    def save_replace_policy(self, checked):
        if checked:
            self.save_policy("replace")

    def save_policy(self, policy):
        try:
            set_fedora_conflict_policy(policy)
            self.status_label.setText("Saved. This setting applies to the next app installation.")
        except Exception as error:
            self.status_label.setText(f"Could not save setting: {error}")

    def go_back(self):
        self.hide()
        self.apps_page.show()
