from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget

try:
    from .ui_helpers import create_back_button
    from .theme import configure_main_window, create_page_header
except ImportError:
    from ui_helpers import create_back_button
    from theme import configure_main_window, create_page_header


class NetworkDrivesPage(QMainWindow):
    def __init__(self, setup_window):
        super().__init__()
        self.setup_window = setup_window
        self.setWindowTitle("Network Drives")
        configure_main_window(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        back_button, _, _, _ = create_back_button(self.go_back)
        layout.addWidget(create_page_header(back_button, "Network Drives"))
        layout.addSpacing(16)
        layout.addWidget(setup_window.network_drives_card)
        layout.addStretch()

    def go_back(self):
        self.setup_window.show()
        self.hide()
