from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class Sidebar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        layout = QVBoxLayout(self)
        self.brand = QLabel("NCM OPS_")
        self.brand.setObjectName("Brand")
        layout.addWidget(self.brand)
        self.buttons: dict[str, QPushButton] = {}
        for label in ["Dashboard", "Switches", "Credentials", "History", "Diff", "Schedules", "Users", "Settings"]:
            button = QPushButton(label)
            self.buttons[label] = button
            layout.addWidget(button)
        layout.addStretch()
