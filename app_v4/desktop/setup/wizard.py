from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWizard, QWizardPage

from app_v4.desktop.setup.service_config import ServiceSetupConfig


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Configure the NCM v4 service."))
        self.master_passphrase = QLineEdit()
        self.master_passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("Master passphrase"))
        layout.addWidget(self.master_passphrase)


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
        self.welcome_page = WelcomePage()
        self.service_page = ServicePage()
        self.admin_page = AdminPage()
        self.addPage(self.welcome_page)
        self.addPage(self.service_page)
        self.addPage(self.admin_page)

    def collect(self) -> ServiceSetupConfig:
        port_text = self.service_page.bind_port.text().strip()
        try:
            bind_port = int(port_text)
        except ValueError:
            bind_port = 8443
        return ServiceSetupConfig(
            master_passphrase=self.welcome_page.master_passphrase.text(),
            admin_username=self.admin_page.username.text().strip() or "admin",
            admin_password=self.admin_page.password.text(),
            bind_host=self.service_page.bind_host.text().strip() or "127.0.0.1",
            bind_port=bind_port,
        )
