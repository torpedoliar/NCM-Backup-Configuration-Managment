from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SettingsView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.title = QLabel("Settings")
        layout.addWidget(self.title)
        for label in ["Service", "Branding", "Retention", "Logs", "About"]:
            layout.addWidget(QLabel(label))
