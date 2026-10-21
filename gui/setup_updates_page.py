from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame, QSizePolicy

from programs.installer_logic import package_manager

try:
    from .theme import apply_dark_theme
except ImportError:
    from theme import apply_dark_theme


class SetupUpdatesPage(QWidget):
    def __init__(self, setup_window):
        super().__init__(setup_window)
        self.setup_window = setup_window
        self.setWindowTitle("Updates")
        apply_dark_theme(self)

        layout = QVBoxLayout(self)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 12, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(setup_window.paru_card)
        setup_window.paru_card.setVisible(package_manager() == "pacman")
        content_layout.addWidget(setup_window.gpu_card)
        content_layout.addWidget(setup_window.update_card)
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
