from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QWizard,
    QWizardPage,
)

from app_v4.desktop.setup.service_config import ServiceSetupConfig
from app_v4.desktop.setup.validators import (
    validate_bind_host,
    validate_bind_port,
    validate_passphrase,
    validate_password,
    validate_username,
)


class _ValidatingPage(QWizardPage):
    def _bind_change(self, *fields: QLineEdit) -> None:
        for field in fields:
            field.textChanged.connect(self._update_error)

    def _update_error(self) -> None:
        error = self._validation_error()
        if hasattr(self, "error_label"):
            self.error_label.setText(error or "")
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._validation_error() is None

    def _validation_error(self) -> str | None:
        raise NotImplementedError


class WelcomePage(_ValidatingPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Welcome")
        self.setSubTitle("Configure the NCM v4 service.")
        layout = QFormLayout(self)
        self.master_passphrase = QLineEdit()
        self.master_passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        self.master_passphrase.setPlaceholderText("Choose a strong passphrase (12+ chars)")
        self.master_passphrase_confirm = QLineEdit()
        self.master_passphrase_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.master_passphrase_confirm.setPlaceholderText("Repeat passphrase")
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addRow("Master passphrase", self.master_passphrase)
        layout.addRow("Confirm passphrase", self.master_passphrase_confirm)
        layout.addRow("", self.error_label)
        self._bind_change(self.master_passphrase, self.master_passphrase_confirm)

    def _validation_error(self) -> str | None:
        return validate_passphrase(self.master_passphrase.text(), self.master_passphrase_confirm.text())


class ServicePage(_ValidatingPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Service")
        self.setSubTitle("Where the local backend will listen.")
        layout = QFormLayout(self)
        self.bind_host = QLineEdit("127.0.0.1")
        self.bind_port = QLineEdit("8443")
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #ffb800;")
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addRow("Bind host", self.bind_host)
        layout.addRow("Bind port", self.bind_port)
        layout.addRow("", self.warning_label)
        layout.addRow("", self.error_label)
        self._bind_change(self.bind_host, self.bind_port)

    def _validation_error(self) -> str | None:
        host_error = validate_bind_host(self.bind_host.text())
        if host_error:
            return host_error
        port_error = validate_bind_port(self.bind_port.text())
        if port_error:
            return port_error
        return None

    def _update_error(self) -> None:
        super()._update_error()
        host = self.bind_host.text().strip()
        if host == "0.0.0.0":
            self.warning_label.setText(
                "⚠ Binding to 0.0.0.0 exposes the service to the local network."
            )
        else:
            self.warning_label.setText("")


class AdminPage(_ValidatingPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Admin")
        self.setSubTitle("Initial administrator account.")
        layout = QFormLayout(self)
        self.username = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirm = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addRow("Admin username", self.username)
        layout.addRow("Admin password", self.password)
        layout.addRow("Confirm password", self.password_confirm)
        layout.addRow("", self.error_label)
        self._bind_change(self.username, self.password, self.password_confirm)

    def _validation_error(self) -> str | None:
        username_error = validate_username(self.username.text())
        if username_error:
            return username_error
        return validate_password(self.password.text(), self.password_confirm.text())


class SetupWizard(QWizard):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NCM v4 Setup")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.welcome_page = WelcomePage()
        self.service_page = ServicePage()
        self.admin_page = AdminPage()
        self.addPage(self.welcome_page)
        self.addPage(self.service_page)
        self.addPage(self.admin_page)
        self.resize(560, 380)

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
