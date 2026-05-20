from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWizard, QWizardPage


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Configure the NCM v4 service."))


class ServicePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Service")
        layout = QVBoxLayout(self)
        self.bind_host = QLineEdit("127.0.0.1")
        self.bind_port = QLineEdit("8443")
        layout.addWidget(QLabel("Bind host"))
        layout.addWidget(self.bind_host)
        layout.addWidget(QLabel("Bind port"))
        layout.addWidget(self.bind_port)


class AdminPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Admin")
        layout = QVBoxLayout(self)
        self.username = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("Admin username"))
        layout.addWidget(self.username)
        layout.addWidget(QLabel("Admin password"))
        layout.addWidget(self.password)


class SetupWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCM v4 Setup")
        self.addPage(WelcomePage())
        self.addPage(ServicePage())
        self.addPage(AdminPage())
