from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from programs.fedora_repositories import (
    fedora_repository_is_configured,
    import_fedora_repositories,
    load_fedora_repositories,
)
try:
    from .theme import configure_main_window, create_page_header
    from .ui_helpers import create_back_button
except ImportError:
    from theme import configure_main_window, create_page_header
    from ui_helpers import create_back_button


class FedoraRepositoryWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, repositories):
        super().__init__()
        self.repositories = repositories

    def run(self):
        try:
            self.progress.emit("Downloading and validating repository files and signing keys")
            result = import_fedora_repositories(self.repositories, self.progress.emit)
            self.finished.emit(result)
        except Exception as error:
            self.error.emit(str(error))


class FedoraRepositoryStatusWorker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, repositories):
        super().__init__()
        self.repositories = repositories

    def run(self):
        try:
            results = [
                (repo["id"], fedora_repository_is_configured(repo))
                for repo in self.repositories
            ]
        except Exception:
            results = [(repo["id"], False) for repo in self.repositories]
        self.finished.emit(results)


class FedoraRepositoriesPage(QMainWindow):
    def __init__(self, apps_page):
        super().__init__()
        self.apps_page = apps_page
        self.thread = None
        self.worker = None
        self.status_thread = None
        self.status_worker = None
        self.repository_states = {}
        self.setWindowTitle("Fedora Repositories and Keys")
        configure_main_window(self)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)
        back_container, _back_button, _back_label, _frame_layout = create_back_button(self.go_back)
        header = create_page_header(back_container, "Fedora Repositories")
        layout.addWidget(header)

        description = QLabel(
            "Import the signed third-party repositories used by apps in the catalog. "
            "Repository package signature checks remain enabled."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.repo_list = QVBoxLayout()
        repo_container = QWidget()
        repo_container.setLayout(self.repo_list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(repo_container)
        layout.addWidget(scroll, 1)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        action_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Status")
        self.refresh_button.clicked.connect(self.refresh_repositories)
        self.import_button = QPushButton("Import All Repositories and Keys")
        self.import_button.clicked.connect(self.confirm_import_all)
        action_row.addWidget(self.refresh_button)
        action_row.addStretch()
        action_row.addWidget(self.import_button)
        layout.addLayout(action_row)
        self.refresh_repositories()

    def refresh_repositories(self):
        if self.status_thread and self.status_thread.isRunning():
            return
        while self.repo_list.count():
            child = self.repo_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        repositories = load_fedora_repositories()
        if not repositories:
            self.repo_list.addWidget(QLabel("No Fedora repositories are configured in the app catalogs."))
            self.import_button.setEnabled(False)
            return

        self.import_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.repository_states = {}
        for repo in repositories:
            card = QFrame()
            card.setObjectName("serviceCard")
            row = QHBoxLayout(card)
            detail_layout = QVBoxLayout()
            name = QLabel(str(repo["name"]))
            name.setObjectName("serviceTitle")
            packages = QLabel("Apps: " + ", ".join(repo["apps"]))
            packages.setWordWrap(True)
            key = QLabel("Signing key: " + repo["gpg_key"])
            key.setWordWrap(True)
            detail_layout.addWidget(name)
            detail_layout.addWidget(QLabel(f"Repository ID: {repo['id']}"))
            detail_layout.addWidget(packages)
            detail_layout.addWidget(key)
            row.addLayout(detail_layout, 1)
            state = QLabel("Checking…")
            row.addWidget(state)
            self.repository_states[repo["id"]] = state
            self.repo_list.addWidget(card)
        self.repo_list.addStretch()
        self.status_thread = QThread(self)
        self.status_worker = FedoraRepositoryStatusWorker(repositories)
        self.status_worker.moveToThread(self.status_thread)
        self.status_thread.started.connect(self.status_worker.run)
        self.status_worker.finished.connect(self.on_status_finished)
        self.status_worker.finished.connect(self.status_thread.quit)
        self.status_worker.finished.connect(self.status_worker.deleteLater)
        self.status_thread.finished.connect(self.status_thread.deleteLater)
        self.status_thread.finished.connect(self.cleanup_status_thread)
        self.status_thread.start()

    def on_status_finished(self, results):
        for repo_id, configured in results:
            state = self.repository_states.get(repo_id)
            if state:
                state_text = "Configured" if configured else "Not configured"
                state.setText(state_text)
                state.setProperty("installed", configured)
                state.style().unpolish(state)
                state.style().polish(state)
        self.refresh_button.setEnabled(True)
        self.import_button.setEnabled(True)

    def cleanup_status_thread(self):
        self.status_thread = None
        self.status_worker = None

    def confirm_import_all(self):
        repositories = load_fedora_repositories()
        if not repositories:
            QMessageBox.information(self, "Fedora Repositories", "No repository definitions were found.")
            return
        names = ", ".join(repo["name"] for repo in repositories)
        result = QMessageBox.question(
            self,
            "Import Fedora Repositories",
            "Import these repositories and their signing keys?\n\n"
            f"{names}\n\nPackage signature verification will remain enabled.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if result == QMessageBox.Yes:
            self.import_all(repositories)

    def import_all(self, repositories):
        if self.thread and self.thread.isRunning():
            return
        self.import_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.status_label.setText("Starting repository import…")
        self.thread = QThread(self)
        self.worker = FedoraRepositoryWorker(repositories)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.error.connect(self.on_import_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.cleanup_thread)
        self.thread.start()

    def on_import_finished(self, message):
        self.status_label.setText(message)
        self.refresh_button.setEnabled(True)
        self.refresh_repositories()

    def on_import_error(self, message):
        self.status_label.setText("Repository import failed.")
        self.refresh_button.setEnabled(True)
        self.import_button.setEnabled(True)
        QMessageBox.critical(self, "Repository Import Error", message)
        self.refresh_repositories()

    def cleanup_thread(self):
        self.thread = None
        self.worker = None

    def go_back(self):
        self.hide()
        self.apps_page.show()

    def closeEvent(self, event):
        if ((self.thread and self.thread.isRunning())
                or (self.status_thread and self.status_thread.isRunning())):
            event.ignore()
            return
        self.apps_page.show()
        event.accept()
