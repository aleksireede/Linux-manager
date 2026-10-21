from PyQt5.QtWidgets import QWidget, QVBoxLayout

try:
    from .theme import apply_dark_theme
except ImportError:
    from theme import apply_dark_theme


class NetworkDrivesPage(QWidget):
    def __init__(self, setup_window):
        super().__init__(setup_window)
        self.setup_window = setup_window
        self.setWindowTitle("Network Drives")
        apply_dark_theme(self)

        layout = QVBoxLayout(self)
        layout.addSpacing(16)
        layout.addWidget(setup_window.network_drives_card)
        layout.addStretch()
