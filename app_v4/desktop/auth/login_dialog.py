from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NCM v4 · Sign in")
        layout = QFormLayout(self)
        self.username = QLineEdit()
        self.username.setPlaceholderText("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Username", self.username)
        layout.addRow("Password", self.password)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def credentials(self) -> tuple[str, str]:
        return self.username.text().strip(), self.password.text()
